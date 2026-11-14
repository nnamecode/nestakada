"""Closed create/drop helper for one disposable TEST-10A PostgreSQL database."""
import os
from pathlib import Path
import re
import sys

import psycopg
from psycopg import sql


RUN_PATTERN = re.compile(r"\A[a-f0-9]{32}\Z")
HASH_PATTERN = re.compile(r"\A[a-f0-9]{64}\Z")
SECRET_ROOT = Path("/run/secrets")


def identity(run_id):
    if not isinstance(run_id, str) or RUN_PATTERN.fullmatch(run_id) is None:
        raise ValueError("T10_DATABASE_RUN_ID_REJECTED")
    return "estakada_test10_" + run_id


def marker_values(run_id, source_sha256, marker):
    name = identity(run_id)
    if (not isinstance(source_sha256, str)
            or HASH_PATTERN.fullmatch(source_sha256) is None
            or not isinstance(marker, str) or HASH_PATTERN.fullmatch(marker) is None):
        raise ValueError("T10_DATABASE_MARKER_REJECTED")
    return name, (run_id, name, source_sha256, marker)


def password():
    value = (SECRET_ROOT / "bootstrap-password").read_text(
        encoding="ascii").strip()
    if re.fullmatch(r"[a-f0-9]{96}", value) is None:
        raise ValueError("T10_DATABASE_SECRET_REJECTED")
    return value


def connection(database="postgres"):
    return psycopg.connect(
        host="db", dbname=database, user="postgres", password=password(),
        connect_timeout=5, sslmode="verify-full",
        sslrootcert=str(SECRET_ROOT / "database-ca"), autocommit=True)


def prepare(run_id, source_sha256, marker):
    name, expected = marker_values(run_id, source_sha256, marker)
    with connection() as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (name,)).fetchone():
            raise RuntimeError("T10_DATABASE_ALREADY_EXISTS")
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER app_migrator").format(
            sql.Identifier(name)))
    try:
        with connection(name) as conn:
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(
                sql.Identifier(name)))
            conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            conn.execute("CREATE SCHEMA app AUTHORIZATION app_migrator")
            conn.execute("CREATE TABLE app.test10_fixture_identity ("
                         "singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton), "
                         "run_id text NOT NULL, database_name text NOT NULL, "
                         "source_sha256 text NOT NULL, marker text NOT NULL)")
            conn.execute("INSERT INTO app.test10_fixture_identity "
                         "(run_id,database_name,source_sha256,marker) VALUES (%s,%s,%s,%s)",
                         expected)
            conn.execute("REVOKE ALL ON TABLE app.test10_fixture_identity FROM PUBLIC, app_migrator, app_runtime")
            conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO app_migrator").format(
                sql.Identifier(name)))
            conn.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM app_runtime").format(
                sql.Identifier(name)))
    except Exception:
        with connection() as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(name)))
        raise
    return name


def teardown(run_id, source_sha256, marker):
    name, expected = marker_values(run_id, source_sha256, marker)
    with connection() as conn:
        row = conn.execute(
            "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=%s",
            (name,)).fetchone()
        if row is None:
            raise RuntimeError("T10_DATABASE_NOT_FOUND")
        if row[0] != "app_migrator":
            raise RuntimeError("T10_DATABASE_OWNER_MISMATCH")
    with connection(name) as target:
        actual = target.execute(
            "SELECT run_id,database_name,source_sha256,marker "
            "FROM app.test10_fixture_identity WHERE singleton=true").fetchone()
        if actual is None or tuple(actual) != expected:
            raise RuntimeError("T10_DATABASE_MARKER_MISMATCH")
    with connection() as conn:
        conn.execute(sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC, app_migrator, app_runtime").format(
            sql.Identifier(name)))
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
            sql.Identifier(name)))
    return name


def main(argv):
    if len(argv) != 5 or argv[1] not in {"prepare", "teardown"}:
        raise ValueError("T10_DATABASE_COMMAND_REJECTED")
    run_id, source_sha256, marker = argv[2:]
    name = (prepare(run_id, source_sha256, marker) if argv[1] == "prepare"
            else teardown(run_id, source_sha256, marker))
    print("T10_DATABASE_" + ("PREPARED:" if argv[1] == "prepare" else "REMOVED:") + name)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except Exception as error:
        code = str(error)
        if re.fullmatch(r"T10_[A-Z0-9_]+", code) is None:
            code = "T10_DATABASE_OPERATION_FAILED"
        raise SystemExit(code) from None
