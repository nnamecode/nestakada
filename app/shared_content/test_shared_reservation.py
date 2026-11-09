"""RSV candidate correctness via real HTTP/PG/FS; no quota monkeypatch."""
from contextlib import contextmanager
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
from django.test import SimpleTestCase

from . import test_shared_http as Q


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
        self.assertFalse(SharedReceipt.objects.filter(pk=value['operationId']).exists())
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
        value = content_html(row)
        digest = hashlib.sha256(value.encode()).hexdigest()
        if row.storage_kind == 'inline':
            self.assertEqual(value, row.html)
            self.assertEqual(digest, row.payload_hash)
        else:
            self.assertEqual(row.storage_kind, 'file')
            self.assertEqual(row.html, '')
            self.assertEqual(digest, row.file_sha256)
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
