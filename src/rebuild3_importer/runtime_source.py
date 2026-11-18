from __future__ import annotations

import os
import re
import secrets
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from rebuild3_importer.source import (
    LatestLedgerVerifier,
    SourceExecutor,
    SourceSession,
    VerifiedLedgerEvidence,
    valid_ledger_evidence,
    valid_snapshot_id,
)


SOURCE_DATABASE = "estakada_foundation"
SOURCE_ROLE = "estakada_rebuild_reader"
SOURCE_TABLES = (
    "auth_user",
    "accounts_userprofile",
    "accounts_pagegrant",
    "content_page",
    "content_route",
    "page_versions_pagecontentstate",
    "page_versions_pagerevision",
    "shared_content_sharedblock",
    "shared_content_sharedrevision",
    "media_library_mediafolder",
    "media_library_pagemediahome",
    "media_library_asset",
    "media_library_assetfile",
    "media_library_assetusage",
)

CREATE_SOURCE_ROLE_SQL = """
CREATE ROLE estakada_rebuild_reader
  LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
  CONNECTION LIMIT 1 VALID UNTIL %s
""".strip()
SOURCE_ROLE_SETTINGS_SQL = (
    "ALTER ROLE estakada_rebuild_reader SET default_transaction_read_only = on",
    "ALTER ROLE estakada_rebuild_reader SET default_transaction_isolation = 'repeatable read'",
    "ALTER ROLE estakada_rebuild_reader SET statement_timeout = '120s'",
    "ALTER ROLE estakada_rebuild_reader SET lock_timeout = '5s'",
    "ALTER ROLE estakada_rebuild_reader SET search_path = 'pg_catalog'",
)
GRANT_SOURCE_SQL = (
    "GRANT CONNECT ON DATABASE estakada_foundation TO estakada_rebuild_reader",
    "GRANT USAGE ON SCHEMA app TO estakada_rebuild_reader",
    "GRANT SELECT ON TABLE "
    + ", ".join(f"app.{name}" for name in SOURCE_TABLES)
    + " TO estakada_rebuild_reader",
    "GRANT SELECT (id) ON TABLE app.service_requests_servicerequest TO estakada_rebuild_reader",
)
REVOKE_SOURCE_SQL = (
    "REVOKE SELECT (id) ON TABLE app.service_requests_servicerequest FROM estakada_rebuild_reader",
    "REVOKE SELECT ON TABLE "
    + ", ".join(f"app.{name}" for name in SOURCE_TABLES)
    + " FROM estakada_rebuild_reader",
    "REVOKE USAGE ON SCHEMA app FROM estakada_rebuild_reader",
    "REVOKE CONNECT ON DATABASE estakada_foundation FROM estakada_rebuild_reader",
)
SOURCE_PRIVILEGE_PROOF_SQL = """
WITH required_tables(name) AS (VALUES
  ('auth_user'), ('accounts_userprofile'), ('accounts_pagegrant'), ('content_page'),
  ('content_route'), ('page_versions_pagecontentstate'), ('page_versions_pagerevision'),
  ('shared_content_sharedblock'), ('shared_content_sharedrevision'),
  ('media_library_mediafolder'), ('media_library_pagemediahome'), ('media_library_asset'),
  ('media_library_assetfile'), ('media_library_assetusage')
), actual_tables AS (
  SELECT c.relname AS name
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app' AND c.relkind IN ('r','p')
    AND has_table_privilege('estakada_rebuild_reader', c.oid, 'SELECT')
), required_settings(value) AS (VALUES
  ('default_transaction_read_only=on'),
  ('default_transaction_isolation=repeatable read'),
  ('statement_timeout=120s'),
  ('lock_timeout=5s'),
  ('search_path=pg_catalog')
), actual_settings(value) AS (
  SELECT unnest(s.setconfig)
  FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole
  WHERE r.rolname = 'estakada_rebuild_reader' AND s.setdatabase = 0
), violations AS (
  SELECT 1 FROM required_tables r FULL JOIN actual_tables a USING (name)
  WHERE r.name IS NULL OR a.name IS NULL
  UNION ALL
  SELECT 1 FROM required_settings r FULL JOIN actual_settings a USING (value)
  WHERE r.value IS NULL OR a.value IS NULL
  UNION ALL
  SELECT 1 FROM pg_database d WHERE
    (d.datname = 'estakada_foundation' AND (
      NOT has_database_privilege('estakada_rebuild_reader', d.oid, 'CONNECT')
      OR has_database_privilege('estakada_rebuild_reader', d.oid, 'CREATE')
      OR has_database_privilege('estakada_rebuild_reader', d.oid, 'TEMP')))
    OR (d.datname <> 'estakada_foundation' AND (
      has_database_privilege('estakada_rebuild_reader', d.oid, 'CONNECT')
      OR has_database_privilege('estakada_rebuild_reader', d.oid, 'CREATE')
      OR has_database_privilege('estakada_rebuild_reader', d.oid, 'TEMP')))
  UNION ALL
  SELECT 1 FROM pg_namespace n
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND (
    (n.nspname = 'app' AND (
      NOT has_schema_privilege('estakada_rebuild_reader', n.oid, 'USAGE')
      OR has_schema_privilege('estakada_rebuild_reader', n.oid, 'CREATE')))
    OR (n.nspname <> 'app' AND (
      has_schema_privilege('estakada_rebuild_reader', n.oid, 'USAGE')
      OR has_schema_privilege('estakada_rebuild_reader', n.oid, 'CREATE'))))
  UNION ALL
  SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p','v','m','f') AND (
      ((n.nspname = 'app' AND c.relname IN (
        'auth_user','accounts_userprofile','accounts_pagegrant','content_page','content_route',
        'page_versions_pagecontentstate','page_versions_pagerevision',
        'shared_content_sharedblock','shared_content_sharedrevision',
        'media_library_mediafolder','media_library_pagemediahome','media_library_asset',
        'media_library_assetfile','media_library_assetusage'))
       <> has_table_privilege('estakada_rebuild_reader', c.oid, 'SELECT')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'INSERT')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'UPDATE')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'DELETE')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'TRUNCATE')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'REFERENCES')
      OR has_table_privilege('estakada_rebuild_reader', c.oid, 'TRIGGER'))
  UNION ALL
  SELECT 1 FROM pg_attribute a
  JOIN pg_class c ON c.oid = a.attrelid
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE a.attnum > 0 AND NOT a.attisdropped
    AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND c.relkind IN ('r','p','v','m','f') AND (
      (((n.nspname = 'app' AND c.relname IN (
          'auth_user','accounts_userprofile','accounts_pagegrant','content_page','content_route',
          'page_versions_pagecontentstate','page_versions_pagerevision',
          'shared_content_sharedblock','shared_content_sharedrevision',
          'media_library_mediafolder','media_library_pagemediahome','media_library_asset',
          'media_library_assetfile','media_library_assetusage'))
        OR (n.nspname = 'app' AND c.relname = 'service_requests_servicerequest'
            AND a.attname = 'id'))
       <> has_column_privilege('estakada_rebuild_reader', c.oid, a.attnum, 'SELECT')
      OR has_column_privilege('estakada_rebuild_reader', c.oid, a.attnum, 'INSERT')
      OR has_column_privilege('estakada_rebuild_reader', c.oid, a.attnum, 'UPDATE')
      OR has_column_privilege('estakada_rebuild_reader', c.oid, a.attnum, 'REFERENCES'))
  UNION ALL
  SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE c.relkind = 'S' AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
    AND (has_sequence_privilege('estakada_rebuild_reader', c.oid, 'USAGE')
      OR has_sequence_privilege('estakada_rebuild_reader', c.oid, 'SELECT')
      OR has_sequence_privilege('estakada_rebuild_reader', c.oid, 'UPDATE'))
  UNION ALL
  SELECT 1 FROM pg_roles WHERE rolname = 'estakada_rebuild_reader' AND (
    rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit OR rolreplication OR rolbypassrls
    OR NOT rolcanlogin OR rolconnlimit <> 1 OR rolvaliduntil IS NULL)
  UNION ALL
  SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
  WHERE r.rolname = 'estakada_rebuild_reader'
)
SELECT count(*) FROM violations
""".strip()
SOURCE_SESSION_SQL = """
SELECT pg_backend_pid(), txid_current(), txid_current_snapshot()::text
""".strip()
SOURCE_ROLE_IDENTITY_SQL = """
SELECT oid, to_char(rolvaliduntil AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
FROM pg_roles WHERE rolname = 'estakada_rebuild_reader'
""".strip()


class SourceRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class SourceEndpoint:
    host: str
    port: int
    sslrootcert: Path
    admin_user: str
    admin_secret_file: Path
    reader_secret_file: Path
    valid_until_utc: str


@dataclass(frozen=True, slots=True)
class _OwnedSecret:
    device: int
    inode: int


class PsycopgSourceExecutor(SourceExecutor):
    __slots__ = ("_connection", "_closed")

    def __init__(self, connection: Any) -> None:
        self._connection = connection
        self._closed = False

    def fetch_one(self, sql: str) -> Sequence[object]:
        if self._closed or not isinstance(sql, str):
            raise SourceRuntimeError("source-executor")
        with self._connection.cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()
        if row is None:
            raise SourceRuntimeError("source-row-missing")
        return tuple(row)

    def fetch_all(self, sql: str) -> Sequence[Sequence[object]]:
        if self._closed or not isinstance(sql, str):
            raise SourceRuntimeError("source-executor")
        with self._connection.cursor() as cursor:
            cursor.execute(sql)
            return tuple(tuple(row) for row in cursor.fetchall())

    def close(self) -> None:
        self._closed = True


class ProvidedLedgerVerifier(LatestLedgerVerifier):
    __slots__ = ("_evidence", "_used")

    def __init__(self, evidence: VerifiedLedgerEvidence) -> None:
        if not isinstance(evidence, VerifiedLedgerEvidence):
            raise SourceRuntimeError("ledger-evidence")
        self._evidence = evidence
        self._used = False

    def latest_for(self, snapshot_id: str) -> VerifiedLedgerEvidence:
        if self._used or self._evidence.snapshot_id != snapshot_id:
            raise SourceRuntimeError("ledger-snapshot")
        self._used = True
        return self._evidence


