"""Temporary, reversible archived-corpus SQL access for the fixed TLS snapshot.

No new roles, direct catalog writes or MAIN journal changes. ACL comparison
normalizes NULL/default ACL storage while retaining both raw catalog witnesses.
GLOBAL ARG is supplied by the existing guarded bootstrap-tool launcher.
"""
import copy
import hashlib
import json
import re
import signal
from pathlib import Path

import psycopg
from psycopg import sql

DATABASE = 'test_estakada_trust_cap_32563'
DATABASE_OID = 32563
ROLE = 'trust_runtime'
SCHEMA = 'trust'
READ_TABLES = {'journal_head', 'journal_credential', 'journal_routepolicy', 'journal_requesttombstone'}
JOURNAL_TABLES = READ_TABLES | {'journal_operation', 'journal_recoveryreceipt', 'journal_admissionpolicy'}
SNAPSHOT_SCOPE = 'ARCHIVE_RUNTIME_SNAPSHOT_ACL'
GRANT_SCOPE = 'ARCHIVE_RUNTIME_SNAPSHOT_GRANT'
TABLE_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER', 'MAINTAIN')
COLUMN_PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES')


class AccessFailure(Exception):
    pass


def ensure(value, code):
    if not value:
        raise AccessFailure(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def closed(value, keys):
    ensure(type(value) is dict and set(value) == set(keys), 'READ_ACCESS_INPUT_REJECTED')


def secret(name):
    value = (Path('/run/secrets') / name).read_text(encoding='ascii').strip()
    ensure(len(value) == 96 and re.fullmatch('[0-9a-f]{96}', value) is not None, 'READ_ACCESS_SECRET_CONFIGURATION')
    return value


def connect(runtime=False):
    return psycopg.connect(host='trust-db', dbname=DATABASE,
        user=ROLE if runtime else 'postgres',
        password=secret('runtime-password' if runtime else 'bootstrap-password'),
        sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
        connect_timeout=3, autocommit=True,
        options='-c lock_timeout=500ms -c statement_timeout=2s -c idle_in_transaction_session_timeout=3s -c default_transaction_read_only=off')


def identity(conn):
    row = conn.execute('''SELECT current_database(),current_user,session_user,d.oid,r.rolsuper
        FROM pg_database d JOIN pg_roles r ON r.rolname=current_user WHERE d.datname=current_database()''').fetchone()
    ensure(row == (DATABASE, 'postgres', 'postgres', DATABASE_OID, True), 'READ_ACCESS_ACTUAL_IDENTITY')


def snapshot(conn):
    identity(conn)
    role = conn.execute('''SELECT oid,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin
        FROM pg_roles WHERE rolname=%s''', [ROLE]).fetchone()
    ensure(role is not None and not any(role[1:6]) and role[6] is True, 'READ_ACCESS_ROLE_FLAGS')
    membership = conn.execute('SELECT roleid,member,grantor,admin_option FROM pg_auth_members WHERE member=%s OR roleid=%s ORDER BY roleid,member,grantor',
        [role[0], role[0]]).fetchall()
    ensure(not membership, 'READ_ACCESS_ROLE_MEMBERSHIP')
    database = conn.execute('SELECT oid,datdba,datacl::text[] FROM pg_database WHERE datname=%s', [DATABASE]).fetchone()
    schema = conn.execute('SELECT oid,nspowner,nspacl::text[] FROM pg_namespace WHERE nspname=%s', [SCHEMA]).fetchone()
    ensure(schema is not None and database[1] != role[0] and schema[1] != role[0], 'READ_ACCESS_OWNERSHIP')
    relations = conn.execute('''SELECT c.oid,c.relname,c.relowner,c.relkind,c.relacl::text[]
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname=%s AND c.relkind IN ('r','p','v','m','f','S') ORDER BY c.relname''', [SCHEMA]).fetchall()
    names = {row[1] for row in relations}
    ensure(JOURNAL_TABLES <= names and names <= JOURNAL_TABLES | {'django_migrations', 'django_migrations_id_seq'}
        and all(row[2] != role[0] for row in relations), 'READ_ACCESS_RELATION_SET')
    def entries(expression, parameters, kind=None, owner=None):
        if kind is None:
            # aclexplode rejects a zero-dimensional empty array; NULL emits no rows.
            query = sql.SQL('SELECT grantor,grantee,privilege_type,is_grantable FROM aclexplode(NULLIF({},\'{{}}\'::aclitem[])) ORDER BY grantor,grantee,privilege_type,is_grantable').format(expression)
            return [list(row) for row in conn.execute(query, parameters).fetchall()]
        query = sql.SQL('SELECT grantor,grantee,privilege_type,is_grantable FROM aclexplode(NULLIF(COALESCE({},acldefault(%s::"char",%s)),\'{{}}\'::aclitem[])) ORDER BY grantor,grantee,privilege_type,is_grantable').format(expression)
        return [list(row) for row in conn.execute(query, [*parameters, kind, owner]).fetchall()]
    normalized = {'database': {'oid': database[0], 'owner': database[1],
        'entries': entries(sql.SQL('(SELECT datacl FROM pg_database WHERE oid=%s)'), [database[0]], 'd', database[1])},
        'schema': {'oid': schema[0], 'owner': schema[1],
            'entries': entries(sql.SQL('(SELECT nspacl FROM pg_namespace WHERE oid=%s)'), [schema[0]], 'n', schema[1])},
        'relations': {}, 'runtimeRole': {'oid': role[0], 'flags': list(role[1:]), 'memberships': []}}
    raw = {'database': database[2], 'schema': schema[2], 'relations': {}}
    privileges = {'database': {name: conn.execute('SELECT has_database_privilege(%s,%s,%s)',
        [ROLE, DATABASE, name]).fetchone()[0] for name in ('CONNECT', 'CREATE', 'TEMPORARY')},
        'schema': {name: conn.execute('SELECT has_schema_privilege(%s,%s,%s)',
        [ROLE, SCHEMA, name]).fetchone()[0] for name in ('USAGE', 'CREATE')}, 'relations': {}}
    for oid, name, owner, kind, acl in relations:
        normalized['relations'][name] = {'oid': oid, 'owner': owner, 'kind': kind,
            # pg_class relkind='S', but acldefault uses lowercase 's' for sequences.
            'entries': entries(sql.SQL('(SELECT relacl FROM pg_class WHERE oid=%s)'), [oid], 's' if kind == 'S' else 'r', owner),
            'columns': {}}
        raw['relations'][name] = {'acl': acl, 'columns': {}}
        if kind == 'S':
            privileges['relations'][name] = {'kind': kind, 'sequence': {privilege:
                conn.execute('SELECT has_sequence_privilege(%s,%s,%s)', [ROLE, oid, privilege]).fetchone()[0]
                for privilege in ('USAGE', 'SELECT', 'UPDATE')}}
            continue
        privileges['relations'][name] = {'kind': kind, 'table': {privilege:
            conn.execute('SELECT has_table_privilege(%s,%s,%s)', [ROLE, oid, privilege]).fetchone()[0]
            for privilege in TABLE_PRIVILEGES}, 'columns': {}}
        columns = conn.execute('SELECT attnum,attname,attacl::text[] FROM pg_attribute WHERE attrelid=%s AND attnum>0 AND NOT attisdropped ORDER BY attnum', [oid]).fetchall()
        for number, column, column_acl in columns:
            normalized['relations'][name]['columns'][column] = entries(
                sql.SQL('(SELECT attacl FROM pg_attribute WHERE attrelid=%s AND attnum=%s)'), [oid, number])
            raw['relations'][name]['columns'][column] = column_acl
            privileges['relations'][name]['columns'][column] = {privilege:
                conn.execute('SELECT has_column_privilege(%s,%s,%s,%s)', [ROLE, oid, number, privilege]).fetchone()[0]
                for privilege in COLUMN_PRIVILEGES}
    return {'schemaVersion': 1, 'scope': SNAPSHOT_SCOPE, 'database': DATABASE, 'oid': DATABASE_OID,
        'role': ROLE, 'schema': SCHEMA, 'normalizedAcl': normalized, 'normalizedAclSha256': digest(normalized),
        'rawAcl': raw, 'rawAclSha256': digest(raw), 'runtimePrivileges': privileges,
        'runtimePrivilegesSha256': digest(privileges)}


def validate_token(value):
    closed(value, {'schemaVersion', 'scope', 'database', 'oid', 'role', 'schema', 'normalizedAcl',
        'normalizedAclSha256', 'rawAcl', 'rawAclSha256', 'runtimePrivileges', 'runtimePrivilegesSha256'})
    ensure(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
        and value['scope'] == SNAPSHOT_SCOPE and value['database'] == DATABASE
        and value['oid'] == DATABASE_OID and value['role'] == ROLE and value['schema'] == SCHEMA
        and digest(value['normalizedAcl']) == value['normalizedAclSha256']
        and digest(value['rawAcl']) == value['rawAclSha256']
        and digest(value['runtimePrivileges']) == value['runtimePrivilegesSha256'], 'READ_ACCESS_REFERENCE_REJECTED')
    return value


def privilege_shape(value, granted):
    p = value['runtimePrivileges']
    if p['database'] != {'CONNECT': granted, 'CREATE': False, 'TEMPORARY': False}:
        return False
    if p['schema'] != {'USAGE': granted, 'CREATE': False}:
        return False
    for name, relation in p['relations'].items():
        if relation['kind'] == 'S':
            if any(relation['sequence'].values()): return False
            continue
        for privilege, enabled in relation['table'].items():
            if enabled is not (granted and name in READ_TABLES and privilege == 'SELECT'):
                return False
        for column, rights in relation['columns'].items():
            for privilege, enabled in rights.items():
                expected = granted and ((name in READ_TABLES and privilege == 'SELECT')
                    or (name == 'journal_head' and column == 'id' and privilege == 'UPDATE'))
                if enabled is not expected: return False
    return True


def same_baseline(current, baseline):
    return (current['normalizedAclSha256'] == baseline['normalizedAclSha256']
        and current['runtimePrivilegesSha256'] == baseline['runtimePrivilegesSha256']
        and privilege_shape(current, False))


def proper_grant(current, baseline):
    if not privilege_shape(baseline, False) or not privilege_shape(current, True):
        return False
    reduced = copy.deepcopy(current['normalizedAcl'])
    runtime_oid = reduced['runtimeRole']['oid']
    def strip(entries, allowed, owner):
        return [row for row in entries if not (row[0] == owner and row[1] == runtime_oid
            and row[2] in allowed and row[3] is False)]
    reduced['database']['entries'] = strip(reduced['database']['entries'], {'CONNECT'}, reduced['database']['owner'])
    reduced['schema']['entries'] = strip(reduced['schema']['entries'], {'USAGE'}, reduced['schema']['owner'])
    for name in READ_TABLES:
        reduced['relations'][name]['entries'] = strip(reduced['relations'][name]['entries'], {'SELECT'},
            reduced['relations'][name]['owner'])
    reduced['relations']['journal_head']['columns']['id'] = strip(
        reduced['relations']['journal_head']['columns']['id'], {'UPDATE'},
        reduced['relations']['journal_head']['owner'])
    return digest(reduced) == baseline['normalizedAclSha256']


def baseline_from(reference):
    if type(reference) is dict and reference.get('scope') == GRANT_SCOPE:
        closed(reference, {'schemaVersion', 'scope', 'baseline', 'granted'})
        ensure(type(reference['schemaVersion']) is int and reference['schemaVersion'] == 1, 'READ_ACCESS_REFERENCE_REJECTED')
        baseline = validate_token(reference['baseline']); granted = validate_token(reference['granted'])
        ensure(proper_grant(granted, baseline), 'READ_ACCESS_GRANT_REFERENCE_REJECTED')
        return baseline
    return validate_token(reference)


def no_runtime_sessions(conn):
    active = conn.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND usename=%s', [DATABASE, ROLE]).fetchone()[0]
    ensure(active == 0, 'READ_ACCESS_RUNTIME_STILL_CONNECTED')


def targeted_revoke(conn):
    conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(sql.Identifier(DATABASE), sql.Identifier(ROLE)))
    conn.execute(sql.SQL('REVOKE USAGE ON SCHEMA {} FROM {}').format(sql.Identifier(SCHEMA), sql.Identifier(ROLE)))
    for table in sorted(READ_TABLES):
        conn.execute(sql.SQL('REVOKE SELECT ON TABLE {}.{} FROM {}').format(
            sql.Identifier(SCHEMA), sql.Identifier(table), sql.Identifier(ROLE)))
    conn.execute(sql.SQL('REVOKE UPDATE (id) ON TABLE {}.journal_head FROM {}').format(sql.Identifier(SCHEMA), sql.Identifier(ROLE)))


