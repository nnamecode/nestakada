"""Own isolated TRUST cluster only; never loads foundation/application settings."""
from pathlib import Path
import psycopg
from psycopg import sql

MAIN = 'estakada_trust'
UNIT = 'test_estakada_trust'


def secret(name):
    value = (Path('/run/secrets') / name).read_text(encoding='ascii').strip()
    if len(value) != 96 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('CREDENTIAL_INVALID')
    return value


def connect(database):
    return psycopg.connect(host='trust-db', dbname=database, user='postgres',
                          password=secret('bootstrap-password'),
                          sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
                          connect_timeout=3, autocommit=True)


def initialize():
    with connect(MAIN) as conn:
        for role, password_file in [('trust_migrator', 'migrator-password'),
                                    ('trust_runtime', 'runtime-password')]:
            row = conn.execute('SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls '
                               'FROM pg_roles WHERE rolname=%s', [role]).fetchone()
            if row is None:
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                                     'NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                    sql.Identifier(role), sql.Literal(secret(password_file))))
            elif any(row):
                raise RuntimeError('ROLE_PRIVILEGES_UNEXPECTED')
        if conn.execute("SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                        "WHERE r.rolname IN ('trust_runtime','trust_migrator') LIMIT 1").fetchone():
            raise RuntimeError('ROLE_MEMBERSHIP_UNEXPECTED')
        if conn.execute("SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles "
                        "WHERE rolname='trust_runtime') LIMIT 1").fetchone():
            raise RuntimeError('RUNTIME_OWNS_DATABASE')
        if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', [UNIT]).fetchone():
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(UNIT)))
        for database in ['postgres', 'template1']:
            conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(database)))
        conn.execute('GRANT CONNECT ON DATABASE postgres TO trust_migrator')
        conn.execute('ALTER ROLE trust_runtime CONNECTION LIMIT 4')
        conn.execute('ALTER ROLE trust_runtime SET search_path=pg_catalog,trust')
        conn.execute('ALTER ROLE trust_migrator SET search_path=trust,pg_catalog')
        for role in ['trust_runtime', 'trust_migrator']:
            for name, value in [('lock_timeout', '500ms'), ('statement_timeout', '2s'),
                                ('idle_in_transaction_session_timeout', '3s')]:
                conn.execute(sql.SQL('ALTER ROLE {} SET {}={}').format(
                    sql.Identifier(role), sql.Identifier(name), sql.Literal(value)))
    for database in [MAIN, UNIT]:
        with connect(database) as conn:
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(database)))
            conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            conn.execute('REVOKE ALL ON SCHEMA public FROM trust_runtime')
            if conn.execute("SELECT 1 FROM pg_namespace WHERE nspowner=(SELECT oid FROM pg_roles "
                            "WHERE rolname='trust_runtime') UNION ALL SELECT 1 FROM pg_class "
                            "WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname='trust_runtime') "
                            "LIMIT 1").fetchone():
                raise RuntimeError('RUNTIME_OWNS_SCHEMA_OR_RELATION')
            owner = conn.execute("SELECT pg_get_userbyid(nspowner) FROM pg_namespace "
                                 "WHERE nspname='trust'").fetchone()
            if owner is None:
                conn.execute('CREATE SCHEMA trust AUTHORIZATION trust_migrator')
            elif owner[0] != 'trust_migrator':
                raise RuntimeError('SCHEMA_OWNER_UNEXPECTED')
            conn.execute('REVOKE ALL ON SCHEMA trust FROM trust_runtime')
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO trust_migrator').format(sql.Identifier(database)))
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM trust_runtime').format(sql.Identifier(database)))
            if database == MAIN:
                conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO trust_runtime').format(sql.Identifier(database)))
                conn.execute('GRANT USAGE ON SCHEMA trust TO trust_runtime')
                conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE trust_migrator IN SCHEMA trust '
                             'GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO trust_runtime')
                conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE trust_migrator IN SCHEMA trust '
                             'GRANT USAGE,SELECT ON SEQUENCES TO trust_runtime')
                conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA trust TO trust_runtime')
                conn.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA trust TO trust_runtime')


if __name__ == '__main__':
    try:
        initialize()
    except Exception as exc:
        raise SystemExit('TRUST_INIT_FAILED_' + type(exc).__name__) from None
    print('TRUST_ROLES_READY')
