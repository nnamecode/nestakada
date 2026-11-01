"""Independent SH1 real-child HTTP checks; accepted writes remain gated."""
import base64
import hashlib
import importlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from uuid import uuid4, uuid5, NAMESPACE_URL

import html5lib
from django.apps import apps
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core import signing
from django.db import connection, IntegrityError, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase, override_settings

from media_library.models import AssetUsage
from media_library.storage import MediaStorage
from media_library.uploads import upload
from page_editor import test_check_http as H
from page_editor.test_media_http import PNG


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedHttpTests(TransactionTestCase):
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw

    def setUp(self):
        H.EditorCheckHttpTests.setUp(self)
        from shared_content.models import SharedBlock, SharedBudget
        # TransactionTestCase flush does not re-run migration data functions.
        # Explicit test setup restores only the two empty trusted components.
        for kind in ('header', 'footer'):
            SharedBlock.objects.get_or_create(kind=kind)
        SharedBudget.objects.get_or_create(singleton=True)
        data = base64.b64decode(PNG, validate=True)
        self.assertEqual(hashlib.sha256(data).hexdigest(),
            '06908e28b4c42eaab6b67833f32c178d0223c07fd5837ad155394777d98fb12c')
        self.asset = upload(actor=self.owner, page_id=self.page.pk,
            upload=SimpleUploadedFile('shared-synthetic.png', data, content_type='image/png'),
            expected_generation=1)
        self.assertEqual(self.asset.status, 'ready')
        self.assertEqual(self.asset.files.count(), 3)
        self.files_before = {str(file.pk): MediaStorage().manifest(file.key)
                             for file in self.asset.files.all()}

    def fixture(self, kind, canary='SHARED-CANARY'):
        marker = str(self.asset.pk)
        image = '<img data-es-shared-asset="%s" alt="Synthetic brand">' % marker
        brand = '<a class="es-brand" href="https://estakada-service.ru/">' + image + '</a>'
        if kind == 'footer':
            return '<footer class="es-footer"><div class="es-footer-left">' + brand + \
                '<p>' + canary + '</p></div><div class="es-footer-legal">' + \
                '<span>Политика конфиденциальности</span><span>Условия использования файлов cookie</span>' + \
                '<span class="es-footer-credit">Сделано в <b>noname</b></span></div></footer>'
        socials = ''.join('<a href="%s" aria-label="%s"><img data-es-shared-asset="%s" alt=""></a>' %
            (href, label, marker) for href, label in (
                ('https://t.me/synthetic', 'Telegram'), ('https://max.ru/synthetic', 'MAX'),
                ('https://www.instagram.com/synthetic', 'Instagram')))
        return '<header class="es-header">' + brand + \
            '<button class="es-menu-button" type="button" aria-expanded="false" aria-controls="es-nav">' + \
            '<span></span><span></span><span></span><b>Меню</b></button>' + \
            '<nav id="es-nav" aria-label="Основное меню"></nav>' + \
            '<div class="es-header-contacts"><div class="es-header-socials">' + socials + '</div>' + \
            '<a class="es-header-address" href="https://yandex.ru/maps/org/57771430682">' + \
            '<b>Москва</b><span>' + canary + '</span></a>' + \
            '<a class="es-header-phone" href="tel:+70000000001"><strong>+70000000001</strong>' + \
            '<span>Ежедневно с 9:00 до 21:00</span></a></div></header>'

    def state(self):
        result = {}
        encoder = DjangoJSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=False)
        models = [*apps.get_app_config('shared_content').get_models(),
                  *apps.get_app_config('page_versions').get_models(),
                  *apps.get_app_config('content').get_models(), AssetUsage]
        for model in models:
            digest, count = hashlib.sha256(), 0
            for row in model.objects.order_by('pk').values().iterator(chunk_size=1):
                digest.update(b'\x1e')
                for fragment in encoder.iterencode(row):
                    digest.update(fragment.encode('utf-8'))
                digest.update(b'\n')
                count += 1
            result[model._meta.label] = (count, digest.hexdigest())
        return result

    def path(self, kind, action=''):
        # Concrete urls.py places commands alongside edit/, not beneath it.
        return '/manage/shared/%s/%s/' % (kind, action if action else 'edit')

    def payload(self, kind, html=None):
        return {'protocol': 'shared-editor-v1', 'generation': 1, 'baseRevisionId': None,
            'sourceMode': 'current', 'draftBasis': None, 'stageId': None,
            'html': self.fixture(kind) if html is None else html}

    def post_shared(self, kind, action, value, *, client=None, csrf=True, read=None):
        client = self.owner_client if client is None else client
        headers = {}
        if csrf and settings.CSRF_COOKIE_NAME in client.cookies:
            headers['HTTP_X_CSRFTOKEN'] = client.cookies[settings.CSRF_COOKIE_NAME].value
        raw = self.raw(value)
        # Framework-only transport seam; actual child and PG remain real.
        with patch('shared_content.views.read_json_bytes', side_effect=read or
                   (lambda request, profile: request.body)):
            return client.post(self.path(kind, action), data=raw,
                               content_type='application/json', **headers)

    def assert_private(self, response):
        self.assertIn('no-store', response.get('Cache-Control', ''))

    def semantic_slot(self, kind, html, expected):
        tree = html5lib.parseFragment(html, treebuilder='etree', namespaceHTMLElements=False)
        root = list(tree)
        self.assertEqual(len(root), 1, 'SHARED_ROOT_COUNT')
        self.assertEqual(root[0].tag, kind)
        if kind == 'header':
            slots = [node for parent in root[0].iter('a')
                     if parent.attrib.get('class') == 'es-header-address'
                     for node in parent if node.tag == 'span']
            self.assertFalse(any(node.tag == 'p' for node in root[0].iter()),
                             'HEADER_FAKE_PARAGRAPH')
        else:
            slots = [node for parent in root[0].iter('div')
                     if parent.attrib.get('class') == 'es-footer-left'
                     for node in parent if node.tag == 'p']
        self.assertEqual(len(slots), 1, 'SHARED_CANARY_SLOT_COUNT')
        self.assertEqual(''.join(slots[0].itertext()), expected)

    def checked(self, kind, html=None):
        before = self.state()
        value = self.payload(kind, html)
        original_popen, children = subprocess.Popen, []

        def capture(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        with patch('editor_runtime.processing.subprocess.Popen', side_effect=capture):
            response = self.post_shared(kind, 'check', value)
        if response.status_code != 200:
            code = 'NO_FIXED_CODE'
            try:
                candidate = response.json().get('code')
                if isinstance(candidate, str) and 0 < len(candidate) <= 120 and all(
                    char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for char in candidate):
                    code = candidate
            except (ValueError, AttributeError, TypeError):
                pass
            print(json.dumps({'scope': 'SHARED_CHECK_REFUSAL_OBSERVATION',
                'kind': kind, 'httpStatus': response.status_code, 'code': code,
                'realChildCount': len(children),
                'childExitCodes': [child.returncode for child in children[:4]],
                'childStreamsClosed': [all(stream.closed for stream in
                    (child.stdin, child.stdout, child.stderr)) for child in children[:4]],
                'childObservationTruncated': len(children) > 4,
                'domainUnchanged': self.state() == before}), flush=True)
        self.assertEqual(response.status_code, 200, 'SHARED_REAL_CHECK_REFUSED')
        self.assert_private(response)
        self.assertEqual(len(children), 1, 'SHARED_REAL_CHILD_COUNT')
        child = children[0]
        self.assertEqual(child.returncode, 0)
        with self.assertRaises(ChildProcessError):
            os.waitpid(child.pid, os.WNOHANG)
        self.assertTrue(all(stream.closed for stream in (child.stdin, child.stdout, child.stderr)))
        result = response.json()
        self.assertEqual(result['inputFingerprint'], hashlib.sha256(self.raw(value)).hexdigest())
        self.assertTrue(isinstance(result['checkReceipt'], str) and bool(result['checkReceipt']))
        from shared_content.services import SALT, inspect_context
        proof = signing.loads(result['checkReceipt'], salt=SALT)
        context = inspect_context(actor=self.owner, kind=kind, generation=1)
        self.assertEqual(proof['protocol'], 'shared-editor-check-v1')
        self.assertEqual(proof['actor'], self.owner.pk)
        self.assertEqual(proof['generation'], 1)
        self.assertEqual(proof['block'], context.block_id)
        self.assertEqual(proof['kind'], kind)
        self.assertEqual(proof['contextStamp'], context.stamp)
        self.assertEqual(proof['schemaVersion'], kind + '-v1')
        self.assertEqual(proof['htmlHash'], hashlib.sha256(result['normalisedHtml'].encode()).hexdigest())
        self.assertRegex(proof['mediaStamp'], r'^[0-9a-f]{64}$')
        self.semantic_slot(kind, result['normalisedHtml'], 'SHARED-CANARY')
        self.assertEqual(self.state(), before, 'CHECK_CONTENT_MUTATION')
        self.assertEqual({str(file.pk): MediaStorage().manifest(file.key)
                          for file in self.asset.files.all()}, self.files_before)
        return value, result

    def test_owner_header_real_child_canary_exact_slot_no_fake_paragraph(self):
        self.checked('header')

    def test_owner_footer_real_child_canary_exact_slot_no_public_claim(self):
        self.checked('footer')

    def test_employee_page_grant_and_anonymous_cannot_read_or_check_shared(self):
        before = self.state()
        for kind in ('header', 'footer'):
            for client in (self.employee_client, self.visitor):
                for action in ('', 'history'):
                    response = client.get(self.path(kind, action))
                    self.assertIn(response.status_code, (401, 403, 303))
                    self.assertNotIn(b'SHARED-CANARY', response.content)
                    self.assert_private(response)
                def forbidden_read(*args, **kwargs):
                    raise AssertionError('UNAUTHORIZED_SHARED_BODY_READ')
                for action in ('check', 'draft', 'apply', 'restore/prepare'):
                    response = self.post_shared(kind, action, self.payload(kind),
                                                client=client, read=forbidden_read)
                    self.assertIn(response.status_code, (401, 403))
                    self.assertNotIn(b'checkReceipt', response.content)
                    self.assert_private(response)
        self.assertEqual(self.state(), before)

    def test_owner_csrf_required_before_shared_body_read(self):
        before = self.state()
        def forbidden_read(*args, **kwargs):
            raise AssertionError('CSRF_FAILURE_SHARED_BODY_READ')
        response = self.post_shared('footer', 'check', self.payload('footer'),
                                    csrf=False, read=forbidden_read)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.state(), before)

    def test_closed_structure_script_styles_templates_and_url_bypasses_refused(self):
        source = self.fixture('header')
        bad_sources = (
            source.replace('SHARED-CANARY', '{{ 7*7 }}'),
            source.replace('SHARED-CANARY', '<script>SHARED-CANARY</script>'),
            source.replace('<span>SHARED-CANARY', '<span onclick="alert(1)">SHARED-CANARY'),
            source.replace('<span>SHARED-CANARY', '<span style="color:red">SHARED-CANARY'),
            source.replace('class="es-header"', 'class="es-header arbitrary"'),
            source.replace('https://yandex.ru/maps/org/57771430682', 'javascript:alert(1)'),
            source.replace('https://yandex.ru/maps/org/57771430682', '//example.invalid/'),
            source.replace('tel:+70000000001', '/'),
            source.replace('tel:+70000000001', '#x'),
            source.replace('https://t.me/synthetic', '/'),
            source.replace('https://t.me/synthetic', '#x'),
            source.replace('<nav id="es-nav" aria-label="Основное меню"></nav>',
                '<nav id="es-nav" aria-label="Основное меню"><a href="/fake/">Fake</a></nav>'),
            '<header><p>SHARED-CANARY</p></header>',
        )
        before = self.state()
        for index, html in enumerate(bad_sources):
            with self.subTest(vector=index):
                response = self.post_shared('header', 'check', self.payload('header', html))
                self.assertEqual(response.status_code, 400, 'UNSAFE_SHARED_ACCEPTED')
                self.assertNotIn(b'checkReceipt', response.content)
                self.assert_private(response)
                self.assertEqual(self.state(), before)

    def test_client_src_srcset_foreign_marker_and_raw_svg_are_not_asset_authority(self):
        source = self.fixture('footer')
        marker = 'data-es-shared-asset="%s"' % self.asset.pk
        bad_sources = (
            source.replace(marker, 'src="https://example.invalid/x.webp"'),
            source.replace(marker, marker + ' src="/private/source.png"'),
            source.replace(marker, marker + ' srcset="/x.webp 2x"'),
            source.replace(str(self.asset.pk), str(uuid4())),
            source.replace('<img ' + marker + ' alt="Synthetic brand">', '<svg onload="alert(1)"></svg>'),
        )
        before = self.state()
        for index, html in enumerate(bad_sources):
            with self.subTest(vector=index):
                response = self.post_shared('footer', 'check', self.payload('footer', html))
                self.assertIn(response.status_code, (400, 409))
                self.assertNotIn(b'checkReceipt', response.content)
                self.assertEqual(self.state(), before)

    def test_missing_real_asset_variant_bytes_prevent_check_receipt(self):
        file = self.asset.files.get(kind='main')
        root = Path(settings.MEDIA_LIBRARY_ROOT).resolve()
        path = (root / file.key).resolve()
        self.assertTrue(path.is_relative_to(root))
        original = path.read_bytes()
        path.unlink()
        before = self.state()
        try:
            response = self.post_shared('footer', 'check', self.payload('footer'))
            self.assertIn(response.status_code, (400, 409, 503))
            self.assertNotIn(b'checkReceipt', response.content)
            self.assertEqual(self.state(), before)
        finally:
            path.write_bytes(original)
        self.checked('footer')

    def test_unknown_reservation_profile_denies_real_draft_and_apply_without_writes(self):
        for kind in ('header', 'footer'):
            value, checked = self.checked(kind)
            if checked['normalisationChanged']:
                value, checked = self.checked(kind, checked['normalisedHtml'])
                self.assertFalse(checked['normalisationChanged'])
            value.update(html=checked['normalisedHtml'], checkReceipt=checked['checkReceipt'],
                         operationId=str(uuid4()))
            for action in ('draft', 'apply'):
                with self.subTest(kind=kind, action=action):
                    before = self.state()
                    response = self.post_shared(kind, action, value)
                    self.assertEqual(response.status_code, 503, 'UNKNOWN_PROFILE_ALLOWED_WRITE')
                    self.assertEqual(response.json()['code'], 'SHARED_BUDGET_PROFILE_UNAVAILABLE')
                    self.assertNotIn(b'resultId', response.content)
                    self.assert_private(response)
                    self.assertEqual(self.state(), before, 'UNKNOWN_PROFILE_PARTIAL_MUTATION')
                    self.checked(kind)

    def test_unknown_kind_not_a_third_shared_block(self):
        before = self.state()
        response = self.owner_client.get(self.path('arbitrary'))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.state(), before)

    def test_compatible_restore_prepare_unknown_profile_refuses_without_stage_or_publication(self):
        source = self.seed_revision('header')
        before = self.state()
        response = self.post_shared('header', 'restore/prepare', {
            'protocol': 'shared-editor-v1', 'generation': 1, 'baseRevisionId': None,
            'sourceRevisionId': str(source.pk), 'operationId': str(uuid4()), 'confirmReplace': True})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'SHARED_BUDGET_PROFILE_UNAVAILABLE')
        self.assertEqual(self.state(), before)
        self.checked('header')

    def seed_revision(self, kind, *, sequence=1, identity=None):
        from shared_content.models import SharedBlock, SharedRevision
        html = self.fixture(kind, 'IMMUTABLE-' + kind)
        values = {'block': SharedBlock.objects.get(kind=kind), 'sequence': sequence,
            'schema_version': kind + '-v1', 'html': html,
            'payload_hash': hashlib.sha256(html.encode()).hexdigest(), 'author_id': self.owner.pk}
        if identity is not None:
            values['id'] = identity
        # Explicit fixture preparation, never a substitute for product Apply.
        return SharedRevision.objects.create(**values)

    def test_snapshot_direct_update_delete_and_duplicate_sequence_are_rejected(self):
        from shared_content.models import SharedRevision
        revision = self.seed_revision('header')
        before = self.state()
        revision.html = 'MUTATED'
        with self.assertRaises(ValidationError):
            revision.save()
        with self.assertRaises(ValidationError):
            SharedRevision.objects.filter(pk=revision.pk).update(html='MUTATED')
        with self.assertRaises(ValidationError):
            revision.delete()
        with self.assertRaises(ValidationError):
            SharedRevision.objects.filter(pk=revision.pk).delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.seed_revision('header')
        self.assertEqual(self.state(), before)

    def test_crossblock_current_rejected_by_actual_database_constraint(self):
        from shared_content.models import SharedBlock, SharedDraft
        header = SharedBlock.objects.get(kind='header')
        footer_revision = self.seed_revision('footer')
        before = self.state()
        table = connection.ops.quote_name(SharedBlock._meta.db_table)
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE ' + table + ' SET current_revision_id=%s WHERE id=%s',
                               [footer_revision.pk, header.pk])
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertEqual(self.state(), before)
        with self.assertRaises(IntegrityError), transaction.atomic():
            html = self.fixture('header')
            SharedDraft.objects.create(block=header, base_revision=footer_revision,
                html=html, payload_hash=hashlib.sha256(html.encode()).hexdigest(), author_id=self.owner.pk)
            with connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        self.assertEqual(self.state(), before)

    def test_third_component_kind_is_rejected_by_database(self):
        from shared_content.models import SharedBlock
        before = self.state()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SharedBlock.objects.create(kind='other')
        self.assertEqual(self.state(), before)

    def test_page_identity_cannot_be_reused_as_shared_consumer(self):
        from page_versions.models import PageRevision
        initial = PageRevision.objects.get(pk=self.initial)
        before = self.state()
        with self.assertRaises(ValidationError):
            self.seed_revision('header', identity=initial.pk)
        self.assertEqual(self.state(), before)

    def test_historical_seed_preflights_footer_collisions_before_any_header_insert(self):
        from page_versions.models import IdentityReservation as PageIdentity
        from shared_content.models import SharedBlock, SharedBudget, SharedIdentityReservation
        migration = importlib.import_module('shared_content.migrations.0001_initial')
        historical_apps = MigrationLoader(connection).project_state(
            ('shared_content', '0001_initial')).apps
        footer_identity = uuid5(NAMESPACE_URL, 'estakada:shared:footer')
        original = self.state()
        for collision in ('page_identity', 'asset_usage'):
            with self.subTest(collision=collision), transaction.atomic():
                # Simulate fresh RunPython prerequisites only inside rollback-
                # owned fixture. No product history exists in this test case.
                with connection.cursor() as cursor:
                    for model in (SharedBlock, SharedBudget, SharedIdentityReservation):
                        table = connection.ops.quote_name(model._meta.db_table)
                        cursor.execute('DELETE FROM ' + table)
                if collision == 'page_identity':
                    PageIdentity.objects.create(id=footer_identity, kind='pagerevision')
                else:
                    AssetUsage.objects.create(asset=self.asset, kind='shared_block',
                                              consumer_id=footer_identity, slot='shared:seed-collision')
                before_seed = self.state()
                with self.assertRaisesRegex(RuntimeError, '^SHARED_SEED_CONSUMER_ID_RESERVED$'):
                    migration.seed_blocks(historical_apps, SimpleNamespace(connection=connection))
                self.assertEqual(self.state(), before_seed, 'SEED_PARTIAL_HEADER_OR_METADATA')
                self.assertFalse(SharedBlock.objects.exists())
                self.assertFalse(SharedIdentityReservation.objects.exists())
                self.assertFalse(SharedBudget.objects.exists())
                transaction.set_rollback(True)
            self.assertEqual(self.state(), original, 'SEED_COLLISION_FIXTURE_NOT_ROLLED_BACK')

    def test_actual_quota_inventory_total_count_and_warning_not_cached_budget(self):
        from shared_content import quota
        from shared_content.models import SharedBudget, SharedCleanupJob
        self.seed_revision('header')
        self.seed_revision('footer')
        measured = quota.measure()
        self.assertEqual(measured['snapshotCount'], 2)
        self.assertEqual(measured['limitBytes'], 268435456)
        self.assertEqual(measured['snapshotLimit'], 10000)
        self.assertFalse(measured['profileAvailable'])
        self.assertEqual(measured['warning'], measured['usedBytes'] >= 201326592)
        self.assertEqual(len(measured['relations']), 9)
        self.assertEqual(len({row['oid'] for row in measured['relations']}), 9)
        self.assertEqual(measured['usedBytes'], sum(row['totalBytes'] for row in measured['relations']))
        tables = sorted(model._meta.db_table for model in
                        apps.get_app_config('shared_content').get_models())
        self.assertEqual(sorted(row['table'] for row in measured['relations']), tables)
        with connection.cursor() as cursor:
            cursor.execute('SELECT c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
                'WHERE n.nspname=%s AND c.relname=%s', ['app', SharedCleanupJob._meta.db_table])
            cleanup_roots = cursor.fetchall()
            self.assertEqual(len(cleanup_roots), 1)
            self.assertIn((SharedCleanupJob._meta.db_table, cleanup_roots[0][0]),
                          {(row['table'], row['oid']) for row in measured['relations']})
            for row in measured['relations']:
                cursor.execute('SELECT pg_total_relation_size(%s::oid),pg_table_size(%s::oid),'
                    'pg_indexes_size(%s::oid)', [row['oid']] * 3)
                total, table, indexes = cursor.fetchone()
                self.assertEqual((row['totalBytes'], row['tableBytesIncludingToast'], row['indexBytes']),
                                 (total, table, indexes))
                self.assertEqual(total, table + indexes)
            # Explicit corrupted cache fixture: fresh accounting must ignore it.
            budget_table = connection.ops.quote_name(SharedBudget._meta.db_table)
            cursor.execute('UPDATE ' + budget_table +
                ' SET snapshot_count=9999,charged_bytes=268435456 WHERE singleton=true')
        fresh = quota.measure()
        self.assertEqual(fresh['snapshotCount'], 2)
        self.assertNotEqual(fresh['usedBytes'], 268435456)
        self.assertEqual(fresh['warning'], fresh['usedBytes'] >= 201326592)

    def seed_count_full(self):
        from shared_content import quota
        from shared_content.models import SharedBlock, SharedRevision, SharedIdentityReservation
        revision_table = connection.ops.quote_name(SharedRevision._meta.db_table)
        identity_table = connection.ops.quote_name(SharedIdentityReservation._meta.db_table)
        # Same finite-experiment 32MiB guard as prior probes, not a write profile.
        self.assertLess(quota.measure()['usedBytes'], 16 * 1024 * 1024,
                        'BOUNDED_COUNT_BASELINE_NO_HEADROOM')
        # Bounded short valid fixtures. This is not a successful product Apply.
        with transaction.atomic(), connection.cursor() as cursor:
            from content.models import lock_content
            lock_content('default')
            for kind in ('header', 'footer'):
                identities = [str(uuid4()) for _ in range(5000)]
                html = self.fixture(kind, 'COUNT-FIXTURE-' + kind)
                cursor.execute('INSERT INTO ' + identity_table + ' (id,kind,block_id) '
                    "SELECT id,'sharedrevision',%s FROM unnest(%s::uuid[]) AS ids(id)",
                    [SharedBlock.objects.get(kind=kind).pk, identities])
                cursor.execute('INSERT INTO ' + revision_table +
                    ' (id,block_id,sequence,schema_version,html,payload_hash,author_id,created_at) '
                    'SELECT id,%s,sequence,%s,%s,%s,%s,CURRENT_TIMESTAMP '
                    'FROM unnest(%s::uuid[]) WITH ORDINALITY AS ids(id,sequence)',
                    [SharedBlock.objects.get(kind=kind).pk, kind + '-v1', html,
                     hashlib.sha256(html.encode()).hexdigest(), self.owner.pk, identities])
                self.assertLess(quota.measure_locked()['usedBytes'], 32 * 1024 * 1024,
                                'BOUNDED_COUNT_FIXTURE_TOO_LARGE')
        self.assertEqual(SharedRevision.objects.count(), 10000)

    def test_actual_10000_rows_count_full_refuses_10001_without_pruning_or_receipt(self):
        from shared_content import quota
        self.seed_count_full()
        measured = quota.measure()
        self.assertEqual(measured['snapshotCount'], 10000)
        self.assertLess(measured['usedBytes'], 32 * 1024 * 1024,
                        'BOUNDED_COUNT_FIXTURE_TOO_LARGE')
        for kind in ('header', 'footer'):
            value, checked = self.checked(kind)
            if checked['normalisationChanged']:
                value, checked = self.checked(kind, checked['normalisedHtml'])
                self.assertFalse(checked['normalisationChanged'])
            value.update(html=checked['normalisedHtml'], checkReceipt=checked['checkReceipt'],
                         operationId=str(uuid4()))
            before = self.state()
            # Exercise the count gate with the guarded unit-only candidate profile;
            # ordinary unit runtime correctly refuses an unavailable profile first.
            from shared_content import profiles
            with profiles.calibration_scope():
                response = self.post_shared(kind, 'apply', value)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['code'], 'SHARED_HISTORY_COUNT_FULL')
            self.assertEqual(self.state(), before)
            self.assertEqual(quota.measure()['snapshotCount'], 10000)
