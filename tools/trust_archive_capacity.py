"""Preserve the second exact TRUST corpus by fixed-name RENAME, never DROP.

All row reads use repeatable-read/read-only PostgreSQL transactions. Django is
configured for model metadata only: no project settings or ORM connection.
"""
import hashlib
import json
import re
import signal
import time
import uuid
from pathlib import Path

import psycopg
from psycopg import sql

MAIN = 'estakada_trust'
UNIT = 'test_estakada_trust'
LEGACY = 'test_estakada_trust_cal_7e145c49'
ARCHIVE = 'test_estakada_trust_cap_32563'
UNIT_OID = 32563
LEGACY_OID = 16387
SOURCE_SHA = '5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986'
UNIT_V2 = '116bb54a5d5d8cc5aa2ff6a4b593c51202aece6accff2421c47b525b9cc4c6b7'
MAIN_V2 = 'dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066'
SCHEMA_SHA = '4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7'
LEGACY_ROWS = '289e7b0f88c6add3e2ecebc4aa361eb62a0672ba3184c12812f87e7d766fb8d0'
LEGACY_TABLES = ['django_migrations', 'journal_credential', 'journal_head',
    'journal_operation', 'journal_requesttombstone', 'journal_routepolicy']
TABLES = sorted(LEGACY_TABLES + ['journal_recoveryreceipt', 'journal_admissionpolicy'])
UNIT_COUNTS = {'django_migrations': 3, 'journal_admissionpolicy': 1, 'journal_credential': 4,
    'journal_head': 1, 'journal_operation': 1000, 'journal_recoveryreceipt': 0,
    'journal_requesttombstone': 1024, 'journal_routepolicy': 4096}
MAIN_COUNTS = {**UNIT_COUNTS, 'journal_admissionpolicy': 0, 'journal_operation': 4,
    'journal_recoveryreceipt': 2, 'journal_requesttombstone': 1, 'journal_routepolicy': 3}
LEGACY_COUNTS = {'django_migrations': 1, 'journal_credential': 3, 'journal_head': 1,
    'journal_operation': 60, 'journal_requesttombstone': 0, 'journal_routepolicy': 15360}
MARKER_PREFIX = 'ESTAKADA-DEV15-CAPACITY:'
STATE_KEYS = {'oid', 'head', 'counts', 'rowsSha256', 'stateV2Sha256', 'schemaFingerprint'}
SUMMARY_KEYS = {'incarnation', 'generation', 'writerEpoch', 'digest', 'logicalBytes', 'reservedBytes'}
LEGACY_KEYS = {'oid', 'counts', 'incarnation', 'generation', 'writerEpoch', 'headDigest',
    'logicalBytes', 'reservedBytes', 'rowsSha256'}
REPORT_KEYS = {'status', 'scope', 'archiveName', 'originalName', 'legacyName', 'legacyState',
    'unitState', 'mainState', 'freshUnitOid', 'freshUnitMarker', 'archivesClosed',
    'dropPerformed', 'sameRowsDigest', 'sameArchiveOid'}


class ArchiveFailure(Exception):
    pass


def ensure(value, code):
    if not value: raise ArchiveFailure(code)


def closed(value, keys):
    ensure(type(value) is dict and set(value) == set(keys), 'CAP_ARCHIVE_REFERENCE_SHAPE')


def hex64(value):
    ensure(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'CAP_ARCHIVE_EXPECTED_DIGEST')


def uuid_value(value):
    ensure(type(value) is str and str(uuid.UUID(value)) == value, 'CAP_ARCHIVE_EXPECTED_UUID')


def valid_legacy(value):
    closed(value, LEGACY_KEYS)
    ensure(value['oid'] == LEGACY_OID and type(value['oid']) is int, 'CAP_ARCHIVE_LEGACY_EXPECTED_OID')
    uuid_value(value['incarnation']); hex64(value['headDigest'])
    ensure(value['counts'] == LEGACY_COUNTS and value['generation'] == '121'
        and value['writerEpoch'] == '1' and value['logicalBytes'] == 66897420
        and value['reservedBytes'] == 0 and value['rowsSha256'] == LEGACY_ROWS,
        'CAP_ARCHIVE_LEGACY_EXPECTED_STATE')


