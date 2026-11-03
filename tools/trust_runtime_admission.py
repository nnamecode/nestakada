"""AD15 operator helper: readonly inspection or one exact B.activate transition.

ARG and the complete result are private operator evidence. No HTTP writer lease,
bootstrap, migration, test authority, credential change or recovery action here.
"""
import hashlib
import json
import os
import re
import signal
import time


class AdmissionFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise AdmissionFailure(code)


def main():
    started = time.monotonic()
    report = {'status': 'FAIL', 'scope': 'AD15-local-policy-not-http-writer',
        'leaseIssued': False, 'nativeTests': 'NOT_RUN', 'production': False}
    def expire(*_):
        raise AdmissionFailure('ADMISSION_HELPER_DEADLINE')
    signal.signal(signal.SIGALRM, expire); signal.alarm(60)
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection, transaction
        from journal import auth, bounded as B, profile as P, state_v2 as V
        from journal.models import Head, AdmissionPolicy
        from journal.protocol import canonical, closed, digest
        arg = globals().get('ARG')
        closed(arg, {'action', 'intent', 'expected', 'baseline', 'evidence'})
        ensure(arg['action'] in ('inspect', 'activate'), 'ADMISSION_ACTION')
        expected = arg['expected']
        closed(expected, {'database', 'oid', 'incarnation', 'sourceFingerprint',
            'schemaFingerprint', 'credentialConfigSha256'})
        ensure(expected['database'] == 'estakada_trust' and type(expected['oid']) is int
            and expected['oid'] > 0 and expected['oid'] not in (16387, 32563, 52766), 'ADMISSION_EXPECTED_DB')
        ensure(connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == expected['database']
            and connection.settings_dict['USER'] == 'trust_migrator'
            and connection.settings_dict['HOST'] == 'trust-db'
            and settings.TRUST_WRITE_PROFILE == 'disabled'
            and os.environ.get('TRUST_TEST_EXECUTION') != '1'
            and not B._unit_authority.get(), 'ADMISSION_ENVIRONMENT')
        ensure(P.source_fingerprint() == expected['sourceFingerprint'] and len(P.source_files()) == 30
            and B._configuration_sha() == expected['credentialConfigSha256']
            and auth.identity() == expected['incarnation'], 'ADMISSION_SOURCE_CONFIG')
        P.runtime_resource_facts()
        closed(arg['evidence'], {'unit', 'calibration', 'review'})
        ensure(arg['evidence'] == {kind: '/evidence/' + kind + '.json'
            for kind in ('unit', 'calibration', 'review')}, 'ADMISSION_EVIDENCE_PATHS')
        with connection.cursor() as cursor:
            cursor.execute('''SELECT current_database(),current_user,session_user,d.oid,
                pg_get_userbyid(d.datdba) FROM pg_database d WHERE d.datname=current_database()''')
            ensure(cursor.fetchone() == (expected['database'], 'trust_migrator', 'trust_migrator',
                expected['oid'], 'postgres'), 'ADMISSION_ACTUAL_IDENTITY')
            cursor.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()')
            ensure(cursor.fetchone() == (True,), 'ADMISSION_TLS')
            cursor.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s AND pid<>pg_backend_pid()',
                [expected['oid']])
            ensure(cursor.fetchone() == (0,), 'ADMISSION_OTHER_SESSIONS')
            cursor.execute("SET statement_timeout='5s'")
            cursor.execute("SET lock_timeout='1s'")

        def inspect():
            # state_v2.state_digest locks Head and is deliberately not called here.
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                ensure(P.schema_fingerprint() == expected['schemaFingerprint'], 'ADMISSION_SCHEMA')
                head = Head.objects.get(pk=1)
                ensure(str(head.incarnation) == expected['incarnation'], 'ADMISSION_INCARNATION')
                B._counts(head)
                state = hashlib.sha256(V.DOMAIN)
                V._frame(state, {'stateDigestVersion': 2, 'head': V.persistent_values(head)})
                legacy = hashlib.sha256(b'AD15-LEGACY-ALL-FIELDS-v1\x00')
                protected = ('id', 'incarnation', 'writer_epoch', 'mode', 'reserved_bytes',
                    'plan_id', 'permitted_operations', 'permitted_recovery_actions')
                V._frame(legacy, {key: V.persistent_values(head)[key] for key in protected})
                counts = {}; admission = None
                for model, limit in V.TABLES:
                    label = {'table': model._meta.db_table,
                        'fields': [field.attname for field in model._meta.concrete_fields]}
                    V._frame(state, label)
                    if model is not AdmissionPolicy:
                        V._frame(legacy, label)
                    count = 0
                    for row in model.objects.order_by(model._meta.pk.attname).iterator(chunk_size=1):
                        count += 1; ensure(count <= limit, 'ADMISSION_ROW_LIMIT')
                        values = V.persistent_values(row); V._frame(state, values)
                        if model is AdmissionPolicy:
                            ensure(count == 1, 'ADMISSION_ONLY_FIRST_POLICY_SUPPORTED')
                            admission = values
                        else:
                            V._frame(legacy, values)
                    V._frame(state, {'count': count}); counts[model.__name__] = count
                    if model is not AdmissionPolicy:
                        V._frame(legacy, {'count': count})
                with connection.cursor() as cursor:
                    cursor.execute('SELECT id,app,name,applied::text FROM django_migrations ORDER BY id')
                    for row in cursor.fetchall():
                        V._frame(legacy, list(row))
                    cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
                    references = int(cursor.fetchone()[0])
                    cursor.execute('SHOW transaction_read_only')
                    ensure(cursor.fetchone() == ('on',), 'ADMISSION_READONLY_LOST')
                return {'database': expected['database'], 'oid': expected['oid'],
                    'head': V.persistent_values(head), 'counts': counts, 'historicalReferences': references,
                    'stateDigestVersion': 2, 'stateDigest': state.hexdigest(),
                    'legacyRowsSha256': legacy.hexdigest(), 'legacySeal': B.legacy_seal(head),
                    'schemaFingerprint': expected['schemaFingerprint'], 'sourceFingerprint': P.source_fingerprint(),
                    'credentialConfigSha256': B._configuration_sha(), 'admission': admission}

        if arg['action'] == 'inspect':
            ensure(arg['intent'] is None and arg['baseline'] is None, 'ADMISSION_INSPECT_ARGUMENT')
            report.update({'status': 'PASS', 'action': 'inspect', 'state': inspect(),
                'policyMutationAttempted': False, 'rowReadsReadonly': True})
        else:
            baseline = arg['baseline']
            ensure(type(baseline) is dict and baseline['admission'] is None
                and baseline['head']['generation'] == 9 and baseline['head']['writer_epoch'] == 2,
                'ADMISSION_BASELINE')
            intent, actor = B._intent(arg['intent'])
            ensure(intent['policy']['epoch'] == '1' and intent['previousPolicy'] is None
                and intent['legacySeal'] == baseline['legacySeal']
                and intent['expected'] == {key: baseline[key] for key in ('head','stateDigestVersion','stateDigest')},
                'ADMISSION_PREPARED_INTENT')
            before = inspect()
            ensure(before['legacyRowsSha256'] == baseline['legacyRowsSha256'], 'ADMISSION_LEGACY_BEFORE')
            if before['admission'] is None:
                ensure(before == baseline, 'ADMISSION_LIVE_BASELINE_CHANGED')
            else:
                ensure(before['admission']['action_id'] == intent['actionId']
                    and before['admission']['intent_digest'] == digest(intent), 'ADMISSION_DIFFERENT_TRANSITION')
            # No UNIT bypass, alternative activation implementation or envelope rewriting.
            result = B.activate(arg['intent'], arg['evidence'])
            after = inspect(); row = after['admission']
            ensure(result['ok'] is True and result['workflowComplete'] is False and row is not None
                and row['action_id'] == intent['actionId'] and row['intent_digest'] == digest(intent)
                and row['policy'] == intent['policy'] and row['receipt'] == result['receipt']
                and row['policy_digest'] == digest(intent['policy']), 'ADMISSION_RECEIPT_MISMATCH')
            ensure(after['legacyRowsSha256'] == baseline['legacyRowsSha256']
                and after['historicalReferences'] == baseline['historicalReferences']
                and after['counts'] == {**baseline['counts'], 'AdmissionPolicy': 1}, 'ADMISSION_LEGACY_AFTER')
            desired = {**baseline['head'], 'generation': baseline['head']['generation'] + 1,
                'logical_bytes': baseline['head']['logical_bytes'] + row['logical_bytes'],
                'digest': result['receipt']['head']['digest']}
            ensure(after['head'] == desired and after['head']['generation'] == 10
                and row['epoch'] == 1 and row['previous_digest'] is None
                and row['legacy_seal'] == baseline['legacySeal'], 'ADMISSION_HEAD_DELTA')
            if result['replay']:
                ensure(before == after, 'ADMISSION_REPLAY_MUTATED')
            report.update({'status': 'PASS', 'action': 'activate', 'result': result,
                'before': before, 'after': after, 'legacyUnchanged': True, 'policyMutationAttempted': True})
        connection.close()
    except Exception as exc:
        code = str(exc) if isinstance(exc, AdmissionFailure) else getattr(exc, 'code', 'ADMISSION_HELPER_FAILED')
        report.update({'errorClass': type(exc).__name__,
            'errorCode': code if re.fullmatch('[A-Z0-9_]{1,80}', str(code)) else 'ADMISSION_HELPER_FAILED',
            'activationOutcome': 'UNKNOWN_IF_SENT_INSPECT_OR_EXACT_RETRY_REQUIRED'})
    finally:
        signal.alarm(0)
        report['elapsedSeconds'] = round(time.monotonic() - started, 6)
    print(json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
