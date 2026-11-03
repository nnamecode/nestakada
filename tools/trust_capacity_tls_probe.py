"""One paced fixed-worker TLS snapshot of the retained 5120-item UNIT corpus."""
import hashlib
import json
import re
import signal
import time
from pathlib import Path

PACE_SECONDS = 0.11


class TLSProbeFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise TLSProbeFailure(code)


def main():
    probe_started = time.monotonic()
    report = {'status': 'FAIL', 'scope': 'one-fixed-tls-unit-snapshot-not-main-admission',
        'dataMutation': False, 'htmlAdmission': False, 'workflowComplete': False,
        'mainDatabaseTouched': False, 'stateV2Verification': 'HOST_READONLY_PRE_POST_AUDITS_REQUIRED'}
    calls = {'requests': 0, 'successfulRequests': 0, 'pageResponses': 0, 'manifestResponses': 0, 'headResponses': 0}
    last_start = None
    intervals = []
    fetch_trace = []
    trace_dropped = 0
    read_started = None
    read_finished = None
    read_snapshot_calls = 0
    # Enclose preflight and bounded child cleanup; the existing reader retains
    # its unchanged 30-second whole deadline and six-second per-request limit.
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TLSProbeFailure('CAPACITY_TLS_PROBE_GUARD')))
    signal.alarm(40)
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        from journal import auth, consumer as C, profile as P
        from journal.protocol import closed
        arg = globals().get('ARG'); closed(arg, {'expectedAudit', 'expectedSnapshotDigest'})
        expected = arg['expectedAudit']; snapshot_sha = arg['expectedSnapshotDigest']
        ensure(type(expected) is dict and expected.get('status') == 'PASS'
            and expected.get('database') == 'test_estakada_trust' and expected.get('oid') == 32563
            and expected.get('stateDigestVersion') == 2 and expected.get('sourceMatchesPolicy') is True
            and expected.get('stages') == {'FINAL_RESTRICTION': 1000}
            and expected.get('counts', {}).get('Operation') == 1000
            and expected.get('counts', {}).get('RoutePolicy') == 4096
            and expected.get('counts', {}).get('RequestTombstone') == 1024,
            'CAPACITY_TLS_EXPECTED_CHECKPOINT')
        C.hex_digest(snapshot_sha); C.hex_digest(expected['stateDigest'])
        ensure(connection.settings_dict['NAME'] == 'test_estakada_trust'
            and connection.settings_dict['USER'] == 'trust_runtime'
            and settings.TRUST_WRITE_PROFILE == 'disabled', 'CAPACITY_TLS_SETTINGS_SCOPE')
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(),current_user,session_user,oid FROM pg_database WHERE datname=current_database()')
            ensure(cursor.fetchone() == ('test_estakada_trust', 'trust_runtime', 'trust_runtime', 32563),
                'CAPACITY_TLS_ACTUAL_SCOPE')
            cursor.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(cursor.fetchone() == (True,), 'CAPACITY_TLS_DATABASE_SSL')
        own_resources = P.runtime_resource_facts()
        ensure(P.source_fingerprint() == expected['actualSourceFingerprint']
            == expected['policySourceFingerprint'], 'CAPACITY_TLS_SOURCE_MISMATCH')
        ensure(hashlib.sha256(Path(settings.TRUST_CREDENTIALS_FILE).read_bytes()).hexdigest()
            == expected['credentialConfigSha256'], 'CAPACITY_TLS_CREDENTIAL_CONFIG_MISMATCH')
        head = expected['head']
        expected_head = {'incarnation': head['incarnation'], 'generation': str(head['generation']),
            'writerEpoch': str(head['writer_epoch']), 'mode': head['mode'], 'digest': head['digest']}
        ensure(head['reserved_bytes'] == 0 and expected_head['mode'] == 'ACTIVE'
            and expected_head['writerEpoch'] == '1' and auth.identity() == expected_head['incarnation'],
            'CAPACITY_TLS_EXPECTED_HEAD')
        C.head_value(expected_head, auth.identity())
        keys = [item for item in auth.configuration().values() if item['role'] == 'reader']
        ensure(len(keys) == 1, 'CAPACITY_TLS_READER_CONFIGURATION')
        reader = C.HTTPSReader(ca_file='/run/secrets/ingress-ca', credential_id=keys[0]['id'], secret=keys[0]['secret'])
        def fetch(target, timeout):
            nonlocal last_start, trace_dropped
            before_delay = time.monotonic()
            delay = max(0.0, last_start+PACE_SECONDS-before_delay) if last_start is not None else 0.0
            kind = 'manifest' if target == '/v1/snapshot-manifest' else 'head' if target == '/v1/head' else 'other'
            match = re.fullmatch(r'/v1/snapshot\?generation=(?:0|[1-9][0-9]{0,18})&cursor=(0|[1-9][0-9]{0,4})', target) if type(target) is str else None
            if match is not None: kind = 'page'
            entry = {'type': kind, 'cursor': int(match.group(1)) if match is not None else None,
                'startOffsetSeconds': round(before_delay-read_started, 6),
                'passedTimeoutSeconds': timeout, 'pacingRequestedSeconds': delay,
                'pacingActualSeconds': 0.0, 'remainingTimeoutSeconds': None,
                'readerElapsedSeconds': None, 'totalElapsedSeconds': None,
                'outcome': 'STARTED', 'errorCode': None, 'errorClass': None}
            if len(fetch_trace) < 54:
                fetch_trace.append(entry)
            else:
                trace_dropped += 1
            try:
                if delay >= timeout:
                    raise C.SnapshotRejected('SNAPSHOT_DEADLINE')
                if delay:
                    pacing_started = time.monotonic()
                    try:
                        time.sleep(delay)
                    finally:
                        entry['pacingActualSeconds'] = round(time.monotonic()-pacing_started, 6)
                remaining = timeout-(time.monotonic()-before_delay)
                entry['remainingTimeoutSeconds'] = remaining
                if remaining <= 0:
                    raise C.SnapshotRejected('SNAPSHOT_DEADLINE')
                current_start = time.monotonic()
                if last_start is not None: intervals.append(current_start-last_start)
                last_start = current_start; calls['requests'] += 1
                reader_started = time.monotonic()
                try:
                    value = reader(target, remaining)
                finally:
                    entry['readerElapsedSeconds'] = round(time.monotonic()-reader_started, 6)
                calls['successfulRequests'] += 1
                if target == '/v1/snapshot-manifest': calls['manifestResponses'] += 1
                elif target == '/v1/head': calls['headResponses'] += 1
                else: calls['pageResponses'] += 1
                entry['outcome'] = 'PASS'
                return value
            except BaseException as error:
                code = getattr(error, 'code', None)
                entry.update(outcome='FAIL', errorCode=code if type(code) is str
                    and re.fullmatch('[A-Z0-9_]{1,80}', code) else 'FETCH_FAILED',
                    errorClass=type(error).__name__ if re.fullmatch('[A-Za-z_][A-Za-z0-9_]{0,79}', type(error).__name__) else 'Exception')
                raise
            finally:
                entry['totalElapsedSeconds'] = round(time.monotonic()-before_delay, 6)
        read_started = time.monotonic()
        read_snapshot_calls += 1
        try:
            snapshot = C.read_snapshot(fetch, expected_head['incarnation'])
        finally:
            read_finished = time.monotonic()
        elapsed = read_finished-read_started
        ensure(elapsed <= C.WHOLE_SECONDS and C.WHOLE_SECONDS == 30 and C.REQUEST_SECONDS == 6,
            'CAPACITY_TLS_DEADLINE')
        ensure(dict(snapshot.head) == expected_head and snapshot.digest == snapshot_sha
            and hashlib.sha256(snapshot.items_bytes).hexdigest() == snapshot_sha
            and snapshot.total_routes == 4096 and snapshot.total_tombstones == 1024,
            'CAPACITY_TLS_SNAPSHOT_MISMATCH')
        ensure(calls == {'requests': 54, 'successfulRequests': 54, 'pageResponses': 52,
            'manifestResponses': 1, 'headResponses': 1}, 'CAPACITY_TLS_REQUEST_COUNTS')
        report.update(status='PASS', case='RP15-011', head=dict(snapshot.head), snapshotDigest=snapshot.digest,
            expectedStateDigestVersion=2, expectedStateDigest=expected['stateDigest'],
            routes=snapshot.total_routes, tombstones=snapshot.total_tombstones, items=5120,
            snapshotBytes=len(snapshot.items_bytes), elapsedSeconds=round(elapsed, 6),
            wholeDeadlineSeconds=30, requestDeadlineSeconds=6, pacedStartIntervalSeconds=PACE_SECONDS,
            minActualRequestStartIntervalSeconds=round(min(intervals), 6),
            retries=0, readSnapshotCalls=1, ownResources=own_resources,
            sourceFingerprint=expected['actualSourceFingerprint'])
    except BaseException as error:
        code = error.args[0] if isinstance(error, TLSProbeFailure) and error.args else getattr(error, 'code', 'CAPACITY_TLS_FAILED')
        report.update(status='FAIL', errorCode=code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}', code)
            else 'CAPACITY_TLS_FAILED', errorClass=type(error).__name__)
    finally:
        signal.alarm(0)
        finished = time.monotonic()
        report.update(fetchTrace=fetch_trace, fetchTraceLimit=54, fetchTraceDropped=trace_dropped,
            readSnapshotCalls=read_snapshot_calls,
            readSnapshotElapsedSeconds=round((read_finished if read_finished is not None else finished)-read_started, 6)
                if read_started is not None else None,
            totalElapsedSeconds=round(finished-probe_started, 6))
    report.update(calls)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