def valid_state(value, *, unit):
    closed(value, STATE_KEYS); closed(value['head'], SUMMARY_KEYS)
    if unit:
        ensure(type(value['oid']) is int and value['oid'] == UNIT_OID, 'CAP_ARCHIVE_EXPECTED_OID')
    else:
        ensure(type(value['oid']) is int and value['oid'] > 0
            and value['oid'] not in (UNIT_OID, LEGACY_OID), 'CAP_ARCHIVE_MAIN_EXPECTED_OID')
    uuid_value(value['head']['incarnation'])
    for key in ('rowsSha256', 'stateV2Sha256', 'schemaFingerprint'): hex64(value[key])
    hex64(value['head']['digest'])
    ensure(value['counts'] == (UNIT_COUNTS if unit else MAIN_COUNTS)
        and value['stateV2Sha256'] == (UNIT_V2 if unit else MAIN_V2)
        and value['schemaFingerprint'] == SCHEMA_SHA
        and value['head']['generation'] == ('2002' if unit else '9')
        and value['head']['writerEpoch'] == ('1' if unit else '2'), 'CAP_ARCHIVE_EXPECTED_COHORT')
    ensure(all(type(value['head'][key]) is int and value['head'][key] >= 0
        for key in ('logicalBytes', 'reservedBytes')), 'CAP_ARCHIVE_EXPECTED_BUDGET_TYPE')
    if unit:
        ensure(value['head']['logicalBytes'] == 30419077 and value['head']['reservedBytes'] == 0,
            'CAP_ARCHIVE_EXPECTED_BUDGET')


def valid_inspect(reference, *, full):
    closed(reference, {'intentId', 'sourceSha256', 'legacyState'} | ({'unit', 'main'} if full else set()))
    uuid_value(reference['intentId'])
    ensure(reference['sourceSha256'] == SOURCE_SHA, 'CAP_ARCHIVE_EXPECTED_SOURCE')
    valid_legacy(reference['legacyState'])
    if full:
        valid_state(reference['unit'], unit=True); valid_state(reference['main'], unit=False)
        ensure(reference['unit']['head']['incarnation'] == reference['main']['head']['incarnation']
            == reference['legacyState']['incarnation'], 'CAP_ARCHIVE_EXPECTED_INCARNATION')


def report_reference(value):
    closed(value, REPORT_KEYS)
    ensure(value['status'] == 'PASS' and value['scope'] == 'DEV15-CAPACITY-ARCHIVE'
        and value['archiveName'] == ARCHIVE and value['originalName'] == UNIT and value['legacyName'] == LEGACY
        and value['archivesClosed'] is True and value['dropPerformed'] is False
        and value['sameRowsDigest'] is True and value['sameArchiveOid'] is True,
        'CAP_ARCHIVE_RECEIPT_SHAPE')
    ensure(type(value['freshUnitMarker']) is str and value['freshUnitMarker'].startswith(MARKER_PREFIX),
        'CAP_ARCHIVE_FRESH_MARKER')
    intent = value['freshUnitMarker'][len(MARKER_PREFIX):]; uuid_value(intent)
    reference = {'intentId': intent, 'sourceSha256': SOURCE_SHA,
        'legacyState': value['legacyState'], 'unit': value['unitState'], 'main': value['mainState']}
    valid_inspect(reference, full=True)
    ensure(type(value['freshUnitOid']) is int and value['freshUnitOid'] > 0
        and value['freshUnitOid'] not in (UNIT_OID, LEGACY_OID, value['mainState']['oid']),
        'CAP_ARCHIVE_FRESH_EXPECTED_OID')
    return reference


def metadata():
    from django.conf import settings
    ensure(not settings.configured, 'CAP_ARCHIVE_SETTINGS_ALREADY_CONFIGURED')
    settings.configure(INSTALLED_APPS=['journal'], SECRET_KEY='metadata-only-not-a-site-secret',
        DATABASES={}, USE_TZ=True)
    import django
    django.setup()
    from journal import profile as P, state_v2 as V
    ensure(P.source_fingerprint() == SOURCE_SHA, 'CAP_ARCHIVE_SOURCE_DRIFT')
    return P, V


