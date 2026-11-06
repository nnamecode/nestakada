"""RSV candidate correctness via real HTTP/PG/FS; no quota monkeypatch."""
from contextlib import contextmanager
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import UUID, uuid4

from django.conf import settings
from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from . import test_shared_http as Q
from page_editor import test_check_http as H


class SharedReservationArithmeticTests(SimpleTestCase):
    def test_rsv009_exact_integer_required_boundary_and_invalid_types(self):
        from .faults import SharedFault
        from .quota import fits
        for required in (0, 1, 65536, 268435456):
            with self.subTest(required=required):
                self.assertTrue(fits(required, required))
                self.assertFalse(fits(required - 1, required))
        for remaining, required in ((True, 1), (1, False), (1.0, 1), (1, -1)):
            with self.subTest(remaining=remaining, required=required):
                with self.assertRaises(SharedFault) as raised:
                    fits(remaining, required)
                self.assertEqual(raised.exception.code, 'SHARED_MEASUREMENT_UNAVAILABLE')
                self.assertEqual(raised.exception.status, 503)
                self.assertTrue(raised.exception.operation_not_started)


def calibration_parent():
    value = os.environ.get('ESTAKADA_SHARED_CALIBRATION_ROOT', '')
    prefix = '/rc-state/rc-q351/'
    if not value.startswith(prefix) or str(UUID(value[len(prefix):])) != value[len(prefix):]:
        raise RuntimeError('RC_TEST_STATE_ROOT_REQUIRED')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open('/rc-state', flags)
    try:
        for name in ('rc-q351', value[len(prefix):]):
            try:
                os.mkdir(name, mode=0o700, dir_fd=fd)
                os.fsync(fd)
            except FileExistsError:
                pass
            nxt = os.open(name, flags, dir_fd=fd)
            info = os.fstat(nxt)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != 0o700):
                os.close(nxt)
                raise RuntimeError('RC_TEST_STATE_ROOT_UNSAFE')
            os.close(fd)
            fd = nxt
    finally:
        os.close(fd)
    return Path(value)


