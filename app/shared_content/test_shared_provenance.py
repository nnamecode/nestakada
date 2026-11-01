"""Real PG provenance/replay tests. Fixture writes are not product Apply."""
import hashlib
import importlib
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, IntegrityError, models, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase, override_settings

from . import commands as C, services as S
from . import test_shared_http as Q
from .faults import SharedFault
from .models import (SharedBlock, SharedRevision, SharedReceipt, SharedIdentityReservation,
                     SharedDraft, SharedRestoreStage, SharedBasePin, SharedCleanupJob)


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedProvenanceTests(TransactionTestCase):
    setUp = Q.SharedHttpTests.setUp
    login = Q.SharedHttpTests.login
    raw = Q.SharedHttpTests.raw
    fixture = Q.SharedHttpTests.fixture
    state = Q.SharedHttpTests.state
    path = Q.SharedHttpTests.path
    post_shared = Q.SharedHttpTests.post_shared
    assert_private = Q.SharedHttpTests.assert_private

    def revision(self, kind='header', sequence=1, source=None):
        html = self.fixture(kind, 'PROVENANCE-' + str(sequence))
        return SharedRevision.objects.create(block=SharedBlock.objects.get(kind=kind), sequence=sequence,
            schema_version=kind + '-v1', html=html, payload_hash=hashlib.sha256(html.encode()).hexdigest(),
            author_id=self.owner.pk, source_revision_id=source.pk if source else None)

    def remove(self, row):
        # Deliberate trusted fixture command; no automatic cleanup/product API.
        with transaction.atomic():
            from content.models import lock_content
            lock_content('default')
            models.QuerySet(model=type(row)).filter(pk=row.pk).delete()

    def operation_fixture(self, source_mode='current'):
        source = self.revision(sequence=1)
        result = self.revision(sequence=2, source=source)
        value = {'protocol': 'shared-editor-v1', 'generation': 1, 'baseRevisionId': str(source.pk),
            'sourceMode': source_mode, 'draftBasis': None, 'stageId': None,
            'html': result.html, 'operationId': str(uuid4()), 'checkReceipt': 'historical-opaque-proof'}
        query = ''
        if source_mode == 'owner-draft':
            draft = SharedDraft.objects.create(block=source.block, base_revision=source,
                html=source.html, payload_hash=source.payload_hash, author_id=self.owner.pk)
            value['draftBasis'] = {'id': str(draft.pk), 'revision': 1}
            query = '?source=owner-draft&draftId=' + str(draft.pk) + '&draftRevision=1'
            self.remove(draft)  # A consumed draft is gone before replay.
        receipt = SharedReceipt.objects.create(id=value['operationId'], action='apply', actor_id=self.owner.pk,
            actor_generation=1, block=source.block, source_revision_id=source.pk, base_revision_id=source.pk,
            fingerprint=S.digest(value), result_code='applied', result_id=result.pk)
        return source, result, value, receipt, query

    def replay(self, value, query='', client=None, raw=None):
        client = client or self.owner_client
        csrf = client.cookies[settings.CSRF_COOKIE_NAME].value if settings.CSRF_COOKIE_NAME in client.cookies else ''
        with patch('shared_content.views.read_json_bytes', side_effect=lambda request, profile: request.body):
            return client.post(self.path('header', 'apply') + query,
                data=self.raw(value) if raw is None else raw, content_type='application/json', HTTP_X_CSRFTOKEN=csrf)

    def no_payload_dependencies(self):
        from contextlib import ExitStack
        stack = ExitStack()
        for target in ('shared_content.views.normalize_input', 'shared_content.views.inspect',
                       'shared_content.storage.SharedStorage.read', 'shared_content.quota.reserve_locked'):
            stack.enter_context(patch(target, side_effect=AssertionError('REPLAY_TOUCHED_PAYLOAD_OR_RESERVATION')))
        return stack

    def test_old_source_body_deleted_receipt_and_new_provenance_survive(self):
        source, result, value, receipt, query = self.operation_fixture()
        self.remove(source)
        self.assertFalse(SharedRevision.objects.filter(pk=source.pk).exists())
        self.assertEqual(SharedRevision.objects.get(pk=result.pk).source_revision_id, source.pk)
        self.assertTrue(SharedIdentityReservation.objects.filter(pk=source.pk, block=source.block, kind='sharedrevision').exists())
        before = self.state()
        with self.no_payload_dependencies():
            response = self.replay(value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['resultId'], str(result.pk))
        self.assertTrue(response.json()['replay'])
        self.assertFalse(response.json()['gone'])
        self.assertEqual(self.state(), before)

    def test_gone_result_and_consumed_source_replay_without_resurrection(self):
        source, result, value, receipt, query = self.operation_fixture('owner-draft')
        self.remove(result); self.remove(source)
        before = self.state()
        with self.no_payload_dependencies():
            response = self.replay(value, query)
            get_response = self.owner_client.get(self.path('header', 'result') + str(receipt.pk) + '/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get_response.status_code, 200)
        for body in (response.json(), get_response.json()):
            self.assertTrue(body['gone'])
            self.assertTrue(body['replay'])
            self.assertEqual(body['resultId'], str(result.pk))
            self.assertEqual(body['resultCode'], 'applied')
        self.assertEqual(self.state(), before)

    def test_closed_selector_fingerprint_and_semantic_json_replay(self):
        source, result, value, receipt, query = self.operation_fixture()
        before = self.state()
        # Canonical semantic fingerprint intentionally accepts JSON whitespace/key order.
        wire = json.dumps(dict(reversed(list(value.items()))), ensure_ascii=False, indent=2).encode()
        with self.no_payload_dependencies():
            self.assertEqual(self.replay(value, raw=wire).status_code, 200)
            self.assertEqual(self.replay({**value, 'html': value['html'] + 'CHANGED'}).status_code, 409)
            self.assertEqual(self.replay({**value, 'unknown': True}).status_code, 400)
            duplicate = self.raw(value)[:-1] + b',"protocol":"shared-editor-v1"}'
            self.assertEqual(self.replay(value, raw=duplicate).status_code, 400)
            self.assertEqual(self.replay(value, '?source=restore-stage&stageId=' + str(uuid4())).status_code, 400)
        self.assertEqual(self.state(), before)

    def test_fresh_authentication_remains_required_for_replay(self):
        source, result, value, receipt, query = self.operation_fixture()
        with self.no_payload_dependencies():
            self.assertEqual(self.replay(value, client=self.employee_client).status_code, 403)
            from django.test import Client
            self.assertEqual(self.replay(value, client=Client(enforce_csrf_checks=True)).status_code, 401)
            from accounts.models import UserProfile
            UserProfile.objects.filter(user=self.owner).update(generation=2)
            self.assertEqual(self.replay(value).status_code, 401)

    def test_typed_source_base_result_constraints_and_null_kind(self):
        source = self.revision(); foreign = self.revision('footer')
        draft = SharedDraft.objects.create(block=source.block, base_revision=source,
            html=source.html, payload_hash=source.payload_hash, author_id=self.owner.pk)
        receipt = SharedReceipt.objects.create(action='apply', actor_id=self.owner.pk, actor_generation=1,
            block=source.block, source_revision_id=source.pk, base_revision_id=source.pk,
            fingerprint='0' * 64, result_code='applied', result_id=source.pk)
        cases = [('source_revision_id', foreign.pk), ('base_revision_id', foreign.pk),
                 ('source_revision_id', draft.pk), ('result_id', draft.pk), ('result_id', uuid4())]
        for column, identity in cases:
            with self.subTest(column=column, target=str(identity)), self.assertRaises(IntegrityError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('UPDATE app.shared_content_sharedreceipt SET ' + column + '=%s WHERE id=%s',
                                   [identity, receipt.pk])
                    cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE app.shared_content_sharedreceipt SET result_id=%s,result_identity_kind=NULL WHERE id=%s',
                           [foreign.pk, receipt.pk])
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
        unbound = uuid4()
        SharedIdentityReservation.objects.create(id=unbound, kind='sharedrevision')
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE app.shared_content_sharedreceipt SET source_revision_id=%s WHERE id=%s', [unbound, receipt.pk])
        with self.assertRaises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('UPDATE app.shared_content_sharedrevision SET source_revision_id=%s WHERE id=%s', [draft.pk, source.pk])

    def test_current_draft_pin_and_held_stage_protection_terminal_fixture_release(self):
        source = self.revision(); block = source.block
        with connection.cursor() as cursor:
            cursor.execute('UPDATE app.shared_content_sharedblock SET current_revision_id=%s WHERE id=%s', [source.pk, block.pk])
        with self.assertRaises(IntegrityError):
            self.remove(source)
        with connection.cursor() as cursor:
            cursor.execute('UPDATE app.shared_content_sharedblock SET current_revision_id=NULL WHERE id=%s', [block.pk])
        draft = SharedDraft.objects.create(block=block, base_revision=source, html=source.html,
            payload_hash=source.payload_hash, author_id=self.owner.pk)
        with self.assertRaises(IntegrityError):
            self.remove(source)
        self.remove(draft)
        pin = SharedBasePin.objects.create(revision=source, holder_kind='fixture', holder_id=uuid4())
        with self.assertRaises(IntegrityError):
            self.remove(source)
        self.remove(pin)
        stage = SharedRestoreStage.objects.create(block=block, actor_id=self.owner.pk, actor_generation=1,
            source_revision=source, base_revision=source, schema_version='header-v1', policy_version='shared-policy-v1')
        receipt = SharedReceipt.objects.create(action='restore_prepare', actor_id=self.owner.pk, actor_generation=1,
            block=block, source_revision_id=source.pk, base_revision_id=source.pk,
            fingerprint='f' * 64, result_code='applied', result_id=stage.pk)
        with self.assertRaises(IntegrityError):
            self.remove(source)
        with connection.cursor() as cursor:
            cursor.execute("UPDATE app.shared_content_sharedrestorestage SET status='released' WHERE id=%s", [stage.pk])
        with self.assertRaises(IntegrityError):
            self.remove(source)  # Terminal metadata must still be explicitly selected for cleanup.
        self.remove(stage); self.remove(source)
        self.assertTrue(C.result_for(SharedReceipt.objects.get(pk=receipt.pk), replay=True)['gone'])
        self.assertTrue(SharedIdentityReservation.objects.filter(pk=stage.pk, block=block).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.revision_with_id(source.pk, block)

    def revision_with_id(self, identity, block):
        return SharedRevision.objects.create(id=identity, block=block, sequence=99, schema_version='header-v1',
            html='reserved', payload_hash=hashlib.sha256(b'reserved').hexdigest(), author_id=self.owner.pk)


class SharedProvenanceMigrationTests(TransactionTestCase):
    previous = [('shared_content', '0002_private_html_descriptors')]
    provenance = [('shared_content', '0003_permanent_provenance')]

    def setUp(self):
        self.assertEqual(os.environ.get('ESTAKADA_LOCAL_ENV'), 'test')
        self.assertEqual(os.environ.get('DJANGO_SETTINGS_MODULE'), 'estakada.settings.local_http')
        self.assertFalse(connection.in_atomic_block)
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user')
            self.assertEqual(cursor.fetchone(), ('estakada_foundation_unit', 'app_migrator'))
        loader = MigrationLoader(connection)
        self.latest = loader.graph.leaf_nodes('shared_content')
        self.assertEqual(self.latest, [('shared_content', '0005_cleanup_jobs')])
        for model in (SharedRevision, SharedDraft, SharedRestoreStage, SharedReceipt, SharedBasePin, SharedCleanupJob):
            self.assertEqual(model.objects.count(), 0, 'PROVENANCE_MIGRATION_REQUIRES_EMPTY_UNIT_HISTORY')
        self.assertFalse(SharedBlock.objects.filter(current_revision__isnull=False).exists())

    def old_models(self):
        return MigrationLoader(connection).project_state(self.previous).apps

    def old_block(self, historical, kind):
        Block = historical.get_model('shared_content', 'SharedBlock')
        Identity = historical.get_model('shared_content', 'SharedIdentityReservation')
        row, _ = Block.objects.get_or_create(kind=kind)
        Identity.objects.get_or_create(id=row.pk, defaults={'kind': 'sharedblock'})
        return row

    def old_revision(self, historical, block, sequence=1, source=None):
        Revision = historical.get_model('shared_content', 'SharedRevision')
        Identity = historical.get_model('shared_content', 'SharedIdentityReservation')
        html = '<header>LEGACY-PROVENANCE-🚀-' + str(sequence) + '</header>'
        row = Revision.objects.create(block=block, sequence=sequence, schema_version='header-v1',
            html=html, payload_hash=hashlib.sha256(html.encode()).hexdigest(), author_id=1,
            source_revision_id=source.pk if source else None)
        Identity.objects.create(id=row.pk, kind='sharedrevision')
        return row

    def restore_latest(self):
        try:
            MigrationExecutor(connection).migrate(self.latest)
        except Exception:
            print('SHARED_PROVENANCE_UNIT_RESTORE_FAILED_STOP_REQUIRED', flush=True)
            raise RuntimeError('SHARED_PROVENANCE_UNIT_RESTORE_FAILED_STOP_REQUIRED') from None

    def test_actual_upgrade_preserves_old_fields_and_backfills_gone_result(self):
        preserved = {}
        old_hashes = {name: hashlib.sha256(Path(importlib.import_module(
            'shared_content.migrations.' + name).__file__).read_bytes()).hexdigest()
            for name in ('0001_initial', '0002_private_html_descriptors',
                         '0003_permanent_provenance', '0004_reservation_metadata')}
        try:
            MigrationExecutor(connection).migrate(self.previous)
            historical = self.old_models()
            block = self.old_block(historical, 'header')
            source = self.old_revision(historical, block)
            result = self.old_revision(historical, block, 2, source)
            Identity = historical.get_model('shared_content', 'SharedIdentityReservation')
            Receipt = historical.get_model('shared_content', 'SharedReceipt')
            gone_id, unbound_id = uuid4(), uuid4()
            Identity.objects.create(id=gone_id, kind='sharedrevision')
            Identity.objects.create(id=unbound_id, kind='shareddraft')
            receipt = Receipt.objects.create(action='apply', actor_id=1, actor_generation=1, block=block,
                source_revision_id=source.pk, base_revision_id=source.pk, fingerprint='a'*64,
                result_code='applied', result_id=gone_id)
            Identity.objects.create(id=receipt.pk, kind='sharedreceipt')
            for model in historical.get_app_config('shared_content').get_models():
                fields = [field.attname for field in model._meta.concrete_fields]
                preserved[model._meta.model_name] = (fields,
                    list(model.objects.order_by('pk').values(*fields)))
        finally:
            self.restore_latest()  # One forward restoration attempt.
        for name, (fields, rows) in preserved.items():
            model = apps.get_model('shared_content', name)
            self.assertEqual(list(model.objects.order_by('pk').values(*fields)), rows)
        for identity in (source.pk, result.pk, gone_id, receipt.pk, block.pk):
            self.assertEqual(SharedIdentityReservation.objects.get(pk=identity).block_id, block.pk)
        self.assertIsNone(SharedIdentityReservation.objects.get(pk=unbound_id).block_id)
        self.assertEqual(SharedReceipt.objects.get(pk=receipt.pk).result_identity_kind, 'sharedrevision')
        for name, expected in old_hashes.items():
            self.assertEqual(hashlib.sha256(Path(importlib.import_module(
                'shared_content.migrations.' + name).__file__).read_bytes()).hexdigest(), expected)

    def test_conflicting_result_block_fails_atomic_upgrade_then_explicit_fixture_repair(self):
        receipt = None
        try:
            MigrationExecutor(connection).migrate(self.previous)
            historical = self.old_models()
            header, footer = self.old_block(historical, 'header'), self.old_block(historical, 'footer')
            source = self.old_revision(historical, header)
            Identity = historical.get_model('shared_content', 'SharedIdentityReservation')
            Receipt = historical.get_model('shared_content', 'SharedReceipt')
            receipt = Receipt.objects.create(action='apply', actor_id=1, actor_generation=1, block=footer,
                fingerprint='c'*64, result_code='applied', result_id=source.pk)
            Identity.objects.create(id=receipt.pk, kind='sharedreceipt')
            before = list(Identity.objects.order_by('id').values('id', 'kind'))
            with self.assertRaisesRegex(RuntimeError, 'SHARED_PROVENANCE_CONFLICT'):
                MigrationExecutor(connection).migrate(self.latest)
            self.assertNotIn(self.provenance[0], MigrationLoader(connection).applied_migrations)
            self.assertNotIn(('shared_content', '0004_reservation_metadata'), MigrationLoader(connection).applied_migrations)
            self.assertNotIn(self.latest[0], MigrationLoader(connection).applied_migrations)
            with connection.cursor() as cursor:
                columns = connection.introspection.get_table_description(cursor, Identity._meta.db_table)
            self.assertNotIn('block_id', {column.name for column in columns})
            self.assertEqual(list(Identity.objects.order_by('id').values('id', 'kind')), before)
        finally:
            if receipt is not None:
                # New condition: repair this deliberately contradictory unit fixture only.
                Receipt.objects.filter(pk=receipt.pk).update(block_id=header.pk)
            self.restore_latest()

    def test_reverse_preflight_refuses_gone_provenance_before_any_schema_change(self):
        block, _ = SharedBlock.objects.get_or_create(kind='header')
        html = 'SOURCE'
        source = SharedRevision.objects.create(block=block, sequence=1, schema_version='header-v1',
            html=html, payload_hash=hashlib.sha256(html.encode()).hexdigest(), author_id=1)
        result = SharedRevision.objects.create(block=block, sequence=2, schema_version='header-v1',
            html=html, payload_hash=source.payload_hash, author_id=1, source_revision_id=source.pk)
        models.QuerySet(model=SharedRevision).filter(pk=source.pk).delete()
        try:
            # Reverse 0005/0004 separately. Only 0003's own preflight/schema
            # change is atomic; earlier reversals are not covered by it.
            MigrationExecutor(connection).migrate(self.provenance)
            historical = MigrationLoader(connection).project_state(self.provenance).apps
            Revision = historical.get_model('shared_content', 'SharedRevision')
            Identity = historical.get_model('shared_content', 'SharedIdentityReservation')

            def snapshot():
                state = {}
                with connection.cursor() as cursor:
                    for model in historical.get_app_config('shared_content').get_models():
                        fields = [field.attname for field in model._meta.concrete_fields]
                        table = model._meta.db_table
                        state[table] = (list(model.objects.order_by('pk').values(*fields)),
                            connection.introspection.get_table_description(cursor, table),
                            connection.introspection.get_constraints(cursor, table))
                return state

            before = snapshot()
            identities = list(Identity.objects.order_by('id').values('id', 'kind', 'block_id'))
            with self.assertRaisesRegex(RuntimeError, 'SHARED_PROVENANCE_REVERSE_REQUIRES_LIVE_REVISION'):
                MigrationExecutor(connection).migrate(self.previous)
            applied = MigrationLoader(connection).applied_migrations
            self.assertIn(self.provenance[0], applied)
            self.assertNotIn(('shared_content', '0004_reservation_metadata'), applied)
            self.assertNotIn(self.latest[0], applied)
            self.assertEqual(snapshot(), before)
            self.assertEqual(Revision.objects.get(pk=result.pk).source_revision_id, source.pk)
            self.assertEqual(list(Identity.objects.order_by('id').values('id', 'kind', 'block_id')), identities)
        finally:
            self.restore_latest()
        self.assertIn(self.latest[0], MigrationLoader(connection).applied_migrations)
        self.assertEqual(SharedRevision.objects.get(pk=result.pk).source_revision_id, source.pk)
        self.assertEqual(list(SharedIdentityReservation.objects.order_by('id').values('id', 'kind', 'block_id')), identities)

    def test_gone_result_alone_does_not_block_reverse_and_forward(self):
        block, _ = SharedBlock.objects.get_or_create(kind='header')
        gone_id = uuid4()
        SharedIdentityReservation.objects.create(id=gone_id, kind='sharedrevision', block=block)
        receipt = SharedReceipt.objects.create(action='apply', actor_id=1, actor_generation=1, block=block,
            fingerprint='d'*64, result_code='applied', result_id=gone_id)
        try:
            MigrationExecutor(connection).migrate(self.previous)
            historical = self.old_models()
            old = historical.get_model('shared_content', 'SharedReceipt').objects.get(pk=receipt.pk)
            self.assertEqual(old.result_id, gone_id)
        finally:
            self.restore_latest()
        self.assertTrue(C.result_for(SharedReceipt.objects.get(pk=receipt.pk), replay=True)['gone'])