@dataclass(frozen=True, slots=True)
class OpenSource:
    executor: PsycopgSourceExecutor
    session: SourceSession
    ledger: ProvidedLedgerVerifier
    lifecycle: "SourceLifecycle"


def _secret(path: Path) -> str:
    descriptor = None
    try:
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if (
            not path.is_absolute()
            or not isinstance(no_follow, int)
            or no_follow == 0
            or not _trusted_parent(path)
        ):
            raise SourceRuntimeError("secret-file")
        descriptor = os.open(path, os.O_RDONLY | no_follow)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
            or (hasattr(os, "geteuid") and info.st_uid != os.geteuid())
            or info.st_size < 1
            or info.st_size > 4096
        ):
            raise SourceRuntimeError("secret-file")
        raw = os.read(descriptor, 4097)
        if len(raw) != info.st_size:
            raise SourceRuntimeError("secret-file")
        value = raw.decode("utf-8", "strict").rstrip("\r\n")
    except SourceRuntimeError:
        raise
    except Exception:
        raise SourceRuntimeError("secret-file") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not value or any(char in value for char in "\r\n\x00"):
        raise SourceRuntimeError("secret-file")
    return value


def _trusted_parent(path: Path) -> bool:
    try:
        parent = path.parent
        info = parent.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or parent.is_symlink()
            or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
            or (hasattr(os, "geteuid") and info.st_uid != os.geteuid())
        ):
            return False
    except Exception:
        return False
    return True