class ReservationFixture:
    login = Q.SharedHttpTests.login
    raw = Q.SharedHttpTests.raw
    fixture = Q.SharedHttpTests.fixture
    state = Q.SharedHttpTests.state
    path = Q.SharedHttpTests.path
    post_shared = Q.SharedHttpTests.post_shared
    semantic_slot = Q.SharedHttpTests.semantic_slot

    def setUp(self):
        parent = calibration_parent()
        with patch('page_editor.test_check_http.TemporaryDirectory',
                   side_effect=lambda: TemporaryDirectory(prefix='owned-', dir=parent)):
            Q.SharedHttpTests.setUp(self)
        self.assertTrue(Path(self.temp.name).is_relative_to(parent))
        self.assertFalse(Path(self.temp.name).is_symlink())

    @contextmanager
    def candidate(self):
        from .profiles import calibration_scope
        with calibration_scope() as evidence:
            self.assertEqual(evidence['status'], 'unvetted')
            self.assertRegex(evidence['sourceFingerprint'], r'^[a-f0-9]{64}$')
            yield evidence

    def context(self, kind):
        from .models import SharedBlock
        current = SharedBlock.objects.get(kind=kind).current_revision_id
        return {'baseRevisionId': str(current) if current else None,
                'sourceMode': 'current', 'draftBasis': None, 'stageId': None}

    def query(self, context):
        if context['sourceMode'] == 'owner-draft':
            return {'source': 'owner-draft', 'draftId': context['draftBasis']['id'],
                    'draftRevision': context['draftBasis']['revision']}
        if context['sourceMode'] == 'restore-stage':
            return {'source': 'restore-stage', 'stageId': context['stageId']}
        return {}

    def send(self, kind, action, value, *, context=None, client=None):
        client = client or self.owner_client
        context = context or {name: value[name] for name in
            ('baseRevisionId', 'sourceMode', 'draftBasis', 'stageId') if name in value}
        query = self.query(context) if context.get('sourceMode') else {}
        url = self.path(kind, action) + ('?' + urlencode(query) if query else '')
        token = client.cookies[settings.CSRF_COOKIE_NAME].value if settings.CSRF_COOKIE_NAME in client.cookies else ''
        with patch('shared_content.views.read_json_bytes', side_effect=lambda request, profile: request.body):
            return client.post(url, data=self.raw(value), content_type='application/json', HTTP_X_CSRFTOKEN=token)

    def intent(self, kind, html, *, context=None, operation_id=None):
        context = self.context(kind) if context is None else context
        value = {'protocol': 'shared-editor-v1', 'generation': 1, **context, 'html': html}
        for index in range(2):
            response = self.send(kind, 'check', value)
            self.assertEqual(response.status_code, 200, 'RC_VALID_CHECK_REFUSED')
            checked = response.json()
            if not checked['normalisationChanged']:
                break
            self.assertEqual(index, 0, 'RC_NORMALIZATION_NOT_IDEMPOTENT')
            value['html'] = checked['normalisedHtml']
        value.update(html=checked['normalisedHtml'], operationId=str(operation_id or uuid4()),
                     checkReceipt=checked['checkReceipt'])
        return value

    def applied(self, kind, action, value):
        from .models import SharedReceipt
        response = self.send(kind, action, value)
        self.assertEqual(response.status_code, 200, 'RC_REAL_POSITIVE_WRITE_REFUSED')
        result = response.json()
        self.assertTrue(result['ok'])
        self.assertFalse(result['replay'])
        self.assertFalse(result['gone'])
        self.assertEqual(result['operationId'], value['operationId'])
        receipt = SharedReceipt.objects.get(pk=value['operationId'])
        self.assertEqual((receipt.action, receipt.result_code, str(receipt.result_id)),
                         (action, 'applied', result['resultId']))
        self.assertRegex(receipt.reservation_book_sha256, r'^[a-f0-9]{64}$')
        self.assertEqual(set(result['editorContext']),
                         {'baseRevisionId', 'sourceMode', 'draftBasis', 'stageId'})
        self.within_cap()
        return result

    def apply_text(self, kind, canary):
        value = self.intent(kind, self.fixture(kind, canary))
        return value, self.applied(kind, 'apply', value)

    def within_cap(self):
        from .quota import measure
        measurement = measure()
        self.assertLessEqual(measurement['usedBytes'], 268435456)
        self.assertLessEqual(measurement['snapshotCount'], 10000)
        self.assertIsNotNone(measurement['effectiveUsedBytes'])
        self.assertLessEqual(measurement['effectiveUsedBytes'], 268435456)
        return measurement

    def body(self, row):
        from .content import content_html
        self.assertEqual(row.storage_kind, 'file')
        self.assertEqual(row.html, '')
        value = content_html(row)
        self.assertEqual(hashlib.sha256(value.encode()).hexdigest(), row.file_sha256)
        return value

    def business(self):
        excluded = {'shared_content.SharedBudget', 'shared_content.SharedReceipt',
                    'shared_content.SharedIdentityReservation'}
        return {key: value for key, value in self.state().items() if key not in excluded}

    def report(self, label, evidence):
        events = []
        for event in evidence['events']:
            numbers = {key: value for key, value in event.get('measurement', {}).items()
                       if type(value) in (int, bool) or value is None}
            events.append({'phase': event['phase'], 'measurement': numbers})
        print(json.dumps({'scope': 'RC_CANDIDATE_OBSERVATION', 'label': label, 'status': 'unvetted',
            'profileId': evidence['profileId'], 'parameters': evidence['parameters'],
            'sourceFingerprint': evidence['sourceFingerprint'], 'sourceFileCount': evidence['sourceFileCount'],
            'schemaSignature': evidence['schemaSignature'], 'pgFacts': evidence['pgFacts'],
            'fsFacts': evidence['fsFacts'], 'events': events}), flush=True)