def restore(conn, baseline):
    with conn.transaction():
        conn.execute('SELECT pg_advisory_xact_lock(374012)')
        no_runtime_sessions(conn)
        current = snapshot(conn)
        ensure(same_baseline(current, baseline) or proper_grant(current, baseline), 'READ_ACCESS_RESTORE_STATE_REJECTED')
        if not same_baseline(current, baseline):
            targeted_revoke(conn)
        result = snapshot(conn)
        ensure(same_baseline(result, baseline), 'READ_ACCESS_RESTORE_MISMATCH')
    return result


def runtime_checks():
    with connect(runtime=True) as runtime:
        row = runtime.execute('SELECT current_database(),current_user,session_user').fetchone()
        ensure(row == (DATABASE, ROLE, ROLE), 'READ_ACCESS_RUNTIME_IDENTITY')
        ensure(runtime.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone() == (True,),
            'READ_ACCESS_RUNTIME_TLS')
        with runtime.transaction(force_rollback=True):
            ensure(runtime.execute('SELECT id FROM trust.journal_head WHERE id=1 FOR UPDATE').fetchall() == [(1,)],
                'READ_ACCESS_RUNTIME_ROWLOCK')
        for query in ('UPDATE trust.journal_head SET mode=mode WHERE id=1',
                      'INSERT INTO trust.journal_head (id) VALUES (1)'):
            try:
                with runtime.transaction(force_rollback=True):
                    runtime.execute(query)
            except psycopg.errors.InsufficientPrivilege:
                continue
            raise AccessFailure('READ_ACCESS_RUNTIME_WRITE_NOT_DENIED')
    return {'runtimeSslRowLockRollback': True, 'deniedHeadModeUpdate': True,
        'deniedHeadInsert': True, 'headIdUpdateExecuted': False}