def connect(database, *, readonly=False):
    ensure(database in (MAIN, UNIT, LEGACY, ARCHIVE), 'CAP_ARCHIVE_DATABASE_SCOPE')
    password = Path('/run/secrets/bootstrap-password').read_text(encoding='ascii').strip()
    ensure(re.fullmatch('[0-9a-f]{96}', password) is not None, 'CAP_ARCHIVE_SECRET_FORMAT')
    return psycopg.connect(host='trust-db', dbname=database, user='postgres', password=password,
        sslmode='verify-full', sslrootcert='/run/secrets/database-ca', connect_timeout=3, autocommit=True,
        options='-c search_path=trust,pg_catalog -c lock_timeout=1000 -c statement_timeout=10000'
            + (' -c default_transaction_read_only=on' if readonly else ''))


def identity(conn, database):
    row = conn.execute('''SELECT current_database(),current_user,session_user,r.rolsuper,d.oid
        FROM pg_database d JOIN pg_roles r ON r.rolname=current_user WHERE d.datname=current_database()''').fetchone()
    ensure(row is not None and row[:4] == (database, 'postgres', 'postgres', True), 'CAP_ARCHIVE_ACTUAL_IDENTITY')
    ensure(conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone() == (True,),
        'CAP_ARCHIVE_ACTUAL_TLS')
    return row[4]


def catalog(control, name):
    return control.execute('SELECT oid,datallowconn,shobj_description(oid,\'pg_database\'),datdba FROM pg_database WHERE datname=%s',
        [name]).fetchone()


def sessions(control, oid, excluding=None):
    return control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s AND (%s::integer IS NULL OR pid<>%s)',
        [oid, excluding, excluding]).fetchone()[0]


def no_connect(control, name, *, migrator_allowed=False):
    row = catalog(control, name); ensure(row is not None, 'CAP_ARCHIVE_DATABASE_MISSING')
    public = control.execute('''SELECT EXISTS(SELECT 1 FROM pg_database d,
        LATERAL aclexplode(NULLIF(COALESCE(d.datacl,acldefault('d',d.datdba)),'{}'::aclitem[])) a
        WHERE d.datname=%s AND a.grantee=0 AND a.privilege_type='CONNECT')''', [name]).fetchone()[0]
    runtime, migrator = control.execute('SELECT has_database_privilege(\'trust_runtime\',%s,\'CONNECT\'),has_database_privilege(\'trust_migrator\',%s,\'CONNECT\')',
        [name, name]).fetchone()
    ensure(not public and not runtime and (migrator_allowed or not migrator), 'CAP_ARCHIVE_CONNECT_NOT_CLOSED')


def readonly_default(control, oid):
    row = control.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=%s AND setrole=0', [oid]).fetchone()
    ensure(row is not None and 'default_transaction_read_only=on' in row[0], 'CAP_ARCHIVE_NOT_DEFAULT_READONLY')


