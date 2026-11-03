"""P29-A: TRUST evidence only; APP/cohort/EDGE admission is not proved here."""
import copy
import hashlib
import uuid
from unittest import TestCase
from unittest.mock import patch

from . import consumer as C
from .protocol import Fault, validate


def publication(policy='LIVE_NO_SET'):
    object_id = str(uuid.uuid4())
    return {'operationId': str(uuid.uuid4()), 'incarnation': str(uuid.uuid4()),
            'expectedGeneration': '0', 'writerEpoch': '1',
            'kind': 'route_publication', 'objectId': object_id, 'basis': 'a' * 64,
            'policies': [{'target': '/Exact?Case=X', 'objectId': object_id,
                          'policy': policy, 'redirectTarget': None}], 'requestIds': []}


class PublicationWireTests(TestCase):
    def test_a001_closed_prepare(self):
        for policy in ('HIDDEN', 'LIVE_NO_SET'):
            self.assertEqual(validate(publication(policy), 'prepare')['policies'][0]['policy'], policy)
        for mutation in ('empty', 'double', 'object', 'ids', 'redirect', 'deleted', 'basis', 'field'):
            body = publication()
            if mutation == 'empty': body['policies'] = []
            elif mutation == 'double':
                item = copy.deepcopy(body['policies'][0]); item['target'] = '/Other'
                body['policies'].append(item)
            elif mutation == 'object': body['policies'][0]['objectId'] = str(uuid.uuid4())
            elif mutation == 'ids': body['requestIds'] = [str(uuid.uuid4())]
            elif mutation == 'redirect': body['policies'][0]['redirectTarget'] = '/Other'
            elif mutation == 'deleted': body['policies'][0]['policy'] = 'DELETED'
            elif mutation == 'basis': body['basis'] = 'A' * 64
            else: body['action'] = 'publish_page'
            with self.subTest(mutation=mutation), self.assertRaises(Fault): validate(body, 'prepare')

    def test_a003_old_kind_cannot_prepare_live_no_set(self):
        body = publication(); body['kind'] = 'route_restriction'
        with self.assertRaises(Fault): validate(body, 'prepare')
        for policy in ('HIDDEN', 'DELETED', 'REDIRECT'):
            body['policies'][0].update(policy=policy, redirectTarget='/Other' if policy == 'REDIRECT' else None)
            validate(body, 'prepare')
        body.update(kind='request_tombstone', requestIds=[str(uuid.uuid4())])
        with self.assertRaises(Fault): validate(body, 'prepare')

    def test_a002_report_formats(self):
        prepared = publication()
        body = {key: prepared[key] for key in ('operationId', 'incarnation', 'expectedGeneration', 'writerEpoch')}
        body.update(outcome='committed', mainIncarnation=str(uuid.uuid4()), mainReceipt='b' * 64,
                    policies=prepared['policies'])
        validate(body, 'report')
        for key, value in (('mainIncarnation', 'invalid'), ('mainReceipt', 'invalid'), ('writerEpoch', '-1')):
            invalid = copy.deepcopy(body); invalid[key] = value
            with self.subTest(key=key), self.assertRaises(Fault): validate(invalid, 'report')

    def test_a005_consumer_policy_and_binding_shape(self):
        item = {'type': 'route', 'key': hashlib.sha256(b'/Exact').hexdigest(), 'target': '/Exact',
                'object_id': str(uuid.uuid4()), 'generation': '1', 'policy': 'LIVE_NO_SET', 'redirect_target': None}
        for policy in ('LIVE_NO_SET', 'HIDDEN', 'DELETED', 'PENDING_DENY', 'REDIRECT'):
            valid = {**item, 'policy': policy, 'redirect_target': '/Other' if policy == 'REDIRECT' else None}
            C._item(valid, 1)
        for key, value in (('policy', 'LIVE'), ('key', '0' * 64), ('object_id', 'invalid'),
                           ('generation', '2'), ('redirect_target', '/Other')):
            with self.subTest(key=key), self.assertRaises(C.SnapshotRejected): C._item({**item, key: value}, 1)


# Imported separately so stdlib wire tests can also run without Django or a DB.
try:
    from django.db import connection, DatabaseError
    from django.test import override_settings
    from . import services as S
    from .models import Head, Operation, RoutePolicy
    from .tests import JournalFixture