def _regular_non_link(path: Path) -> bool:
    descriptor = None
    try:
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if (
            not path.is_absolute()
            or not isinstance(no_follow, int)
            or no_follow == 0
            or not _trusted_parent(path)
        ):
            return False
        descriptor = os.open(path, os.O_RDONLY | no_follow)
        info = os.fstat(descriptor)
        return (
            stat.S_ISREG(info.st_mode)
            and (not hasattr(os, "geteuid") or info.st_uid == os.geteuid())
            and 0 < info.st_size <= 16 * 1024 * 1024
        )
    except Exception:
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_secret(path: Path, value: str) -> _OwnedSecret:
    if (
        not path.is_absolute()
        or not _trusted_parent(path)
        or path.exists()
        or path.is_symlink()
    ):
        raise SourceRuntimeError("reader-secret-target")
    descriptor = None
    owned = None
    failure: BaseException | None = None
    try:
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if not isinstance(no_follow, int) or no_follow == 0:
            raise SourceRuntimeError("reader-secret-no-follow")
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow, 0o600
        )
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise SourceRuntimeError("reader-secret-write")
        owned = _OwnedSecret(info.st_dev, info.st_ino)
        payload = value.encode("utf-8")
        if os.write(descriptor, payload) != len(payload):
            raise SourceRuntimeError("reader-secret-write")
        os.fsync(descriptor)
    except BaseException as exc:
        failure = exc

    close_ambiguous = False
    if descriptor is not None:
        closing = descriptor
        descriptor = None
        try:
            os.close(closing)
        except BaseException:
            close_ambiguous = True
    if failure is not None or close_ambiguous:
        cleanup_ambiguous = close_ambiguous
        if owned is not None:
            try:
                _delete_owned_secret(path, owned)
            except BaseException:
                cleanup_ambiguous = True
        if cleanup_ambiguous:
            raise SourceRuntimeError("reader-secret-write-cleanup-ambiguous") from None
        if isinstance(failure, Exception):
            raise SourceRuntimeError("reader-secret-write") from None
        assert failure is not None
        raise failure
    assert owned is not None
    return owned


def _delete_owned_secret(path: Path, owned: _OwnedSecret) -> None:
    try:
        if not _trusted_parent(path):
            raise SourceRuntimeError("reader-secret-parent")
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or (info.st_dev, info.st_ino) != (owned.device, owned.inode)
        ):
            raise SourceRuntimeError("reader-secret-identity")
        path.unlink()
    except SourceRuntimeError:
        raise
    except Exception:
        raise SourceRuntimeError("reader-secret-delete") from None


def _valid_expiry(value: object) -> bool:
    if not isinstance(value, str) or re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z",
        value,
    ) is None:
        return False
    try:
        expiry = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    now = datetime.now(timezone.utc)
    return now + timedelta(minutes=1) <= expiry <= now + timedelta(minutes=30)


