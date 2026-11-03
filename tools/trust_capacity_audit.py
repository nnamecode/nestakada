"""Read-only, repeatable-read audit of the retained UNIT; never locks/mutates Head."""
import hashlib
import json
import os

import django
django.setup()
from django.db import connection, transaction
from django.db.models import Count
from journal import bounded as B, profile as P, state_v2 as V
from journal.models import Head, Operation, RoutePolicy, RequestTombstone, AdmissionPolicy, Credential, RecoveryReceipt


def main():
    if (connection.settings_dict['NAME'] != 'test_estakada_trust'
        or os.environ.get('TRUST_TEST_EXECUTION') != '1'):
        raise RuntimeError('AUDIT_SCOPE')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            cursor.execute('SELECT current_database(),current_user,session_user,oid FROM pg_database WHERE datname=current_database()')
            identity = cursor.fetchone()
            if identity != ('test_estakada_trust', 'trust_migrator', 'trust_migrator', 32563):
                raise RuntimeError('AUDIT_IDENTITY')
        head = Head.objects.get(pk=1)
        hasher = hashlib.sha256(V.DOMAIN)
        V._frame(hasher, {'stateDigestVersion': V.VERSION, 'head': V.persistent_values(head)})
        counts = {}
        for model, limit in V.TABLES:
            fields = [field.attname for field in model._meta.concrete_fields]
            V._frame(hasher, {'table': model._meta.db_table, 'fields': fields})
            count = 0
            for row in model.objects.order_by(model._meta.pk.attname).iterator(chunk_size=1):
                count += 1
                if count > limit:
                    raise RuntimeError('AUDIT_COUNT_CAP')
                V._frame(hasher, V.persistent_values(row))
            V._frame(hasher, {'count': count})
            counts[model.__name__] = count
        policy = AdmissionPolicy.objects.get(epoch=1)
        B._policy(policy.policy)
        actual_source = P.source_fingerprint()
        stages = {row['stage']: row['count'] for row in Operation.objects.values('stage').annotate(count=Count('id'))}
        with connection.cursor() as cursor:
            cursor.execute("SELECT COALESCE(sum(jsonb_array_length(payload->'policies')),0) FROM journal_operation")
            refs = int(cursor.fetchone()[0])
            cursor.execute('SHOW transaction_read_only')
            if cursor.fetchone() != ('on',):
                raise RuntimeError('AUDIT_NOT_READONLY')
        return {'status': 'PASS', 'database': identity[0], 'oid': identity[3],
            'scope': 'repeatable-read-readonly-state-v2-formula-not-head-lock-proof',
            'head': V.persistent_values(head), 'counts': counts, 'historicalReferences': refs,
            'stages': stages, 'stateDigestVersion': V.VERSION, 'stateDigest': hasher.hexdigest(),
            'schemaFingerprint': P.schema_fingerprint(), 'policyId': str(policy.pk),
            'policyDigest': policy.policy_digest, 'policySourceFingerprint': policy.policy['sourceFingerprint'],
            'actualSourceFingerprint': actual_source,
            'sourceMatchesPolicy': actual_source == policy.policy['sourceFingerprint'],
            'credentialConfigSha256': B._configuration_sha(), 'policy': policy.policy,
            'dataMutation': False, 'headLock': False}


try:
    print(json.dumps(main(), sort_keys=True))
except Exception as error:
    print(json.dumps({'status': 'FAIL', 'code': 'CAPACITY_READONLY_AUDIT_FAILED',
                      'errorClass': type(error).__name__}))
    raise SystemExit(1)