except ModuleNotFoundError as error:
    if error.name != 'django': raise
else:
    class PublicationDatabaseTests(JournalFixture):
        def body(self, policy='LIVE_NO_SET'):
            body = publication(policy)
            body.update(incarnation=self.identity, expectedGeneration=str(Head.objects.get().generation))
            return body

        def test_a001_a002_a003_prepare_report_and_replay(self):
            for policy in ('HIDDEN', 'LIVE_NO_SET'):
                body = self.body(policy); body['policies'][0]['target'] += policy
                prepared = self.mutate(body)
                self.assertEqual(RoutePolicy.objects.get(operation_id=body['operationId']).policy, 'PENDING_DENY')
                changed = copy.deepcopy(body); changed['basis'] = 'c' * 64
                self.fault('PHASE_CONFLICT', lambda: self.mutate(changed))
                report = self.report_body(body)
                wrong = copy.deepcopy(report); wrong['policies'][0]['policy'] = 'HIDDEN' if policy == 'LIVE_NO_SET' else 'LIVE_NO_SET'
                self.fault('POLICY_SET_MISMATCH', lambda: self.mutate(wrong, 'report'))
                final = self.mutate(report, 'report'); generation = Head.objects.get().generation
                self.assertNotEqual(prepared['phaseReceipt']['fingerprint'], final['phaseReceipt']['fingerprint'])
                self.assertEqual(self.mutate(body)['phaseReceipt'], prepared['phaseReceipt'])
                self.assertEqual(self.mutate(report, 'report')['phaseReceipt'], final['phaseReceipt'])
                self.assertEqual(Head.objects.get().generation, generation)
                for key, value in (('mainReceipt', 'c' * 64), ('mainIncarnation', str(uuid.uuid4()))):
                    changed = copy.deepcopy(report); changed[key] = value
                    self.fault('PHASE_CONFLICT', lambda: self.mutate(changed, 'report'))
                self.assertEqual(RoutePolicy.objects.get(operation_id=body['operationId']).policy, policy)

        def test_a004_unknown_abort_and_status(self):
            body = self.body(); self.mutate(body)
            unknown = self.report_body(body, 'unknown'); response = self.mutate(unknown, 'report')
            self.assertEqual(S.operation_status(self.reader, body['operationId'])['operation']['phases']['unknown']['receipt'], response['phaseReceipt'])
            self.mutate(self.report_body(body, 'aborted'), 'report')
            self.assertEqual(RoutePolicy.objects.get().policy, 'PENDING_DENY')
            self.assertEqual(self.mutate(unknown, 'report')['stage'], 'RECONCILE_REQUIRED')
            self.fault('TERMINAL_IMMUTABLE', lambda: self.mutate(self.report_body(body), 'report'))

        def test_a006_real_sql_error_rolls_back_report_and_retry(self):
            body = self.body(); self.mutate(body); report = self.report_body(body)
            before = S.read_head(self.reader)
            original = Head.save
            def fail_save(instance, *args, **kwargs):
                with connection.cursor() as cursor: cursor.execute('SELECT 1/0')
                return original(instance, *args, **kwargs)
            with patch.object(Head, 'save', fail_save), self.assertRaises(DatabaseError): self.mutate(report, 'report')
            self.assertEqual(S.read_head(self.reader), before)
            self.assertEqual(RoutePolicy.objects.get().policy, 'PENDING_DENY')
            self.assertEqual(Operation.objects.get().stage, 'PENDING_DENY')
            self.mutate(report, 'report'); self.mutate(report, 'report')
            self.assertEqual(Head.objects.get().generation, int(before['generation']) + 1)

        def test_a007_disabled_profile_and_count_cap(self):
            body = self.body()
            with override_settings(TRUST_WRITE_PROFILE='disabled'), patch.object(S, '_test_mode') as mode:
                mode.get.return_value = False
                with self.assertNumQueries(0): self.fault('WRITE_PROFILE_DISABLED', lambda: self.mutate(body))
            with patch.object(S.Operation.objects, 'count', return_value=10000):
                self.fault('COUNT_CAP_REACHED', lambda: self.mutate(body))
            self.assertEqual(Operation.objects.count(), 0)
