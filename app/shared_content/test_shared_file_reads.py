"""SH2 actual file-mode metadata/read evidence; no successful product Apply."""
import hashlib
import importlib
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, IntegrityError, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings

from shared_content import test_shared_http as Q
from shared_content import test_shared_reads as R
from shared_content.faults import SharedFault


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedFileReadTests(TransactionTestCase):
    setUp = Q.SharedHttpTests.setUp
    login = Q.SharedHttpTests.login
    raw = Q.SharedHttpTests.raw
    fixture = Q.SharedHttpTests.fixture
    state = Q.SharedHttpTests.state
    path = Q.SharedHttpTests.path
    post_shared = Q.SharedHttpTests.post_shared
    assert_private = Q.SharedHttpTests.assert_private
    semantic_slot = Q.SharedHttpTests.semantic_slot
    parsed = R.SharedReadHttpTests.parsed
    marked_text = R.SharedReadHttpTests.marked_text

    def file_fixture(self, kind, *, sequence=1):
        from shared_content.models import SharedBlock, SharedRevision
        from shared_content.policy import normalize_html
        from shared_content.storage import SharedStorage
        # Producer preparation is explicit fixture setup, never an Apply bypass.
        html = normalize_html(self.fixture(kind, 'FILE-CANARY-' + kind), kind)['html']
        store = SharedStorage()
        descriptor = store.write_new(html)
        block = SharedBlock.objects.get(kind=kind)
        revision = SharedRevision.objects.create(block=block, sequence=sequence,
            schema_version=kind + '-v1', html='', payload_hash=descriptor['file_sha256'],
            author_id=self.owner.pk, **descriptor)
        with transaction.atomic(), connection.cursor() as cursor:
            from content.models import lock_content
            lock_content('default')
            cursor.execute('UPDATE ' + connection.ops.quote_name(SharedBlock._meta.db_table) +
                ' SET current_revision_id=%s,generation=2 WHERE id=%s', [revision.pk, block.pk])
        return store, descriptor, revision, html

    def test_owner_filemode_editor_version_and_compare_use_actual_disk_bytes(self):
        for kind in ('header', 'footer'):
            store, descriptor, revision, html = self.file_fixture(kind)
            self.assertEqual(revision.html, '')
            self.assertEqual((store.root / descriptor['file_key']).read_text(encoding='utf-8'), html)
            before = self.state()
            editor = self.parsed(self.owner_client.get(self.path(kind)))
            inputs = [node for node in editor.iter('textarea') if node.attrib.get('id') == 'shared-html']
            self.assertEqual(len(inputs), 1)
            self.assertEqual(''.join(inputs[0].itertext()), html)
            version = self.parsed(self.owner_client.get(self.path(kind, 'versions/' + str(revision.pk))))
            self.assertEqual(self.marked_text(version, 'data-saved-html'), html)
            comparison = self.parsed(self.owner_client.get(
                self.path(kind, 'compare') + '?versionId=' + str(revision.pk)))
            self.assertEqual(self.marked_text(comparison, 'data-saved-html'), html)
            self.assertEqual(self.marked_text(comparison, 'data-current-html'), html)
            self.semantic_slot(kind, html, 'FILE-CANARY-' + kind)
            self.assertEqual(self.state(), before, 'FILEMODE_OWNER_READ_MUTATED_METADATA')

    def test_filemode_missing_and_same_length_tampering_refuse_without_inline_fallback(self):
        from shared_content.content import content_html
        store, descriptor, revision, html = self.file_fixture('header')
        path = store.root / descriptor['file_key']
        before = self.state()
        original = path.read_bytes()
        tampered = original.replace(b'FILE-CANARY-header', b'EVIL-CANARY-header')
        self.assertEqual(len(tampered), len(original))
        self.assertNotEqual(tampered, original)
        path.write_bytes(tampered)
        with self.assertRaises(SharedFault):
            content_html(revision)
        response = self.owner_client.get(self.path('header'))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b'FILE-CANARY-header', response.content)
        path.unlink()
        with self.assertRaises(SharedFault):
            content_html(revision)
        # Deliberately malformed mixed descriptor cannot hide a missing blob.
        with self.assertRaises(SharedFault):
            content_html({**descriptor, 'html': 'INLINE-FALLBACK-CANARY',
                          'payload_hash': descriptor['file_sha256']})
        response = self.owner_client.get(self.path('header', 'versions/' + str(revision.pk)))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.state(), before)

    def test_actual_combined_quota_includes_referenced_orphan_and_directory_blocks(self):
        from shared_content import quota
        from shared_content.models import SharedRevision, SharedDraft
        store, descriptor, _, _ = self.file_fixture('footer')
        orphan = store.write_new('UNREFERENCED-ORPHAN')
        references = list(SharedRevision.objects.filter(storage_kind='file').values_list('file_key', flat=True))
        references += list(SharedDraft.objects.filter(storage_kind='file').values_list('file_key', flat=True))
        inventory = store.inventory(referenced_keys=references)
        measurement = quota.measure()
        pg_actual = sum(row['totalBytes'] for row in measurement['relations'])
        self.assertEqual(measurement['actualOwnFsAllocatedBytes'], inventory['actualAllocatedBytes'])
        self.assertEqual(measurement['actualCombinedBytes'], pg_actual + inventory['actualAllocatedBytes'])
        self.assertEqual(measurement['usedBytes'], measurement['actualCombinedBytes'])
        self.assertEqual(inventory['orphanCount'], 1)
        self.assertEqual(inventory['blobCount'], 2)
        self.assertFalse(measurement['profileAvailable'])
        self.assertFalse(measurement['fsMetadataReserveAvailable'])
        self.assertIsNone(measurement['reserveBytes'])
        self.assertEqual((store.root / orphan['file_key']).read_bytes(), b'UNREFERENCED-ORPHAN')
        self.assertEqual(measurement['warning'], measurement['usedBytes'] >= 201326592)

    def test_legacy_historical_shape_uses_actual_db_defaults_preserving_inline_nonce(self):
        from shared_content.models import SharedBlock, SharedRevision, SharedDraft
        historical = MigrationLoader(connection).project_state(('shared_content', '0001_initial')).apps
        OldRevision = historical.get_model('shared_content', 'SharedRevision')
        OldDraft = historical.get_model('shared_content', 'SharedDraft')
        block = SharedBlock.objects.get(kind='footer')
        nonce = 'LEGACY-' + uuid4().hex + '-старые данные 🚀'
        html = self.fixture('footer', nonce)
        expected_hash = hashlib.sha256(html.encode()).hexdigest()
        old = OldRevision.objects.create(id=uuid4(), block_id=block.pk, sequence=1,
            schema_version='footer-v1', html=html, payload_hash=expected_hash, author_id=self.owner.pk)
        draft = OldDraft.objects.create(id=uuid4(), block_id=block.pk, revision=1,
            base_revision_id=old.pk, html=html, payload_hash=expected_hash, author_id=self.owner.pk)
        from shared_content.content import content_html
        for model, identity in ((SharedRevision, old.pk), (SharedDraft, draft.pk)):
            row = model.objects.get(pk=identity)
            self.assertEqual((row.html, row.payload_hash), (html, expected_hash))
            self.assertEqual((row.storage_kind, row.file_key, row.byte_size, row.file_sha256),
                             ('inline', '', None, ''))
            self.assertEqual(content_html(row), html)
        self.assertEqual(SharedDraft.objects.get(pk=draft.pk).base_revision_id, old.pk)
        # Real old-shape INSERT against migrated DB proves additive defaults;
        # this is not a downgrade/re-upgrade experiment on preexisting rows.

    def test_mixed_unknown_and_malformed_file_metadata_rejected_by_database(self):
        from shared_content.models import SharedBlock, SharedRevision
        store, descriptor, _, _ = self.file_fixture('footer')
        values = {'id': uuid4(), 'block': SharedBlock.objects.get(kind='header'), 'sequence': 1,
            'schema_version': 'header-v1', 'html': '', 'payload_hash': descriptor['file_sha256'],
            'author_id': self.owner.pk, **descriptor}
        # Raw SQL skips model clean so these are actual DB constraints.
        invalid = ({'storage_kind': 'bogus'}, {'html': 'MIXED'}, {'byte_size': None},
                   {'file_sha256': 'BAD'}, {'payload_hash': '0' * 64},
                   {'file_key': 'blobs/00/' + '11' * 16 + '.html'})
        for change in invalid:
            with self.subTest(fields=tuple(change)), self.assertRaises(IntegrityError), transaction.atomic():
                row = {**values, **change}
                columns = ('id', 'block_id', 'sequence', 'schema_version', 'html', 'payload_hash',
                           'author_id', 'storage_kind', 'file_key', 'byte_size', 'file_sha256')
                row['block_id'] = row['block'].pk
                with connection.cursor() as cursor:
                    cursor.execute('INSERT INTO ' + connection.ops.quote_name(SharedRevision._meta.db_table) +
                        ' (' + ','.join(columns) + ',created_at) VALUES (' +
                        ','.join(['%s'] * len(columns)) + ',CURRENT_TIMESTAMP)', [row[key] for key in columns])

    def test_explicit_inline_integrity_and_filemode_no_fallback(self):
        from shared_content.content import content_html
        text = 'INLINE-INTACT-🚀'
        descriptor = {'storage_kind': 'inline', 'html': text, 'file_key': '', 'byte_size': None,
                      'file_sha256': '', 'payload_hash': hashlib.sha256(text.encode()).hexdigest()}
        self.assertEqual(content_html(descriptor), text)
        for altered in ({'payload_hash': '0' * 64}, {'html': text + 'TAMPER'},
                        {'storage_kind': 'file'}, {'file_key': 'unexpected'}):
            with self.assertRaises(SharedFault):
                content_html({**descriptor, **altered})

    def test_simple_inline_writes_need_no_profile_and_create_no_blob_or_journal(self):
        from shared_content.storage import SharedStorage
        from shared_content.models import SharedBlock, SharedDraft, SharedRevision
        store = SharedStorage()
        store.write_new('EXISTING-ORPHAN')
        for kind in ('header', 'footer'):
            block = SharedBlock.objects.get(kind=kind)
            payload = {'protocol': 'shared-editor-v1', 'generation': 1,
                'baseRevisionId': str(block.current_revision_id) if block.current_revision_id else None,
                'sourceMode': 'current', 'draftBasis': None, 'stageId': None, 'html': self.fixture(kind)}
            response = self.post_shared(kind, 'check', payload)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            payload['html'] = result['normalisedHtml']
            response = self.post_shared(kind, 'check', payload)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            payload.update(checkReceipt=result['checkReceipt'])
            for action in ('draft', 'apply'):
                payload['operationId'] = str(uuid4())
                before_fs = store.inventory()
                response = self.post_shared(kind, action, payload)
                self.assertEqual(response.status_code, 200)
                result_id = response.json()['resultId']
                row = (SharedDraft if action == 'draft' else SharedRevision).objects.get(pk=result_id)
                self.assertEqual(row.storage_kind, 'inline')
                self.assertEqual(store.inventory(), before_fs, 'UNKNOWN_PROFILE_STAGED_FILE_OR_JOURNAL')

    def test_real_check_current_file_and_direct_restore_read_outside_sql_transactions(self):
        from django.core import signing
        from shared_content.models import SharedRevision
        from shared_content.policy import normalize_html
        from shared_content.services import SALT
        from shared_content.storage import SharedStorage
        store, current_descriptor, current, current_html = self.file_fixture('header', sequence=2)
        old_html = normalize_html(self.fixture('header', 'RESTORE-FILE-CANARY-header').replace(
            '+70000000001', '+70000000009'), 'header')['html']
        old_descriptor = store.write_new(old_html)
        old = SharedRevision.objects.create(block=current.block, sequence=1,
            schema_version='header-v1', html='', payload_hash=old_descriptor['file_sha256'],
            author_id=self.owner.pk, **old_descriptor)
        for descriptor, expected in ((current_descriptor, current_html), (old_descriptor, old_html)):
            actual = (store.root / descriptor['file_key']).read_bytes()
            self.assertEqual(actual, expected.encode())
            self.assertEqual(hashlib.sha256(actual).hexdigest(), descriptor['file_sha256'])
        before_db, before_fs = self.state(), store.inventory()
        original_read, reads = SharedStorage.read, []

        def observed_read(instance, descriptor):
            self.assertFalse(connection.in_atomic_block, 'FILE_PAYLOAD_READ_INSIDE_SQL_TRANSACTION')
            value = original_read(instance, descriptor)
            reads.append((descriptor['file_key'], hashlib.sha256(value.encode()).hexdigest()))
            return value

        payload = {'protocol': 'shared-editor-v1', 'generation': 1,
            'baseRevisionId': str(current.pk), 'sourceMode': 'current',
            'draftBasis': None, 'stageId': None, 'html': current_html}
        with patch.object(SharedStorage, 'read', new=observed_read):
            checked = self.post_shared('header', 'check', payload)
            self.assertEqual(checked.status_code, 200)
            value = checked.json()
            self.assertEqual(value['normalisedHtml'], current_html)
            self.assertEqual(value['inputFingerprint'], hashlib.sha256(self.raw(payload)).hexdigest())
            self.assertEqual(value['baseRevisionId'], str(current.pk))
            proof = signing.loads(value['checkReceipt'], salt=SALT)
            self.assertEqual((proof['actor'], proof['kind'], proof['block']),
                             (self.owner.pk, 'header', str(current.block_id)))
            self.assertEqual(proof['htmlHash'], current_descriptor['file_sha256'])
            self.semantic_slot('header', value['normalisedHtml'], 'FILE-CANARY-header')
            token = self.owner_client.cookies[settings.CSRF_COOKIE_NAME].value
            restored = self.owner_client.post(
                f'/manage/shared/header/versions/{old.pk}/restore/',
                data={'expectedCurrentId': str(current.pk), 'confirmed': 'yes'},
                HTTP_X_CSRFTOKEN=token)
            self.assertEqual(restored.status_code, 409)
            self.assertEqual(restored.json()['code'], 'SHARED_MEDIA_UNAVAILABLE')
        self.assertIn((current_descriptor['file_key'], current_descriptor['file_sha256']), reads)
        self.assertIn((old_descriptor['file_key'], old_descriptor['file_sha256']), reads)
        self.assertEqual(self.state(), before_db, 'FILE_CHECK_OR_RESTORE_MUTATED_METADATA')
        self.assertEqual(store.inventory(), before_fs, 'FILE_CHECK_OR_RESTORE_STAGED_BLOB')
        # Actual current and compatible target-source only. No held-stage or native RAM claim.


