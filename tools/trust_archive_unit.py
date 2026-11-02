"""Preserve the exact owned UNIT corpus by RENAME, never DROP or table reset.

Executed by the closed local wrapper in the existing init/tool role. Its stdin
entry point supplies ACTION and REFERENCE through a fixed Python launcher.
"""
import hashlib
import json
from pathlib import Path
import signal
import time
import uuid
import psycopg
from psycopg import sql

MAIN = 'estakada_trust'
UNIT = 'test_estakada_trust'
ARCHIVE = 'test_estakada_trust_cal_7e145c49'
TABLES = ['django_migrations', 'journal_credential', 'journal_head',
          'journal_operation', 'journal_requesttombstone', 'journal_routepolicy']


def ensure(value, code):
    if not value:
        raise RuntimeError(code)


def connect(database, *, readonly=False):
    ensure(database in (MAIN, UNIT, ARCHIVE), 'ARCHIVE_DATABASE_SCOPE')
    password = Path('/run/secrets/bootstrap-password').read_text(encoding='ascii').strip()
    ensure(len(password) == 96 and all(c in '0123456789abcdef' for c in password), 'ARCHIVE_SECRET_FORMAT')
    return psycopg.connect(host='trust-db', dbname=database, user='postgres', password=password,
                          sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
                          connect_timeout=3, autocommit=True,
                          options='-c statement_timeout=10000 -c lock_timeout=1000'
                                  + (' -c default_transaction_read_only=on' if readonly else ''))