def raw_rows(conn, tables):
    names = [row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='trust' ORDER BY tablename")]
    ensure(names == sorted(tables), 'CAP_ARCHIVE_TABLE_SET')
    hasher = hashlib.sha256(); counts = {}
    for table in tables:
        key = 'request_id' if table == 'journal_requesttombstone' else 'key' if table == 'journal_routepolicy' else 'id'
        query = sql.SQL('SELECT row_to_json(t)::text FROM trust.{} t ORDER BY {}').format(sql.Identifier(table), sql.Identifier(key))
        count = 0
        with conn.cursor(name='capacity_raw_'+table) as cursor:
            cursor.execute(query)
            while rows := cursor.fetchmany(32):
                for row in rows:
                    raw = row[0].encode('utf-8')
                    hasher.update(table.encode('ascii')+b'\0'+str(len(raw)).encode('ascii')+b':'+raw)
                    count += 1
        counts[table] = count
    return counts, hasher.hexdigest()


def read_state(database, P, V, *, existing_conn=None, legacy=False):
    owned = existing_conn is None
    conn = connect(database, readonly=True) if owned else existing_conn
    try:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            oid = identity(conn, database)
            counts, rows_sha = raw_rows(conn, LEGACY_TABLES if legacy else TABLES)
            head = json.loads(conn.execute('SELECT row_to_json(t)::text FROM trust.journal_head t WHERE id=1').fetchone()[0])
            ensure(head['mode'] == 'ACTIVE', 'CAP_ARCHIVE_HEAD_MODE')
            if legacy:
                ensure(list(conn.execute('SELECT app,name FROM trust.django_migrations ORDER BY app,name'))
                    == [('journal', '0001_initial')], 'CAP_ARCHIVE_LEGACY_SCHEMA')
                return {'oid': oid, 'counts': counts, 'incarnation': head['incarnation'],
                    'generation': str(head['generation']), 'writerEpoch': str(head['writer_epoch']),
                    'headDigest': head['digest'], 'logicalBytes': head['logical_bytes'],
                    'reservedBytes': head['reserved_bytes'], 'rowsSha256': rows_sha}
            from journal.models import Head
            ensure(set(head) == {field.attname for field in Head._meta.concrete_fields}, 'CAP_ARCHIVE_HEAD_FIELDS')
            v2 = hashlib.sha256(V.DOMAIN)
            V._frame(v2, {'stateDigestVersion': V.VERSION, 'head': head})
            for model, limit in V.TABLES:
                fields = [field.attname for field in model._meta.concrete_fields]
                V._frame(v2, {'table': model._meta.db_table, 'fields': fields})
                query = sql.SQL('SELECT row_to_json(t)::text FROM trust.{} t ORDER BY {}').format(
                    sql.Identifier(model._meta.db_table), sql.Identifier(model._meta.pk.attname))
                count = 0
                with conn.cursor(name='capacity_v2_'+model._meta.db_table) as cursor:
                    cursor.execute(query)
                    while rows := cursor.fetchmany(1):
                        value = json.loads(rows[0][0]); count += 1
                        ensure(count <= limit and set(value) == set(fields), 'CAP_ARCHIVE_V2_BOUND')
                        V._frame(v2, value)
                V._frame(v2, {'count': count})
            original_connection = P.connection
            try:
                P.connection = conn
                schema_sha = P.schema_fingerprint()
            finally:
                P.connection = original_connection
            ensure(conn.execute('SHOW transaction_read_only').fetchone() == ('on',), 'CAP_ARCHIVE_READONLY_LOST')
            return {'oid': oid, 'head': {'incarnation': head['incarnation'], 'generation': str(head['generation']),
                'writerEpoch': str(head['writer_epoch']), 'digest': head['digest'],
                'logicalBytes': head['logical_bytes'], 'reservedBytes': head['reserved_bytes']},
                'counts': counts, 'rowsSha256': rows_sha, 'stateV2Sha256': v2.hexdigest(), 'schemaFingerprint': schema_sha}
    finally:
        if owned: conn.close()


def execute(arg, progress):
    closed(arg, {'action', 'reference'}); action = arg['action']; reference = arg['reference']
    ensure(action in ('inspect', 'archive', 'recover', 'verify'), 'CAP_ARCHIVE_ACTION_SCOPE')
    report_input = reference if action == 'verify' else None
    if action == 'verify': reference = report_reference(reference)
    else: valid_inspect(reference, full=action != 'inspect')
    # All reference/OID shape failures above precede every PostgreSQL connection.
    P, V = metadata(); progress['stage'] = 'CONTROL_CONNECT'
    control = connect(MAIN); original_closed = False
    def mutate(statement):
        progress['catalogMutationAttempted'] = True
        control.execute(statement)
    def fixed_oid(name, oid):
        row = catalog(control, name)
        ensure(row is not None and row[0] == oid, 'CAP_ARCHIVE_CATALOG_OID_CHANGED')
        return row
    def close_archive(name, oid):
        row = catalog(control, name)
        if row is not None and row[0] == oid and row[1]:
            mutate(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(name)))
    def wait_no_sessions(oid, code):
        # Only wait for completed owned reads to disappear; never cancel a PID.
        for _ in range(20):
            if sessions(control, oid) == 0: return
            time.sleep(0.05)
        raise ArchiveFailure(code)
    def archived_state(name, oid, *, legacy=False):
        row = fixed_oid(name, oid); no_connect(control, name); readonly_default(control, oid)
        ensure(sessions(control, oid) == 0, 'CAP_ARCHIVE_ARCHIVE_HAS_SESSION')
        try:
            if not row[1]: mutate(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(name)))
            return read_state(name, P, V, legacy=legacy)
        finally:
            close_archive(name, oid)
            wait_no_sessions(oid, 'CAP_ARCHIVE_ARCHIVE_HAS_SESSION')
    def legacy_state():
        value = archived_state(LEGACY, LEGACY_OID, legacy=True)
        ensure(value == reference['legacyState'], 'CAP_ARCHIVE_LEGACY_CHANGED')
        return value
    def main_state():
        value = read_state(MAIN, P, V); valid_state(value, unit=False)
        ensure(value['head']['incarnation'] == reference['legacyState']['incarnation'], 'CAP_ARCHIVE_MAIN_INCARNATION')
        if 'main' in reference: ensure(value == reference['main'], 'CAP_ARCHIVE_MAIN_CHANGED')
        return value
    def fresh(empty, expected_oid=None):
        row = catalog(control, UNIT)
        ensure(row is not None and row[0] not in (UNIT_OID, LEGACY_OID), 'CAP_ARCHIVE_FRESH_OID')
        ensure(row[2] == MARKER_PREFIX+reference['intentId'], 'CAP_ARCHIVE_FRESH_UNMARKED')
        if expected_oid is not None: ensure(row[0] == expected_oid, 'CAP_ARCHIVE_FRESH_OID_CHANGED')
        ensure(row[1] is True, 'CAP_ARCHIVE_FRESH_CLOSED')
        postgres_oid = control.execute("SELECT oid FROM pg_roles WHERE rolname='postgres'").fetchone()[0]
        ensure(row[3] == postgres_oid, 'CAP_ARCHIVE_FRESH_OWNER')
        no_connect(control, UNIT, migrator_allowed=not empty)
        if empty:
            with connect(UNIT, readonly=True) as conn:
                with conn.transaction():
                    conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
                    ensure(identity(conn, UNIT) == row[0], 'CAP_ARCHIVE_FRESH_ACTUAL_OID')
                    count = conn.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema' AND c.relkind IN ('r','p','v','m','f','S')").fetchone()[0]
                    ensure(count == 0, 'CAP_ARCHIVE_FRESH_NOT_EMPTY')
        return row[0], row[2]
    def stable_report(unit_state, main, legacy, fresh_oid, marker):
        for name, oid in ((ARCHIVE, UNIT_OID), (LEGACY, LEGACY_OID)):
            ensure(fixed_oid(name, oid)[1] is False, 'CAP_ARCHIVE_NOT_CLOSED')
            no_connect(control, name); readonly_default(control, oid)
        return {'status': 'PASS', 'scope': 'DEV15-CAPACITY-ARCHIVE', 'archiveName': ARCHIVE,
            'originalName': UNIT, 'legacyName': LEGACY, 'legacyState': legacy, 'unitState': unit_state,
            'mainState': main, 'freshUnitOid': fresh_oid, 'freshUnitMarker': marker,
            'archivesClosed': True, 'dropPerformed': False, 'sameRowsDigest': True, 'sameArchiveOid': True}
    try:
        identity(control, MAIN)
        if action == 'inspect':
            progress['stage'] = 'INSPECT'
            row = fixed_oid(UNIT, UNIT_OID); ensure(row[1] is True, 'CAP_ARCHIVE_UNIT_UNAVAILABLE')
            ensure(catalog(control, ARCHIVE) is None, 'CAP_ARCHIVE_ALREADY_EXISTS')
            unit = read_state(UNIT, P, V); valid_state(unit, unit=True)
            main = main_state(); legacy = legacy_state()
            ensure(unit['head']['incarnation'] == legacy['incarnation'], 'CAP_ARCHIVE_UNIT_INCARNATION')
            return {'status': 'PASS', 'scope': 'DEV15-CAPACITY-INSPECT',
                'reference': {**reference, 'unit': unit, 'main': main}}
        if action == 'archive':
            progress['stage'] = 'PREPARE_ARCHIVE'
            ensure(catalog(control, ARCHIVE) is None, 'CAP_ARCHIVE_ALREADY_EXISTS')
            original = fixed_oid(UNIT, UNIT_OID); ensure(original[1] is True, 'CAP_ARCHIVE_UNIT_UNAVAILABLE')
            ensure(sessions(control, UNIT_OID) == 0, 'CAP_ARCHIVE_ACTIVE_SESSION')
            main = main_state(); legacy_state()
            progress['stage'] = 'FINAL_DRAINED_HASH'
            with connect(UNIT, readonly=True) as own:
                own_pid = own.execute('SELECT pg_backend_pid()').fetchone()[0]
                ensure(identity(own, UNIT) == UNIT_OID, 'CAP_ARCHIVE_ACTUAL_UNIT_OID')
                ensure(sessions(control, UNIT_OID, own_pid) == 0, 'CAP_ARCHIVE_ACTIVE_SESSION')
                # Keep our read-only connection; no new client may enter now.
                original_closed = True
                mutate(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(UNIT)))
                ensure(sessions(control, UNIT_OID, own_pid) == 0, 'CAP_ARCHIVE_ACTIVE_SESSION')
                drained = read_state(UNIT, P, V, existing_conn=own)
                ensure(drained == reference['unit'], 'CAP_ARCHIVE_DRAINED_STATE_CHANGED')
            wait_no_sessions(UNIT_OID, 'CAP_ARCHIVE_ACTIVE_SESSION')
            progress['stage'] = 'RENAME'
            mutate(sql.SQL('ALTER DATABASE {} RENAME TO {}').format(sql.Identifier(UNIT), sql.Identifier(ARCHIVE)))
            mutate(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC,trust_runtime,trust_migrator').format(sql.Identifier(ARCHIVE)))
            mutate(sql.SQL('ALTER DATABASE {} SET default_transaction_read_only=on').format(sql.Identifier(ARCHIVE)))
            progress['stage'] = 'VERIFY_ARCHIVE'
            unit = archived_state(ARCHIVE, UNIT_OID)
            ensure(unit == reference['unit'], 'CAP_ARCHIVE_ROWS_CHANGED')
            ensure(catalog(control, UNIT) is None, 'CAP_ARCHIVE_FRESH_NAME_TAKEN')
            progress['stage'] = 'CREATE_FRESH'
            mutate(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(UNIT)))
            mutate(sql.SQL('COMMENT ON DATABASE {} IS {}').format(sql.Identifier(UNIT), sql.Literal(MARKER_PREFIX+reference['intentId'])))
            mutate(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC,trust_runtime,trust_migrator').format(sql.Identifier(UNIT)))
            fresh_oid, marker = fresh(True)
            progress['stage'] = 'FINAL_VERIFY'
            return stable_report(unit, main_state(), legacy_state(), fresh_oid, marker)
        progress['stage'] = 'READ_COMPLETED_ARCHIVE'
        ensure(catalog(control, ARCHIVE) is not None, 'CAP_ARCHIVE_NOT_COMPLETED')
        unit = archived_state(ARCHIVE, UNIT_OID)
        ensure(unit == reference['unit'], 'CAP_ARCHIVE_ROWS_CHANGED')
        main = main_state(); legacy = legacy_state()
        fresh_oid, marker = fresh(action == 'recover', report_input['freshUnitOid'] if report_input else None)
        result = stable_report(unit, main, legacy, fresh_oid, marker)
        if report_input is not None: ensure(result == report_input, 'CAP_ARCHIVE_REPORT_CHANGED')
        return result
    finally:
        # Never adopt, rename or remove an unknown database during cleanup.
        cleanup_failed = False
        for name, oid in ((ARCHIVE, UNIT_OID), (LEGACY, LEGACY_OID)):
            try:
                close_archive(name, oid)
            except BaseException:
                cleanup_failed = True
        try:
            row = catalog(control, UNIT)
            if original_closed and row is not None and row[0] == UNIT_OID and not row[1]:
                mutate(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(UNIT)))
        except BaseException:
            cleanup_failed = True
        finally:
            control.close()
        if cleanup_failed:
            progress['cleanupFailed'] = True
            raise ArchiveFailure('CAP_ARCHIVE_CLEANUP_FAILED') from None


def main():
    progress = {'stage': 'REFERENCE_VALIDATION', 'catalogMutationAttempted': False, 'cleanupFailed': False}
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(ArchiveFailure('CAP_ARCHIVE_DEADLINE')))
    signal.alarm(120)
    try:
        result = execute(globals().get('ARG'), progress)
    except BaseException as error:
        code = error.args[0] if isinstance(error, ArchiveFailure) and error.args else 'CAP_ARCHIVE_FAILED'
        result = {'status': 'FAIL', 'errorCode': code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}', code)
            else 'CAP_ARCHIVE_FAILED', 'errorClass': type(error).__name__, **progress,
            'dataMutation': 'NOT_ASSERTED' if progress['catalogMutationAttempted'] else False,
            'journalRowWrites': False, 'dropPerformed': False}
    finally:
        signal.alarm(0)
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