class SharedAdditiveMigrationTests(TransactionTestCase):
    """Explicitly authorized serial unit-DB migration experiment only."""

    def test_real_backward_fixture_forward_preserves_legacy_bodies_ids_and_references(self):
        self.assertEqual(os.environ.get('ESTAKADA_LOCAL_ENV'), 'test')
        self.assertEqual(os.environ.get('DJANGO_SETTINGS_MODULE'), 'estakada.settings.local_http')
        self.assertEqual(getattr(settings, 'ENVIRONMENT', None), 'test')
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertFalse(connection.in_atomic_block)
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user')
            self.assertEqual(cursor.fetchone(), ('estakada_foundation_unit', 'app_migrator'))
        from shared_content.models import (SharedRevision, SharedDraft, SharedRestoreStage,
            SharedReceipt, SharedBasePin, SharedBlock)
        for model in (SharedRevision, SharedDraft, SharedRestoreStage, SharedReceipt, SharedBasePin):
            self.assertEqual(model.objects.count(), 0, 'MIGRATION_FIXTURE_REQUIRES_EMPTY_SHARED_HISTORY')
        self.assertFalse(SharedBlock.objects.filter(current_revision__isnull=False).exists())
        loader = MigrationLoader(connection)
        latest = loader.graph.leaf_nodes('shared_content')
        self.assertEqual(len(latest), 1)
        self.assertEqual(latest[0][0], 'shared_content')
        old_target = ('shared_content', '0001_initial')
        self.assertIn(old_target, loader.disk_migrations)
        self.assertNotEqual(latest, [old_target], 'ADDITIVE_MIGRATION_NOT_PRESENT')
        module = importlib.import_module(loader.disk_migrations[old_target].__module__)
        original_migration_sha = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        projections, before = {}, {}

        def manifest(model, fields):
            rows = list(model.objects.order_by('pk').values(*fields))
            encoded = json.dumps(rows, cls=DjangoJSONEncoder, sort_keys=True,
                                 ensure_ascii=False, separators=(',', ':')).encode()
            return (len(rows), hashlib.sha256(encoded).hexdigest())

        try:
            MigrationExecutor(connection).migrate([old_target])
            historical = MigrationLoader(connection).project_state(old_target).apps
            Block = historical.get_model('shared_content', 'SharedBlock')
            Revision = historical.get_model('shared_content', 'SharedRevision')
            Draft = historical.get_model('shared_content', 'SharedDraft')
            Identity = historical.get_model('shared_content', 'SharedIdentityReservation')
            Pin = historical.get_model('shared_content', 'SharedBasePin')
            Folder = historical.get_model('media_library', 'MediaFolder')
            Asset = historical.get_model('media_library', 'Asset')
            Usage = historical.get_model('media_library', 'AssetUsage')
            block, _ = Block.objects.get_or_create(kind='header', defaults={'id': uuid4()})
            Identity.objects.get_or_create(id=block.pk, defaults={'kind': 'sharedblock'})
            nonce = 'OLD-DATA-' + uuid4().hex + '-кириллица-🚀'
            html = '<header><p>' + nonce + '</p></header>'
            payload_hash = hashlib.sha256(html.encode()).hexdigest()
            revision_id, draft_id = uuid4(), uuid4()
            Revision.objects.create(id=revision_id, block=block, sequence=1,
                schema_version='header-v1', html=html, payload_hash=payload_hash, author_id=1)
            Draft.objects.create(id=draft_id, block=block, revision=3, base_revision_id=revision_id,
                html=html + 'DRAFT', payload_hash=hashlib.sha256((html + 'DRAFT').encode()).hexdigest(), author_id=1)
            for identity, kind in ((revision_id, 'sharedrevision'), (draft_id, 'shareddraft')):
                Identity.objects.create(id=identity, kind=kind)
            Block.objects.filter(pk=block.pk).update(current_revision_id=revision_id, generation=3)
            pin = Pin.objects.create(id=uuid4(), revision_id=revision_id, holder_kind='draft', holder_id=draft_id)
            Identity.objects.create(id=pin.pk, kind='sharedbasepin')
            # Metadata-only Asset fixture: no claim of image-byte validation.
            folder = Folder.objects.create(id=uuid4(), path='shared-migration-fixture')
            asset = Asset.objects.create(id=uuid4(), folder=folder, status='ready', provenance='unit-migration-fixture')
            Usage.objects.create(id=uuid4(), asset=asset, kind='shared_block',
                                 consumer_id=revision_id, slot='shared:header:brand')
            for model in (Block, Revision, Draft, Identity, Pin, Folder, Asset, Usage):
                label = (model._meta.app_label, model._meta.model_name)
                fields = [field.attname for field in model._meta.concrete_fields]
                projections[label] = fields
                before[label] = manifest(model, fields)
        finally:
            # Exactly one forward restoration attempt, even if fixture setup
            # fails. A failed restore stops this run; never repeat it unchanged.
            try:
                MigrationExecutor(connection).migrate(latest)
            except Exception:
                print(json.dumps({'scope': 'SHB_ADDITIVE_MIGRATION', 'stage': 'restore_latest',
                                  'status': 'STOP_REQUIRED'}), flush=True)
                raise RuntimeError('SHARED_UNIT_SCHEMA_RESTORE_FAILED_STOP_REQUIRED') from None
        updated = MigrationLoader(connection).project_state(latest).apps
        self.assertTrue(bool(before), 'LEGACY_MIGRATION_FIXTURE_NOT_RECORDED')
        for label, fields in projections.items():
            self.assertEqual(manifest(updated.get_model(*label), fields), before[label],
                             'ADDITIVE_MIGRATION_CHANGED_LEGACY_ROWS')
        for name, identity in (('SharedRevision', revision_id), ('SharedDraft', draft_id)):
            row = updated.get_model('shared_content', name).objects.get(pk=identity)
            self.assertEqual((row.storage_kind, row.file_key, row.byte_size, row.file_sha256),
                             ('inline', '', None, ''))
        # Historical projections above include every OLD identity field (id/kind).
        # The new binding is checked separately, not dropped from an all-field digest.
        UpdatedIdentity = updated.get_model('shared_content', 'SharedIdentityReservation')
        expected_bindings = {row.pk: row.pk for row in
            updated.get_model('shared_content', 'SharedBlock').objects.all()}
        expected_bindings.update({revision_id: block.pk, draft_id: block.pk, pin.pk: block.pk})
        for identity, expected_block in expected_bindings.items():
            self.assertEqual(UpdatedIdentity.objects.get(pk=identity).block_id, expected_block,
                             'ADDITIVE_IDENTITY_BLOCK_BINDING_INVALID')
        self.assertEqual(hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
                         original_migration_sha, 'APPLIED_0001_SOURCE_CHANGED')
