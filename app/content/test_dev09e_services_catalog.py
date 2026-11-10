from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
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
from page_editor.clean import restricted_clean
from page_versions import engine, schema
from page_versions.creation import initial_snapshot
from page_versions.models import (
    IdentityReservation, OwnerDraft, PageContentState, VersionBasePin,
)

from . import dev09_migration_apply as migration
from .models import Page, Route
from .reads import public_tree


def raw(model):
    return models.QuerySet(model=model, using='default')


@override_settings(
    PASSWORD_HASHERS=FAST_HASHERS, ENVIRONMENT='test',
    DEV09_MIGRATION_APPLY_ENABLED=True,
)
class Dev09ServicesCatalogTests(TransactionTestCase):
    reset_sequences = True
    parent_id = UUID('e80c3de1-feea-4847-b550-325a825ffc0e')
    catalog_id = UUID('f39af842-05a7-4101-af9a-2fc320d457d0')

    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)

    def state(self):
        labels = ('content', 'page_versions', 'media_library', 'audit')
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in labels
            for model in apps.get_app_config(label).get_models()
        }

    def assert_fault(self, code, action):
        with self.assertRaises(ValidationError) as caught:
            action()
        self.assertIn(code, caught.exception.messages)

    def create_exact_parent(self, *, name='Главная'):
        page = Page.objects.create(
            id=self.parent_id, name=name, kind=Page.Kind.HOME,
            position=0, is_published=False)
        Route.objects.create(
            page=page, target='/', kind=Route.Kind.PRIMARY, is_legacy=True)
        payload = initial_snapshot(
            Page.Kind.HOME, h1='АВТОТЕХЦЕНТР ЭСТАКАДА',
            title='Главная | Автосервис «Эстакада»').data(Page.Kind.HOME)
        revision = engine.new_revision(
            page, None, payload, 'initial', self.owner)
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
        return page

    def test_mige_package_renderer_is_exact_closed_and_safe(self):
        package = migration._read_services_package()
        page = package['page']
        payload = migration._services_payload(page)
        main = payload['main_text']
        links = [group for group in page['groups']]
        expected_hrefs = []
        for group in links:
            expected_hrefs.append(group['href'])
            expected_hrefs.extend(item['href'] for item in group['items'])
        self.assertEqual(len(expected_hrefs), 58)
        self.assertEqual(main.count('<h2>'), 5)
        self.assertEqual(main.count('<ul>'), 5)
        self.assertEqual(main.count('<li>'), 53)
        self.assertEqual(main.count('<a href="'), 58)
        self.assertEqual(
            [part.split('"', 1)[0] for part in main.split('<a href="')[1:]],
            expected_hrefs)
        self.assertEqual(restricted_clean(main), main)
        for forbidden in ('<script', '<style', ' on', ' class=', ' aria-',
                          'javascript:', 'http://', 'https://'):
            self.assertNotIn(forbidden, main.lower())
        self.assertEqual(
            (payload['h1'], payload['title'], payload['intro_text'],
             payload['description'], payload['price'], payload['main_image'],
             payload['preview_image'], payload['embedded_images']),
            ('Услуги и цены автосервиса "Эстакада"',
             'Услуги | Автосервис «Эстакада»', '', '', None, None, None, []))

    def test_mige_package_mutations_fail_closed(self):
        value = migration._read_services_package()
        cases = {
            'schema': ('schema', 'dev09-services-catalog-v0'),
            'extra_key': ('extra', True),
            'javascript': ('href', 'javascript:alert(1)'),
            'http': ('href', 'https://example.invalid/services/a'),
            'query': ('href', '/services/a?x=1'),
            'fragment': ('href', '/services/a#x'),
            'backslash': ('href', '/services/a\\x'),
            'quote': ('href', '/services/a"onload="x'),
            'control': ('href', '/services/a\nx'),
            'script': ('name', '<script>alert(1)</script>'),
            'event': ('name', '<img onerror=alert(1)>'),
            'style': ('name', '<style>body{display:none}</style>'),
            'class': ('name', '<b class=x>name</b>'),
            'on_attribute': ('name', '<b onclick=x>name</b>'),
            'aria': ('name', '<b aria-label=x>name</b>'),
            'valid_wrong_name': ('name', 'Другое корректное имя'),
            'valid_wrong_href': ('href', '/services/valid-but-wrong'),
        }
        for label, (field, replacement) in cases.items():
            with self.subTest(case=label):
                changed = deepcopy(value)
                if label == 'schema':
                    changed[field] = replacement
                elif label == 'extra_key':
                    changed['page']['groups'][0][field] = replacement
                else:
                    changed['page']['groups'][0]['items'][0][field] = replacement
                self.assert_fault(
                    'MIGRATION_PACKAGE_INVALID',
                    lambda changed=changed: migration._validate_services_package(changed))

        reordered = deepcopy(value)
        reordered['page']['groups'][0]['items'].reverse()
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_services_package(reordered))

        escaped = deepcopy(value['page'])
        escaped['groups'][0]['name'] = '<>&"'
        rendered = migration._services_payload(escaped)['main_text']
        self.assertIn('<strong>&lt;&gt;&amp;"</strong>', rendered)
        self.assertNotIn('<strong><>&"</strong>', rendered)

    def test_mige_standalone_parent_create_hidden_and_exact_replay(self):
        parent = self.create_exact_parent()
        self.assertEqual(Page.objects.count(), 1)
        result = migration.apply_services_catalog()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 1, 'published': 0})
        page = Page.objects.get(pk=self.catalog_id)
        self.assertEqual(
            (page.parent_id, page.position, page.kind, page.is_published),
            (parent.pk, 1, Page.Kind.SERVICES, False))
        self.assertEqual(
            list(Route.objects.filter(page=page).values_list(
                'kind', 'target', 'is_legacy')),
            [(Route.Kind.PRIMARY, '/services/', True)])
        self.assertFalse(PageGrant.objects.filter(page=page).exists())
        self.assertFalse(Page.objects.filter(kind=Page.Kind.ARTICLE).exists())
        self.assertNotIn(str(page.pk), {str(row['id']) for row in public_tree()})
        before = self.state()
        replay = migration.apply_services_catalog()
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)

    def test_mige_missing_or_changed_parent_refuses_without_mutation(self):
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_services_catalog)
        self.assertEqual(self.state(), before)
        self.create_exact_parent(name='Changed')
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_services_catalog)
        self.assertEqual(self.state(), before)

    def test_mige_partial_catalog_conflict_refuses_without_mutation(self):
        self.create_exact_parent()
        Page.objects.create(
            id=self.catalog_id, name='Partial', kind=Page.Kind.SERVICES,
            parent_id=self.parent_id, position=1, is_published=False)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_services_catalog)
        self.assertEqual(self.state(), before)

    def test_mige_late_failure_rolls_back_catalog_and_preserves_parent(self):
        self.create_exact_parent()
        before = self.state()
        with patch('content.dev09_migration_apply.record_event',
                   side_effect=RuntimeError('SYNTHETIC_CATALOG_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_CATALOG_AUDIT_FAILURE'):
                migration.apply_services_catalog()
        self.assertEqual(self.state(), before)
        self.assertTrue(Page.objects.filter(pk=self.parent_id).exists())
        self.assertFalse(Page.objects.filter(pk=self.catalog_id).exists())

    def test_mige_disabled_stops_before_catalog_package(self):
        with override_settings(DEV09_MIGRATION_APPLY_ENABLED=False), patch(
                'content.dev09_migration_apply._read_services_package') as package:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_services_catalog)
            package.assert_not_called()

    def test_mige_concurrent_calls_create_once_then_replay(self):
        self.create_exact_parent()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_services_catalog()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
        self.assertEqual(Page.objects.filter(pk=self.catalog_id).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='MIGRATION_PAGE_IMPORTED',
            object_ref='uuid:' + str(self.catalog_id)).count(), 1)

    def create_exact_services_parent(self):
        self.create_exact_parent()
        migration.apply_services_catalog()
        return Page.objects.get(pk=self.catalog_id)

    def test_migf_package_renderer_exact_safe_and_mutations_closed(self):
        package = migration._read_service_roots_package()
        self.assertEqual([len(page['tiles']) for page in package['pages']], [17, 5])
        self.assertEqual(package['pages'][0]['tiles'][6]['name'],
                         'Климат-контроль, Печка')
        self.assertFalse(any(tile['name'] == 'Автомойка'
                             for tile in package['pages'][1]['tiles']))
        for page in package['pages']:
            main = migration._service_root_payload(page)['main_text']
            self.assertEqual(main.count('<ul>'), 1)
            self.assertEqual(main.count('<li>'), len(page['tiles']))
            self.assertEqual(main.count('<a href="'), len(page['tiles']))
            self.assertEqual(restricted_clean(main), main)
        for field, replacement in (
                ('name', '<script>alert(1)</script>'),
                ('name', '<b class=x>name</b>'),
                ('name', '<b onclick=x>name</b>'),
                ('name', '<b aria-label=x>name</b>'),
                ('name', '<style>body{display:none}</style>'),
                ('href', 'javascript:alert(1)'),
                ('href', 'https://example.invalid/services/x'),
                ('href', '/services/remont/x?query=1'),
                ('href', '/services/remont/x#fragment'),
                ('href', '/services/remont/x\\path'),
                ('href', '/services/remont/x\ncontrol'),
                ('href', '/services/remont/x" onclick="x'),
                ('href', '/services/remont/valid-but-wrong')):
            changed = deepcopy(package)
            changed['pages'][0]['tiles'][0][field] = replacement
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda changed=changed: migration._validate_service_roots_package(changed))

    def test_migf_exact_parent_create_two_hidden_and_zero_write_replay(self):
        parent = self.create_exact_services_parent()
        result = migration.apply_service_roots()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 2, 'published': 0})
        children = list(Page.objects.filter(parent=parent).order_by('position'))
        self.assertEqual(
            [(page.position, page.kind, page.is_published) for page in children],
            [(2, Page.Kind.SERVICE_CATALOG, False),
             (4, Page.Kind.SERVICE_CATALOG, False)])
        self.assertEqual(
            list(Route.objects.filter(page__in=children).order_by('target').values_list(
                'target', flat=True)),
            ['/services/drugie-uslugi/', '/services/remont/'])
        self.assertFalse(PageGrant.objects.filter(page__in=children).exists())
        before = self.state()
        replay = migration.apply_service_roots()
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)

    def test_migf_missing_or_changed_parent_and_mixed_state_refuse(self):
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED', migration.apply_service_roots)
        self.assertEqual(self.state(), before)
        self.create_exact_services_parent()
        raw(Page).filter(pk=self.catalog_id).update(name='Changed')
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED', migration.apply_service_roots)
        self.assertEqual(self.state(), before)
        raw(Page).filter(pk=self.catalog_id).update(name='Услуги и цены')
        package = migration._read_service_roots_package()
        first = package['pages'][0]
        Page.objects.create(
            id=UUID(first['page_id']), name=first['name'], kind=first['kind'],
            parent_id=first['parent_id'], position=first['position'],
            is_published=False)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT', migration.apply_service_roots)
        self.assertEqual(self.state(), before)

    def test_migf_second_page_failure_rolls_back_and_concurrency_replays(self):
        self.create_exact_services_parent()
        before = self.state()
        original = migration._create_aggregate
        calls = 0

        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('SYNTHETIC_SECOND_ROOT_FAILURE')
            return original(*args)

        with patch('content.dev09_migration_apply._create_aggregate', side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_SECOND_ROOT_FAILURE'):
                migration.apply_service_roots()
        self.assertEqual(self.state(), before)
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_service_roots()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)

    def create_exact_service_roots(self):
        self.create_exact_services_parent()
        migration.apply_service_roots()
        return list(Page.objects.filter(
            kind=Page.Kind.SERVICE_CATALOG).order_by('position'))

    def test_migh_package_renderer_exact_safe_and_mutations_closed(self):
        parents = migration._read_service_roots_package()
        package = migration._read_service_details_package(parents)
        self.assertEqual(len(package['pages']), 10)
        self.assertEqual(
            {page['parent_id'] for page in package['pages']},
            {page['page_id'] for page in parents['pages']})
        for page in package['pages']:
            payload = migration._service_detail_payload(page)
            self.assertEqual(restricted_clean(payload['intro_text']),
                             payload['intro_text'])
            self.assertEqual(restricted_clean(payload['main_text']),
                             payload['main_text'])
            self.assertTrue(payload['intro_text'].startswith('<p>'))
            self.assertTrue(payload['main_text'])
            self.assertNotIn('<script', payload['main_text'].lower())
            self.assertNotIn('javascript:', payload['main_text'].lower())
        for field, replacement in (
                ('url', '/services/remont/valid-but-wrong/'),
                ('name', '<script>alert(1)</script>'),
                ('parent_id', str(self.parent_id))):
            changed = deepcopy(package)
            changed['pages'][0][field] = replacement
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda changed=changed: migration._validate_service_details_package(
                    changed, parents))
        changed = deepcopy(package)
        changed['pages'][0]['blocks'][0]['unexpected'] = True
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_service_details_package(changed, parents))
        list_page = next(page for page in package['pages']
                         if any(block.get('items') and len(block['items']) > 1
                                for block in page['blocks']))
        list_index = next(index for index, block in enumerate(list_page['blocks'])
                          if block.get('items') and len(block['items']) > 1)
        strong_page = next(page for page in package['pages']
                           if any(any(segment['strong']
                                      for segment in block.get('segments', []))
                                  for block in page['blocks']))
        strong_index = next(
            index for index, block in enumerate(strong_page['blocks'])
            if any(segment['strong'] for segment in block.get('segments', [])))

        def remove_block(value):
            value['pages'][0]['blocks'].pop()

        def add_block(value):
            value['pages'][0]['blocks'].append({
                'type': 'paragraph',
                'segments': [{'text': 'extra', 'strong': False}]})

        def swap_blocks(value):
            blocks = value['pages'][0]['blocks']
            blocks[0], blocks[1] = blocks[1], blocks[0]

        def list_block(value):
            page = next(row for row in value['pages']
                        if row['map_id'] == list_page['map_id'])
            return page['blocks'][list_index]

        def remove_item(value):
            list_block(value)['items'].pop()

        def add_item(value):
            list_block(value)['items'].append(
                [{'text': 'extra', 'strong': False}])

        def swap_items(value):
            list_block(value)['items'].reverse()

        def change_strong(value):
            page = next(row for row in value['pages']
                        if row['map_id'] == strong_page['map_id'])
            segment = next(row for row in page['blocks'][strong_index]['segments']
                           if row['strong'])
            segment['strong'] = False

        def alter_text(value):
            value['pages'][0]['blocks'][0]['segments'][0]['text'] += ' altered'

        for label, mutate in (
                ('remove_block', remove_block), ('add_block', add_block),
                ('swap_blocks', swap_blocks), ('remove_item', remove_item),
                ('add_item', add_item), ('swap_items', swap_items),
                ('change_strong', change_strong), ('alter_text', alter_text)):
            with self.subTest(structural_drift=label):
                changed = deepcopy(package)
                mutate(changed)
                self.assert_fault(
                    'MIGRATION_PACKAGE_INVALID',
                    lambda changed=changed:
                    migration._validate_service_details_package(changed, parents))
        escaped = deepcopy(package['pages'][0])
        escaped['intro'] = '<>&"'
        rendered = migration._service_detail_payload(escaped)['intro_text']
        self.assertEqual(rendered, '<p>&lt;&gt;&amp;"</p>')
        for unsafe in (
                '"quoted"', '<script>alert(1)</script>',
                '<style>body{display:none}</style>', '<b class=x>class</b>',
                '<b onclick=x>event</b>', '<b onload=x>on-prefix</b>',
                '<b aria-label=x>aria</b>', '<a href=/x>link</a>',
                '{{ 7|add:7 }}'):
            with self.subTest(unsafe=unsafe):
                escaped = deepcopy(package['pages'][0])
                escaped['intro'] = unsafe
                payload = migration._service_detail_payload(escaped)
                self.assertEqual(restricted_clean(payload['intro_text']),
                                 payload['intro_text'])
                if '<' in unsafe:
                    self.assertNotIn(unsafe, payload['intro_text'])
        for invalid in ('control\x00text', '\ud800'):
            escaped = deepcopy(package['pages'][0])
            escaped['intro'] = invalid
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda escaped=escaped:
                migration._service_detail_payload(escaped))

    def test_migh_exact_parents_create_ten_hidden_and_zero_write_replay(self):
        parents = self.create_exact_service_roots()
        result = migration.apply_service_details()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 10, 'published': 0})
        package = migration._read_service_details_package()
        children = list(Page.objects.filter(
            pk__in=[UUID(page['page_id']) for page in package['pages']]))
        self.assertEqual(len(children), 10)
        self.assertTrue(all(page.kind == Page.Kind.SERVICE
                            and not page.is_published for page in children))
        self.assertEqual({page.parent_id for page in children},
                         {page.pk for page in parents})
        self.assertEqual(
            set(Route.objects.filter(page__in=children).values_list(
                'target', flat=True)),
            {page['url'] for page in package['pages']})
        self.assertFalse(PageGrant.objects.filter(page__in=children).exists())
        before = self.state()
        replay = migration.apply_service_details()
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)

    def test_migh_missing_changed_parent_and_mixed_state_refuse(self):
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_service_details)
        self.assertEqual(self.state(), before)
        parents = self.create_exact_service_roots()
        raw(Page).filter(pk=parents[0].pk).update(name='Changed')
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_service_details)
        self.assertEqual(self.state(), before)
        raw(Page).filter(pk=parents[0].pk).update(name=parents[0].name)
        package = migration._read_service_details_package()
        for descriptor in package['pages']:
            with self.subTest(one_present=descriptor['map_id']):
                class RollbackPartial(Exception):
                    pass
                try:
                    with transaction.atomic():
                        Page.objects.create(
                            id=UUID(descriptor['page_id']),
                            name=descriptor['name'], kind=descriptor['kind'],
                            parent_id=descriptor['parent_id'],
                            position=descriptor['position'], is_published=False)
                        before = self.state()
                        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                                          migration.apply_service_details)
                        self.assertEqual(self.state(), before)
                        raise RollbackPartial
                except RollbackPartial:
                    pass

    def test_migh_route_reservation_position_and_audit_collisions_refuse(self):
        self.create_exact_service_roots()
        descriptor = migration._read_service_details_package()['pages'][0]

        class RollbackCollision(Exception):
            pass

        def check(setup):
            try:
                with transaction.atomic():
                    setup()
                    before = self.state()
                    self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                                      migration.apply_service_details)
                    self.assertEqual(self.state(), before)
                    raise RollbackCollision
            except RollbackCollision:
                pass

        def route_collision():
            page = Page.objects.create(
                name='Unrelated', kind=Page.Kind.ARTICLE, position=99,
                is_published=False)
            Route.objects.create(
                page=page, kind=Route.Kind.PRIMARY,
                target=descriptor['url'])

        def reservation_collision():
            IdentityReservation.objects.create(
                id=UUID(descriptor['page_id']), kind='synthetic')

        def position_collision():
            Page.objects.create(
                name='Sibling', kind=Page.Kind.ARTICLE,
                parent_id=descriptor['parent_id'],
                position=descriptor['position'], is_published=False)

        def audit_collision():
            record_event(
                category=Category.PAGES_LINKS,
                event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
                source=Source.APPLICATION, result=Result.SUCCESS,
                actor_id=self.owner.pk, object_kind='page',
                object_ref=UUID(descriptor['page_id']))

        for label, setup in (
                ('route', route_collision),
                ('reservation', reservation_collision),
                ('position', position_collision),
                ('audit', audit_collision)):
            with self.subTest(collision=label):
                check(setup)

    def test_migh_tenth_page_failure_rolls_back_and_concurrency_replays(self):
        self.create_exact_service_roots()
        before = self.state()
        original = migration._create_aggregate
        calls = 0

        def fail_tenth(*args):
            nonlocal calls
            calls += 1
            if calls == 10:
                raise RuntimeError('SYNTHETIC_TENTH_DETAIL_FAILURE')
            return original(*args)

        with patch('content.dev09_migration_apply._create_aggregate',
                   side_effect=fail_tenth):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_TENTH_DETAIL_FAILURE'):
                migration.apply_service_details()
        self.assertEqual(self.state(), before)
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_service_details()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)

    def test_migi_package_renderer_exact_safe_and_mutations_closed(self):
        catalog = migration._read_services_package()
        package = migration._read_planned_maintenance_package(catalog)
        self.assertEqual(len(package['pages']), 9)
        self.assertEqual(package['pages'][0]['kind'], Page.Kind.SERVICE_SECTION)
        self.assertEqual(
            [page['position'] for page in package['pages']],
            [1, 0, 1, 3, 4, 5, 6, 7, 8])
        self.assertFalse(any(page['position'] == 2
                             for page in package['pages'][1:]))
        for page in package['pages']:
            payload = migration._service_detail_payload(page)
            self.assertEqual(restricted_clean(payload['intro_text']),
                             payload['intro_text'])
            self.assertEqual(restricted_clean(payload['main_text']),
                             payload['main_text'])
            self.assertNotIn('<script', payload['main_text'].lower())
            self.assertNotIn('javascript:', payload['main_text'].lower())
        for label, mutate in (
                ('schema', lambda value: value.update(schema='wrong')),
                ('position2', lambda value: value['pages'][1].update(position=2)),
                ('kind', lambda value: value['pages'][0].update(
                    kind=Page.Kind.SERVICE)),
                ('extra', lambda value: value['pages'][0].update(extra=True)),
                ('unsafe', lambda value: value['pages'][0].update(
                    intro='<script>alert(1)</script>'))):
            with self.subTest(mutation=label):
                changed = deepcopy(package)
                mutate(changed)
                self.assert_fault(
                    'MIGRATION_PACKAGE_INVALID',
                    lambda changed=changed:
                    migration._validate_planned_maintenance_package(
                        changed, catalog))
        changed_catalog = deepcopy(catalog)
        changed_catalog['page']['groups'][1]['items'][3]['name'] = 'Changed'
        self.assert_fault(
            'MIGRATION_PACKAGE_INVALID',
            lambda: migration._validate_planned_maintenance_package(
                package, changed_catalog))
        for invalid in ('control\x00text', '\ud800'):
            changed = deepcopy(package['pages'][0])
            changed['intro'] = invalid
            self.assert_fault(
                'MIGRATION_PACKAGE_INVALID',
                lambda changed=changed: migration._service_detail_payload(changed))

    def test_migi_exact_catalog_create_nine_hidden_and_zero_write_replay(self):
        catalog = self.create_exact_services_parent()
        result = migration.apply_planned_maintenance()
        self.assertEqual(result, {
            'status': 'pass', 'replayed': False, 'pages': 9, 'published': 0})
        package = migration._read_planned_maintenance_package()
        pages = list(Page.objects.filter(
            pk__in=[UUID(page['page_id']) for page in package['pages']]))
        parent = Page.objects.get(pk=UUID(package['pages'][0]['page_id']))
        self.assertEqual(parent.parent_id, catalog.pk)
        self.assertEqual(parent.kind, Page.Kind.SERVICE_SECTION)
        self.assertFalse(parent.is_published)
        children = [page for page in pages if page.pk != parent.pk]
        self.assertEqual(
            sorted(page.position for page in children), [0, 1, 3, 4, 5, 6, 7, 8])
        self.assertTrue(all(page.parent_id == parent.pk
                            and page.kind == Page.Kind.SERVICE
                            and not page.is_published for page in children))
        self.assertFalse(PageGrant.objects.filter(page__in=pages).exists())
        self.assertFalse(Route.objects.filter(
            target='/services/planovoe-to/zamena-filtrov').exists())
        self.assertNotIn(str(parent.pk), {str(row['id']) for row in public_tree()})
        before = self.state()
        replay = migration.apply_planned_maintenance()
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), before)

    def test_migi_missing_changed_catalog_and_every_mixed_state_refuse(self):
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_planned_maintenance)
        self.assertEqual(self.state(), before)
        self.create_exact_services_parent()
        raw(Page).filter(pk=self.catalog_id).update(name='Changed')
        before = self.state()
        self.assert_fault('MIGRATION_PARENT_REQUIRED',
                          migration.apply_planned_maintenance)
        self.assertEqual(self.state(), before)
        raw(Page).filter(pk=self.catalog_id).update(name='Услуги и цены')
        package = migration._read_planned_maintenance_package()
        parent_descriptor = package['pages'][0]
        for descriptor in package['pages']:
            with self.subTest(one_present=descriptor['map_id']):
                class RollbackPartial(Exception):
                    pass
                try:
                    with transaction.atomic():
                        if descriptor is not parent_descriptor:
                            Page.objects.create(
                                id=UUID(parent_descriptor['page_id']),
                                name=parent_descriptor['name'],
                                kind=parent_descriptor['kind'],
                                parent_id=parent_descriptor['parent_id'],
                                position=parent_descriptor['position'],
                                is_published=False)
                        Page.objects.create(
                            id=UUID(descriptor['page_id']),
                            name=descriptor['name'], kind=descriptor['kind'],
                            parent_id=descriptor['parent_id'],
                            position=descriptor['position'], is_published=False)
                        before = self.state()
                        self.assert_fault(
                            'MIGRATION_EXISTING_CONFLICT',
                            migration.apply_planned_maintenance)
                        self.assertEqual(self.state(), before)
                        raise RollbackPartial
                except RollbackPartial:
                    pass

    def test_migi_collisions_and_unexpected_position2_refuse(self):
        self.create_exact_services_parent()
        descriptor = migration._read_planned_maintenance_package()['pages'][0]

        class RollbackCollision(Exception):
            pass

        def check(setup):
            try:
                with transaction.atomic():
                    setup()
                    before = self.state()
                    self.assert_fault(
                        'MIGRATION_EXISTING_CONFLICT',
                        migration.apply_planned_maintenance)
                    self.assertEqual(self.state(), before)
                    raise RollbackCollision
            except RollbackCollision:
                pass

        def route_collision():
            page = Page.objects.create(
                name='Unrelated', kind=Page.Kind.ARTICLE, position=99,
                is_published=False)
            Route.objects.create(
                page=page, kind=Route.Kind.PRIMARY, target=descriptor['url'])

        def reservation_collision():
            IdentityReservation.objects.create(
                id=UUID(descriptor['page_id']), kind='synthetic')

        def audit_collision():
            record_event(
                category=Category.PAGES_LINKS,
                event_code='MIGRATION_PAGE_IMPORTED', level=Level.INFO,
                source=Source.APPLICATION, result=Result.SUCCESS,
                actor_id=self.owner.pk, object_kind='page',
                object_ref=UUID(descriptor['page_id']))

        for label, setup in (
                ('route', route_collision),
                ('reservation', reservation_collision),
                ('audit', audit_collision)):
            with self.subTest(collision=label):
                check(setup)
        migration.apply_planned_maintenance()
        parent_id = UUID(descriptor['page_id'])
        Page.objects.create(
            name='Unexpected position 2', kind=Page.Kind.SERVICE,
            parent_id=parent_id, position=2, is_published=False)
        before = self.state()
        self.assert_fault('MIGRATION_EXISTING_CONFLICT',
                          migration.apply_planned_maintenance)
        self.assertEqual(self.state(), before)

    def test_migi_disabled_stops_before_package(self):
        with override_settings(DEV09_MIGRATION_APPLY_ENABLED=False), patch(
                'content.dev09_migration_apply._read_services_package') as reader:
            self.assert_fault('MIGRATION_APPLY_DISABLED',
                              migration.apply_planned_maintenance)
            reader.assert_not_called()

    def test_migi_ninth_failure_rolls_back_and_concurrency_replays(self):
        self.create_exact_services_parent()
        before = self.state()
        original = migration._create_aggregate
        calls = 0

        def fail_ninth(*args):
            nonlocal calls
            calls += 1
            if calls == 9:
                raise RuntimeError('SYNTHETIC_NINTH_MAINTENANCE_FAILURE')
            return original(*args)

        with patch('content.dev09_migration_apply._create_aggregate',
                   side_effect=fail_ninth):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_NINTH_MAINTENANCE_FAILURE'):
                migration.apply_planned_maintenance()
        self.assertEqual(self.state(), before)
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return migration.apply_planned_maintenance()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