# D-384: retain database default readonly=on; only these operator/rowlock
# connections use session readonly=off. There is no ALTER DATABASE/ROLE SET.
def control_connect():
    return psycopg.connect(host='trust-db', dbname='estakada_trust', user='postgres',
        password=secret('bootstrap-password'), sslmode='verify-full',
        sslrootcert='/run/secrets/database-ca', connect_timeout=3, autocommit=True,
        options='-c lock_timeout=500ms -c statement_timeout=2s -c default_transaction_read_only=off')


def catalog(control):
    ensure(control.execute('SELECT current_database(),current_user,session_user').fetchone()
        == ('estakada_trust','postgres','postgres'), 'WORKER_ACCESS_CONTROL_IDENTITY')
    row = control.execute("""SELECT d.oid,d.datallowconn,COALESCE(
        (SELECT 'default_transaction_read_only=on'=ANY(s.setconfig) FROM pg_db_role_setting s
         WHERE s.setdatabase=d.oid AND s.setrole=0),false)
        FROM pg_database d WHERE d.datname=%s""",[DATABASE]).fetchone()
    ensure(row is not None and row[0]==DATABASE_OID and row[2] is True,
        'WORKER_ACCESS_ARCHIVE_IDENTITY')
    return {'database':DATABASE,'oid':row[0],'allowConnections':row[1],'defaultReadonly':True}