@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedReservationTests(ReservationFixture, TransactionTestCase):
    def test_real_owner_draft_and_apply_filemode_both_blocks_independent(self):
        from .models import SharedBlock, SharedDraft, SharedRevision
        with self.candidate() as evidence:
            for kind in ('header', 'footer'):
                other = 'footer' if kind == 'header' else 'header'
                other_before = SharedBlock.objects.get(kind=other).current_revision_id
                before_count = SharedRevision.objects.count()
                value = self.intent(kind, self.fixture(kind, 'DRAFT-' + kind))
                draft_result = self.applied(kind, 'draft', value)
                draft = SharedDraft.objects.get(pk=draft_result['resultId'])
                self.semantic_slot(kind, self.body(draft), 'DRAFT-' + kind)
                self.assertIsNone(SharedBlock.objects.get(kind=kind).current_revision_id)
                self.assertEqual(SharedRevision.objects.count(), before_count)
                chosen = draft_result['editorContext']
                applied_intent = self.intent(kind, self.body(draft), context=chosen)
                result = self.applied(kind, 'apply', applied_intent)
                row = SharedRevision.objects.get(pk=result['resultId'])
                self.semantic_slot(kind, self.body(row), 'DRAFT-' + kind)
                self.assertEqual(SharedBlock.objects.get(kind=kind).current_revision_id, row.pk)
                self.assertFalse(SharedDraft.objects.filter(pk=draft.pk).exists())
                self.assertEqual(SharedBlock.objects.get(kind=other).current_revision_id, other_before)
                self.assertEqual(SharedRevision.objects.count(), before_count + 1)
            self.report('RSV-001-both-blocks', evidence)

    def test_restore_stage_apply_literal_phone_and_metadata_first_exact_replay(self):
        from .models import SharedRevision, SharedRestoreStage, SharedBasePin
        with self.candidate() as evidence:
            _, old_result = self.apply_text('header', 'OLD-CONTACT')
            old = SharedRevision.objects.get(pk=old_result['resultId'])
            old_html, old_hash = self.body(old), old.file_sha256
            newer = self.fixture('header', 'NEW-CONTACT').replace('+70000000001', '+70000000002')
            self.applied('header', 'apply', self.intent('header', newer))
            current = self.context('header')
            before_revision = current['baseRevisionId']
            operation = str(uuid4())
            prepared = self.send('header', 'restore/prepare', {'protocol': 'shared-editor-v1',
                'generation': 1, 'baseRevisionId': before_revision, 'sourceRevisionId': str(old.pk),
                'operationId': operation, 'confirmReplace': True}, context=current)
            self.assertEqual(prepared.status_code, 200)
            selected = prepared.json()['editorContext']
            stage = SharedRestoreStage.objects.get(pk=prepared.json()['resultId'])
            self.assertEqual(stage.status, 'held')
            self.assertTrue(SharedBasePin.objects.filter(holder_id=stage.pk).exists())
            self.assertEqual(self.context('header')['baseRevisionId'], before_revision)
            value = self.intent('header', old_html, context=selected)
            result = self.applied('header', 'apply', value)
            row = SharedRevision.objects.get(pk=result['resultId'])
            self.assertEqual(self.body(row), old_html)
            self.assertIn('+70000000001', self.body(row))
            self.assertNotIn('+70000000002', self.body(row))
            self.assertEqual(row.source_revision_id, old.pk)
            old.refresh_from_db()
            self.assertEqual(old.file_sha256, old_hash)
            stage.refresh_from_db()
            self.assertEqual(stage.status, 'consumed')
            self.assertFalse(SharedBasePin.objects.filter(holder_id=stage.pk).exists())
            before = self.state()
            with patch('shared_content.views.normalize_input', side_effect=AssertionError('REPLAY_NORMALIZED_OLD_SOURCE')), \
                 patch('shared_content.storage.SharedStorage.read', side_effect=AssertionError('REPLAY_READ_OLD_BODY')):
                replay = self.send('header', 'apply', value)
            self.assertEqual(replay.status_code, 200)
            self.assertTrue(replay.json()['replay'])
            self.assertEqual(replay.json()['resultId'], result['resultId'])
            self.assertEqual(replay.json()['editorContext'], result['editorContext'])
            self.assertEqual(self.state(), before)
            altered = {**value, 'html': value['html'].replace('OLD-CONTACT', 'DIFFERENT')}
            refusal = self.send('header', 'apply', altered)
            self.assertEqual(refusal.status_code, 409)
            self.assertEqual(refusal.json()['code'], 'SHARED_OPERATION_CONFLICT')
            self.report('RSV-002-004-restore-replay', evidence)

    def test_draft_basis_counter_frozen_ack_and_stale_current_denial_before_book(self):
        from .models import SharedDraft, SharedReceipt, SharedBudget
        from .storage import SharedStorage
        with self.candidate() as evidence:
            self.apply_text('header', 'CURRENT')
            first_value = self.intent('header', self.fixture('header', 'DRAFT-ONE'))
            first = self.applied('header', 'draft', first_value)
            second = self.applied('header', 'draft', self.intent('header', self.fixture('header', 'DRAFT-TWO'),
                                                               context=first['editorContext']))
            self.assertEqual(second['resultId'], first['resultId'])
            self.assertEqual(second['editorContext']['draftBasis']['revision'],
                             first['editorContext']['draftBasis']['revision'] + 1)
            replay = self.send('header', 'draft', first_value)
            self.assertEqual(replay.status_code, 200)
            self.assertEqual(replay.json()['editorContext'], first['editorContext'])
            stale_value = self.intent('header', self.fixture('header', 'STALE-INPUT'))
            self.apply_text('header', 'NEW-CURRENT')
            before_db, before_fs = self.state(), SharedStorage().inventory()
            before_debt = SharedBudget.objects.get().retained_debt_bytes
            denied = self.send('header', 'apply', stale_value)
            self.assertEqual(denied.status_code, 409)
            self.assertFalse(SharedReceipt.objects.filter(pk=stale_value['operationId']).exists())
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, before_debt)
            self.assertEqual(self.state(), before_db)
            self.assertEqual(SharedStorage().inventory(), before_fs)
            self.assertEqual(SharedDraft.objects.get(pk=first['resultId']).revision,
                             second['editorContext']['draftBasis']['revision'])
            self.report('RSV-003-draft-basis-stale', evidence)

    def test_actual_metadata_abort_retains_debt_orphan_and_same_id_cannot_execute_twice(self):
        from . import reservations
        from .models import SharedBudget, SharedReceipt
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('header', self.fixture('header', 'FAULTED-INPUT'))
            before = self.business()
            before_debt = SharedBudget.objects.get().retained_debt_bytes
            original, hits, book_hashes = reservations._fault_boundary, [], []
            def fault(phase):
                if phase == 'book_durable':
                    path = Path(self.temp.name) / 'private/shared-content/journal' / (UUID(value['operationId']).hex + '.json')
                    book_hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
                if phase == 'metadata_written':
                    hits.append(phase)
                    raise OSError(errno.EIO, 'RSV_TEST_METADATA_FAULT')
                return original(phase)
            with patch('shared_content.reservations._fault_boundary', side_effect=fault):
                failed = self.send('header', 'apply', value)
            self.assertEqual(hits, ['metadata_written'])
            self.assertEqual(failed.status_code, 409)
            self.assertEqual(failed.json()['code'], 'SHARED_OPERATION_ABORTED')
            self.assertTrue(failed.json()['outcomeKnown'])
            receipt = SharedReceipt.objects.get(pk=value['operationId'])
            self.assertEqual(receipt.result_code, 'aborted')
            self.assertIsNone(receipt.result_id)
            self.assertEqual(book_hashes, [receipt.reservation_book_sha256])
            self.assertEqual(receipt.reservation_profile, evidence['profileId'])
            expected_fingerprint = hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(receipt.fingerprint, expected_fingerprint)
            debt = SharedBudget.objects.get().retained_debt_bytes
            self.assertEqual(debt - before_debt, evidence['parameters']['usage_abort_debt_allowance'])
            self.assertEqual(self.business(), before)
            inventory = SharedStorage().inventory()
            self.assertGreaterEqual(inventory['orphanCount'], 1)
            self.assertEqual(inventory['journalCount'], 0)
            before_state = self.state()
            with patch('shared_content.views.normalize_input', side_effect=AssertionError('ABORT_REEXECUTED')):
                repeated = self.send('header', 'apply', value)
            self.assertEqual(repeated.status_code, 409)
            self.assertTrue(repeated.json()['outcomeKnown'])
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
            self.assertEqual(self.state(), before_state)
            self.apply_text('header', 'EXPLICIT-NEW-OPERATION')
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
            self.report('RSV-006-known-abort-debt', evidence)

    def test_real_partial_blob_write_aborts_once_preserves_orphan_and_book_binding(self):
        from .models import SharedBudget, SharedReceipt
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('footer', self.fixture('footer', 'PARTIAL-BLOB'))
            before, debt = self.business(), SharedBudget.objects.get().retained_debt_bytes
            original_write, hits = os.write, []
            root = Path(self.temp.name) / 'private/shared-content/blobs'
            def partial(fd, data):
                actual = os.readlink('/proc/self/fd/' + str(fd))
                if Path(actual).is_relative_to(root):
                    hits.append(True)
                    if len(hits) == 1:
                        return original_write(fd, data[:5])
                    raise OSError(errno.EIO, 'RSV_TEST_PARTIAL_BLOB')
                return original_write(fd, data)
            with patch('shared_content.storage.os.write', side_effect=partial):
                response = self.send('footer', 'apply', value)
            self.assertEqual(len(hits), 2, 'REAL_PARTIAL_BLOB_FAULT_NOT_REACHED')
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['code'], 'SHARED_OPERATION_ABORTED')
            self.assertTrue(response.json()['outcomeKnown'])
            receipt = SharedReceipt.objects.get(pk=value['operationId'])
            self.assertEqual(receipt.result_code, 'aborted')
            self.assertRegex(receipt.reservation_book_sha256, r'^[a-f0-9]{64}$')
            self.assertEqual(self.business(), before)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes - debt,
                             evidence['parameters']['usage_abort_debt_allowance'])
            inventory = SharedStorage().inventory()
            self.assertEqual((inventory['blobCount'], inventory['orphanCount'], inventory['journalCount']), (1, 1, 0))
            blob = next(row for row in inventory['files'] if row['kind'] == 'blob')
            self.assertEqual((SharedStorage().root / blob['key']).read_bytes(), value['html'].encode()[:5])
            self.within_cap()
            self.report('RSV-006-real-partial-blob', evidence)

    def test_session_revocation_after_check_denies_before_new_reservation(self):
        from django.contrib.sessions.models import Session
        from .models import SharedReceipt, SharedBudget
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('footer', self.fixture('footer', 'SESSION-INPUT'))
            before_db, before_fs = self.state(), SharedStorage().inventory()
            debt = SharedBudget.objects.get().retained_debt_bytes
            Session.objects.filter(
                pk=self.owner_client.session.session_key).delete()
            response = self.send('footer', 'apply', value)
            self.assertEqual(response.status_code, 401)
            self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
            self.assertEqual(self.state(), before_db)
            self.assertEqual(SharedStorage().inventory(), before_fs)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
            self.report('RSV-UI005-backend-session-only', evidence)

    def test_actual_session_lease_and_free_domain_locks_during_blob_io(self):
        from . import reservations
        from .faults import SharedFault
        from content.models import CONTENT_LOCK
        from accounts.services import AUTH_LOCK
        with self.candidate() as evidence:
            other = connection.Database.connect(**connection.get_connection_params())
            other.autocommit = True
            self.assertEqual(other.execute('SELECT current_database(),current_user').fetchone(),
                             ('estakada_foundation_unit', 'app_migrator'))
            hits, original = [], reservations._fault_boundary
            def inspect(phase):
                if phase == 'blob_durable':
                    self.assertFalse(connection.in_atomic_block)
                    hits.append(phase)
                    self.assertFalse(other.execute('SELECT pg_try_advisory_lock(%s)', [reservations.LEASE_KEY]).fetchone()[0])
                    with other.transaction():
                        self.assertTrue(other.execute('SELECT pg_try_advisory_xact_lock(%s)', [CONTENT_LOCK]).fetchone()[0])
                        self.assertTrue(other.execute('SELECT pg_try_advisory_xact_lock(%s)', [AUTH_LOCK]).fetchone()[0])
                return original(phase)
            try:
                with reservations.session_lease():
                    with self.assertRaises(SharedFault) as denied:
                        with reservations.session_lease():
                            pass
                    self.assertEqual(denied.exception.code, 'SHARED_RESERVATION_BUSY')
                with patch('shared_content.reservations._fault_boundary', side_effect=inspect):
                    self.apply_text('footer', 'LEASE-REAL-HTTP')
                self.assertEqual(hits, ['blob_durable'])
                self.assertTrue(other.execute('SELECT pg_try_advisory_lock(%s)', [reservations.LEASE_KEY]).fetchone()[0])
                self.assertTrue(other.execute('SELECT pg_advisory_unlock(%s)', [reservations.LEASE_KEY]).fetchone()[0])
            finally:
                other.close()
            self.report('RSV-005-lease-and-domain', evidence)

    def test_assigned_usage_share_counts_real_shared_and_page_refs_then_recalculates(self):
        from media_library.models import AssetUsage
        from media_library.services import attach, detach
        from .models import SharedIdentityReservation
        from .quota import measure
        with self.candidate() as evidence:
            self.apply_text('header', 'OWN-USAGE')
            before = self.business()
            attach(kind='ordinary_version', consumer_id=self.initial, slot='qa-page-image', asset_id=self.asset.pk)
            measurements = []
            for remove in (False, True):
                if remove:
                    detach(kind='ordinary_version', consumer_id=self.initial, slot='qa-page-image')
                value = measure()
                rows = list(AssetUsage.objects.values('kind', 'consumer_id'))
                identities = {row['id']: row for row in SharedIdentityReservation.objects.values('id', 'kind', 'block_id')}
                own = 0
                for row in rows:
                    identity = identities.get(row['consumer_id'])
                    if identity and identity['block_id'] is not None and (
                        (row['kind'] == 'shared_block' and identity['kind'] == 'sharedrevision') or
                        (row['kind'] == 'draft' and identity['kind'] == 'shareddraft')):
                        own += 1
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_total_relation_size(%s::regclass)',
                                   ['app.' + AssetUsage._meta.db_table])
                    physical = cursor.fetchone()[0]
                assigned = (physical * own + len(rows) - 1) // len(rows) if own else 0
                self.assertEqual((value['allRefs'], value['ownRefs'], value['usageRootBytes'], value['assignedUsageBytes']),
                                 (len(rows), own, physical, assigned))
                measurements.append(value)
            self.assertEqual(measurements[1]['ownRefs'], measurements[0]['ownRefs'])
            self.assertEqual(measurements[1]['allRefs'], measurements[0]['allRefs'] - 1)
            self.assertGreaterEqual(measurements[1]['assignedUsageBytes'], measurements[0]['assignedUsageBytes'])
            self.assertEqual(self.business(), before)
            self.report('RSV-010-assigned-share-real-counts', evidence)

    def test_unknown_wrongkind_and_unbound_shared_usage_cannot_be_silently_unassigned(self):
        from media_library.models import AssetUsage
        from media_library.services import attach, detach
        from page_versions.models import OwnerDraft
        from .faults import SharedFault
        from .models import SharedBlock, SharedIdentityReservation, SharedBudget, SharedReceipt
        from .quota import measure
        from .storage import SharedStorage
        with self.candidate() as evidence:
            page_draft = OwnerDraft.objects.get(page=self.page)
            attach(kind='draft', consumer_id=page_draft.pk, slot='qa-page-draft', asset_id=self.asset.pk)
            valid = measure()
            self.assertEqual((valid['ownRefs'], valid['allRefs']), (0, 1))
            block = SharedBlock.objects.get(kind='header')
            wrong = SharedIdentityReservation.objects.create(id=uuid4(), kind='shareddraft', block=block)
            unbound = SharedIdentityReservation.objects.create(id=uuid4(), kind='sharedrevision', block=None)
            consumers = (uuid4(), wrong.pk, unbound.pk, self.initial)
            for consumer in consumers:
                value = self.intent('header', self.fixture('header', 'OWNERSHIP-DENIAL'))
                usage = AssetUsage.objects.create(asset=self.asset, kind='shared_block',
                                                  consumer_id=consumer, slot='qa-shared-consumer')
                before, debt = self.business(), SharedBudget.objects.get().retained_debt_bytes
                before_fs = SharedStorage().inventory()
                with self.assertRaises(SharedFault) as unavailable:
                    measure()
                self.assertEqual(unavailable.exception.code, 'SHARED_MEASUREMENT_UNAVAILABLE')
                denied = self.send('header', 'apply', value)
                self.assertEqual(denied.status_code, 503)
                self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
                self.assertFalse(SharedIdentityReservation.objects.filter(pk=value['operationId']).exists())
                self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
                self.assertEqual(self.business(), before)
                self.assertEqual(SharedStorage().inventory(), before_fs)
                detach(kind=usage.kind, consumer_id=usage.consumer_id, slot=usage.slot)
            self.report('RSV-010-ownership-refusals', evidence)

    def test_postcommit_response_fault_preserves_truth_then_exact_reconcile_without_duplicate(self):
        from . import reservations
        from .models import SharedReceipt, SharedRevision, SharedBudget
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('footer', self.fixture('footer', 'COMMITTED-RESPONSE-FAULT'))
            original, hits = reservations._fault_boundary, []
            def fault(phase):
                if phase == 'db_committed':
                    self.assertFalse(connection.in_atomic_block)
                    hits.append(phase)
                    raise OSError(errno.EIO, 'RSV_TEST_POSTCOMMIT_RESPONSE_FAULT')
                return original(phase)
            with patch('shared_content.reservations._fault_boundary', side_effect=fault):
                unknown = self.send('footer', 'apply', value)
            self.assertEqual(hits, ['db_committed'])
            self.assertEqual(unknown.status_code, 503)
            self.assertFalse(unknown.json()['outcomeKnown'])
            receipt = SharedReceipt.objects.get(pk=value['operationId'])
            self.assertEqual(receipt.result_code, 'applied')
            self.assertEqual(SharedRevision.objects.count(), 1)
            self.assertEqual(SharedStorage().inventory()['journalCount'], 1)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, 0)
            before = self.business()
            replay = self.send('footer', 'apply', value)
            self.assertEqual(replay.status_code, 200)
            self.assertTrue(replay.json()['replay'])
            self.assertEqual(replay.json()['resultId'], str(receipt.result_id))
            self.assertEqual(SharedRevision.objects.count(), 1)
            self.assertEqual(SharedReceipt.objects.filter(pk=value['operationId']).count(), 1)
            self.assertEqual(SharedStorage().inventory()['journalCount'], 0)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, 0)
            self.assertEqual(self.business(), before)
            self.within_cap()
            self.report('RCREV003-ordinary-postcommit-known-truth', evidence)

    def test_postcommit_actual_unsafe_measurement_persists_fault_after_bad_row_removed(self):
        from media_library.models import AssetUsage
        from media_library.services import detach
        from . import reservations
        from .models import SharedReceipt, SharedRevision, SharedBudget
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('header', self.fixture('header', 'UNSAFE-AFTER-COMMIT'))
            original, injected = reservations._fault_boundary, []
            def insert_actual_bad_usage(phase):
                if phase == 'db_committed':
                    self.assertFalse(connection.in_atomic_block)
                    injected.append(AssetUsage.objects.create(asset=self.asset, kind='shared_block',
                        consumer_id=uuid4(), slot='qa-postcommit-invalid'))
                return original(phase)
            with patch('shared_content.reservations._fault_boundary', side_effect=insert_actual_bad_usage):
                unknown = self.send('header', 'apply', value)
            self.assertEqual(len(injected), 1)
            self.assertEqual(unknown.status_code, 503)
            self.assertFalse(unknown.json()['outcomeKnown'])
            receipt = SharedReceipt.objects.get(pk=value['operationId'])
            self.assertEqual(receipt.result_code, 'applied')
            self.assertEqual(SharedRevision.objects.count(), 1)
            self.assertEqual(SharedBudget.objects.get().accounting_version, 'faulted')
            self.assertEqual(SharedStorage().inventory()['journalCount'], 1)
            bad = injected[0]
            detach(kind=bad.kind, consumer_id=bad.consumer_id, slot=bad.slot)
            next_value = self.intent('footer', self.fixture('footer', 'MUST-STAY-CLOSED'))
            before, debt = self.business(), SharedBudget.objects.get().retained_debt_bytes
            closed = self.send('footer', 'apply', next_value)
            self.assertEqual(closed.status_code, 503)
            self.assertEqual(SharedBudget.objects.get().accounting_version, 'faulted')
            self.assertFalse(SharedReceipt.objects.filter(pk=next_value['operationId']).exists())
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, debt)
            self.assertEqual(self.business(), before)
            self.assertEqual(SharedRevision.objects.count(), 1)
            self.report('RCREV003-persistent-unsafe-latch', evidence)

    def test_failed_real_db_fault_latch_then_fresh_session_cannot_autoabort_missing_receipt(self):
        from django.db import DatabaseError
        from media_library.models import AssetUsage
        from media_library.services import detach
        from . import reservations
        from .models import SharedReceipt, SharedBudget
        from .storage import SharedStorage
        with self.candidate() as evidence:
            value = self.intent('header', self.fixture('header', 'NO-RECEIPT-UNKNOWN'))
            original, injected, failed_latches = reservations._fault_boundary, [], []
            before_version = SharedBudget.objects.get().accounting_version
            other = connection.Database.connect(**connection.get_connection_params())
            self.assertEqual(other.execute('SELECT current_database(),current_user').fetchone(),
                             ('estakada_foundation_unit', 'app_migrator'))
            table = SharedBudget._meta.db_table
            other.execute('SELECT singleton FROM ' + connection.ops.quote_name(table) +
                          ' WHERE singleton=true FOR UPDATE')
            def inject(phase):
                if phase == 'book_durable':
                    injected.append(AssetUsage.objects.create(asset=self.asset, kind='shared_block',
                        consumer_id=uuid4(), slot='qa-precommit-invalid'))
                return original(phase)
            def bound_actual_latch_update(execute, sql, params, many, context):
                if sql.lstrip().upper().startswith('UPDATE ') and table in sql and params and 'faulted' in params:
                    execute("SET LOCAL lock_timeout='100ms'", None, False, context)
                    try:
                        return execute(sql, params, many, context)
                    except DatabaseError:
                        failed_latches.append(True)
                        raise
                return execute(sql, params, many, context)
            try:
                with connection.execute_wrapper(bound_actual_latch_update), \
                     patch('shared_content.reservations._fault_boundary', side_effect=inject):
                    unknown = self.send('header', 'apply', value)
            finally:
                other.rollback()
                other.close()
            self.assertEqual(len(injected), 1)
            self.assertEqual(failed_latches, [True], 'ACTUAL_PG_LATCH_TIMEOUT_NOT_REACHED')
            self.assertEqual(unknown.status_code, 503)
            self.assertFalse(unknown.json()['outcomeKnown'])
            self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
            self.assertEqual(SharedBudget.objects.get().accounting_version, before_version)
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, 0)
            bad = injected[0]
            detach(kind=bad.kind, consumer_id=bad.consumer_id, slot=bad.slot)
            before = self.state()
            before_fs = SharedStorage().inventory()
            self.assertEqual(before_fs['journalCount'], 1)
            self.report('RCREV003-real-latch-write-failed', evidence)
        # Fresh DB session/lease and calibration scope have no LiveAttempt.
        connection.close()
        with self.candidate() as evidence:
            replay = self.send('header', 'apply', value)
            self.assertEqual(replay.status_code, 503)
            self.assertFalse(replay.json()['outcomeKnown'])
            self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
            self.assertEqual(SharedBudget.objects.get().retained_debt_bytes, 0)
            self.assertEqual(self.state(), before)
            self.assertEqual(SharedStorage().inventory(), before_fs)
            self.report('RCREV003-fresh-session-no-autoabort', evidence)
