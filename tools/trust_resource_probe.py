"""RA15-002/003/005: catalog-only resource audit of four fixed TRUST databases.

Closed archives are opened only for bootstrap catalog reads and closed again.
No business rows, ACL grants, database defaults or Django/ORM are touched.
"""
import json
import re
import signal
import time
from pathlib import Path

import psycopg
from psycopg import sql

MAIN = 'estakada_trust'
UNIT = 'test_estakada_trust'
ARCHIVES = {'test_estakada_trust_cal_7e145c49': 16387, 'test_estakada_trust_cap_32563': 32563}
EXPECTED = {**ARCHIVES, UNIT: 52766}
TABLES = {'django_migrations', 'journal_head', 'journal_credential', 'journal_operation',
    'journal_routepolicy', 'journal_requesttombstone', 'journal_recoveryreceipt', 'journal_admissionpolicy'}


class ResourceFailure(Exception):
    pass


def ensure(value, code):
    if not value: raise ResourceFailure(code)


def closed(value, keys):
    ensure(type(value) is dict and set(value) == set(keys), 'RESOURCE_PROBE_INPUT_SHAPE')


def cgroup():
    root = Path('/sys/fs/cgroup')
    def number(name):
        value = (root/name).read_text(encoding='ascii').strip()
        return int(value) if value.isdecimal() else value
    def pairs(name):
        return {key: int(value) for key, value in
            (line.split() for line in (root/name).read_text(encoding='ascii').splitlines())}
    return {'memoryPeak': number('memory.peak'), 'memoryMax': number('memory.max'),
        'memoryCurrent': number('memory.current'), 'memoryEvents': pairs('memory.events'),
        'cpuMax': (root/'cpu.max').read_text(encoding='ascii').strip(), 'cpuStat': pairs('cpu.stat'),
        'pidsMax': number('pids.max'), 'pidsCurrent': number('pids.current'),
        'pidsPeak': number('pids.peak') if (root/'pids.peak').exists() else 'NOT_MEASURED'}


def connect(database, *, readonly):
    ensure(database in {MAIN, UNIT, *ARCHIVES}, 'RESOURCE_PROBE_DATABASE_SCOPE')
    password = Path('/run/secrets/bootstrap-password').read_text(encoding='ascii').strip()
    ensure(re.fullmatch('[a-f0-9]{96}', password) is not None, 'RESOURCE_PROBE_SECRET_FORMAT')
    return psycopg.connect(host='trust-db', dbname=database, user='postgres', password=password,
        sslmode='verify-full', sslrootcert='/run/secrets/database-ca', connect_timeout=3, autocommit=True,
        options='-c search_path=trust,pg_catalog -c statement_timeout=5000 -c lock_timeout=1000'
            + (' -c default_transaction_read_only=on' if readonly else ''))


def identity(conn, name, oid):
    row = conn.execute('''SELECT current_database(),current_user,session_user,d.oid,r.rolsuper,
        pg_get_userbyid(d.datdba) FROM pg_database d JOIN pg_roles r ON r.rolname=current_user
        WHERE d.datname=current_database()''').fetchone()
    ensure(row == (name, 'postgres', 'postgres', oid, True, 'postgres'), 'RESOURCE_PROBE_ACTUAL_IDENTITY')
    ensure(conn.execute('SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()').fetchone() == (True,),
        'RESOURCE_PROBE_TLS')


def catalog(control, name, oid):
    row = control.execute('SELECT oid,datallowconn,pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s',
        [name]).fetchone()
    ensure(row is not None and row[0] == oid and row[2] == 'postgres', 'RESOURCE_PROBE_CATALOG_OID')
    return row


def sessions(control, oid):
    return control.execute('SELECT count(*) FROM pg_stat_activity WHERE datid=%s', [oid]).fetchone()[0]


