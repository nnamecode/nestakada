from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import UUID

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import close_old_connections, models, transaction
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import PageGrant
from accounts.tests import FAST_HASHERS, PASSWORD
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from page_editor.clean import restricted_clean
from page_versions import engine, schema
from page_versions.creation import initial_snapshot
from page_versions.models import (
    IdentityReservation, OwnerDraft, PageContentState, VersionBasePin,
)

from . import dev09_migration_apply as migration
from .models import Page, Route
from .test_public_http import fake_shared


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV09_MIGRATION_APPLY_ENABLED=True,
)
class Dev09CombinedServicesTests(TransactionTestCase):
    reset_sequences = True
    home_id = UUID('e80c3de1-feea-4847-b550-325a825ffc0e')

    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        package = migration._read_combined_infographic_package()
        row = package['media']
        raw(MediaFolder).bulk_create([MediaFolder(
            id=UUID(row['folder_id']), path=row['folder_path'])])
        raw(Asset).bulk_create([Asset(
            id=UUID(row['asset_id']), folder_id=row['folder_id'],
            status=Asset.Status.READY,
            provenance=migration.COMBINED_INFOGRAPHIC_PROVENANCE,
            source_sha256=row['sha256'])])
        raw(AssetFile).bulk_create([AssetFile(
            id=UUID(row['file_id']), asset_id=row['asset_id'],
            kind=AssetFile.Kind.MAIN, key=row['storage_key'],
            sha256=row['sha256'], byte_size=row['bytes'])])
        expected = {'sha256': row['sha256'], 'byte_size': row['bytes']}
        self.storage = type('ExactStorage', (), {
            'manifest': lambda _self, key: expected.copy()
            if key == row['storage_key'] else (_ for _ in ()).throw(OSError())
        })()
        self.media_storage = patch.object(
            migration, 'MediaStorage', return_value=self.storage)
        self.media_storage.start()
        self.addCleanup(self.media_storage.stop)

    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def state(self):
        labels = ('content', 'page_versions', 'media_library', 'audit')
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in labels
            for model in apps.get_app_config(label).get_models()
        }

    def create_home(self):
        page = Page.objects.create(
            id=self.home_id, name='Главная', kind=Page.Kind.HOME,
            position=0, is_published=False)
        Route.objects.create(
            page=page, target='/', kind=Route.Kind.PRIMARY, is_legacy=True)
        payload = initial_snapshot(
            Page.Kind.HOME, h1='АВТОТЕХЦЕНТР ЭСТАКАДА',
            title='Главная | Автосервис «Эстакада»').data(Page.Kind.HOME)
        revision = engine.new_revision(page, None, payload, 'initial', self.owner)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        instant = engine.now()
        draft = OwnerDraft.objects.create(
            page=page, revision=1, base_revision=revision, payload=payload,
            payload_hash=schema.digest(payload), author_id=self.owner.pk,
            created_at=instant, updated_at=instant)
        VersionBasePin.objects.create(
            revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
        record_event(
            category=Category.PAGES_LINKS,
            event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=self.owner.pk, object_kind='page', object_ref=page.pk)

    def create_exact_parents(self):
        self.create_home()
        migration.apply_services_catalog()
        migration.apply_service_roots()
        migration.apply_planned_maintenance()
        migration.apply_diagnostics_branch()

    def test_migm_001_004_package_renderer_exact_safe_and_closed(self):
        package = migration._read_combined_services_package()
        infographic = migration._read_combined_infographic_package()
        self.assertEqual((len(package['pages']), len(package['routes'])), (24, 25))
        self.assertEqual(
            migration._combined_digest(package['pages']),
            migration.COMBINED_PAGES_SHA256)
        self.assertEqual(
            migration._combined_digest(package['routes']),
            migration.COMBINED_ROUTES_SHA256)
        payloads = [migration._combined_payload(page) for page in package['pages']]
        self.assertTrue(all(restricted_clean(payload['main_text']) ==
                            payload['main_text'] for payload in payloads))
        rendered = ''.join(payload['intro_text'] + payload['main_text']
                           for payload in payloads).lower()
        for forbidden in ('<script', '<style', 'javascript:', ' onclick=',
                          ' onerror=', '{%', '{{'):
            self.assertNotIn(forbidden, rendered)
        wash = next(page for page in package['pages'] if page['map_id'] == 'MAP-115')
        wash_routes = [route for route in package['routes']
                       if route['page_id'] == wash['page_id']]
        self.assertEqual([route['kind'] for route in wash_routes], ['primary', 'alias'])
        self.assertIn('от 1500', next(payload['main_text'] for page, payload in
                                   zip(package['pages'], payloads, strict=True)
                                   if page['map_id'] == 'MAP-038'))
        self.assertIn('от 3000', next(payload['main_text'] for page, payload in
                                     zip(package['pages'], payloads, strict=True)
                                     if page['map_id'] == 'MAP-073'))
        map019 = next(page for page in package['pages']
                      if page['map_id'] == 'MAP-019')
        illustrated = migration._combined_payload(map019, infographic)
        self.assertEqual(
            [node['kind'] for node in illustrated['layout']],
            ['text', 'image', 'text', 'price'])
        self.assertEqual(illustrated['layout'][1], {
            'id': infographic['binding']['block_id'], 'kind': 'image',
            'image_id': infographic['media']['image_id']})
        self.assertEqual(illustrated['embedded_images'][0]['asset_id'],
                         infographic['media']['asset_id'])

    def test_migm_009_010_mutations_and_caps_fail_before_render(self):
        original = migration._read_combined_services_package()
        cases = {
            'extra': lambda value: value['pages'][0].update(extra=True),
            'raw_html': lambda value: value['pages'][0]['blocks'][0].update(
                type='raw_html'),
            'template': lambda value: value['pages'][0].update(name='{{x}}'),
            'script': lambda value: value['pages'][0].update(name='<script>x</script>'),
        }
        for label, mutate in cases.items():
            with self.subTest(case=label):
                value = deepcopy(original)
                mutate(value)
                digest = migration._combined_digest(value['pages'])
                value['inputs']['page_content_sha256'] = digest
                with patch.object(migration, 'COMBINED_PAGES_SHA256', digest):
                    self.assert_fault(
                        'MIGRATION_PACKAGE_INVALID',
                        lambda value=value: migration._validate_combined_services_package(
                            value))
        reordered = deepcopy(original)
        reordered['routes'].reverse()
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_combined_services_package(reordered))

        base = {'plain': 0, 'blocks': 0, 'items': 0, 'sections': 0,
                'tables': 0, 'cells': 0}
        for field, limit in (('plain', 65536), ('blocks', 128), ('items', 256),
                             ('sections', 32), ('tables', 4)):
            with self.subTest(page_cap=field):
                exact = {**base, field: limit}
                migration._combined_enforce_page_caps(exact)
                over = {**exact, field: limit + 1}
                self.assert_fault(
                    'MIGRATION_PACKAGE_INVALID',
                    lambda over=over: migration._combined_enforce_page_caps(over))
        for field, limit in (('blocks', 2048), ('cells', 4096)):
            with self.subTest(package_cap=field):
                exact = {'blocks': 0, 'cells': 0, field: limit}
                migration._combined_enforce_package_caps(exact)
                over = {**exact, field: limit + 1}
                self.assert_fault(
                    'MIGRATION_PACKAGE_INVALID',
                    lambda over=over: migration._combined_enforce_package_caps(over))
        migration._combined_enforce_rendered_caps(
            page_bytes=131072, package_bytes=2097152)
        for kwargs in ({'page_bytes': 131073}, {'package_bytes': 2097153}):
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda kwargs=kwargs: migration._combined_enforce_rendered_caps(**kwargs))
        migration._combined_enforce_package_bytes(524288)
        for size in (0, 524289):
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda size=size: migration._combined_enforce_package_bytes(size))
        migration._combined_text('x' * 8192)
        self.assert_fault('MIGRATION_PACKAGE_INVALID',
                          lambda: migration._combined_text('x' * 8193))
        exact_segments = {'type': 'paragraph', 'segments': [
            {'text': 'x', 'strong': False} for _ in range(128)]}
        migration._validate_combined_block(exact_segments, map_id='MAP-010')
        too_many = deepcopy(exact_segments)
        too_many['segments'].append({'text': 'x', 'strong': False})
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_combined_block(too_many, map_id='MAP-010'))
        exact_items = {'type': 'unordered_list', 'items': [
            {'segments': [{'text': 'x', 'strong': False}]}
            for _ in range(128)]}
        migration._validate_combined_block(exact_items, map_id='MAP-010')
        too_many_items = deepcopy(exact_items)
        too_many_items['items'].append({
            'segments': [{'text': 'x', 'strong': False}]})
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_combined_block(
                too_many_items, map_id='MAP-010'))
        exact_sections = {'type': 'ordered_sections', 'items': [
            {'heading': 'H', 'blocks': [{
                'type': 'paragraph',
                'segments': [{'text': 'x', 'strong': False}]}]}
            for _ in range(32)]}
        migration._validate_combined_block(exact_sections, map_id='MAP-041')
        too_many_sections = deepcopy(exact_sections)
        too_many_sections['items'].append(deepcopy(exact_sections['items'][0]))
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_combined_block(
                too_many_sections, map_id='MAP-041'))
        migration._combined_enforce_table_caps(rows=128, columns=16, cells=2048)
        for kwargs in ({'rows': 129, 'columns': 16, 'cells': 2048},
                       {'rows': 128, 'columns': 17, 'cells': 2048},
                       {'rows': 128, 'columns': 16, 'cells': 2049}):
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda kwargs=kwargs: migration._combined_enforce_table_caps(**kwargs))
        too_deep = {'type': 'ordered_list', 'items': [{
            'segments': [{'text': 'x', 'strong': False}],
            'children': [{'type': 'unordered_list', 'items': [{
                'segments': [{'text': 'y', 'strong': False}],
                'children': [{'type': 'unordered_list', 'items': [{
                    'segments': [{'text': 'z', 'strong': False}]}]}]}]}]}]}
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_combined_block(too_deep, map_id='MAP-024'))

        nested = {'type': 'ordered_list', 'items': [{
            'segments': [{'text': 'x', 'strong': False}],
            'children': [{'type': 'unordered_list', 'items': [
                {'segments': [{'text': 'y', 'strong': False}]},
                {'segments': [{'text': 'zz', 'strong': False}]},
            ]}]}, {'segments': [{'text': 'www', 'strong': False}]}]}
        sections = {'type': 'ordered_sections', 'items': [{
            'heading': 'H', 'blocks': [
                {'type': 'paragraph',
                 'segments': [{'text': 'p', 'strong': False}]},
                {'type': 'unordered_list', 'items': [
                    {'segments': [{'text': 'a', 'strong': False}]},
                    {'segments': [{'text': 'bc', 'strong': False}]},
                ]},
            ]}]}
        cell = lambda text: {
            'text': text, 'strong': False, 'rowspan': 1,
            'colspan': 1, 'scope': None}
        table = {'type': 'table', 'caption': None,
                 'header': [cell('A'), cell('B')],
                 'rows': [[cell('C'), cell('D')]]}
        total = {'plain': 0, 'blocks': 0, 'items': 0, 'sections': 0,
                 'tables': 0, 'cells': 0}
        for block in (nested, sections, table):
            stats = migration._combined_block_stats(block)
            for key in total:
                total[key] += stats[key]
        self.assertEqual(total, {
            'plain': 16, 'blocks': 6, 'items': 6,
            'sections': 1, 'tables': 1, 'cells': 4})
        migration._combined_enforce_page_caps(total)
        migration._combined_enforce_package_caps(
            {'blocks': total['blocks'], 'cells': total['cells']})

    def test_migm_005_007_create_hidden_routes_and_zero_write_replay(self):
        self.create_exact_parents()
        before_pages = Page.objects.count()
        result = migration.apply_combined_services()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 24,
            'routes': 25, 'published': 0})
        package = migration._read_combined_services_package()
        ids = [UUID(page['page_id']) for page in package['pages']]
        self.assertEqual(Page.objects.filter(pk__in=ids).count(), 24)
        self.assertEqual(Page.objects.filter(pk__in=ids, is_published=True).count(), 0)
        self.assertEqual(Route.objects.filter(page_id__in=ids).count(), 25)
        self.assertFalse(PageGrant.objects.filter(page_id__in=ids).exists())
        map019_id = UUID(next(page['page_id'] for page in package['pages']
                              if page['map_id'] == 'MAP-019'))
        state = PageContentState.objects.get(page_id=map019_id)
        draft = OwnerDraft.objects.get(page_id=map019_id)
        self.assertEqual(
            set(AssetUsage.objects.filter(asset_id=(
                migration._read_combined_infographic_package()['media']['asset_id']))
                .values_list('kind', 'consumer_id')),
            {(AssetUsage.Kind.CURRENT_PAGE, map019_id),
             (AssetUsage.Kind.ORDINARY_VERSION, state.current_revision_id),
             (AssetUsage.Kind.DRAFT, draft.pk)})
        self.assertEqual(Page.objects.count(), before_pages + 24)
        wash_id = UUID(next(page['page_id'] for page in package['pages']
                            if page['map_id'] == 'MAP-115'))
        self.assertEqual(
            list(Route.objects.filter(page_id=wash_id).order_by('target').values_list(
                'kind', 'target')),
            [('primary', '/services/avtomojka'),
             ('alias', '/services/drugie-uslugi/avtomojka')])
        before = self.state()
        replay = migration.apply_combined_services()
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)

    @override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                       SEO_ROBOTS_PROFILE='deny-all')
    def test_migm_006_same_wash_page_primary_alias_http_and_canonical(self):
        self.create_exact_parents()
        migration.apply_combined_services()
        package = migration._read_combined_services_package()
        wash = next(page for page in package['pages'] if page['map_id'] == 'MAP-115')
        raw(Page).filter(pk=UUID(wash['page_id'])).update(is_published=True)
        with patch('content.public_views.render_shared', side_effect=fake_shared):
            primary = self.client.get('/services/avtomojka')
            alias = self.client.get('/services/drugie-uslugi/avtomojka')
        self.assertEqual((primary.status_code, alias.status_code), (200, 200))
        self.assertEqual(primary.content, alias.content)
        self.assertIn(
            b'<link rel="canonical" href="http://localhost:8767/services/avtomojka">',
            alias.content)

    @override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                       SEO_ROBOTS_PROFILE='deny-all')
    def test_migm_006_map019_public_image_follows_intro_and_precedes_main(self):
        self.create_exact_parents()
        migration.apply_combined_services()
        combined = migration._read_combined_services_package()
        infographic = migration._read_combined_infographic_package()
        descriptor = next(page for page in combined['pages']
                          if page['map_id'] == 'MAP-019')
        raw(Page).filter(pk=descriptor['page_id']).update(is_published=True)
        with patch('content.public_views.render_shared', side_effect=fake_shared):
            response = self.client.get(descriptor['url'])
        source = response.content.decode()
        payload = migration._combined_payload(descriptor, infographic)
        alt = infographic['media']['alt']
        self.assertEqual(response.status_code, 200)
        self.assertLess(source.index(payload['intro_text']),
                        source.index('alt="' + alt + '"'))
        self.assertLess(source.index('alt="' + alt + '"'),
                        source.index(payload['main_text']))
        self.assertIn('/public-media/' + infographic['media']['file_id'] + '/',
                      source)
        self.assertEqual(source.count('alt="' + alt + '"'), 1)

    def test_migm_008_missing_changed_and_partial_refuse_without_writes(self):
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_combined_services)
        self.assertEqual(self.state(), before)
        self.create_exact_parents()
        parent_id = migration.SERVICES_PAGE['page_id']
        raw(Page).filter(pk=parent_id).update(name='Changed')
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_combined_services)
        self.assertEqual(self.state(), before)
        raw(Page).filter(pk=parent_id).update(name=migration.SERVICES_PAGE['name'])
        page = migration._read_combined_services_package()['pages'][0]
        Page.objects.create(
            id=UUID(page['page_id']), name=page['name'], kind=page['kind'],
            parent_id=page['parent_id'], position=page['position'],
            is_published=False)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_combined_services)
        self.assertEqual(self.state(), before)

    def test_migm_014_media_mismatch_refuses_before_page_writes(self):
        self.create_exact_parents()
        row = migration._read_combined_infographic_package()['media']
        raw(Asset).filter(pk=row['asset_id']).update(status=Asset.Status.STAGED)
        before = self.state()
        self.assert_fault('MIGRATION_MEDIA_UNAVAILABLE',
                          migration.apply_combined_services)
        self.assertEqual(self.state(), before)

    def test_migm_014_physical_manifest_race_rolls_back_page_writes(self):
        self.create_exact_parents()
        row = migration._read_combined_infographic_package()['media']
        expected = {'sha256': row['sha256'], 'byte_size': row['bytes']}

        class RaceStorage:
            calls = 0

            def manifest(self, key):
                self.calls += 1
                if key != row['storage_key']:
                    raise OSError()
                if self.calls == 1:
                    return expected.copy()
                return {'sha256': '0' * 64, 'byte_size': row['bytes']}

        before = self.state()
        self.assert_fault(
            'MIGRATION_MEDIA_UNAVAILABLE',
            lambda: migration.apply_combined_services(storage=RaceStorage()))
        self.assertEqual(self.state(), before)

    def test_migm_014_missing_usage_refuses_exact_replay_without_writes(self):
        self.create_exact_parents()
        migration.apply_combined_services()
        infographic = migration._read_combined_infographic_package()
        raw(AssetUsage).filter(
            asset_id=infographic['media']['asset_id'],
            kind=AssetUsage.Kind.CURRENT_PAGE).delete()
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_combined_services)
        self.assertEqual(self.state(), before)

    def test_migm_008_sibling_reservation_and_foreign_route_collisions(self):
        self.create_exact_parents()
        package = migration._read_combined_services_package()

        class RollbackCollision(Exception):
            pass

        def check(setup):
            try:
                with transaction.atomic():
                    setup()
                    before = self.state()
                    self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                                      migration.apply_combined_services)
                    self.assertEqual(self.state(), before)
                    raise RollbackCollision
            except RollbackCollision:
                pass

        first = package['pages'][0]
        other = next(page for page in package['pages'] if page['map_id'] == 'MAP-015')
        check(lambda: Page.objects.create(
            id=UUID('10000000-0000-4000-8000-000000000001'), name='Occupied',
            kind=Page.Kind.SERVICE, parent_id=other['parent_id'],
            position=other['position'], is_published=False))
        check(lambda: IdentityReservation.objects.create(
            id=UUID(first['page_id']), kind='synthetic'))

        def foreign_route():
            page = Page.objects.create(
                id=UUID('10000000-0000-4000-8000-000000000002'), name='Foreign',
                kind=Page.Kind.SERVICE, parent_id=None, position=99,
                is_published=False)
            Route.objects.create(
                page=page, target='/services/drugie-uslugi/avtomojka',
                kind=Route.Kind.ALIAS, is_legacy=True)

        check(foreign_route)

    def test_migm_011_last_route_failure_rolls_back_all(self):
        self.create_exact_parents()
        before = self.state()
        original = Route.objects.create
        calls = 0

        def fail_last(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 25:
                raise RuntimeError('SYNTHETIC_LAST_ROUTE_FAILURE')
            return original(*args, **kwargs)

        with patch.object(Route.objects, 'create', side_effect=fail_last):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_LAST_ROUTE_FAILURE'):
                migration.apply_combined_services()
        self.assertEqual(calls, 25)
        self.assertEqual(self.state(), before)

        original_revision = engine.new_revision
        revisions = 0

        def fail_last_revision(*args, **kwargs):
            nonlocal revisions
            revisions += 1
            if revisions == 24:
                raise RuntimeError('SYNTHETIC_LAST_VERSION_FAILURE')
            return original_revision(*args, **kwargs)

        with patch('content.dev09_migration_apply.engine.new_revision',
                   side_effect=fail_last_revision):
            with self.assertRaisesRegex(RuntimeError,
                                        'SYNTHETIC_LAST_VERSION_FAILURE'):
                migration.apply_combined_services()
        self.assertEqual(revisions, 24)
        self.assertEqual(self.state(), before)

    def test_migm_012_concurrent_create_once_then_replay(self):
        self.create_exact_parents()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_combined_services()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)

    def test_migm_013_disabled_stops_before_package_read(self):
        with override_settings(DEV09_MIGRATION_APPLY_ENABLED=False), patch(
                'content.dev09_migration_apply._read_combined_services_package') as reader:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_combined_services)
            reader.assert_not_called()


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV09_MIGRATION_APPLY_ENABLED=True,
)
class Dev09CombinedInfographicImportTests(TransactionTestCase):
    reset_sequences = True

    def test_migm_015_exact_media_import_and_zero_write_replay(self):
        package = deepcopy(migration._read_combined_infographic_package())
        content = b'bounded-map019-test-webp'
        row = package['media']
        row['relative_path'] = 'media/design-concepts/map019-test.webp'
        row['bytes'] = len(content)
        row['sha256'] = hashlib.sha256(content).hexdigest()
        sources = TemporaryDirectory()
        media = TemporaryDirectory()
        self.addCleanup(sources.cleanup)
        self.addCleanup(media.cleanup)
        source = Path(sources.name, row['relative_path'])
        source.parent.mkdir(parents=True)
        source.write_bytes(content)
        with patch.object(migration, '_read_combined_infographic_package',
                          return_value=package), \
                override_settings(MEDIA_LIBRARY_ROOT=media.name):
            first = migration.import_combined_infographic_media(
                source_root=sources.name, storage=MediaStorage())
            before = {
                'folders': list(MediaFolder.objects.values()),
                'assets': list(Asset.objects.values()),
                'files': list(AssetFile.objects.values()),
            }
            second = migration.import_combined_infographic_media(
                source_root=sources.name, storage=MediaStorage())
        self.assertEqual(first['result'], 'created')
        self.assertEqual(second['result'], 'replayed')
        self.assertEqual({
            'folders': list(MediaFolder.objects.values()),
            'assets': list(Asset.objects.values()),
            'files': list(AssetFile.objects.values()),
        }, before)
        self.assertEqual(Asset.objects.get(pk=row['asset_id']).status,
                         Asset.Status.READY)

    @override_settings(DEV09_MIGRATION_APPLY_ENABLED=False)
    def test_migm_016_media_import_default_off_before_package_read(self):
        with patch.object(migration, '_read_combined_infographic_package') as reader:
            with self.assertRaisesMessage(ValidationError,
                                          'MIGRATION_APPLY_DISABLED'):
                migration.import_combined_infographic_media(
                    source_root='missing')
        reader.assert_not_called()

    def test_migm_017_media_import_missing_source_fails_closed(self):
        with self.assertRaisesMessage(ValidationError,
                                      'MIGRATION_MEDIA_SOURCE_UNAVAILABLE'):
            migration.import_combined_infographic_media(
                source_root='definitely-missing-map019-source-root')
        self.assertFalse(MediaFolder.objects.exists())
        self.assertFalse(Asset.objects.exists())