def no_sessions(control):
    ensure(control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s',
        [DATABASE_OID]).fetchone()==(0,), 'WORKER_ACCESS_ARCHIVE_HAS_SESSION')


def set_open(control, value):
    catalog(control)
    control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS {}').format(
        sql.Identifier(DATABASE),sql.SQL('true' if value else 'false')))


def baseline_value(value):
    closed(value,{'scope','catalog','acl'})
    ensure(value['scope']=='DEV15-WORKER-TLS-BASELINE'
        and value['catalog']=={'database':DATABASE,'oid':DATABASE_OID,
            'allowConnections':False,'defaultReadonly':True}, 'WORKER_ACCESS_BASELINE_CATALOG')
    validate_token(value['acl'])
    ensure(privilege_shape(value['acl'],False), 'WORKER_ACCESS_BASELINE_PRIVILEGES')
    return value


def main():
    result={'status':'FAIL','scope':'DEV15-WORKER-TLS-ACCESS','reference':None,
        'journalRowWrites':False,'databaseDefaultChanged':False}
    baseline=None; grant_possible=False; success_grant=False; control=None
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(AccessFailure('WORKER_ACCESS_DEADLINE')))
    signal.alarm(90)
    try:
        arg=globals().get('ARG');closed(arg,{'action','reference'})
        action=arg['action'];ensure(action in ('baseline','grant','restore'),'WORKER_ACCESS_ACTION')
        result['action']=action
        if action!='baseline':baseline=baseline_value(arg['reference']);result['reference']=baseline
        else:ensure(arg['reference'] is None,'WORKER_ACCESS_REFERENCE')
        control=control_connect();before=catalog(control);no_sessions(control)
        if action in ('baseline','grant'):
            ensure(before['allowConnections'] is False,'WORKER_ACCESS_ARCHIVE_NOT_CLOSED')
            ordinary=control.execute("SELECT has_database_privilege('trust_runtime',%s,'CONNECT'),has_database_privilege('trust_migrator',%s,'CONNECT')",[DATABASE,DATABASE]).fetchone()
            public=control.execute("SELECT EXISTS(SELECT 1 FROM pg_database d,LATERAL aclexplode(NULLIF(COALESCE(d.datacl,acldefault('d',d.datdba)),'{}'::aclitem[])) a WHERE d.datname=%s AND a.grantee=0 AND a.privilege_type='CONNECT')",[DATABASE]).fetchone()[0]
            ensure(ordinary==(False,False) and public is False,'WORKER_ACCESS_ORDINARY_CONNECT_OPEN')
        set_open(control,True)
        with connect() as conn:
            if action=='baseline':
                value=snapshot(conn);ensure(privilege_shape(value,False),'WORKER_ACCESS_BASELINE_NOT_CLOSED')
                baseline={'scope':'DEV15-WORKER-TLS-BASELINE','catalog':before,'acl':value}
                result.update(reference=baseline,status='PASS')
            elif action=='grant':
                with conn.transaction():
                    current=snapshot(conn)
                    ensure(same_baseline(current,baseline['acl'])
                        and current['rawAclSha256']==baseline['acl']['rawAclSha256'],'WORKER_ACCESS_BASELINE_DRIFT')
                    grant_possible=True
                    conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(DATABASE),sql.Identifier(ROLE)))
                    conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(SCHEMA),sql.Identifier(ROLE)))
                    for table in sorted(READ_TABLES):
                        conn.execute(sql.SQL('GRANT SELECT ON TABLE {}.{} TO {}').format(sql.Identifier(SCHEMA),sql.Identifier(table),sql.Identifier(ROLE)))
                    conn.execute(sql.SQL('GRANT UPDATE (id) ON TABLE {}.journal_head TO {}').format(sql.Identifier(SCHEMA),sql.Identifier(ROLE)))
                    granted=snapshot(conn);ensure(proper_grant(granted,baseline['acl']),'WORKER_ACCESS_NOT_MINIMAL')
                controls=runtime_checks()
                ensure(catalog(control)['defaultReadonly'] is True,'WORKER_ACCESS_DEFAULT_CHANGED')
                success_grant=True
                result.update(status='PASS',reference=baseline,controls=controls,
                    grantedAclSha256=granted['normalizedAclSha256'],temporaryGrantActive=True)
            else:
                restored=restore(conn,baseline['acl'])
                result.update(status='PASS',reference=baseline,restored=True,effectiveBaselineEqual=True,
                    rawCatalogEqual=restored['rawAclSha256']==baseline['acl']['rawAclSha256'],
                    restoredRawAcl=restored['rawAcl'],restoredRawAclSha256=restored['rawAclSha256'])
    except BaseException as error:
        code=error.args[0] if isinstance(error,AccessFailure) and error.args else 'WORKER_ACCESS_FAILED'
        result.update(status='FAIL',errorCode=code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}',code)
            else 'WORKER_ACCESS_FAILED',errorClass=type(error).__name__)
        if grant_possible and baseline is not None:
            try:
                with connect() as conn:restored=restore(conn,baseline['acl'])
                result.update(reference=baseline,restored=True,effectiveBaselineEqual=True,
                    restoredRawAclSha256=restored['rawAclSha256'])
            except BaseException:result.update(restored=False,restoreErrorCode='WORKER_ACCESS_RESTORE_FAILED')
    finally:
        signal.alarm(0)
        if control is not None:
            try:
                if not success_grant:
                    no_sessions(control);set_open(control,False)
                result['catalogAfter']=catalog(control)
                ensure(result['catalogAfter']['defaultReadonly'] is True
                    and result['catalogAfter']['allowConnections'] is success_grant,'WORKER_ACCESS_FINAL_CATALOG')
            except BaseException:
                # Closing a known archive is attempted even if session checks fail.
                try:set_open(control,False)
                except BaseException:pass
                result.update(status='FAIL',cleanupErrorCode='WORKER_ACCESS_FINAL_CLOSE_FAILED')
            finally:control.close()
    print(json.dumps(result,sort_keys=True,separators=(',',':')))
    return 0 if result['status']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())