def archive_baseline(control, name, oid, *, closed_required):
    row = catalog(control, name, oid)
    if closed_required: ensure(row[1] is False, 'RESOURCE_PROBE_ARCHIVE_NOT_CLOSED')
    ordinary = control.execute("SELECT has_database_privilege('trust_runtime',%s,'CONNECT'),has_database_privilege('trust_migrator',%s,'CONNECT')",
        [name, name]).fetchone()
    public = control.execute("""SELECT EXISTS(SELECT 1 FROM pg_database d,LATERAL
        aclexplode(NULLIF(COALESCE(d.datacl,acldefault('d',d.datdba)),'{}'::aclitem[])) a
        WHERE d.datname=%s AND a.grantee=0 AND a.privilege_type='CONNECT')""", [name]).fetchone()[0]
    readonly = control.execute('SELECT setconfig FROM pg_db_role_setting WHERE setdatabase=%s AND setrole=0',
        [oid]).fetchone()
    ensure(ordinary == (False, False) and public is False, 'RESOURCE_PROBE_ARCHIVE_CONNECT_OPEN')
    ensure(readonly is not None and 'default_transaction_read_only=on' in readonly[0],
        'RESOURCE_PROBE_ARCHIVE_DEFAULT_CHANGED')
    ensure(sessions(control, oid) == 0, 'RESOURCE_PROBE_ARCHIVE_HAS_SESSION')
    return {'name': name, 'oid': oid, 'allowConnections': row[1], 'defaultReadonly': True,
        'ordinaryConnect': False, 'sessions': 0}