def state(database):
    with connect(database, readonly=True) as conn:
        ensure(conn.execute('SELECT current_database(),current_user').fetchone() == (database, 'postgres'),
               'ARCHIVE_CONNECTION_IDENTITY')
        names = [row[0] for row in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='trust' ORDER BY tablename")]
        ensure(names == sorted(TABLES), 'ARCHIVE_SCHEMA_UNEXPECTED')
        digest = hashlib.sha256()
        counts = {}
        for table in TABLES:
            query = sql.SQL('SELECT row_to_json(t)::text FROM trust.{} t ORDER BY {}').format(
                sql.Identifier(table), sql.Identifier('request_id' if table == 'journal_requesttombstone'
                                                     else 'key' if table == 'journal_routepolicy' else 'id'))
            count = 0
            # Explicit read-only transaction permits a bounded server cursor.
            with conn.transaction():
                with conn.cursor(name='preserve_' + table) as cursor:
                    cursor.execute(query)
                    while rows := cursor.fetchmany(32):
                        for row in rows:
                            data = row[0].encode('utf-8')
                            digest.update(table.encode('ascii') + b'\0' + str(len(data)).encode() + b':' + data)
                            count += 1
            counts[table] = count
        head = conn.execute('SELECT incarnation::text,generation,writer_epoch,digest,logical_bytes,reserved_bytes '
                            'FROM trust.journal_head WHERE id=1').fetchone()
        ensure(head is not None, 'ARCHIVE_HEAD_MISSING')
        migrations = list(conn.execute('SELECT app,name FROM trust.django_migrations ORDER BY app,name'))
        ensure(migrations == [('journal', '0001_initial')], 'ARCHIVE_MIGRATION_SCOPE')
        oid = conn.execute('SELECT oid FROM pg_database WHERE datname=current_database()').fetchone()[0]
        return {'oid': oid, 'counts': counts, 'incarnation': head[0], 'generation': str(head[1]),
                'writerEpoch': str(head[2]), 'headDigest': head[3], 'logicalBytes': head[4],
                'reservedBytes': head[5], 'rowsSha256': digest.hexdigest()}


def check_original(value, expected):
    ensure(str(uuid.UUID(expected['incarnation'])) == expected['incarnation'], 'ARCHIVE_EXPECTED_IDENTITY')
    ensure(value['incarnation'] == expected['incarnation'] and value['generation'] == '121'
           and value['writerEpoch'] == '1' and value['logicalBytes'] == 66897420
           and value['reservedBytes'] == 0, 'ARCHIVE_COHORT_HEAD')
    ensure(value['counts'] == {'django_migrations': 1, 'journal_credential': 3, 'journal_head': 1,
                              'journal_operation': 60, 'journal_requesttombstone': 0,
                              'journal_routepolicy': 15360}, 'ARCHIVE_COHORT_COUNTS')
    ensure(expected['calibrationStatus'] == 'PASS' and expected['generation'] == value['generation'],
           'ARCHIVE_REFERENCE_MISMATCH')


def execute(action, reference):
    ensure(action in ('archive', 'verify'), 'ARCHIVE_ACTION_SCOPE')
    signal.alarm(60)
    with connect(MAIN) as control:
        ensure(control.execute('SELECT current_user').fetchone()[0] == 'postgres', 'ARCHIVE_OPERATOR_SCOPE')
        if action == 'archive':
            ensure(control.execute('SELECT 1 FROM pg_database WHERE datname=%s', [ARCHIVE]).fetchone() is None,
                   'ARCHIVE_ALREADY_EXISTS')
            original = control.execute('SELECT oid,datallowconn FROM pg_database WHERE datname=%s', [UNIT]).fetchone()
            ensure(original is not None and original[1], 'ARCHIVE_ORIGINAL_UNAVAILABLE')
            ensure(control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s',
                                   [original[0]]).fetchone()[0] == 0, 'ARCHIVE_HAS_ACTIVE_SESSION')
            before = state(UNIT)
            check_original(before, reference)
            # Wait only for our completed read connection to leave the catalog.
            for _ in range(20):
                if control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s',
                                   [before['oid']]).fetchone()[0] == 0:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError('ARCHIVE_HAS_ACTIVE_SESSION')
            control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(UNIT)))
            if control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s',
                               [before['oid']]).fetchone()[0] != 0:
                control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(UNIT)))
                raise RuntimeError('ARCHIVE_HAS_ACTIVE_SESSION')
            control.execute(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(
                sql.Identifier(UNIT), sql.Identifier(ARCHIVE)))
            control.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC,trust_runtime,trust_migrator').format(
                sql.Identifier(ARCHIVE)))
            control.execute(sql.SQL('ALTER DATABASE {} SET default_transaction_read_only=on').format(
                sql.Identifier(ARCHIVE)))
        else:
            before = reference['state']
            ensure(control.execute('SELECT oid FROM pg_database WHERE datname=%s', [ARCHIVE]).fetchone() ==
                   (before['oid'],), 'ARCHIVE_OID_CHANGED')
        control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(ARCHIVE)))
        try:
            after = state(ARCHIVE)
            ensure(after == before, 'ARCHIVE_ROW_STATE_CHANGED')
        finally:
            control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(ARCHIVE)))
        ensure(not control.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',
                                   [ARCHIVE]).fetchone()[0], 'ARCHIVE_NOT_CLOSED')
        if action == 'archive':
            ensure(control.execute('SELECT 1 FROM pg_database WHERE datname=%s', [UNIT]).fetchone() is None,
                   'FRESH_UNIT_NAME_TAKEN')
            control.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(UNIT)))
            with connect(UNIT, readonly=True) as fresh:
                ensure(fresh.execute("SELECT count(*) FROM pg_tables WHERE schemaname NOT IN "
                                     "('pg_catalog','information_schema')").fetchone()[0] == 0,
                       'FRESH_UNIT_NOT_EMPTY')
                new_oid = fresh.execute('SELECT oid FROM pg_database WHERE datname=current_database()').fetchone()[0]
                ensure(new_oid != before['oid'], 'FRESH_UNIT_OID_REUSED')
        else:
            new_oid = reference['freshUnitOid']
            ensure(control.execute('SELECT oid FROM pg_database WHERE datname=%s', [UNIT]).fetchone() ==
                   (new_oid,), 'FRESH_UNIT_OID_CHANGED')
    return {'status': 'PASS', 'archiveName': ARCHIVE, 'originalName': UNIT, 'state': after,
            'freshUnitOid': new_oid, 'sameArchiveOid': True, 'sameRowsDigest': True,
            'archiveConnectionsClosed': True, 'dropPerformed': False}


if __name__ == '__main__':
    try:
        result = execute(ACTION, REFERENCE)
    except Exception as error:
        # No database message, SQL, row or secret in the public result.
        code = str(error) if type(error) is RuntimeError else type(error).__name__
        if not code.replace('_', '').isalnum() or len(code) > 100:
            code = 'ARCHIVE_FAILED'
        print(json.dumps({'status': 'FAIL', 'errorClass': type(error).__name__,
                          'errorCode': code, 'dataPreserved': True}))
        raise SystemExit(1) from None
    print(json.dumps(result))
