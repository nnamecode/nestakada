"""Private, bounded, read-only MAIN fixture for LG15; never print publicly."""
import hashlib
import json
import re
import signal
from pathlib import Path

import psycopg
from psycopg import sql

SOURCE = '014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672'
SCHEMA = '4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7'
MAIN_V2 = 'dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'
LIMIT = 65536


class ExportFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise ExportFailure(code)


def main():
    report = {'status': 'FAIL', 'scope': 'LG15-private-main-fixture'}
    def expire(*_):
        raise ExportFailure('LG_EXPORT_DEADLINE')
    signal.signal(signal.SIGALRM, expire); signal.alarm(60)
    try:
        ensure(globals().get('ARG') == {}, 'LG_EXPORT_ARGUMENT')
        from django.conf import settings
        ensure(not settings.configured, 'LG_EXPORT_SETTINGS_ALREADY_CONFIGURED')
        settings.configure(INSTALLED_APPS=['journal'], DATABASES={},
            SECRET_KEY='metadata-only-not-a-site-secret', USE_TZ=True)
        import django
        django.setup()
        from journal import profile as P, state_v2 as V
        from journal.models import Head
        from journal.protocol import canonical, digest
        ensure(P.source_fingerprint() == SOURCE, 'LG_EXPORT_SOURCE')
        password = Path('/run/secrets/bootstrap-password').read_text(encoding='ascii').strip()
        ensure(re.fullmatch('[0-9a-f]{96}', password) is not None, 'LG_EXPORT_SECRET_FORMAT')
        with psycopg.connect(host='trust-db', dbname='estakada_trust', user='postgres',
                password=password, sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
                connect_timeout=3, autocommit=True, options='-c search_path=trust,pg_catalog '
                '-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=1000') as conn:
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                identity = conn.execute('''SELECT current_database(),current_user,session_user,d.oid,
                    pg_get_userbyid(d.datdba),r.rolsuper FROM pg_database d JOIN pg_roles r
                    ON r.rolname=current_user WHERE d.datname=current_database()''').fetchone()
                ensure(identity == ('estakada_trust', 'postgres', 'postgres', 16384, 'postgres', True),
                    'LG_EXPORT_ACTUAL_IDENTITY')
                ensure(conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone()
                    == (True,), 'LG_EXPORT_TLS')
                previous = P.connection
                try:
                    P.connection = conn
                    ensure(P.schema_fingerprint() == SCHEMA, 'LG_EXPORT_SCHEMA')
                finally:
                    P.connection = previous
                tables = {}
                for model in (Head, *(model for model, _ in V.TABLES)):
                    fields = {field.attname for field in model._meta.concrete_fields}
                    query = sql.SQL('SELECT row_to_json(t) FROM {} t ORDER BY {}').format(
                        sql.Identifier(model._meta.db_table), sql.Identifier(model._meta.pk.column))
                    rows = []
                    for (row,) in conn.execute(query):
                        ensure(type(row) is dict and set(row) == fields, 'LG_EXPORT_ROW_SHAPE')
                        rows.append(row)
                        ensure(len(canonical({**tables, model._meta.db_table: rows})) < LIMIT,
                            'LG_EXPORT_TOO_LARGE')
                    tables[model._meta.db_table] = rows
                expected = {'journal_head': 1, 'journal_credential': 4, 'journal_operation': 4,
                    'journal_routepolicy': 3, 'journal_requesttombstone': 1,
                    'journal_recoveryreceipt': 2, 'journal_admissionpolicy': 0}
                counts = {name: len(rows) for name, rows in tables.items()}
                ensure(counts == expected, 'LG_EXPORT_COUNTS')
                head = tables['journal_head'][0]
                ensure(head['generation'] == 9 and head['writer_epoch'] == 2
                    and head['mode'] == 'ACTIVE' and head['plan_id'] is not None, 'LG_EXPORT_HEAD')
                hasher = hashlib.sha256(V.DOMAIN)
                V._frame(hasher, {'stateDigestVersion': 2, 'head': head})
                for model, maximum in V.TABLES:
                    rows = tables[model._meta.db_table]
                    ensure(len(rows) <= maximum, 'LG_EXPORT_V2_BOUND')
                    V._frame(hasher, {'table': model._meta.db_table,
                        'fields': [field.attname for field in model._meta.concrete_fields]})
                    for row in rows:
                        V._frame(hasher, row)
                    V._frame(hasher, {'count': len(rows)})
                ensure(hasher.hexdigest() == MAIN_V2, 'LG_EXPORT_STATE')
                references = sum(len(row['payload']['policies']) for row in tables['journal_operation'])
                snapshot = {'database': 'estakada_trust', 'oid': 16384,
                    'sourceFingerprint': SOURCE, 'schemaFingerprint': SCHEMA,
                    'stateDigestVersion': 2, 'stateDigest': MAIN_V2, 'tables': tables,
                    'counts': counts, 'historicalReferences': references}
                result = {'status': 'PASS', 'scope': report['scope'],
                    'snapshot': snapshot, 'snapshotSha256': digest(snapshot)}
                ensure(len(canonical(result)) <= LIMIT, 'LG_EXPORT_TOO_LARGE')
                report = result
    except Exception as exc:
        code = str(exc) if isinstance(exc, ExportFailure) else getattr(exc, 'code', 'LG_EXPORT_FAILED')
        report = {'status': 'FAIL', 'scope': report['scope'], 'errorClass': type(exc).__name__,
            'errorCode': code if re.fullmatch('[A-Z0-9_]{1,80}', str(code)) else 'LG_EXPORT_FAILED'}
    finally:
        signal.alarm(0)
    print(json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