def measure(name, oid):
    with connect(name, readonly=True) as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            identity(conn, name, oid)
            names = {row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname='trust'")}
            expected_tables = TABLES - {'journal_recoveryreceipt', 'journal_admissionpolicy'} if name == 'test_estakada_trust_cal_7e145c49' else TABLES
            ensure(names == expected_tables, 'RESOURCE_PROBE_TABLE_SET')
            rows = conn.execute('''SELECT n.nspname,c.relname,c.relkind,c.oid,
                pg_relation_size(c.oid,'main'),pg_table_size(c.oid),pg_indexes_size(c.oid),
                CASE WHEN c.reltoastrelid=0 THEN 0 ELSE pg_total_relation_size(c.reltoastrelid) END,
                pg_total_relation_size(c.oid)
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname<>'information_schema'
                AND c.relkind IN ('r','p','m','S','f') ORDER BY n.nspname,c.relname''').fetchall()
            ensure(rows and all(type(value) is int and value >= 0 for row in rows for value in row[4:]),
                'RESOURCE_PROBE_RELATION_BYTES')
            relations = [{'schema': row[0], 'relation': row[1], 'kind': row[2], 'oid': row[3],
                'heapBytes': row[4], 'tableBytes': row[5], 'indexBytes': row[6],
                'toastBytes': row[7], 'totalBytes': row[8]} for row in rows]
            database_bytes = conn.execute('SELECT pg_database_size(current_database())').fetchone()[0]
            ensure(type(database_bytes) is int and database_bytes >= 0, 'RESOURCE_PROBE_DATABASE_BYTES')
            temp = conn.execute('SELECT temp_files,temp_bytes,stats_reset FROM pg_stat_database WHERE datname=current_database()').fetchone()
            wal = conn.execute('SELECT wal_records,wal_fpi,wal_bytes,stats_reset FROM pg_stat_wal').fetchone()
            ensure(temp is not None and wal is not None and all(value is not None and int(value) >= 0
                for value in (*temp[:2], *wal[:3])), 'RESOURCE_PROBE_STATS_UNAVAILABLE')
            ensure(conn.execute('SHOW transaction_read_only').fetchone() == ('on',), 'RESOURCE_PROBE_READONLY_LOST')
            return {'name': name, 'oid': oid, 'databaseBytes': database_bytes, 'relations': relations,
                'tableRelationCount': len(expected_tables),
                'temp': {'files': int(temp[0]), 'bytes': int(temp[1]),
                    'statsReset': temp[2].isoformat() if temp[2] is not None else None,
                    'cumulative': True, 'scope': 'this-database-history'},
                'wal': {'records': int(wal[0]), 'fpi': int(wal[1]), 'bytes': int(wal[2]),
                    'statsReset': wal[3].isoformat() if wal[3] is not None else None,
                    'cumulative': True, 'scope': 'whole-cluster-history-not-additive-per-database'},
                'readonly': True, 'repeatableRead': True,
                'accounting': 'detail-only; table-includes-heap-toast-fsm; total-includes-table-and-index'}


def main():
    started = time.monotonic(); control = None; identities = {}; cleanup_errors = []
    report = {'status': 'FAIL', 'scope': 'RA15-catalog-only-resource-audit', 'databases': [],
        'journalRowWrites': False, 'aclChanges': False, 'defaultChanges': False,
        'archivesBaseline': [], 'archivesAfter': [], 'resources': {}}
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(ResourceFailure('RESOURCE_PROBE_DEADLINE')))
    signal.alarm(60)
    try:
        arg = globals().get('ARG'); closed(arg, {'databases'})
        ensure(type(arg['databases']) is list and len(arg['databases']) == 4, 'RESOURCE_PROBE_DATABASE_LIST')
        for row in arg['databases']:
            closed(row, {'name', 'oid'})
            ensure(type(row['name']) is str and row['name'] in {MAIN, UNIT, *ARCHIVES}
                and row['name'] not in identities and type(row['oid']) is int and row['oid'] > 0,
                'RESOURCE_PROBE_DATABASE_INPUT')
            identities[row['name']] = row['oid']
        ensure(set(identities) == {MAIN, UNIT, *ARCHIVES}
            and len(set(identities.values())) == 4
            and all(identities[name] == oid for name, oid in EXPECTED.items()), 'RESOURCE_PROBE_EXPECTED_OIDS')
        report['resources']['before'] = cgroup()
        control = connect(MAIN, readonly=False); identity(control, MAIN, identities[MAIN])
        for name, oid in ARCHIVES.items():
            report['archivesBaseline'].append(archive_baseline(control, name, oid, closed_required=True))
        for name in sorted(identities):
            oid = identities[name]; catalog(control, name, oid)
            if name in ARCHIVES:
                archive_baseline(control, name, oid, closed_required=True)
                try:
                    control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(name)))
                    report['databases'].append(measure(name, oid))
                finally:
                    current = catalog(control, name, oid)
                    if current[1]: control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(name)))
                    # Only wait for the just-completed bootstrap read to leave.
                    for _ in range(20):
                        if sessions(control, oid) == 0: break
                        time.sleep(0.05)
                    else: raise ResourceFailure('RESOURCE_PROBE_ARCHIVE_SESSION_REMAINS')
                    report['archivesAfter'].append(archive_baseline(control, name, oid, closed_required=True))
            else:
                report['databases'].append(measure(name, oid))
        ensure(len(report['databases']) == 4 and len(report['archivesAfter']) == 2,
            'RESOURCE_PROBE_INCOMPLETE')
        report['status'] = 'PASS'
    except BaseException as error:
        code = error.args[0] if isinstance(error, ResourceFailure) and error.args else 'RESOURCE_PROBE_FAILED'
        report.update(status='FAIL', errorCode=code if type(code) is str and re.fullmatch('[A-Z0-9_]{1,80}', code)
            else 'RESOURCE_PROBE_FAILED', errorClass=type(error).__name__)
    finally:
        signal.alarm(0)
        if control is not None:
            for name, oid in ARCHIVES.items():
                try:
                    row = catalog(control, name, oid)
                    if row[1]: control.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(name)))
                    archive_baseline(control, name, oid, closed_required=True)
                except BaseException:
                    cleanup_errors.append({'name': name, 'code': 'RESOURCE_PROBE_ARCHIVE_CLEANUP_FAILED'})
            control.close()
        try:
            report['resources']['after'] = cgroup()
        except BaseException:
            cleanup_errors.append({'code': 'RESOURCE_PROBE_CGROUP_UNAVAILABLE'})
        report['cleanupErrors'] = cleanup_errors
        if cleanup_errors: report['status'] = 'FAIL'
        report['elapsedSeconds'] = round(time.monotonic()-started, 6)
    print(json.dumps(report, sort_keys=True, separators=(',', ':')))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
