"""Idempotent initialization of one explicitly isolated development cluster.

Credentials enter from mounted files, never CLI/env values or output. This tool
does not create website users and never drops schemas, databases or volumes.
"""
import os
from pathlib import Path

import psycopg
from psycopg import sql

MAIN_DB = 'estakada_foundation'
UNIT_DB = 'estakada_foundation_unit'
ROLE_SECRETS = {'app_migrator': 'migrator-password', 'app_runtime': 'runtime-password'}


def password(name):
    value = (Path('/run/secrets') / name).read_text(encoding='ascii').strip()
    if len(value) != 96 or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError('Credential format rejected')
    return value


def connection(database):
    return psycopg.connect(host='db', dbname=database, user='postgres',
                          password=password('bootstrap-password'), connect_timeout=5,
                          sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
                          autocommit=True)


def initialize(environment):
    if environment not in ('dev', 'test'):
        raise ValueError('Unknown isolated environment')
    with connection(MAIN_DB) as conn:
        for role, secret in ROLE_SECRETS.items():
            existing = conn.execute(
                'SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls '
                'FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
            if existing is None:
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                                    'NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                    sql.Identifier(role), sql.Literal(password(secret))))
            elif any(existing):
                raise RuntimeError('Existing service role has unexpected privileges')
        if conn.execute("SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                        "WHERE r.rolname IN ('app_runtime','app_migrator') LIMIT 1").fetchone():
            raise RuntimeError('Service role has unexpected membership')
        if conn.execute("SELECT 1 FROM pg_database WHERE datdba=(SELECT oid FROM pg_roles "
                        "WHERE rolname='app_runtime') LIMIT 1").fetchone():
            raise RuntimeError('Runtime role unexpectedly owns a database')
        conn.execute('ALTER ROLE app_runtime CONNECTION LIMIT 10')
        conn.execute('ALTER ROLE app_runtime SET search_path=pg_catalog,app')
        conn.execute('ALTER ROLE app_migrator SET search_path=app,pg_catalog')
        for db in ('postgres', 'template1'):
            conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(db)))
        if environment == 'test':
            if not conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (UNIT_DB,)).fetchone():
                conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(UNIT_DB)))
            # Django --keepdb only reads pg_database here; no CREATEDB/TEMP is granted.
            conn.execute('GRANT CONNECT ON DATABASE postgres TO app_migrator')

    databases = [MAIN_DB] + ([UNIT_DB] if environment == 'test' else [])
    for database in databases:
        with connection(database) as conn:
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(database)))
            conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO app_migrator').format(sql.Identifier(database)))
            conn.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
            conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM app_runtime').format(sql.Identifier(database)))
            schema_owner = conn.execute(
                "SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='app'").fetchone()
            if schema_owner is None:
                conn.execute('CREATE SCHEMA app AUTHORIZATION app_migrator')
            elif schema_owner[0] != 'app_migrator':
                raise RuntimeError('Existing app schema has unexpected owner')
            if database == MAIN_DB:
                conn.execute('REVOKE ALL ON SCHEMA app FROM app_runtime')
                conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO app_runtime').format(sql.Identifier(database)))
                conn.execute('GRANT USAGE ON SCHEMA app TO app_runtime')
                conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA app '
                             'GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO app_runtime')
                conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE app_migrator IN SCHEMA app '
                             'GRANT USAGE,SELECT ON SEQUENCES TO app_runtime')
                conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA app TO app_runtime')
                conn.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA app TO app_runtime')
            else:
                conn.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM app_runtime').format(sql.Identifier(database)))

    # Validate credential files against real authentication, not merely role names.
    for role, secret in ROLE_SECRETS.items():
        with psycopg.connect(host='db', dbname=MAIN_DB, user=role, password=password(secret),
                             sslmode='verify-full', sslrootcert='/run/secrets/database-ca',
                             connect_timeout=5) as conn:
            if conn.execute('SELECT current_user').fetchone()[0] != role:
                raise RuntimeError('Service identity mismatch')


if __name__ == '__main__':
    try:
        initialize(os.environ.get('FOUNDATION_ENV', ''))
    except Exception as exc:
        # A database error may contain a statement or connection string; no raw exception output.
        raise SystemExit('Foundation database initialization failed: ' + type(exc).__name__) from None
    print('Foundation roles and schemas initialized; application users were not created')