class SourceLifecycle:
    __slots__ = (
        "_admin", "_reader", "_executor", "_secret_path", "_secret_identity",
        "_role_oid", "_closed",
    )

    def __init__(
        self,
        admin: Any,
        reader: Any,
        executor: PsycopgSourceExecutor,
        secret_path: Path,
        secret_identity: _OwnedSecret,
        role_oid: int,
    ) -> None:
        self._admin = admin
        self._reader = reader
        self._executor = executor
        self._secret_path = secret_path
        self._secret_identity = secret_identity
        self._role_oid = role_oid
        self._closed = False

    @classmethod
    def _open_session(
        cls,
        endpoint: SourceEndpoint,
        evidence: VerifiedLedgerEvidence | object,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> OpenSource | tuple[PsycopgSourceExecutor, SourceSession, "SourceLifecycle"]:
        if (
            not isinstance(endpoint, SourceEndpoint)
            or not isinstance(endpoint.host, str)
            or not endpoint.host
            or isinstance(endpoint.port, bool)
            or not isinstance(endpoint.port, int)
            or not 1 <= endpoint.port <= 65535
            or not isinstance(endpoint.admin_user, str)
            or not endpoint.admin_user
            or SOURCE_ROLE in endpoint.admin_user
            or not all(isinstance(path, Path) for path in (
                endpoint.sslrootcert, endpoint.admin_secret_file, endpoint.reader_secret_file
            ))
            or not isinstance(endpoint.sslrootcert, Path)
            or not isinstance(endpoint.admin_secret_file, Path)
            or not isinstance(endpoint.reader_secret_file, Path)
            or not endpoint.sslrootcert.is_absolute()
            or not _regular_non_link(endpoint.sslrootcert)
            or not _trusted_parent(endpoint.admin_secret_file)
            or not _trusted_parent(endpoint.reader_secret_file)
            or not _valid_expiry(endpoint.valid_until_utc)
        ):
            raise SourceRuntimeError("source-endpoint")
        if connect is None:
            from psycopg import connect as psycopg_connect

            connect = psycopg_connect
        password = secrets.token_urlsafe(48)
        admin = reader = None
        role_oid = None
        role_created = False
        create_started = False
        create_returned = False
        create_rejected = False
        secret_identity = None
        try:
            secret_identity = _write_secret(endpoint.reader_secret_file, password)
            admin = connect(
                host=endpoint.host,
                port=endpoint.port,
                dbname=SOURCE_DATABASE,
                user=endpoint.admin_user,
                password=_secret(endpoint.admin_secret_file),
                sslmode="verify-full",
                sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            with admin.cursor() as cursor:
                create_started = True
                try:
                    cursor.execute(CREATE_SOURCE_ROLE_SQL, (password, endpoint.valid_until_utc))
                except Exception as create_exc:
                    if getattr(create_exc, "sqlstate", None) == "42710":
                        create_rejected = True
                        raise SourceRuntimeError("source-role-collision") from None
                    raise
                create_returned = True
                role_created = True
                cursor.execute(SOURCE_ROLE_IDENTITY_SQL)
                identity = cursor.fetchone()
                if (
                    identity is None
                    or len(tuple(identity)) != 2
                    or type(tuple(identity)[0]) is not int
                    or tuple(identity)[0] <= 0
                ):
                    raise SourceRuntimeError("source-role-identity")
                role_oid = tuple(identity)[0]
                if tuple(identity)[1] != endpoint.valid_until_utc:
                    raise SourceRuntimeError("source-role-expiry")
                for sql in SOURCE_ROLE_SETTINGS_SQL + GRANT_SOURCE_SQL:
                    cursor.execute(sql)
                cursor.execute(SOURCE_PRIVILEGE_PROOF_SQL)
                proof = cursor.fetchone()
            if proof is None or tuple(proof) != (0,):
                raise SourceRuntimeError("source-privileges")
            reader = connect(
                host=endpoint.host,
                port=endpoint.port,
                dbname=SOURCE_DATABASE,
                user=SOURCE_ROLE,
                password=password,
                sslmode="verify-full",
                sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            with reader.cursor() as cursor:
                cursor.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cursor.execute(SOURCE_SESSION_SQL)
                row = cursor.fetchone()
            if row is None or len(row) != 3:
                raise SourceRuntimeError("source-session")
            session = SourceSession(row[0], row[1], row[2])
            if not valid_snapshot_id(session.snapshot_id):
                raise SourceRuntimeError("source-session")
            executor = PsycopgSourceExecutor(reader)
            lifecycle = cls(
                admin, reader, executor, endpoint.reader_secret_file, secret_identity, role_oid
            )
            if evidence is _UNBOUND_SESSION:
                return executor, session, lifecycle
            verifier = ProvidedLedgerVerifier(evidence)
            return OpenSource(executor, session, verifier, lifecycle)
        except BaseException as exc:
            cleanup_error = False
            create_ambiguous = create_started and not create_returned and not create_rejected
            role_removed = False
            if reader is not None:
                try:
                    reader.close()
                except BaseException:
                    cleanup_error = True
            if admin is not None:
                if role_oid is not None and not create_ambiguous:
                    try:
                        cls._drop(admin, role_oid)
                        role_removed = True
                    except BaseException:
                        cleanup_error = True
                elif role_created and not create_ambiguous:
                    cleanup_error = True
                try:
                    admin.close()
                except BaseException:
                    cleanup_error = True
            if secret_identity is not None and not create_ambiguous and (
                not role_created or role_removed
            ):
                try:
                    _delete_owned_secret(endpoint.reader_secret_file, secret_identity)
                except BaseException:
                    cleanup_error = True
            if create_ambiguous:
                raise SourceRuntimeError("source-role-create-ambiguous") from None
            if cleanup_error:
                raise SourceRuntimeError("source-open-cleanup-ambiguous") from None
            if isinstance(exc, SourceRuntimeError):
                raise
            if isinstance(exc, Exception):
                raise SourceRuntimeError("source-open") from None
            raise

    @classmethod
    def open(
        cls,
        endpoint: SourceEndpoint,
        evidence: VerifiedLedgerEvidence,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> OpenSource:
        opened = cls._open_session(endpoint, evidence, connect=connect)
        if not isinstance(opened, OpenSource):
            raise SourceRuntimeError("source-open")
        return opened

    @staticmethod
    def _drop(admin: Any, role_oid: int) -> None:
        with admin.cursor() as cursor:
            cursor.execute("SELECT oid FROM pg_roles WHERE rolname = 'estakada_rebuild_reader'")
            identity = cursor.fetchone()
            if identity is None or tuple(identity) != (role_oid,):
                raise SourceRuntimeError("source-role-identity")
            cursor.execute("ALTER ROLE estakada_rebuild_reader NOLOGIN")
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE usename = 'estakada_rebuild_reader'"
            )
            row = cursor.fetchone()
            if row is None or tuple(row) != (0,):
                raise SourceRuntimeError("source-sessions")
            for sql in REVOKE_SOURCE_SQL:
                cursor.execute(sql)
            cursor.execute("DROP ROLE estakada_rebuild_reader")

    def close(self) -> None:
        if self._closed:
            raise SourceRuntimeError("source-close-reuse")
        self._closed = True
        error = False
        role_removed = False
        try:
            self._executor.close()
        except BaseException:
            error = True
        try:
            self._reader.close()
        except BaseException:
            error = True
        try:
            self._drop(self._admin, self._role_oid)
            role_removed = True
        except BaseException:
            error = True
        try:
            self._admin.close()
        except BaseException:
            error = True
        if role_removed:
            try:
                _delete_owned_secret(self._secret_path, self._secret_identity)
            except BaseException:
                error = True
        if error:
            raise SourceRuntimeError("source-close-ambiguous")


_UNBOUND_SESSION = object()


def open_source_bound(
    endpoint: SourceEndpoint,
    bind_ledger: Callable[[str], VerifiedLedgerEvidence],
    *,
    connect: Callable[..., Any] | None = None,
) -> OpenSource:
    if not callable(bind_ledger):
        raise SourceRuntimeError("ledger-binder")
    opened = SourceLifecycle._open_session(endpoint, _UNBOUND_SESSION, connect=connect)
    if isinstance(opened, OpenSource) or not isinstance(opened, tuple) or len(opened) != 3:
        raise SourceRuntimeError("source-bind-open")
    executor, session, lifecycle = opened
    try:
        evidence = bind_ledger(session.snapshot_id)
        if not valid_ledger_evidence(evidence, session.snapshot_id):
            raise SourceRuntimeError("ledger-evidence")
        verifier = ProvidedLedgerVerifier(evidence)
        return OpenSource(executor, session, verifier, lifecycle)
    except BaseException:
        try:
            lifecycle.close()
        except BaseException:
            raise SourceRuntimeError("source-bind-cleanup-ambiguous") from None
        raise


def capture_run_authority(
    endpoint: SourceEndpoint,
    *,
    connect: Callable[..., Any] | None = None,
) -> tuple[Any, Any, str]:
    """Capture exact public facts, close DB authority, then compose in memory."""

    opened = SourceLifecycle._open_session(
        endpoint,
        _UNBOUND_SESSION,
        connect=connect,
    )
    if isinstance(opened, OpenSource) or not isinstance(opened, tuple) or len(opened) != 3:
        raise SourceRuntimeError("capture-open")
    executor, session, lifecycle = opened
    try:
        from rebuild3_importer.freeze_authority import capture_source_authority

        capture = capture_source_authority(executor, session)
    except BaseException:
        try:
            lifecycle.close()
        except BaseException:
            raise SourceRuntimeError("capture-close-ambiguous") from None
        raise
    try:
        lifecycle.close()
    except BaseException:
        raise SourceRuntimeError("capture-close-ambiguous") from None

    from rebuild3_importer.media_authority import compose_run_authority

    return compose_run_authority(capture)
