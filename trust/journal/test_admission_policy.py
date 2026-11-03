"""RP15-001/003 schema evidence, not a working admission/activation PASS."""
import copy
import uuid

from django.db import DatabaseError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from .models import AdmissionPolicy, Head
from .services import physical_facts


class AdmissionPolicySchemaTests(TransactionTestCase):
    def row(self, **changes):
        values = dict(id=uuid.uuid4(), epoch=1, previous_digest=None,
            legacy_seal='a' * 64, policy={'scope': 'LOCAL_TRUST_BOUNDED_WRITER'},
            policy_digest='b' * 64, action_id=uuid.uuid4(), intent_digest='c' * 64,
            state_digest_version=2, prior_state={'generation': '9'},
            receipt={'generation': '10'}, logical_bytes=4096)
        values.update(changes)
        return values

    def reject(self, action):
        with self.assertRaises(DatabaseError), transaction.atomic():
            action()

    def test_rp003_queryset_and_raw_sql_cannot_update_or_delete(self):
        row = AdmissionPolicy.objects.create(**self.row())
        before = AdmissionPolicy.objects.values().get(pk=row.pk)
        self.reject(lambda: AdmissionPolicy.objects.filter(pk=row.pk).update(logical_bytes=4097))
        self.reject(lambda: AdmissionPolicy.objects.filter(pk=row.pk).delete())
        with connection.cursor() as cursor:
            self.reject(lambda: cursor.execute(
                'UPDATE journal_admissionpolicy SET logical_bytes=logical_bytes WHERE id=%s', [row.pk]))
            self.reject(lambda: cursor.execute('DELETE FROM journal_admissionpolicy WHERE id=%s', [row.pk]))
        self.assertEqual(AdmissionPolicy.objects.values().get(pk=row.pk), before)

    def test_rp003_identity_epoch_digest_and_action_are_unique(self):
        row = self.row()
        AdmissionPolicy.objects.create(**row)
        for field in ('id', 'epoch', 'policy_digest', 'action_id'):
            with self.subTest(field=field):
                other = self.row(epoch=2, previous_digest='b' * 64, legacy_seal=None,
                    policy_digest='d' * 64)
                other[field] = row[field]
                if field == 'epoch':
                    other.update(previous_digest=None, legacy_seal='a' * 64)
                self.reject(lambda: AdmissionPolicy.objects.create(**other))
        self.assertEqual(AdmissionPolicy.objects.count(), 1)

    def test_rp003_shape_rejects_bad_epoch_version_size_and_predecessor(self):
        invalid = [dict(epoch=0), dict(state_digest_version=1), dict(logical_bytes=0),
            dict(logical_bytes=32769), dict(legacy_seal=None), dict(previous_digest='d' * 64),
            dict(epoch=2), dict(epoch=2, previous_digest='d' * 64),
            dict(epoch=2, previous_digest=None, legacy_seal=None),
            dict(policy_digest='x' * 64), dict(intent_digest='short'), dict(legacy_seal='Z' * 64)]
        for change in invalid:
            with self.subTest(change=change):
                self.reject(lambda: AdmissionPolicy.objects.create(**self.row(**change)))
        self.assertEqual(AdmissionPolicy.objects.count(), 0)

    def test_rp003_first_and_successor_shapes_accept_exact_charge_boundary(self):
        first = AdmissionPolicy.objects.create(**self.row(logical_bytes=32768))
        second = AdmissionPolicy.objects.create(**self.row(epoch=2, previous_digest=first.policy_digest,
            legacy_seal=None, policy_digest='d' * 64))
        self.assertEqual(second.previous_digest, first.policy_digest)
        self.assertEqual(AdmissionPolicy.objects.count(), 2)
        self.assertFalse(Head.objects.exists())
        self.assertIn('journal_admissionpolicy', physical_facts()['relations'])


class AdmissionPolicyMigrationTests(TransactionTestCase):
    """Only the guarded UNIT runner may execute this reversible schema fixture."""
    def test_rp001_additive_migration_preserves_legacy_state_and_has_no_policy(self):
        self.assertEqual(connection.settings_dict['NAME'], 'test_estakada_trust')
        self.assertEqual(connection.vendor, 'postgresql')
        old_target = [('journal', '0002_local_test_recovery')]
        new_target = [('journal', '0003_admission_policy')]
        executor = MigrationExecutor(connection)
        executor.migrate(old_target)
        try:
            apps = executor.loader.project_state(old_target).apps
            old_models = [apps.get_model('journal', name) for name in (
                'Head', 'Credential', 'Operation', 'RoutePolicy', 'RequestTombstone', 'RecoveryReceipt')]
            head, credential, operation, route, tombstone, recovery = old_models
            incarnation, plan_id, op_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            head.objects.create(incarnation=incarnation, generation=9, writer_epoch=2, digest='a' * 64,
                plan_id=plan_id, permitted_operations=[str(op_id)], permitted_recovery_actions=[])
            credential.objects.create(id='old-writer', principal='machine', role='writer',
                verifier='b' * 64, writer_epoch=2, active=True)
            operation.objects.create(id=op_id, credential_id='old-writer', principal='machine',
                writer_epoch=2, kind='route_restriction', object_id=uuid.uuid4(),
                prepare_fingerprint='c' * 64, payload={'policies': []}, phases={},
                logical_bytes=4096, reserve_bytes=8192)
            route.objects.create(key='d' * 64, target='/Exact?Case=A', object_id=uuid.uuid4(),
                operation_id=op_id, generation=9, policy='PENDING_DENY')
            tombstone.objects.create(request_id=uuid.uuid4(), operation_id=op_id, generation=9)
            recovery.objects.create(id=uuid.uuid4(), credential_id='recovery', principal='operator',
                action='fence', fingerprint='e' * 64, receipt={'old': True}, logical_bytes=1024)
            before = {model._meta.model_name: copy.deepcopy(list(model.objects.order_by(model._meta.pk.name).values()))
                for model in old_models}
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
            self.assertEqual(AdmissionPolicy.objects.count(), 0)
            for model in old_models:
                self.assertEqual(list(model.objects.order_by(model._meta.pk.name).values()),
                    before[model._meta.model_name])
            with self.assertRaises(DatabaseError), transaction.atomic():
                head.objects.update(plan_id=uuid.uuid4())
        finally:
            MigrationExecutor(connection).migrate(new_target)
