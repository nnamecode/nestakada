"""RP15-007 digest foundation; runtime recovery integration is separate."""
import copy
import uuid
from unittest.mock import patch

from django.db import transaction

from . import state_v2 as V
from .models import AdmissionPolicy, Credential, Head, Operation, RecoveryReceipt
from .tests import JournalFixture


class StateV2Tests(JournalFixture):
    def calculate(self):
        with transaction.atomic():
            return V.state_digest(Head.objects.select_for_update().get(pk=1))

    def test_rp007_requires_transaction_and_current_head(self):
        self.fault('RECONCILIATION_LOCK_REQUIRED',
                   lambda: V.state_digest(Head.objects.get(pk=1)))
        stale = Head.objects.get(pk=1)
        self.mutate(self.prepare_body())
        with transaction.atomic():
            self.fault('RECONCILIATION_HEAD_CHANGED', lambda: V.state_digest(stale))

    def test_rp007_repeatable_and_sensitive_to_full_payload_and_verifier(self):
        body = self.prepare_body('/Точный?Case=X')
        self.mutate(body)
        before = self.calculate()
        self.assertEqual(before, self.calculate())
        # Credential metadata can change legitimately during recovery.
        Credential.objects.filter(pk='writer').update(verifier='f' * 64)
        after = self.calculate()
        self.assertNotEqual(before, after)
        self.assertNotIn('f' * 64, after)
        # Test serialization coverage without violating immutable DB guards.
        op = Operation.objects.get(pk=body['operationId'])
        row = V.persistent_values(op)
        self.assertEqual(set(row), {f.attname for f in op._meta.concrete_fields})
        for key in row:
            changed = copy.deepcopy(row)
            changed[key] = {'different': key}
            one = V.hashlib.sha256(V.DOMAIN)
            two = V.hashlib.sha256(V.DOMAIN)
            V._frame(one, row)
            V._frame(two, changed)
            self.assertNotEqual(one.digest(), two.digest(), key)

    def test_rp007_streams_more_than_legacy_sixteen_operations(self):
        for index in range(17):
            self.mutate(self.prepare_body('/v2/' + str(index)))
        self.assertEqual(len(self.calculate()), 64)
        # A regression to list(queryset) or queryset caching must fail.
        from django.db.models.query import QuerySet
        original = QuerySet.iterator
        sizes = []

        def observed(query, *args, **kwargs):
            sizes.append(kwargs.get('chunk_size'))
            return original(query, *args, **kwargs)

        with patch.object(QuerySet, 'iterator', observed):
            self.calculate()
        self.assertEqual(sizes, [1] * len(V.TABLES))

    def test_rp007_count_and_row_size_fail_closed(self):
        self.mutate(self.prepare_body())
        with patch.object(V, 'TABLES', ((Operation, 0),)):
            self.fault('RECONCILIATION_UNAVAILABLE', self.calculate)
        with patch.object(V, 'MAX_ROW_BYTES', 16):
            self.fault('RECONCILIATION_UNAVAILABLE', self.calculate)

    def test_rp007_every_persistent_table_and_field_is_framed(self):
        framed = []
        original = V._frame

        def capture(hasher, value):
            framed.append(value)
            original(hasher, value)

        with patch.object(V, '_frame', capture):
            self.calculate()
        self.assertEqual(framed[0]['stateDigestVersion'], 2)
        self.assertEqual(set(framed[0]['head']),
                         {f.attname for f in Head._meta.concrete_fields})
        tables = [value for value in framed if 'table' in value]
        self.assertEqual([value['table'] for value in tables],
                         [model._meta.db_table for model, _ in V.TABLES])
        for value, (model, _) in zip(tables, V.TABLES):
            self.assertEqual(value['fields'], [f.attname for f in model._meta.concrete_fields])

    def test_rp007_full_digest_sensitive_to_every_persistent_field(self):
        body = self.prepare_body('/Mixed?Case=Ё')
        self.mutate(body)
        self.mutate(self.report_body(body), 'report')
        tomb = self.prepare_body()
        tomb.update(kind='request_tombstone', policies=[], requestIds=[str(uuid.uuid4())])
        self.mutate(tomb)
        RecoveryReceipt.objects.create(id=uuid.uuid4(), credential_id='recovery',
            principal='recovery-machine', action='fence', fingerprint='e' * 64,
            receipt={'scope': 'digest-fixture'}, logical_bytes=1024)
        AdmissionPolicy.objects.create(id=uuid.uuid4(), epoch=1, legacy_seal='a' * 64,
            policy={'scope': 'LOCAL_TRUST_BOUNDED_WRITER'}, policy_digest='b' * 64,
            action_id=uuid.uuid4(), intent_digest='c' * 64, prior_state={'generation': '3'},
            receipt={'generation': '4'}, logical_bytes=4096)
        baseline = self.calculate()
        from django.db.models.query import QuerySet
        original = QuerySet.iterator
        # Immutable DB rows cannot be edited for this negative test. Inject
        # one changed field into the actual server-cursor stream instead.
        for model, _ in V.TABLES:
            self.assertTrue(model.objects.exists(), model.__name__)
            for field in model._meta.concrete_fields:
                touched = []

                def altered(query, *args, **kwargs):
                    for row in original(query, *args, **kwargs):
                        if query.model is model:
                            row = copy.copy(row)
                            setattr(row, field.attname, {'changed': field.attname})
                            touched.append(True)
                        yield row

                with self.subTest(model=model.__name__, field=field.attname):
                    with patch.object(QuerySet, 'iterator', altered):
                        self.assertNotEqual(self.calculate(), baseline)
                    self.assertTrue(touched)
        for field in Head._meta.concrete_fields:
            head = copy.copy(Head.objects.get(pk=1))
            setattr(head, field.attname, {'changed': field.attname})
            with self.subTest(model='Head', field=field.attname):
                with patch.object(Head.objects, 'select_for_update') as locked:
                    locked.return_value.get.return_value = head
                    self.assertNotEqual(self.calculate(), baseline)
        self.assertEqual(self.calculate(), baseline)
