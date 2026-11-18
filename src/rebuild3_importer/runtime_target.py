from __future__ import annotations

import json
import hashlib
import os
import re
import secrets
import stat
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from rebuild3_importer.coordinator import (
    CleanupProof,
    PreTargetProof,
    RESULT_SCHEMA,
    RESULT_VERSION,
    ProjectionCounts,
    ReadbackProof,
    SafeResult,
    TargetNames,
    target_names,
)
from rebuild3_importer.manifest import PublicManifest, target_storage_key
from rebuild3_importer.runtime_source import (
    _delete_owned_secret,
    _regular_non_link,
    _secret,
    _trusted_parent,
    _valid_expiry,
    _write_secret,
)
from rebuild3_importer.source import PrivateSourceRows, SourcePreflight, VerifiedLedgerEvidence


class TargetRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


RESULT_FIELDS = frozenset({
    "schema", "version", "phase", "run_id", "database", "media_key",
    "manifest_digest", "ledger_identity", "ledger_generation", "ledger_digest",
    "counts", "database_digest", "source_media_digest", "target_media_digest",
    "error_code",
})
COUNT_FIELDS = frozenset({
    "site_settings", "pages", "routes", "current", "previous", "staff",
    "grants", "assets", "files", "usages", "albums", "photos",
})
SHA256 = re.compile(r"[0-9a-f]{64}")
ALLOWED_ERROR_CODES = frozenset({
    "create-failed",
    "prepare-failed",
    "database-import-failed",
    "file-copy-failed",
    "precommit-verify-failed",
    "readback-failed",
    "readback-mismatch",
    "close-identities-failed",
    "seal-absent",
    "seal-ambiguous",
})

TARGET_MAINTENANCE_DATABASE = "postgres"
TARGET_SCHEMA = "app"
TARGET_TABLES = (
    "accounts_user",
    "pages_page",
    "pages_route",
    "pages_pagecontent",
    "pages_pagegrant",
    "media_asset",
    "media_assetfile",
    "media_assetusage",
    "pages_sitesettings",
    "gallery_galleryalbum",
    "gallery_galleryphoto",
)
TARGET_MIGRATION_LEAVES = frozenset({
    ("contenttypes", "0002_remove_content_type_name"),
    ("auth", "0012_alter_user_first_name_max_length"),
    ("sessions", "0001_initial"),
    ("audit", "0001_initial"),
    ("accounts", "0001_initial"),
    ("media", "0001_initial"),
    ("pages", "0002_sitesettings"),
    ("gallery", "0001_initial"),
})

INSERT_ASSET_SQL = """
INSERT INTO app.media_asset (id, purpose, source_sha256, state, created_at)
VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
""".strip()
INSERT_FILE_SQL = """
INSERT INTO app.media_assetfile
  (id, asset_id, kind, storage_key, sha256, byte_size, mime_type, width, height)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
""".strip()
INSERT_PAGE_SQL = """
INSERT INTO app.pages_page (id, name, kind, parent_id, position, is_published)
VALUES (%s, %s, %s, %s, %s, %s)
""".strip()
INSERT_ROUTE_SQL = """
INSERT INTO app.pages_route (id, page_id, target, mode, outcome)
VALUES (%s, %s, %s, %s, %s)
""".strip()
INSERT_SETTINGS_SQL = """
INSERT INTO app.pages_sitesettings
  (id, singleton_key, structure_generation, settings_generation,
   organization_name, legal_name, phone_display, phone_e164, address,
   opening_hours, contact_email, map_url, max_url, telegram_url, logo_asset_id)
VALUES (%s, TRUE, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""".strip()
INSERT_USAGE_SQL = """
INSERT INTO app.media_assetusage
  (id, asset_id, scope, target_uuid, slot, position)
VALUES (%s, %s, %s, %s, %s, %s)
""".strip()
INSERT_ALBUM_SQL = """
INSERT INTO app.gallery_galleryalbum (id, page_id, generation, position)
VALUES (%s, %s, %s, %s)
""".strip()
INSERT_PHOTO_SQL = """
INSERT INTO app.gallery_galleryphoto
  (id, album_id, asset_id, position, alt)
VALUES (%s, %s, %s, %s, %s)
""".strip()
INSERT_STAFF_SQL = """
INSERT INTO app.accounts_user
  (id, password, last_login, is_superuser, username, first_name, last_name,
   email, is_staff, is_active, date_joined, role, generation)
VALUES (%s, '!', NULL, %s, %s, '', '', '', TRUE, %s, CURRENT_TIMESTAMP, %s, %s)
""".strip()
INSERT_CONTENT_SQL = """
INSERT INTO app.pages_pagecontent
  (page_id, generation, current_payload, current_hash, current_author_id,
   current_created_at, previous_payload, previous_hash, previous_author_id,
   previous_created_at, last_operation_id, last_operation_action,
   last_result_generation, last_result_hash)
VALUES (%s, %s, %s::jsonb, %s, %s, %s,
        %s::jsonb, %s, %s, %s, NULL, NULL, NULL, NULL)
""".strip()
INSERT_GRANT_SQL = """
INSERT INTO app.pages_pagegrant (id, staff_id, page_id, groups)
VALUES (%s, %s, %s, %s::jsonb)
""".strip()
TARGET_COUNT_SQL = """
SELECT
  (SELECT count(*) FROM app.pages_sitesettings),
  (SELECT count(*) FROM app.pages_page),
  (SELECT count(*) FROM app.pages_route),
  (SELECT count(*) FROM app.pages_pagecontent),
  (SELECT count(*) FROM app.pages_pagecontent WHERE previous_payload IS NOT NULL),
  (SELECT count(*) FROM app.accounts_user),
  (SELECT count(*) FROM app.pages_pagegrant),
  (SELECT count(*) FROM app.media_asset),
  (SELECT count(*) FROM app.media_assetfile),
  (SELECT count(*) FROM app.media_assetusage),
  (SELECT count(*) FROM app.gallery_galleryalbum),
  (SELECT count(*) FROM app.gallery_galleryphoto)
""".strip()
TARGET_INVARIANT_SQL = """
WITH violations AS (
  SELECT 'usage-ready' AS code
  FROM app.media_assetusage u JOIN app.media_asset a ON a.id = u.asset_id
  WHERE a.state <> 'READY'
  UNION ALL SELECT 'usage-page' FROM app.media_assetusage u
  LEFT JOIN app.pages_page p ON p.id = u.target_uuid
  WHERE u.scope IN ('PAGE_CURRENT','PAGE_PREVIOUS') AND p.id IS NULL
  UNION ALL SELECT 'usage-settings' FROM app.media_assetusage u
  LEFT JOIN app.pages_sitesettings s ON s.id = u.target_uuid
  WHERE u.scope = 'SITE_SETTINGS'
    AND (s.id IS NULL OR u.slot <> 'logo' OR u.position <> 0)
  UNION ALL SELECT 'content-missing' FROM app.pages_page p
  LEFT JOIN app.pages_pagecontent c ON c.page_id = p.id WHERE c.page_id IS NULL
  UNION ALL SELECT 'grant-shape' FROM app.pages_pagegrant g
  JOIN app.accounts_user u ON u.id = g.staff_id
  WHERE u.role <> 'EMPLOYEE' OR NOT u.is_active
  UNION ALL SELECT 'gallery-asset' FROM app.gallery_galleryphoto p
  JOIN app.media_asset a ON a.id = p.asset_id
  WHERE a.purpose <> 'GALLERY_ORIGINAL' OR a.state <> 'READY'
)
SELECT count(*) FROM violations
""".strip()
TARGET_READBACK_QUERIES = {
    "assets": "SELECT id,purpose,source_sha256,state,(created_at IS NOT NULL AND created_at <= CURRENT_TIMESTAMP) FROM app.media_asset ORDER BY id",
    "files": "SELECT id,asset_id,kind,storage_key,sha256,byte_size,mime_type,width,height FROM app.media_assetfile ORDER BY id",
    "pages": "SELECT id,name,kind,parent_id,position,is_published FROM app.pages_page ORDER BY id",
    "routes": "SELECT id,page_id,target,mode,outcome FROM app.pages_route ORDER BY id",
    "settings": "SELECT id,structure_generation,settings_generation,organization_name,legal_name,phone_display,phone_e164,address,opening_hours,contact_email,map_url,max_url,telegram_url,logo_asset_id FROM app.pages_sitesettings ORDER BY id",
    "usages": "SELECT id,asset_id,scope,target_uuid,slot,position FROM app.media_assetusage ORDER BY id",
    "albums": "SELECT id,page_id,generation,position FROM app.gallery_galleryalbum ORDER BY id",
    "photos": "SELECT id,album_id,asset_id,position,alt FROM app.gallery_galleryphoto ORDER BY id",
    "staff": "SELECT id,username,is_active,role,generation,is_superuser,is_staff,password,last_login,first_name,last_name,email,(date_joined IS NOT NULL AND date_joined <= CURRENT_TIMESTAMP) FROM app.accounts_user ORDER BY id",
    "content": "SELECT page_id,generation,current_payload,current_hash,current_author_id,current_created_at,previous_payload,previous_hash,previous_author_id,previous_created_at,last_operation_id,last_operation_action,last_result_generation,last_result_hash FROM app.pages_pagecontent ORDER BY page_id",
    "grants": "SELECT staff_id,page_id,groups FROM app.pages_pagegrant ORDER BY staff_id,page_id",
}
OWNER_SETTINGS = (
    "search_path=app, pg_catalog",
    "statement_timeout=5min",
    "lock_timeout=5s",
    "idle_in_transaction_session_timeout=1min",
)
IMPORTER_SETTINGS = (
    "search_path=app, pg_catalog",
    "statement_timeout=15min",
    "lock_timeout=5s",
    "idle_in_transaction_session_timeout=1min",
)
TARGET_COLLISION_SQL = """
SELECT
  (SELECT oid FROM pg_database WHERE datname = %s),
  (SELECT oid FROM pg_roles WHERE rolname = %s),
  (SELECT oid FROM pg_roles WHERE rolname = %s)
""".strip()
TARGET_IDENTITY_SQL = """
SELECT d.oid, d.datdba, owner_role.oid, importer_role.oid
FROM pg_database d
JOIN pg_roles owner_role ON owner_role.rolname = %s
JOIN pg_roles importer_role ON importer_role.rolname = %s
WHERE d.datname = %s
""".strip()
EMPTY_PUBLIC_SQL = """
SELECT count(*)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S','f')
""".strip()
TARGET_ROLE_IDENTITY_SQL = """
SELECT r.oid, r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolinherit,
       r.rolreplication, r.rolbypassrls, r.rolcanlogin, r.rolconnlimit,
       (SELECT count(*) FROM pg_auth_members m
        WHERE m.roleid = r.oid OR m.member = r.oid)
FROM pg_roles r WHERE r.rolname = %s
""".strip()
TARGET_LOGIN_IDENTITY_SQL = """
SELECT r.oid, r.rolcanlogin,
       to_char(r.rolvaliduntil AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
FROM pg_roles r WHERE r.rolname = %s
""".strip()
TARGET_SESSION_COUNT_SQL = """
SELECT count(*) FROM pg_stat_activity WHERE usename = %s
""".strip()
TARGET_RUNTIME_SETTINGS_SQL = """
SELECT current_user, current_database(),
       current_setting('search_path'),
       current_setting('statement_timeout'),
       current_setting('lock_timeout'),
       current_setting('idle_in_transaction_session_timeout')
""".strip()
TARGET_GLOBAL_PROOF_SQL = """
WITH role_row AS (
  SELECT oid, rolsuper, rolcreatedb, rolcreaterole, rolinherit,
         rolreplication, rolbypassrls, rolcanlogin, rolconnlimit
  FROM pg_roles WHERE rolname = %s
), violations AS (
  SELECT 'role-shape' AS code FROM role_row
  WHERE rolsuper OR rolcreatedb OR rolcreaterole OR rolinherit
     OR rolreplication OR rolbypassrls OR rolcanlogin IS DISTINCT FROM %s
     OR rolconnlimit <> 1
  UNION ALL SELECT 'role-membership' FROM role_row r
  WHERE EXISTS (SELECT 1 FROM pg_auth_members m
                WHERE m.roleid = r.oid OR m.member = r.oid)
  UNION ALL SELECT 'other-database' FROM pg_database d
  WHERE d.datname <> %s AND d.datname <> 'template0'
    AND (has_database_privilege(%s, d.oid, 'CONNECT')
      OR has_database_privilege(%s, d.oid, 'CREATE')
      OR has_database_privilege(%s, d.oid, 'TEMP'))
)
SELECT count(*) FROM violations
""".strip()
TARGET_SETTINGS_PROOF_SQL = """
WITH expected(value) AS (
  SELECT unnest(%(expected)s::text[])
), actual(value) AS (
  SELECT unnest(s.setconfig)
  FROM pg_db_role_setting s
  WHERE s.setrole = %(role)s::regrole
    AND s.setdatabase = (SELECT oid FROM pg_database WHERE datname = %(database)s)
), violations AS (
  (SELECT value FROM expected EXCEPT SELECT value FROM actual)
  UNION ALL
  (SELECT value FROM actual EXCEPT SELECT value FROM expected)
  UNION ALL
  SELECT value FROM unnest(COALESCE(
    (SELECT rolconfig FROM pg_roles WHERE rolname = %(role)s), ARRAY[]::text[]
  )) value
  UNION ALL
  SELECT 'extra-database-setting' FROM pg_db_role_setting s
  WHERE s.setrole = %(role)s::regrole
    AND s.setdatabase <> (SELECT oid FROM pg_database WHERE datname = %(database)s)
)
SELECT count(*) FROM violations
""".strip()
TARGET_ROLE_ABSENT_SQL = """
SELECT count(*) FROM pg_roles WHERE rolname = %s
""".strip()
TARGET_PRIVILEGE_PROOF_SQL = """
WITH expected(name) AS (
  SELECT unnest(%(tables)s::text[])
), app_tables AS (
  SELECT c.oid, c.relname, c.relkind, c.relowner, c.relacl
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'app' AND c.relkind IN ('r','p','v','m','S','f')
), app_functions AS (
  SELECT p.oid, p.proowner, p.proacl
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'app'
), app_types AS (
  SELECT t.oid, t.typowner, t.typacl
  FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
  WHERE n.nspname = 'app'
), violations AS (
  SELECT 'database-public' AS code
  FROM pg_database d
  WHERE d.datname = current_database() AND EXISTS (
    SELECT 1 FROM aclexplode(COALESCE(d.datacl, acldefault('d', d.datdba))) x
    WHERE x.grantee = 0 AND x.privilege_type IN ('CONNECT','CREATE','TEMPORARY')
  )
  UNION ALL SELECT 'schema-public'
  FROM pg_namespace n WHERE n.nspname = 'app' AND EXISTS (
    SELECT 1 FROM aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner))) x
    WHERE x.grantee = 0 AND x.privilege_type IN ('USAGE','CREATE')
  )
  UNION ALL SELECT 'importer-database'
  WHERE NOT has_database_privilege(%(importer)s, current_database(), 'CONNECT')
     OR has_database_privilege(%(importer)s, current_database(), 'CREATE')
     OR has_database_privilege(%(importer)s, current_database(), 'TEMP')
  UNION ALL SELECT 'importer-schema'
  WHERE NOT has_schema_privilege(%(importer)s, 'app', 'USAGE')
     OR has_schema_privilege(%(importer)s, 'app', 'CREATE')
  UNION ALL SELECT 'owner-database'
  WHERE NOT has_database_privilege(%(owner)s, current_database(), 'CONNECT')
     OR NOT has_database_privilege(%(owner)s, current_database(), 'CREATE')
     OR NOT has_database_privilege(%(owner)s, current_database(), 'TEMP')
  UNION ALL SELECT 'schema-owner' FROM pg_namespace n
  WHERE n.nspname = 'app' AND n.nspowner <> %(owner)s::regrole
  UNION ALL SELECT 'missing-table' FROM expected e
  LEFT JOIN app_tables t ON t.relname = e.name AND t.relkind IN ('r','p')
  WHERE t.oid IS NULL
  UNION ALL SELECT 'importer-table' FROM expected e
  WHERE NOT has_table_privilege(%(importer)s, 'app.' || e.name, 'SELECT')
     OR NOT has_table_privilege(%(importer)s, 'app.' || e.name, 'INSERT')
     OR has_table_privilege(%(importer)s, 'app.' || e.name, 'UPDATE')
     OR has_table_privilege(%(importer)s, 'app.' || e.name, 'DELETE')
     OR has_table_privilege(%(importer)s, 'app.' || e.name, 'TRUNCATE')
     OR has_table_privilege(%(importer)s, 'app.' || e.name, 'REFERENCES')
     OR has_table_privilege(%(importer)s, 'app.' || e.name, 'TRIGGER')
     OR has_any_column_privilege(%(importer)s, 'app.' || e.name,
                                 'UPDATE,REFERENCES')
  UNION ALL SELECT 'unexpected-importer-table' FROM app_tables t
  LEFT JOIN expected e ON e.name = t.relname
  WHERE e.name IS NULL AND t.relkind IN ('r','p','v','m','f')
    AND (has_table_privilege(%(importer)s, t.oid,
          'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
      OR has_any_column_privilege(%(importer)s, t.oid,
                                  'SELECT,INSERT,UPDATE,REFERENCES'))
  UNION ALL SELECT 'importer-sequence' FROM app_tables t
  WHERE t.relkind = 'S' AND has_sequence_privilege(%(importer)s, t.oid,
                                                    'USAGE,SELECT,UPDATE')
  UNION ALL SELECT 'public-object' FROM app_tables t
  WHERE EXISTS (
    SELECT 1 FROM aclexplode(COALESCE(
      t.relacl,
      acldefault((CASE WHEN t.relkind = 'S' THEN 'S' ELSE 'r' END)::"char",
                 t.relowner)
    )) x WHERE x.grantee = 0
  )
  UNION ALL SELECT 'importer-function' FROM app_functions p
  WHERE has_function_privilege(%(importer)s, p.oid, 'EXECUTE')
  UNION ALL SELECT 'public-function' FROM app_functions p
  WHERE EXISTS (
    SELECT 1 FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) x
    WHERE x.grantee = 0
  )
  UNION ALL SELECT 'importer-type' FROM app_types t
  WHERE has_type_privilege(%(importer)s, t.oid, 'USAGE')
  UNION ALL SELECT 'public-type' FROM app_types t
  WHERE EXISTS (
    SELECT 1 FROM aclexplode(COALESCE(t.typacl, acldefault('T', t.typowner))) x
    WHERE x.grantee = 0
  )
  UNION ALL SELECT 'owner-object' FROM app_tables t
  WHERE t.relowner <> %(owner)s::regrole
  UNION ALL SELECT 'owner-function' FROM app_functions p
  WHERE p.proowner <> %(owner)s::regrole
  UNION ALL SELECT 'owner-type' FROM app_types t
  WHERE t.typowner <> %(owner)s::regrole
  UNION ALL SELECT 'database-owner' FROM pg_database d
  WHERE d.datname = current_database() AND d.datdba <> %(owner)s::regrole
  UNION ALL SELECT 'default-public' FROM pg_default_acl a
  WHERE a.defaclrole = %(owner)s::regrole
    AND EXISTS (
      SELECT 1 FROM aclexplode(COALESCE(a.defaclacl, acldefault(a.defaclobjtype, a.defaclrole))) x
      WHERE x.grantee = 0
    )
)
SELECT count(*) FROM violations
""".strip()


@dataclass(frozen=True, slots=True)
class TargetEndpoint:
    host: str
    port: int
    sslrootcert: Path
    admin_user: str
    admin_secret_file: Path
    secret_root: Path
    valid_until_utc: str


def _generated_identifier(value: object, prefix: str) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or re.fullmatch(r"[a-z][a-z0-9_]{0,62}", value) is None
    ):
        raise TargetRuntimeError("target-identifier")
    return value


def _target_endpoint(value: object) -> TargetEndpoint:
    if not isinstance(value, TargetEndpoint):
        raise TargetRuntimeError("target-endpoint")
    paths = (value.sslrootcert, value.admin_secret_file, value.secret_root)
    if (
        not isinstance(value.host, str)
        or not value.host
        or isinstance(value.port, bool)
        or not isinstance(value.port, int)
        or not 1 <= value.port <= 65535
        or not isinstance(value.admin_user, str)
        or not value.admin_user
        or not all(isinstance(path, Path) and path.is_absolute() for path in paths)
        or not _regular_non_link(value.sslrootcert)
        or not _trusted_parent(value.admin_secret_file)
        or not _trusted_directory(value.secret_root)
        or not _valid_expiry(value.valid_until_utc)
    ):
        raise TargetRuntimeError("target-endpoint")
    return value


def _execute(cursor: Any, sql: str, params: tuple[object, ...] | None = None) -> None:
    cursor.execute(sql, params)


class TargetDatabaseLifecycle:
    """Generated target DB/role lifecycle; statements accept no caller identifiers."""

    __slots__ = (
        "_endpoint", "_names", "_connect", "_admin", "_target_admin",
        "_database_oid", "_owner_oid", "_importer_oid", "_owner_secret",
        "_importer_secret", "_importer", "_prepare_started", "_grants_started",
        "_prepared", "_closed",
    )

    def __init__(
        self,
        endpoint: TargetEndpoint,
        names: TargetNames,
        connect: Callable[..., Any],
        admin: Any,
        target_admin: Any,
        database_oid: int,
        owner_oid: int,
        importer_oid: int,
    ) -> None:
        self._endpoint = endpoint
        self._names = names
        self._connect = connect
        self._admin = admin
        self._target_admin = target_admin
        self._database_oid = database_oid
        self._owner_oid = owner_oid
        self._importer_oid = importer_oid
        self._owner_secret = None
        self._importer_secret = None
        self._importer = None
        self._prepare_started = False
        self._grants_started = False
        self._prepared = False
        self._closed = False

    @staticmethod
    def _role_identity(
        cursor: Any, name: str, oid: int, *, login: bool | None,
    ) -> None:
        _execute(cursor, TARGET_ROLE_IDENTITY_SQL, (name,))
        row = cursor.fetchone()
        if (
            row is None
            or len(tuple(row)) != 10
            or tuple(row)[:7] != (oid, False, False, False, False, False, False)
            or (login is not None and tuple(row)[7] is not login)
            or tuple(row)[8:] != (1, 0)
        ):
            raise TargetRuntimeError("target-role-identity")

    def _login_identity(self, cursor: Any, name: str, oid: int) -> None:
        _execute(cursor, TARGET_LOGIN_IDENTITY_SQL, (name,))
        row = cursor.fetchone()
        if row is None or tuple(row) != (oid, True, self._endpoint.valid_until_utc):
            raise TargetRuntimeError("target-role-login")

    @staticmethod
    def _settings_identity(
        cursor: Any,
        role: str,
        database: str,
        expected: tuple[str, ...],
    ) -> None:
        _execute(
            cursor,
            TARGET_SETTINGS_PROOF_SQL,
            {"expected": list(expected), "role": role, "database": database},
        )
        row = cursor.fetchone()
        if row is None or tuple(row) != (0,):
            raise TargetRuntimeError("target-role-settings")

    @staticmethod
    def _global_identity(
        cursor: Any,
        role: str,
        database: str,
        *,
        login: bool,
    ) -> None:
        _execute(
            cursor,
            TARGET_GLOBAL_PROOF_SQL,
            (role, login, database, role, role, role),
        )
        row = cursor.fetchone()
        if row is None or tuple(row) != (0,):
            raise TargetRuntimeError("target-global-privileges")

    def _disable_owned_secret(
        self,
        role: str,
        oid: int,
        path: Path,
        identity: Any,
    ) -> None:
        with self._target_admin.cursor() as cursor:
            self._role_identity(cursor, role, oid, login=None)
            _execute(cursor, f"ALTER ROLE {role} NOLOGIN")
            self._role_identity(cursor, role, oid, login=False)
            _execute(cursor, TARGET_SESSION_COUNT_SQL, (role,))
            sessions = cursor.fetchone()
            if sessions is None or tuple(sessions) != (0,):
                raise TargetRuntimeError("target-role-sessions")
        _delete_owned_secret(path, identity)

    @classmethod
    def create(
        cls,
        endpoint: TargetEndpoint,
        names: TargetNames,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> "TargetDatabaseLifecycle":
        endpoint = _target_endpoint(endpoint)
        if not isinstance(names, TargetNames) or target_names(names.run_id) != names:
            raise TargetRuntimeError("target-names")
        database = _generated_identifier(names.database, "estakada_rebuild_")
        owner = _generated_identifier(names.owner_role, "estakada_rb3_owner_")
        importer = _generated_identifier(names.importer_role, "estakada_rb3_importer_")
        if connect is None:
            from psycopg import connect as psycopg_connect

            connect = psycopg_connect
        admin = target_admin = None
        create_started = False
        try:
            admin_password = _secret(endpoint.admin_secret_file)
            admin = connect(
                host=endpoint.host,
                port=endpoint.port,
                dbname=TARGET_MAINTENANCE_DATABASE,
                user=endpoint.admin_user,
                password=admin_password,
                sslmode="verify-full",
                sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            with admin.cursor() as cursor:
                _execute(cursor, TARGET_COLLISION_SQL, (database, owner, importer))
                collision = cursor.fetchone()
                if collision is None or tuple(collision) != (None, None, None):
                    raise TargetRuntimeError("target-collision")
                create_started = True
                _execute(cursor, (
                    f"CREATE ROLE {owner} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1"
                ))
                _execute(cursor, (
                    f"CREATE ROLE {importer} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 1"
                ))
                _execute(cursor, f"CREATE DATABASE {database} OWNER {owner}")
                _execute(cursor, TARGET_IDENTITY_SQL, (owner, importer, database))
                identity = cursor.fetchone()
            if (
                identity is None
                or len(tuple(identity)) != 4
                or any(type(item) is not int or item <= 0 for item in tuple(identity))
                or tuple(identity)[1] != tuple(identity)[2]
            ):
                raise TargetRuntimeError("target-identity")
            database_oid, database_owner_oid, owner_oid, importer_oid = tuple(identity)
            with admin.cursor() as cursor:
                cls._role_identity(cursor, owner, owner_oid, login=False)
                cls._role_identity(cursor, importer, importer_oid, login=False)
            target_admin = connect(
                host=endpoint.host,
                port=endpoint.port,
                dbname=database,
                user=endpoint.admin_user,
                password=admin_password,
                sslmode="verify-full",
                sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            with target_admin.cursor() as cursor:
                cls._role_identity(cursor, owner, owner_oid, login=False)
                cls._role_identity(cursor, importer, importer_oid, login=False)
                _execute(cursor, EMPTY_PUBLIC_SQL)
                public_count = cursor.fetchone()
                if public_count is None or tuple(public_count) != (0,):
                    raise TargetRuntimeError("target-public-nonempty")
                for sql in (
                    f"REVOKE CONNECT, CREATE, TEMP ON DATABASE {database} FROM PUBLIC",
                    "DROP SCHEMA public",
                    f"CREATE SCHEMA app AUTHORIZATION {owner}",
                    "REVOKE ALL ON SCHEMA app FROM PUBLIC",
                    f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app "
                    "REVOKE ALL ON TABLES FROM PUBLIC",
                    f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app "
                    "REVOKE ALL ON SEQUENCES FROM PUBLIC",
                    f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app "
                    "REVOKE ALL ON FUNCTIONS FROM PUBLIC",
                    f"ALTER DEFAULT PRIVILEGES FOR ROLE {owner} IN SCHEMA app "
                    "REVOKE ALL ON TYPES FROM PUBLIC",
                    f"ALTER ROLE {owner} IN DATABASE {database} SET search_path = app,pg_catalog",
                    f"ALTER ROLE {owner} IN DATABASE {database} SET statement_timeout = '5min'",
                    f"ALTER ROLE {owner} IN DATABASE {database} SET lock_timeout = '5s'",
                    f"ALTER ROLE {owner} IN DATABASE {database} "
                    "SET idle_in_transaction_session_timeout = '1min'",
                    f"ALTER ROLE {importer} IN DATABASE {database} SET search_path = app,pg_catalog",
                    f"ALTER ROLE {importer} IN DATABASE {database} SET statement_timeout = '15min'",
                    f"ALTER ROLE {importer} IN DATABASE {database} SET lock_timeout = '5s'",
                    f"ALTER ROLE {importer} IN DATABASE {database} "
                    "SET idle_in_transaction_session_timeout = '1min'",
                ):
                    _execute(cursor, sql)
            return cls(
                endpoint, names, connect, admin, target_admin,
                database_oid, owner_oid, importer_oid,
            )
        except TargetRuntimeError:
            if target_admin is not None:
                try:
                    target_admin.close()
                except Exception:
                    pass
            if admin is not None:
                try:
                    admin.close()
                except Exception:
                    pass
            if create_started:
                raise TargetRuntimeError("target-create-ambiguous") from None
            raise
        except Exception:
            if target_admin is not None:
                try:
                    target_admin.close()
                except Exception:
                    pass
            if admin is not None:
                try:
                    admin.close()
                except Exception:
                    pass
            raise TargetRuntimeError(
                "target-create-ambiguous" if create_started else "target-create"
            ) from None

    @classmethod
    def recover_after_create(
        cls,
        endpoint: TargetEndpoint,
        names: TargetNames,
        *,
        connect: Callable[..., Any] | None = None,
    ) -> tuple[str, "TargetDatabaseLifecycle | None"]:
        endpoint = _target_endpoint(endpoint)
        if not isinstance(names, TargetNames) or target_names(names.run_id) != names:
            raise TargetRuntimeError("target-names")
        if connect is None:
            from psycopg import connect as psycopg_connect

            connect = psycopg_connect
        admin = target_admin = None
        try:
            admin = connect(
                host=endpoint.host, port=endpoint.port,
                dbname=TARGET_MAINTENANCE_DATABASE, user=endpoint.admin_user,
                password=_secret(endpoint.admin_secret_file),
                sslmode="verify-full", sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            with admin.cursor() as cursor:
                _execute(
                    cursor, TARGET_COLLISION_SQL,
                    (names.database, names.owner_role, names.importer_role),
                )
                row = cursor.fetchone()
                if row is None or len(tuple(row)) != 3:
                    raise TargetRuntimeError("target-acquisition-ambiguous")
                present = tuple(item is not None for item in row)
                if present == (False, False, False):
                    admin.close()
                    return "ABSENT", None
                if present != (True, True, True):
                    admin.close()
                    return "AMBIGUOUS", None
                _execute(
                    cursor, TARGET_IDENTITY_SQL,
                    (names.owner_role, names.importer_role, names.database),
                )
                identity = cursor.fetchone()
            if (
                identity is None
                or len(tuple(identity)) != 4
                or any(type(item) is not int or item <= 0 for item in tuple(identity))
                or tuple(identity)[1] != tuple(identity)[2]
                or tuple(row) != (
                    tuple(identity)[0], tuple(identity)[2], tuple(identity)[3],
                )
            ):
                admin.close()
                return "AMBIGUOUS", None
            target_admin = connect(
                host=endpoint.host, port=endpoint.port, dbname=names.database,
                user=endpoint.admin_user, password=_secret(endpoint.admin_secret_file),
                sslmode="verify-full", sslrootcert=str(endpoint.sslrootcert),
                autocommit=True,
            )
            lifecycle = cls(
                endpoint, names, connect, admin, target_admin,
                tuple(identity)[0], tuple(identity)[2], tuple(identity)[3],
            )
            with target_admin.cursor() as cursor:
                lifecycle._role_identity(
                    cursor, names.owner_role, lifecycle._owner_oid, login=False,
                )
                lifecycle._role_identity(
                    cursor, names.importer_role, lifecycle._importer_oid, login=False,
                )
            return "ACQUIRED", lifecycle
        except Exception:
            if target_admin is not None:
                try:
                    target_admin.close()
                except Exception:
                    pass
            if admin is not None:
                try:
                    admin.close()
                except Exception:
                    pass
            return "AMBIGUOUS", None

    def prepare(
        self,
        migrate: Callable[[TargetEndpoint, TargetNames, Path], None],
    ) -> Any:
        if self._closed or self._prepare_started:
            raise TargetRuntimeError("target-prepare-state")
        if not callable(migrate):
            raise TargetRuntimeError("target-migrate")
        self._prepare_started = True
        owner_secret_path = self._endpoint.secret_root / f"{self._names.run_id}.owner.secret"
        importer_secret_path = self._endpoint.secret_root / f"{self._names.run_id}.importer.secret"
        owner_password = secrets.token_urlsafe(48)
        importer_password = secrets.token_urlsafe(48)
        try:
            self._owner_secret = _write_secret(owner_secret_path, owner_password)
            with self._target_admin.cursor() as cursor:
                self._role_identity(
                    cursor, self._names.owner_role, self._owner_oid, login=False,
                )
                self._settings_identity(
                    cursor, self._names.owner_role, self._names.database,
                    OWNER_SETTINGS,
                )
            with self._admin.cursor() as cursor:
                self._global_identity(
                    cursor, self._names.owner_role, self._names.database, login=False,
                )
            with self._target_admin.cursor() as cursor:
                _execute(
                    cursor,
                    f"ALTER ROLE {self._names.owner_role} LOGIN PASSWORD %s VALID UNTIL %s",
                    (owner_password, self._endpoint.valid_until_utc),
                )
                self._login_identity(cursor, self._names.owner_role, self._owner_oid)
            with self._admin.cursor() as cursor:
                self._global_identity(
                    cursor, self._names.owner_role, self._names.database, login=True,
                )
            migrate(self._endpoint, self._names, owner_secret_path)
            owner_probe = self._connect(
                host=self._endpoint.host,
                port=self._endpoint.port,
                dbname=self._names.database,
                user=self._names.owner_role,
                password=owner_password,
                sslmode="verify-full",
                sslrootcert=str(self._endpoint.sslrootcert),
                autocommit=True,
            )
            try:
                with owner_probe.cursor() as cursor:
                    _execute(cursor, TARGET_RUNTIME_SETTINGS_SQL)
                    settings = cursor.fetchone()
                    if settings is None or tuple(settings) != (
                        self._names.owner_role, self._names.database,
                        "app, pg_catalog", "5min", "5s", "1min",
                    ):
                        raise TargetRuntimeError("target-owner-settings")
            finally:
                owner_probe.close()
            with self._target_admin.cursor() as cursor:
                self._role_identity(
                    cursor, self._names.owner_role, self._owner_oid, login=True,
                )
                _execute(cursor, f"ALTER ROLE {self._names.owner_role} NOLOGIN")
                self._role_identity(
                    cursor, self._names.owner_role, self._owner_oid, login=False,
                )
                self._settings_identity(
                    cursor, self._names.owner_role, self._names.database,
                    OWNER_SETTINGS,
                )
                _execute(cursor, TARGET_SESSION_COUNT_SQL, (self._names.owner_role,))
                sessions = cursor.fetchone()
                if sessions is None or tuple(sessions) != (0,):
                    raise TargetRuntimeError("target-owner-sessions")
                for table in TARGET_TABLES:
                    self._grants_started = True
                    _execute(cursor, f"REVOKE ALL ON TABLE app.{table} FROM PUBLIC")
                    _execute(
                        cursor,
                        f"GRANT SELECT, INSERT ON TABLE app.{table} TO {self._names.importer_role}",
                    )
                _execute(cursor, "REVOKE ALL ON ALL SEQUENCES IN SCHEMA app FROM PUBLIC")
                _execute(cursor, "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC")
                _execute(cursor, f"GRANT CONNECT ON DATABASE {self._names.database} TO {self._names.importer_role}")
                _execute(cursor, f"GRANT USAGE ON SCHEMA app TO {self._names.importer_role}")
                self._role_identity(
                    cursor, self._names.importer_role, self._importer_oid, login=False,
                )
                self._settings_identity(
                    cursor, self._names.importer_role, self._names.database,
                    IMPORTER_SETTINGS,
                )
                _execute(
                    cursor,
                    TARGET_PRIVILEGE_PROOF_SQL,
                    {
                        "tables": list(TARGET_TABLES),
                        "importer": self._names.importer_role,
                        "owner": self._names.owner_role,
                    },
                )
                proof = cursor.fetchone()
                if proof is None or tuple(proof) != (0,):
                    raise TargetRuntimeError("target-privileges")
            with self._admin.cursor() as cursor:
                self._global_identity(
                    cursor, self._names.owner_role, self._names.database,
                    login=False,
                )
                self._global_identity(
                    cursor, self._names.importer_role, self._names.database,
                    login=False,
                )
            _delete_owned_secret(owner_secret_path, self._owner_secret)
            self._owner_secret = None
            self._importer_secret = _write_secret(importer_secret_path, importer_password)
            with self._target_admin.cursor() as cursor:
                self._role_identity(
                    cursor, self._names.importer_role, self._importer_oid, login=False,
                )
                _execute(
                    cursor,
                    f"ALTER ROLE {self._names.importer_role} LOGIN PASSWORD %s VALID UNTIL %s",
                    (importer_password, self._endpoint.valid_until_utc),
                )
                self._login_identity(
                    cursor, self._names.importer_role, self._importer_oid,
                )
            with self._admin.cursor() as cursor:
                self._global_identity(
                    cursor, self._names.importer_role, self._names.database,
                    login=True,
                )
            self._importer = self._connect(
                host=self._endpoint.host,
                port=self._endpoint.port,
                dbname=self._names.database,
                user=self._names.importer_role,
                password=importer_password,
                sslmode="verify-full",
                sslrootcert=str(self._endpoint.sslrootcert),
                autocommit=False,
            )
            with self._importer.cursor() as cursor:
                _execute(cursor, TARGET_RUNTIME_SETTINGS_SQL)
                settings = cursor.fetchone()
                if settings is None or tuple(settings) != (
                    self._names.importer_role, self._names.database,
                    "app, pg_catalog", "15min", "5s", "1min",
                ):
                    raise TargetRuntimeError("target-importer-settings")
            self._importer.rollback()
            self._prepared = True
            return self._importer
        except Exception as exc:
            cleanup_error = False
            if self._importer is not None:
                try:
                    self._importer.close()
                    self._importer = None
                except Exception:
                    cleanup_error = True
            for role, oid, path, attribute in (
                (
                    self._names.importer_role, self._importer_oid,
                    importer_secret_path, "_importer_secret",
                ),
                (
                    self._names.owner_role, self._owner_oid,
                    owner_secret_path, "_owner_secret",
                ),
            ):
                identity = getattr(self, attribute)
                if identity is None:
                    continue
                try:
                    self._disable_owned_secret(role, oid, path, identity)
                    setattr(self, attribute, None)
                except Exception:
                    cleanup_error = True
            if cleanup_error:
                raise TargetRuntimeError("target-prepare-ambiguous") from None
            if isinstance(exc, TargetRuntimeError):
                raise exc
            raise TargetRuntimeError("target-prepare-ambiguous") from None

    def close_identities(self) -> None:
        if self._closed:
            raise TargetRuntimeError("target-close-reuse")
        self._closed = True
        error = False
        owner_safe = False
        importer_removed = False
        if self._importer is not None:
            try:
                self._importer.close()
            except Exception:
                error = True
        try:
            with self._target_admin.cursor() as cursor:
                self._role_identity(
                    cursor, self._names.owner_role, self._owner_oid,
                    login=None,
                )
                _execute(cursor, f"ALTER ROLE {self._names.owner_role} NOLOGIN")
                self._role_identity(
                    cursor, self._names.owner_role, self._owner_oid, login=False,
                )
                _execute(cursor, TARGET_SESSION_COUNT_SQL, (self._names.owner_role,))
                owner_sessions = cursor.fetchone()
                if owner_sessions is None or tuple(owner_sessions) != (0,):
                    error = True
                else:
                    owner_safe = True
                self._role_identity(
                    cursor, self._names.importer_role, self._importer_oid,
                    login=None,
                )
                _execute(cursor, f"ALTER ROLE {self._names.importer_role} NOLOGIN")
                self._role_identity(
                    cursor, self._names.importer_role, self._importer_oid, login=False,
                )
                _execute(cursor, TARGET_SESSION_COUNT_SQL, (self._names.importer_role,))
                sessions = cursor.fetchone()
                if sessions is None or tuple(sessions) != (0,):
                    error = True
                else:
                    if self._grants_started:
                        for table in TARGET_TABLES:
                            _execute(
                                cursor,
                                f"REVOKE SELECT, INSERT ON TABLE app.{table} FROM {self._names.importer_role}",
                            )
                        _execute(cursor, f"REVOKE USAGE ON SCHEMA app FROM {self._names.importer_role}")
                        _execute(cursor, f"REVOKE CONNECT ON DATABASE {self._names.database} FROM {self._names.importer_role}")
                    _execute(cursor, f"ALTER ROLE {self._names.importer_role} IN DATABASE {self._names.database} RESET ALL")
                    _execute(cursor, f"DROP ROLE {self._names.importer_role}")
                    _execute(cursor, "SELECT oid FROM pg_roles WHERE rolname = %s", (self._names.importer_role,))
                    if cursor.fetchone() is not None:
                        error = True
                    else:
                        importer_removed = True
        except Exception:
            error = True
        if self._owner_secret is not None and owner_safe:
            try:
                _delete_owned_secret(
                    self._endpoint.secret_root / f"{self._names.run_id}.owner.secret",
                    self._owner_secret,
                )
                self._owner_secret = None
            except Exception:
                error = True
        if self._importer_secret is not None and importer_removed:
            try:
                _delete_owned_secret(
                    self._endpoint.secret_root / f"{self._names.run_id}.importer.secret",
                    self._importer_secret,
                )
                self._importer_secret = None
            except Exception:
                error = True
        try:
            self._target_admin.close()
            self._admin.close()
        except Exception:
            error = True
        if error:
            raise TargetRuntimeError("target-close-ambiguous")


def run_target_migrations(
    endpoint: TargetEndpoint,
    names: TargetNames,
    owner_secret_file: Path,
) -> None:
    """Apply only the current reviewed Django migration leaves to one generated DB."""
    endpoint = _target_endpoint(endpoint)
    if not isinstance(names, TargetNames) or target_names(names.run_id) != names:
        raise TargetRuntimeError("target-names")
    if (
        not isinstance(owner_secret_file, Path)
        or owner_secret_file != endpoint.secret_root / f"{names.run_id}.owner.secret"
    ):
        raise TargetRuntimeError("target-owner-secret")
    alias = f"rb3_{names.run_id.hex}"
    connection = None
    connections_ref = None
    alias_registered = False
    failure: TargetRuntimeError | None = None
    try:
        from django.db import connections
        from django.db.migrations.executor import MigrationExecutor
        from django.db.migrations.recorder import MigrationRecorder

        connections_ref = connections
        if alias in connections_ref.databases:
            raise TargetRuntimeError("target-migration-alias")
        connections_ref.databases[alias] = {
            "ATOMIC_REQUESTS": False,
            "AUTOCOMMIT": True,
            "CONN_HEALTH_CHECKS": False,
            "ENGINE": "django.db.backends.postgresql",
            "NAME": names.database,
            "USER": names.owner_role,
            "PASSWORD": _secret(owner_secret_file),
            "HOST": endpoint.host,
            "PORT": endpoint.port,
            "CONN_MAX_AGE": 0,
            "DISABLE_SERVER_SIDE_CURSORS": False,
            "OPTIONS": {
                "sslmode": "verify-full",
                "sslrootcert": str(endpoint.sslrootcert),
            },
            "TEST": {},
            "TIME_ZONE": "Europe/Moscow",
        }
        alias_registered = True
        connection = connections_ref[alias]
        executor = MigrationExecutor(connection)
        leaves = frozenset(executor.loader.graph.leaf_nodes())
        if leaves != TARGET_MIGRATION_LEAVES:
            raise TargetRuntimeError("target-migration-leaves")
        executor.migrate(sorted(leaves))
        applied = frozenset(MigrationRecorder(connection).applied_migrations())
        if not TARGET_MIGRATION_LEAVES <= applied:
            raise TargetRuntimeError("target-migration-apply")
    except TargetRuntimeError as exc:
        failure = exc
    except Exception:
        failure = TargetRuntimeError("target-migration-ambiguous")
    finally:
        cleanup_error = False
        if alias_registered and connections_ref is not None:
            try:
                config = connections_ref.databases.get(alias)
                if not isinstance(config, dict):
                    cleanup_error = True
                else:
                    config["PASSWORD"] = ""
            except Exception:
                cleanup_error = True
            if connection is not None:
                try:
                    connection.settings_dict["PASSWORD"] = ""
                except Exception:
                    cleanup_error = True
                try:
                    connection.close()
                except Exception:
                    cleanup_error = True
            storage = getattr(connections_ref, "_connections", None)
            if storage is None:
                cleanup_error = True
            else:
                try:
                    getattr(storage, alias)
                except AttributeError:
                    pass
                else:
                    try:
                        del connections_ref[alias]
                    except Exception:
                        cleanup_error = True
            try:
                connections_ref.databases.pop(alias, None)
            except Exception:
                cleanup_error = True
            try:
                if alias in connections_ref.databases:
                    cleanup_error = True
                if storage is not None:
                    try:
                        getattr(storage, alias)
                    except AttributeError:
                        pass
                    else:
                        cleanup_error = True
            except Exception:
                cleanup_error = True
            if cleanup_error:
                raise TargetRuntimeError("target-migration-cleanup-ambiguous") from None
    if failure is not None:
        raise failure from None


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
    except Exception:
        raise TargetRuntimeError("target-json") from None


class ProjectionWriter:
    """Literal bounded inserts for one already validated manifest/private stream."""

    __slots__ = (
        "_connection", "_manifest", "_private", "_ledger", "_begun",
        "_verified", "_committed",
    )

    def __init__(self, connection: Any) -> None:
        if connection is None:
            raise TargetRuntimeError("target-import-connection")
        self._connection = connection
        self._manifest: PublicManifest | None = None
        self._private: Any = None
        self._ledger: Any = None
        self._begun = False
        self._verified = False
        self._committed = False

    def begin(self) -> None:
        if self._begun or self._committed:
            raise TargetRuntimeError("target-import-state")
        with self._connection.cursor() as cursor:
            _execute(cursor, "BEGIN ISOLATION LEVEL SERIALIZABLE")
        self._begun = True

    def import_public(self, manifest: PublicManifest) -> None:
        if not self._begun or self._manifest is not None or not isinstance(manifest, PublicManifest):
            raise TargetRuntimeError("target-public-state")
        sections = manifest.sections
        if frozenset(sections) != frozenset({
            "routes", "pages", "assets", "files", "usages",
            "gallery_albums", "gallery_photos",
        }):
            raise TargetRuntimeError("target-public-shape")
        page_rows = {row["id"]: row for row in sections["pages"]}
        if len(page_rows) != len(sections["pages"]) or any(
            row["parent_id"] is not None and row["parent_id"] not in page_rows
            for row in sections["pages"]
        ):
            raise TargetRuntimeError("target-page-reference")
        remaining = set(page_rows)
        ordered_pages: list[dict[str, Any]] = []
        while remaining:
            ready = sorted(
                (page_rows[item] for item in remaining
                 if page_rows[item]["parent_id"] is None
                 or page_rows[item]["parent_id"] not in remaining),
                key=lambda row: (row["position"], row["id"]),
            )
            if not ready:
                raise TargetRuntimeError("target-page-cycle")
            ordered_pages.extend(ready)
            remaining.difference_update(row["id"] for row in ready)
        with self._connection.cursor() as cursor:
            for row in sections["assets"]:
                _execute(cursor, INSERT_ASSET_SQL, (
                    row["id"], row["purpose"], row["source_sha256"], row["state"],
                ))
            for row in sections["files"]:
                _execute(cursor, INSERT_FILE_SQL, (
                    row["id"], row["asset_id"], row["kind"],
                    target_storage_key(row), row["sha256"], row["byte_size"],
                    row["mime_type"], row["width"], row["height"],
                ))
            for row in ordered_pages:
                _execute(cursor, INSERT_PAGE_SQL, (
                    row["id"], row["name"], row["kind"], row["parent_id"],
                    row["position"], row["is_published"],
                ))
            for row in sections["routes"]:
                _execute(cursor, INSERT_ROUTE_SQL, (
                    row["id"], row["page_id"], row["target"],
                    row["mode"], row["outcome"],
                ))
            settings = manifest.site_settings
            _execute(cursor, INSERT_SETTINGS_SQL, (
                settings["id"], settings["structure_generation"],
                settings["settings_generation"], settings["organization_name"],
                settings["legal_name"], settings["phone_display"],
                settings["phone_e164"], settings["address"],
                settings["opening_hours"], settings["contact_email"],
                settings["map_url"], settings["max_url"],
                settings["telegram_url"], settings["logo_asset_id"],
            ))
            for row in sections["usages"]:
                _execute(cursor, INSERT_USAGE_SQL, (
                    row["id"], row["asset_id"], row["scope"], row["target_uuid"],
                    row["slot"], row["position"],
                ))
            for row in sections["gallery_albums"]:
                _execute(cursor, INSERT_ALBUM_SQL, (
                    row["id"], row["page_id"], row["generation"], row["position"],
                ))
            for row in sections["gallery_photos"]:
                _execute(cursor, INSERT_PHOTO_SQL, (
                    row["id"], row["album_id"], row["asset_id"],
                    row["position"], row["alt"],
                ))
        self._manifest = manifest

    def import_private(self, rows: Any) -> None:
        from rebuild3_importer.source import PrivateSourceRows

        if (
            not self._begun or self._manifest is None or self._private is not None
            or not isinstance(rows, PrivateSourceRows)
        ):
            raise TargetRuntimeError("target-private-state")
        pages = {row["id"]: row for row in self._manifest.sections["pages"]}
        provenance: dict[tuple[str, str], uuid.UUID] = {}
        for item in rows.provenance:
            key = (str(item.page_id), item.version)
            if key in provenance or key[0] not in pages or item.version not in ("CURRENT", "PREVIOUS"):
                raise TargetRuntimeError("target-provenance")
            provenance[key] = item.staff_id
        staff_ids = {item.id for item in rows.staff}
        staff_by_id = {item.id: item for item in rows.staff}
        usernames = {item.username for item in rows.staff}
        owners = [item for item in rows.staff if item.role == "OWNER"]
        if (
            len(staff_ids) != len(rows.staff)
            or len(usernames) != len(rows.staff)
            or len(owners) != 1
            or owners[0].username != "nesadmin"
            or not owners[0].is_active
            or any(
                item.role not in ("OWNER", "EMPLOYEE")
                or not isinstance(item.username, str)
                or not item.username
                or type(item.is_active) is not bool
                or type(item.generation) is not int
                or item.generation < 1
                for item in rows.staff
            )
        ):
            raise TargetRuntimeError("target-staff")
        expected = {
            (page_id, version)
            for page_id, page in pages.items()
            for version in (("CURRENT",) if page["previous"] is None else ("CURRENT", "PREVIOUS"))
        }
        if set(provenance) != expected or any(value not in staff_ids for value in provenance.values()):
            raise TargetRuntimeError("target-provenance")
        grant_keys = {(item.staff_id, item.page_id) for item in rows.grants}
        if len(grant_keys) != len(rows.grants) or any(
            (staff := staff_by_id.get(item.staff_id)) is None
            or staff.role != "EMPLOYEE"
            or not staff.is_active
            or str(item.page_id) not in pages
            or item.groups not in (("text",), ("prices",), ("text", "prices"))
            for item in rows.grants
        ):
            raise TargetRuntimeError("target-grant")
        with self._connection.cursor() as cursor:
            for item in rows.staff:
                _execute(cursor, INSERT_STAFF_SQL, (
                    item.id, item.role == "OWNER", item.username,
                    item.is_active, item.role, item.generation,
                ))
            for page_id in sorted(pages):
                page = pages[page_id]
                current = page["current"]
                previous = page["previous"]
                _execute(cursor, INSERT_CONTENT_SQL, (
                    page_id, page["content_generation"],
                    _canonical_json(current["payload"]), current["sha256"],
                    provenance[(page_id, "CURRENT")], current["created_at"],
                    None if previous is None else _canonical_json(previous["payload"]),
                    None if previous is None else previous["sha256"],
                    None if previous is None else provenance[(page_id, "PREVIOUS")],
                    None if previous is None else previous["created_at"],
                ))
            for item in rows.grants:
                _execute(cursor, INSERT_GRANT_SQL, (
                    uuid.uuid4(), item.staff_id, item.page_id,
                    _canonical_json(list(item.groups)),
                ))
        self._private = rows

    def apply_zero_ledger(self, evidence: Any) -> None:
        from rebuild3_importer.source import VerifiedLedgerEvidence

        if (
            not self._begun or self._private is None or self._ledger is not None
            or not isinstance(evidence, VerifiedLedgerEvidence)
            or evidence.row_count != 0
            or self._manifest is None
            or evidence.snapshot_id != self._manifest.snapshot_id
        ):
            raise TargetRuntimeError("target-ledger")
        self._ledger = evidence

    def verify_counts(self) -> ProjectionCounts:
        if not self._begun or self._manifest is None or self._private is None or self._ledger is None:
            raise TargetRuntimeError("target-verify-state")
        with self._connection.cursor() as cursor:
            _execute(cursor, TARGET_INVARIANT_SQL)
            invariant = cursor.fetchone()
            if invariant is None or tuple(invariant) != (0,):
                raise TargetRuntimeError("target-invariants")
            _execute(cursor, TARGET_COUNT_SQL)
            row = cursor.fetchone()
        if row is None or len(tuple(row)) != 12 or any(
            type(value) is not int or value < 0 for value in tuple(row)
        ):
            raise TargetRuntimeError("target-counts")
        result = ProjectionCounts(*tuple(row))
        manifest = self._manifest.sections
        expected = ProjectionCounts(
            1, len(manifest["pages"]), len(manifest["routes"]),
            len(manifest["pages"]),
            sum(item["previous"] is not None for item in manifest["pages"]),
            len(self._private.staff), len(self._private.grants),
            len(manifest["assets"]), len(manifest["files"]),
            len(manifest["usages"]), len(manifest["gallery_albums"]),
            len(manifest["gallery_photos"]),
        )
        if result != expected:
            raise TargetRuntimeError("target-counts")
        self._verified = True
        return result

    def commit(self) -> None:
        if not self._begun or not self._verified or self._committed:
            raise TargetRuntimeError("target-import-state")
        self._connection.commit()
        self._committed = True
        self._begun = False

    def rollback(self) -> None:
        if not self._begun or self._committed:
            raise TargetRuntimeError("target-import-state")
        self._connection.rollback()
        self._begun = False

    def clear_private(self) -> None:
        self._private = None
        self._ledger = None


def _readback_value(value: object) -> object:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TargetRuntimeError("target-readback-time")
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(value, (dict, list)):
        return _canonical_json(value)
    return value


def _readback_rows(
    cursor: Any, sql: str, expected_count: int,
) -> tuple[tuple[object, ...], ...]:
    _execute(cursor, sql)
    return tuple(
        tuple(_readback_value(value) for value in row)
        for row in cursor.fetchmany(expected_count + 1)
    )


class CommittedReadback:
    """Exact committed projection comparison; it is deliberately not a repository."""

    __slots__ = ("_connection", "_used")

    def __init__(self, connection: Any) -> None:
        if connection is None:
            raise TargetRuntimeError("target-readback-connection")
        self._connection = connection
        self._used = False

    def read(
        self,
        manifest: PublicManifest,
        private: PrivateSourceRows,
        ledger: VerifiedLedgerEvidence,
        source_media_digest: str,
        target_media_digest: str,
    ) -> ReadbackProof:
        if (
            self._used or not isinstance(manifest, PublicManifest)
            or not isinstance(private, PrivateSourceRows)
            or not isinstance(ledger, VerifiedLedgerEvidence)
            or ledger.row_count != 0 or ledger.snapshot_id != manifest.snapshot_id
            or not isinstance(source_media_digest, str)
            or not isinstance(target_media_digest, str)
            or SHA256.fullmatch(source_media_digest) is None
            or source_media_digest != target_media_digest
        ):
            raise TargetRuntimeError("target-readback-state")
        self._used = True
        sections = manifest.sections
        provenance = {
            (str(item.page_id), item.version): str(item.staff_id)
            for item in private.provenance
        }
        expected: dict[str, tuple[tuple[object, ...], ...]] = {
            "assets": tuple(sorted((
                row["id"], row["purpose"], row["source_sha256"], row["state"], True,
            ) for row in sections["assets"])),
            "files": tuple(sorted((
                row["id"], row["asset_id"], row["kind"], target_storage_key(row),
                row["sha256"], row["byte_size"], row["mime_type"],
                row["width"], row["height"],
            ) for row in sections["files"])),
            "pages": tuple(sorted((
                row["id"], row["name"], row["kind"], row["parent_id"],
                row["position"], row["is_published"],
            ) for row in sections["pages"])),
            "routes": tuple(sorted((
                row["id"], row["page_id"], row["target"], row["mode"], row["outcome"],
            ) for row in sections["routes"])),
            "settings": ((
                manifest.site_settings["id"],
                manifest.site_settings["structure_generation"],
                manifest.site_settings["settings_generation"],
                manifest.site_settings["organization_name"],
                manifest.site_settings["legal_name"],
                manifest.site_settings["phone_display"],
                manifest.site_settings["phone_e164"],
                manifest.site_settings["address"],
                manifest.site_settings["opening_hours"],
                manifest.site_settings["contact_email"],
                manifest.site_settings["map_url"], manifest.site_settings["max_url"],
                manifest.site_settings["telegram_url"],
                manifest.site_settings["logo_asset_id"],
            ),),
            "usages": tuple(sorted((
                row["id"], row["asset_id"], row["scope"], row["target_uuid"],
                row["slot"], row["position"],
            ) for row in sections["usages"])),
            "albums": tuple(sorted((
                row["id"], row["page_id"], row["generation"], row["position"],
            ) for row in sections["gallery_albums"])),
            "photos": tuple(sorted((
                row["id"], row["album_id"], row["asset_id"], row["position"], row["alt"],
            ) for row in sections["gallery_photos"])),
            "staff": tuple(sorted((
                str(item.id), item.username, item.is_active, item.role, item.generation,
                item.role == "OWNER", True, "!", None, "", "", "", True,
            ) for item in private.staff)),
            "content": tuple(sorted((
                row["id"], row["content_generation"],
                _canonical_json(row["current"]["payload"]), row["current"]["sha256"],
                provenance[(row["id"], "CURRENT")], row["current"]["created_at"],
                None if row["previous"] is None else _canonical_json(row["previous"]["payload"]),
                None if row["previous"] is None else row["previous"]["sha256"],
                None if row["previous"] is None else provenance[(row["id"], "PREVIOUS")],
                None if row["previous"] is None else row["previous"]["created_at"],
                None, None, None, None,
            ) for row in sections["pages"])),
            "grants": tuple(sorted((
                str(item.staff_id), str(item.page_id), _canonical_json(list(item.groups)),
            ) for item in private.grants)),
        }
        expected_counts = ProjectionCounts(
            1, len(sections["pages"]), len(sections["routes"]),
            len(sections["pages"]),
            sum(row["previous"] is not None for row in sections["pages"]),
            len(private.staff), len(private.grants), len(sections["assets"]),
            len(sections["files"]), len(sections["usages"]),
            len(sections["gallery_albums"]), len(sections["gallery_photos"]),
        )
        try:
            with self._connection.cursor() as cursor:
                _execute(cursor, "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
                _execute(cursor, TARGET_INVARIANT_SQL)
                invariant = cursor.fetchone()
                if invariant is None or tuple(invariant) != (0,):
                    raise TargetRuntimeError("target-readback-invariants")
                _execute(cursor, TARGET_COUNT_SQL)
                count_row = cursor.fetchone()
                if (
                    count_row is None or len(tuple(count_row)) != 12
                    or any(type(value) is not int or value < 0 for value in tuple(count_row))
                ):
                    raise TargetRuntimeError("target-readback-counts")
                counts = ProjectionCounts(*tuple(count_row))
                if counts != expected_counts:
                    raise TargetRuntimeError("target-readback-counts")
                actual = {
                    name: _readback_rows(cursor, sql, len(expected[name]))
                    for name, sql in TARGET_READBACK_QUERIES.items()
                }
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("target-readback-ambiguous") from None
        if any(actual[name] != rows for name, rows in expected.items()):
            raise TargetRuntimeError("target-readback-drift")
        return ReadbackProof(
            RESULT_SCHEMA, RESULT_VERSION, counts, manifest.digest, manifest.digest,
            source_media_digest, target_media_digest, ledger.identity,
            ledger.generation, ledger.digest, True, True, True,
        )


class ConcreteRunOps:
    """One bounded composition of the reviewed target components."""

    __slots__ = (
        "_endpoint", "_source_lifecycle", "_media", "_result_root", "_connect",
        "_names", "_target", "_authority", "_connection", "_writer",
        "_manifest", "_private", "_ledger", "_source_media_digest",
        "_target_media_digest", "_source_closed", "_target_closed",
        "_source_close_attempted", "_target_close_attempted", "_phase",
    )

    def __init__(
        self, endpoint: TargetEndpoint, source_lifecycle: Any, media: Any,
        result_root: Path, *, connect: Callable[..., Any] | None = None,
    ) -> None:
        if source_lifecycle is None or media is None or not isinstance(result_root, Path):
            raise TargetRuntimeError("runops-config")
        self._endpoint = _target_endpoint(endpoint)
        self._source_lifecycle = source_lifecycle
        self._media = media
        self._result_root = result_root
        self._connect = connect
        self._names = None
        self._target = None
        self._authority = None
        self._connection = None
        self._writer = None
        self._manifest = None
        self._private = None
        self._ledger = None
        self._source_media_digest = None
        self._target_media_digest = None
        self._source_closed = False
        self._target_closed = False
        self._source_close_attempted = False
        self._target_close_attempted = False
        self._phase = "INIT"

    def _exact_names(self, names: TargetNames) -> None:
        if not isinstance(names, TargetNames) or target_names(names.run_id) != names:
            raise TargetRuntimeError("runops-names")
        if self._names is None:
            self._names = names
        elif self._names != names:
            raise TargetRuntimeError("runops-names")

    def validate_pre_target(
        self, manifest: PublicManifest, source: SourcePreflight,
    ) -> PreTargetProof:
        if self._phase != "INIT" or not isinstance(source, SourcePreflight):
            raise TargetRuntimeError("runops-pretarget")
        sections = manifest.sections
        counts = ProjectionCounts(
            1, len(sections["pages"]), len(sections["routes"]),
            len(sections["pages"]),
            sum(row["previous"] is not None for row in sections["pages"]),
            source.staff_count, source.grant_count, len(sections["assets"]),
            len(sections["files"]), len(sections["usages"]),
            len(sections["gallery_albums"]), len(sections["gallery_photos"]),
        )
        if (
            source.current_count != counts.current
            or source.previous_count != counts.previous
        ):
            raise TargetRuntimeError("runops-source-counts")
        self._source_media_digest = self._media.preflight(manifest)
        self._manifest = manifest
        self._phase = "PREFLIGHT"
        return PreTargetProof(counts, self._source_media_digest)

    def create_empty_target(self, names: TargetNames) -> None:
        self._exact_names(names)
        if self._phase != "PREFLIGHT" or self._target is not None:
            raise TargetRuntimeError("runops-target-state")
        self._phase = "ACQUIRE_PENDING"
        target = TargetDatabaseLifecycle.create(self._endpoint, names, connect=self._connect)
        self._target = target
        self._phase = "TARGET"

    def target_acquisition_status(self, names: TargetNames) -> str:
        self._exact_names(names)
        if self._phase != "ACQUIRE_PENDING" or self._target is not None:
            raise TargetRuntimeError("runops-acquisition-state")
        status, lifecycle = TargetDatabaseLifecycle.recover_after_create(
            self._endpoint, names, connect=self._connect,
        )
        if status == "ACQUIRED":
            self._target = lifecycle
            self._phase = "TARGET"
        elif status in ("ABSENT", "AMBIGUOUS"):
            self._phase = status
        else:
            self._phase = "AMBIGUOUS"
        return status

    def _result_authority(self) -> "ResultAuthority":
        if self._names is None:
            raise TargetRuntimeError("runops-result-state")
        if self._authority is None:
            self._authority = ResultAuthority(self._result_root, self._names)
        return self._authority

    def record_created(self, result: SafeResult) -> None:
        if self._phase != "TARGET":
            raise TargetRuntimeError("runops-result-state")
        self._result_authority().record_created(result)
        self._phase = "CREATED"

    def prepare_target(self, names: TargetNames) -> None:
        self._exact_names(names)
        if self._phase != "CREATED" or self._target is None or self._connection is not None:
            raise TargetRuntimeError("runops-prepare-state")
        self._connection = self._target.prepare(run_target_migrations)
        self._writer = ProjectionWriter(self._connection)
        self._phase = "PREPARED"

    def begin_import(self, names: TargetNames) -> None:
        self._exact_names(names)
        if self._phase != "PREPARED" or self._writer is None:
            raise TargetRuntimeError("runops-import-state")
        self._writer.begin()
        self._phase = "BEGUN"

    def import_public(self, manifest: PublicManifest) -> None:
        if self._phase != "BEGUN" or manifest is not self._manifest or self._writer is None:
            raise TargetRuntimeError("runops-manifest")
        self._writer.import_public(manifest)
        self._phase = "PUBLIC"

    def import_private(self, rows: PrivateSourceRows) -> None:
        if self._phase != "PUBLIC" or self._writer is None or self._private is not None:
            raise TargetRuntimeError("runops-private")
        self._writer.import_private(rows)
        self._private = rows
        self._phase = "PRIVATE"

    def apply_zero_request_ledger(self, evidence: VerifiedLedgerEvidence) -> None:
        if self._phase != "PRIVATE" or self._writer is None or self._ledger is not None:
            raise TargetRuntimeError("runops-ledger")
        self._writer.apply_zero_ledger(evidence)
        self._ledger = evidence
        self._phase = "LEDGER"

    def copy_and_verify_files(self, manifest: PublicManifest, names: TargetNames) -> None:
        self._exact_names(names)
        if self._phase != "LEDGER" or manifest is not self._manifest:
            raise TargetRuntimeError("runops-manifest")
        self._target_media_digest = self._media.copy_and_verify(manifest, names)
        self._phase = "COPIED"

    def verify_before_commit(
        self, manifest: PublicManifest, rows: PrivateSourceRows,
    ) -> None:
        if (
            self._phase != "COPIED" or manifest is not self._manifest
            or rows is not self._private or self._writer is None
        ):
            raise TargetRuntimeError("runops-verify-state")
        self._writer.verify_counts()
        self._phase = "VERIFIED"

    def commit(self) -> None:
        if self._phase != "VERIFIED" or self._writer is None:
            raise TargetRuntimeError("runops-commit-state")
        self._phase = "COMMIT_PENDING"
        self._writer.commit()
        self._phase = "COMMITTED"

    def rollback(self) -> None:
        if self._phase == "COMMIT_PENDING":
            raise TargetRuntimeError("runops-rollback-ambiguous")
        if self._writer is None or self._phase not in (
            "PREPARED", "BEGUN", "PUBLIC", "PRIVATE", "LEDGER", "COPIED", "VERIFIED",
        ):
            raise TargetRuntimeError("runops-rollback-state")
        if self._phase == "PREPARED":
            self._connection.rollback()
        else:
            self._writer.rollback()
        self._writer.clear_private()
        self._private = None
        self._phase = "ROLLEDBACK"

    def readback(self, manifest: PublicManifest, names: TargetNames) -> ReadbackProof:
        self._exact_names(names)
        if (
            self._phase != "COMMITTED" or manifest is not self._manifest or self._connection is None
            or self._private is None or self._ledger is None
            or self._source_media_digest is None or self._target_media_digest is None
        ):
            raise TargetRuntimeError("runops-readback-state")
        media_digest = self._media.readback(manifest, names)
        if media_digest != self._target_media_digest:
            raise TargetRuntimeError("runops-media-readback")
        proof = CommittedReadback(self._connection).read(
            manifest, self._private, self._ledger,
            self._source_media_digest, media_digest,
        )
        self._writer.clear_private()
        self._private = None
        self._phase = "READBACK"
        return proof

    def close_source_identity(self) -> None:
        if self._source_close_attempted:
            raise TargetRuntimeError("runops-source-close-state")
        self._source_close_attempted = True
        try:
            self._source_lifecycle.close()
            self._source_closed = True
        finally:
            if self._writer is not None:
                self._writer.clear_private()
            self._private = None

    def close_identities(self, names: TargetNames) -> None:
        self._exact_names(names)
        if self._target is None or self._target_close_attempted:
            raise TargetRuntimeError("runops-target-close-state")
        self._target_close_attempted = True
        self._target.close_identities()
        self._target_closed = True

    def record_sealed(self, result: SafeResult) -> None:
        if self._phase != "READBACK" or not self._source_closed or not self._target_closed:
            raise TargetRuntimeError("runops-seal-state")
        self._result_authority().record_terminal(result)
        self._phase = "SEALED"

    def seal_status(self, result: SafeResult) -> str:
        if self._phase not in ("READBACK", "SEALED"):
            return "AMBIGUOUS"
        return self._result_authority().seal_status(result)

    def record_failed(self, result: SafeResult) -> None:
        if not self._source_closed or not self._target_closed:
            raise TargetRuntimeError("runops-failed-state")
        self._result_authority().record_terminal(result)

    def cleanup_proof(self, names: TargetNames) -> CleanupProof:
        self._exact_names(names)
        return CleanupProof(True, False, False, False, False, False, False)

    def cleanup_exact_pair(self, names: TargetNames) -> None:
        self._exact_names(names)
        raise TargetRuntimeError("cleanup-pointer-authority-absent")


def _media_digest(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(
        sorted(rows, key=lambda row: str(row["storage_key"])),
        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _not_reparse(info: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(info, "st_file_attributes", 0)
    return not flag or not attributes & flag


def _read_hash(
    descriptor: int, expected_size: int, *, retain: bool = False,
) -> tuple[int, str, bytes]:
    if type(expected_size) is not int or expected_size < 1:
        raise TargetRuntimeError("media-size")
    digest = hashlib.sha256()
    size = 0
    retained = bytearray()
    while True:
        block = os.read(descriptor, min(1024 * 1024, expected_size + 1 - size))
        if not block:
            break
        size += len(block)
        if size > expected_size:
            raise TargetRuntimeError("media-size")
        digest.update(block)
        if retain:
            retained.extend(block)
        elif len(retained) < 16:
            retained.extend(block[:16 - len(retained)])
    os.lseek(descriptor, 0, os.SEEK_SET)
    return size, digest.hexdigest(), bytes(retained)


def _close_descriptors(*descriptors: int | None) -> bool:
    error = False
    closed: set[int] = set()
    for descriptor in descriptors:
        if descriptor is None or descriptor in closed:
            continue
        closed.add(descriptor)
        try:
            os.close(descriptor)
        except Exception:
            error = True
    return error


def _open_child_directory(parent: int, name: str, code: str) -> int:
    descriptor = None
    try:
        descriptor = os.open(
            name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent,
        )
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode) or not _not_reparse(info):
            raise TargetRuntimeError(code)
        owned = descriptor
        descriptor = None
        return owned
    except Exception as exc:
        if _close_descriptors(descriptor):
            raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
        if isinstance(exc, TargetRuntimeError):
            raise
        raise TargetRuntimeError(code) from None


def _media_magic(mime_type: str, data: bytes, trusted_svg: bool) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if mime_type != "image/svg+xml" or not trusted_svg:
        return False
    try:
        text = data.decode("utf-8", "strict")
    except UnicodeDecodeError:
        return False
    folded = text.casefold()
    active = (
        "<!doctype", "<!entity", "<script", "<foreignobject", "javascript:",
        "data:", " xlink:href=\"http", " href=\"http", " xlink:href='http",
        " href='http",
    )
    return (
        "<svg" in folded
        and folded.rstrip().endswith("</svg>")
        and not any(token in folded for token in active)
        and re.search(r"\son[a-z0-9_-]+\s*=", folded) is None
    )


def _open_root(path: Path, code: str) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if (
        not isinstance(no_follow, int) or no_follow == 0
        or not isinstance(directory, int) or directory == 0
        or not _trusted_directory(path)
    ):
        raise TargetRuntimeError(code)
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY | directory | no_follow)
        info = os.fstat(descriptor)
        listed = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or not _not_reparse(info)
            or (info.st_dev, info.st_ino) != (listed.st_dev, listed.st_ino)
        ):
            raise TargetRuntimeError(code)
        return descriptor
    except TargetRuntimeError:
        if _close_descriptors(descriptor):
            raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
        raise
    except Exception:
        if _close_descriptors(descriptor):
            raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
        raise TargetRuntimeError(code) from None


def _open_beneath(root_descriptor: int, relative: str, code: str) -> int:
    parts = relative.split("/")
    if not parts or any(not part or part in (".", "..") for part in parts):
        raise TargetRuntimeError(code)
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    current = os.dup(root_descriptor)
    result = None
    try:
        for part in parts[:-1]:
            following = _open_child_directory(current, part, code)
            previous = current
            current = following
            if _close_descriptors(previous):
                cleanup_error = _close_descriptors(current)
                current = -1
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous")
        result = os.open(parts[-1], os.O_RDONLY | no_follow, dir_fd=current)
        info = os.fstat(result)
        if not stat.S_ISREG(info.st_mode) or not _not_reparse(info):
            cleanup_error = _close_descriptors(result)
            result = None
            if cleanup_error:
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous")
            raise TargetRuntimeError(code)
        previous = current
        current = -1
        if _close_descriptors(previous):
            _close_descriptors(result)
            result = None
            raise TargetRuntimeError("media-descriptor-cleanup-ambiguous")
        current = -1
        owned_result = result
        result = None
        return owned_result
    except TargetRuntimeError:
        if result is not None:
            if _close_descriptors(result):
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
        raise
    except Exception:
        if result is not None:
            if _close_descriptors(result):
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
        raise TargetRuntimeError(code) from None
    finally:
        if current >= 0 and _close_descriptors(current):
            if result is not None:
                _close_descriptors(result)
                result = None
            raise TargetRuntimeError("media-descriptor-cleanup-ambiguous")


class MediaTransfer:
    """One contained source snapshot and one generated byte-for-byte target copy."""

    __slots__ = (
        "_source_root", "_target_root", "_trusted_svg", "_source_descriptor",
        "_handles", "_manifest_digest", "_source_digest", "_copied", "_closed",
    )

    def __init__(
        self, source_media_root: Path, target_rebuild_root: Path,
        trusted_svg_sha256: frozenset[str],
    ) -> None:
        if (
            not isinstance(source_media_root, Path)
            or not isinstance(target_rebuild_root, Path)
            or not isinstance(trusted_svg_sha256, frozenset)
            or any(not isinstance(value, str) or SHA256.fullmatch(value) is None
                   for value in trusted_svg_sha256)
        ):
            raise TargetRuntimeError("media-config")
        try:
            common = Path(os.path.commonpath((source_media_root, target_rebuild_root)))
        except ValueError:
            common = None
        if common in (source_media_root, target_rebuild_root):
            raise TargetRuntimeError("media-roots")
        self._source_root = source_media_root
        self._target_root = target_rebuild_root
        self._trusted_svg = trusted_svg_sha256
        source_descriptor = _open_root(source_media_root, "media-source-root")
        target_descriptor = None
        try:
            target_descriptor = _open_root(target_rebuild_root, "media-target-root")
            owned_target = target_descriptor
            target_descriptor = None
            if _close_descriptors(owned_target):
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous")
        except Exception as exc:
            if _close_descriptors(target_descriptor, source_descriptor):
                raise TargetRuntimeError("media-descriptor-cleanup-ambiguous") from None
            if isinstance(exc, TargetRuntimeError):
                raise
            raise TargetRuntimeError("media-config-ambiguous") from None
        self._source_descriptor = source_descriptor
        self._handles: dict[str, int] = {}
        self._manifest_digest: str | None = None
        self._source_digest: str | None = None
        self._copied = False
        self._closed = False

    def preflight(self, manifest: PublicManifest) -> str:
        if self._closed or self._manifest_digest is not None or not isinstance(manifest, PublicManifest):
            raise TargetRuntimeError("media-preflight-state")
        digest_rows: list[dict[str, object]] = []
        try:
            for row in manifest.sections["files"]:
                path = row["source_path"]
                descriptor = self._handles.get(path)
                if descriptor is None:
                    descriptor = _open_beneath(
                        self._source_descriptor, path, "media-source-file",
                    )
                    self._handles[path] = descriptor
                os.lseek(descriptor, 0, os.SEEK_SET)
                retain = row["mime_type"] == "image/svg+xml"
                size, digest, sample = _read_hash(
                    descriptor, row["byte_size"], retain=retain,
                )
                trusted_svg = digest in self._trusted_svg
                if (
                    size != row["byte_size"]
                    or digest != row["sha256"]
                    or not _media_magic(row["mime_type"], sample, trusted_svg)
                ):
                    raise TargetRuntimeError("media-source-drift")
                digest_rows.append({
                    "storage_key": target_storage_key(row),
                    "sha256": digest,
                    "byte_size": size,
                })
        except TargetRuntimeError:
            self.close()
            raise
        except Exception:
            self.close()
            raise TargetRuntimeError("media-preflight-ambiguous") from None
        self._manifest_digest = manifest.digest
        self._source_digest = _media_digest(digest_rows)
        return self._source_digest

    def copy_and_verify(self, manifest: PublicManifest, names: TargetNames) -> str:
        if (
            self._closed or self._copied or self._source_digest is None
            or not isinstance(manifest, PublicManifest)
            or manifest.digest != self._manifest_digest
            or not isinstance(names, TargetNames) or target_names(names.run_id) != names
        ):
            raise TargetRuntimeError("media-copy-state")
        target_root = _open_root(self._target_root, "media-target-root")
        run_descriptor = media_descriptor = None
        actual: list[dict[str, object]] = []
        try:
            run_part = str(names.run_id)
            os.mkdir(run_part, 0o700, dir_fd=target_root)
            os.fsync(target_root)
            run_descriptor = _open_child_directory(
                target_root, run_part, "media-target-path",
            )
            os.mkdir("media", 0o700, dir_fd=run_descriptor)
            os.fsync(run_descriptor)
            media_descriptor = _open_child_directory(
                run_descriptor, "media", "media-target-path",
            )
            for row in sorted(
                manifest.sections["files"], key=target_storage_key,
            ):
                key = target_storage_key(row)
                source = self._handles[row["source_path"]]
                parent = os.dup(media_descriptor)
                try:
                    parts = key.split("/")
                    for part in parts[:-1]:
                        try:
                            os.mkdir(part, 0o700, dir_fd=parent)
                            os.fsync(parent)
                        except FileExistsError:
                            pass
                        following = _open_child_directory(
                            parent, part, "media-target-path",
                        )
                        previous = parent
                        parent = following
                        if _close_descriptors(previous):
                            _close_descriptors(parent)
                            parent = -1
                            raise TargetRuntimeError(
                                "media-copy-cleanup-ambiguous",
                            )
                    target = os.open(
                        parts[-1], os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600, dir_fd=parent,
                    )
                    try:
                        os.lseek(source, 0, os.SEEK_SET)
                        written = 0
                        digest = hashlib.sha256()
                        while True:
                            block = os.read(
                                source,
                                min(1024 * 1024, row["byte_size"] + 1 - written),
                            )
                            if not block:
                                break
                            if written + len(block) > row["byte_size"]:
                                raise TargetRuntimeError("media-source-drift")
                            offset = 0
                            while offset < len(block):
                                count = os.write(target, block[offset:])
                                if count <= 0:
                                    raise TargetRuntimeError("media-target-write")
                                offset += count
                            written += len(block)
                            digest.update(block)
                        os.fsync(target)
                        os.lseek(target, 0, os.SEEK_SET)
                        size, readback, _sample = _read_hash(
                            target, row["byte_size"],
                        )
                        if (
                            written != row["byte_size"] or size != written
                            or digest.hexdigest() != row["sha256"]
                            or readback != row["sha256"]
                        ):
                            raise TargetRuntimeError("media-target-drift")
                        actual.append({
                            "storage_key": key, "sha256": readback,
                            "byte_size": size,
                        })
                    finally:
                        if _close_descriptors(target):
                            raise TargetRuntimeError("media-copy-cleanup-ambiguous")
                    os.fsync(parent)
                finally:
                    if parent >= 0 and _close_descriptors(parent):
                        raise TargetRuntimeError("media-copy-cleanup-ambiguous")
            os.fsync(media_descriptor)
            digest = _media_digest(actual)
            if digest != self._source_digest:
                raise TargetRuntimeError("media-target-digest")
            self._copied = True
            return digest
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("media-copy-ambiguous") from None
        finally:
            cleanup_error = _close_descriptors(
                media_descriptor, run_descriptor, target_root,
            )
            try:
                self.close()
            except Exception:
                cleanup_error = True
            if cleanup_error:
                raise TargetRuntimeError("media-copy-cleanup-ambiguous") from None

    def readback(self, manifest: PublicManifest, names: TargetNames) -> str:
        if (
            not self._copied or self._source_digest is None
            or not isinstance(manifest, PublicManifest)
            or manifest.digest != self._manifest_digest
            or not isinstance(names, TargetNames) or target_names(names.run_id) != names
        ):
            raise TargetRuntimeError("media-readback-state")
        target_root = _open_root(self._target_root, "media-target-root")
        run_descriptor = media_descriptor = None
        expected_files = {target_storage_key(row) for row in manifest.sections["files"]}
        expected_directories = {
            "/".join(key.split("/")[:index])
            for key in expected_files
            for index in range(1, len(key.split("/")))
        }
        actual_files: set[str] = set()
        actual_directories: set[str] = set()

        def inventory(directory_descriptor: int, prefix: str = "") -> None:
            for name in os.listdir(directory_descriptor):
                if not isinstance(name, str) or not name or "/" in name or name in (".", ".."):
                    raise TargetRuntimeError("media-target-inventory")
                child = os.open(
                    name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_descriptor,
                )
                try:
                    info = os.fstat(child)
                    key = f"{prefix}/{name}" if prefix else name
                    if not _not_reparse(info):
                        raise TargetRuntimeError("media-target-inventory")
                    if stat.S_ISDIR(info.st_mode):
                        actual_directories.add(key)
                        inventory(child, key)
                    elif stat.S_ISREG(info.st_mode):
                        actual_files.add(key)
                    else:
                        raise TargetRuntimeError("media-target-inventory")
                finally:
                    if _close_descriptors(child):
                        raise TargetRuntimeError("media-readback-cleanup-ambiguous")

        try:
            run_descriptor = _open_child_directory(
                target_root, str(names.run_id), "media-target-path",
            )
            media_descriptor = _open_child_directory(
                run_descriptor, "media", "media-target-path",
            )
            if set(os.listdir(run_descriptor)) != {"media"}:
                raise TargetRuntimeError("media-target-inventory")
            inventory(media_descriptor)
            if actual_files != expected_files or actual_directories != expected_directories:
                raise TargetRuntimeError("media-target-inventory")
            actual: list[dict[str, object]] = []
            for row in manifest.sections["files"]:
                descriptor = _open_beneath(
                    media_descriptor, target_storage_key(row), "media-target-file",
                )
                try:
                    retain = row["mime_type"] == "image/svg+xml"
                    size, digest, sample = _read_hash(
                        descriptor, row["byte_size"], retain=retain,
                    )
                finally:
                    if _close_descriptors(descriptor):
                        raise TargetRuntimeError("media-readback-cleanup-ambiguous")
                if (
                    size != row["byte_size"] or digest != row["sha256"]
                    or not _media_magic(
                        row["mime_type"], sample, digest in self._trusted_svg,
                    )
                ):
                    raise TargetRuntimeError("media-target-drift")
                actual.append({
                    "storage_key": target_storage_key(row),
                    "sha256": digest, "byte_size": size,
                })
            digest = _media_digest(actual)
            if digest != self._source_digest:
                raise TargetRuntimeError("media-target-digest")
            return digest
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("media-readback-ambiguous") from None
        finally:
            if _close_descriptors(media_descriptor, run_descriptor, target_root):
                raise TargetRuntimeError("media-readback-cleanup-ambiguous") from None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        error = False
        for descriptor in self._handles.values():
            try:
                os.close(descriptor)
            except Exception:
                error = True
        try:
            os.close(self._source_descriptor)
        except Exception:
            error = True
        self._handles.clear()
        if error:
            raise TargetRuntimeError("media-source-close-ambiguous")


def _trusted_directory(path: Path) -> bool:
    try:
        info = path.lstat()
        return (
            path.is_absolute()
            and stat.S_ISDIR(info.st_mode)
            and not path.is_symlink()
            and not info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
            and (not hasattr(os, "geteuid") or info.st_uid == os.geteuid())
        )
    except Exception:
        return False


def _directory_fsync(path: Path) -> None:
    descriptor = None
    try:
        descriptor = os.open(path, os.O_RDONLY)
        os.fsync(descriptor)
    except Exception:
        raise TargetRuntimeError("result-directory-flush") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _counts(value: object) -> ProjectionCounts:
    if not isinstance(value, dict) or frozenset(value) != COUNT_FIELDS:
        raise TargetRuntimeError("result-counts")
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise TargetRuntimeError("result-counts")
    if value["site_settings"] != 1:
        raise TargetRuntimeError("result-counts")
    return ProjectionCounts(**value)


def _canonical_result(result: SafeResult) -> bytes:
    if not isinstance(result, SafeResult):
        raise TargetRuntimeError("result-shape")
    value = asdict(result)
    value["run_id"] = str(result.run_id)
    value["ledger_identity"] = str(result.ledger_identity)
    _parse_result(value, expected=result)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def _same_basis(created: SafeResult, terminal: SafeResult) -> bool:
    return (
        created.phase == "CREATED"
        and created.run_id == terminal.run_id
        and created.database == terminal.database
        and created.media_key == terminal.media_key
        and created.manifest_digest == terminal.manifest_digest
        and created.ledger_identity == terminal.ledger_identity
        and created.ledger_generation == terminal.ledger_generation
        and created.ledger_digest == terminal.ledger_digest
        and created.counts == terminal.counts
        and created.source_media_digest == terminal.source_media_digest
    )


def _parse_result(value: object, *, expected: SafeResult | None = None) -> SafeResult:
    if not isinstance(value, dict) or frozenset(value) != RESULT_FIELDS:
        raise TargetRuntimeError("result-shape")
    try:
        run_id = uuid.UUID(value["run_id"])
        ledger_identity = uuid.UUID(value["ledger_identity"])
    except (ValueError, TypeError, AttributeError):
        raise TargetRuntimeError("result-identity") from None
    try:
        names = target_names(run_id)
    except Exception:
        raise TargetRuntimeError("result-identity") from None
    phase = value["phase"]
    if (
        value["schema"] != RESULT_SCHEMA
        or type(value["version"]) is not int
        or value["version"] != RESULT_VERSION
        or phase not in ("CREATED", "SEALED", "FAILED")
        or value["database"] != names.database
        or value["media_key"] != names.media_key
        or not isinstance(value["manifest_digest"], str)
        or SHA256.fullmatch(value["manifest_digest"]) is None
        or type(value["ledger_generation"]) is not int
        or value["ledger_generation"] < 1
        or not isinstance(value["ledger_digest"], str)
        or SHA256.fullmatch(value["ledger_digest"]) is None
        or not isinstance(value["source_media_digest"], str)
        or SHA256.fullmatch(value["source_media_digest"]) is None
    ):
        raise TargetRuntimeError("result-shape")
    counts = _counts(value["counts"])
    database_digest = value["database_digest"]
    target_media_digest = value["target_media_digest"]
    error_code = value["error_code"]
    if phase == "CREATED":
        valid_phase = database_digest is None and target_media_digest is None and error_code is None
    elif phase == "SEALED":
        valid_phase = (
            isinstance(database_digest, str)
            and SHA256.fullmatch(database_digest) is not None
            and database_digest == value["manifest_digest"]
            and isinstance(target_media_digest, str)
            and SHA256.fullmatch(target_media_digest) is not None
            and target_media_digest == value["source_media_digest"]
            and error_code is None
        )
    else:
        valid_phase = (
            database_digest is None
            and target_media_digest is None
            and error_code in ALLOWED_ERROR_CODES
        )
    if not valid_phase:
        raise TargetRuntimeError("result-phase")
    result = SafeResult(
        value["schema"], value["version"], phase, run_id, value["database"],
        value["media_key"], value["manifest_digest"], ledger_identity,
        value["ledger_generation"], value["ledger_digest"], counts,
        database_digest, value["source_media_digest"], target_media_digest, error_code,
    )
    if expected is not None and result != expected:
        raise TargetRuntimeError("result-drift")
    return result


class ResultAuthority:
    """Exact write-once CREATED plus one terminal result for one generated run."""

    __slots__ = ("_root", "_names")

    def __init__(self, result_root: Path, names: TargetNames) -> None:
        if not isinstance(result_root, Path) or not _trusted_directory(result_root):
            raise TargetRuntimeError("result-root")
        if not isinstance(names, TargetNames) or target_names(names.run_id) != names:
            raise TargetRuntimeError("result-names")
        self._root = result_root
        self._names = names

    @property
    def run_root(self) -> Path:
        return self._root / str(self._names.run_id)

    def record_created(self, result: SafeResult) -> None:
        if (
            not isinstance(result, SafeResult)
            or result.phase != "CREATED"
            or result.run_id != self._names.run_id
        ):
            raise TargetRuntimeError("result-created")
        payload = _canonical_result(result)
        try:
            self.run_root.mkdir(mode=0o700)
        except Exception:
            raise TargetRuntimeError("result-run-root") from None
        if not _trusted_directory(self.run_root):
            raise TargetRuntimeError("result-run-root")
        try:
            _directory_fsync(self._root)
        except Exception:
            raise TargetRuntimeError("result-run-root-ambiguous") from None
        self._publish("CREATED.json", payload)

    def record_terminal(self, result: SafeResult) -> None:
        if (
            not isinstance(result, SafeResult)
            or result.phase not in ("SEALED", "FAILED")
            or result.run_id != self._names.run_id
        ):
            raise TargetRuntimeError("result-terminal")
        payload = _canonical_result(result)
        if not _trusted_directory(self.run_root):
            raise TargetRuntimeError("result-terminal-ambiguous")
        try:
            entries = tuple(self.run_root.iterdir())
            if (
                len(entries) != 1
                or entries[0].name != "CREATED.json"
                or entries[0].is_symlink()
                or not stat.S_ISREG(entries[0].lstat().st_mode)
            ):
                raise TargetRuntimeError("result-terminal-ambiguous")
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("result-terminal-ambiguous") from None
        created = self._read("CREATED.json")
        if not _same_basis(created, result):
            raise TargetRuntimeError("result-created-drift")
        self._publish(f"{result.phase}.json", payload)

    def seal_status(self, expected: SafeResult) -> str:
        if (
            not isinstance(expected, SafeResult)
            or expected.phase != "SEALED"
            or expected.run_id != self._names.run_id
        ):
            return "AMBIGUOUS"
        try:
            names = {entry.name for entry in self.run_root.iterdir()}
            if names - {"CREATED.json", "SEALED.json", "FAILED.json"}:
                return "AMBIGUOUS"
            if "FAILED.json" in names:
                return "AMBIGUOUS"
            if "CREATED.json" not in names:
                return "AMBIGUOUS"
            if "SEALED.json" not in names:
                return "ABSENT"
            created = self._read("CREATED.json")
            sealed = self._read("SEALED.json")
            return (
                "EXACT"
                if sealed == expected and _same_basis(created, sealed)
                else "AMBIGUOUS"
            )
        except Exception:
            return "AMBIGUOUS"

    def _publish(self, name: str, payload: bytes) -> None:
        if name not in ("CREATED.json", "SEALED.json", "FAILED.json"):
            raise TargetRuntimeError("result-name")
        target = self.run_root / name
        temporary = self.run_root / f".{name}.{uuid.uuid4()}.tmp"
        placeholder = None
        descriptor = None
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if not isinstance(no_follow, int) or no_follow == 0:
            raise TargetRuntimeError("result-no-follow")
        try:
            descriptor = os.open(
                temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow, 0o600,
            )
            if os.write(descriptor, payload) != len(payload):
                raise TargetRuntimeError("result-write")
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            placeholder = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow, 0o600,
            )
            os.close(placeholder)
            placeholder = None
            os.replace(temporary, target)
            _directory_fsync(self.run_root)
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("result-publish") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if placeholder is not None:
                os.close(placeholder)
            if temporary.exists() and not temporary.is_symlink():
                temporary.unlink()

    def _read(self, name: str) -> SafeResult:
        path = self.run_root / name
        descriptor = None
        no_follow = getattr(os, "O_NOFOLLOW", None)
        if not isinstance(no_follow, int) or no_follow == 0:
            raise TargetRuntimeError("result-no-follow")
        try:
            descriptor = os.open(path, os.O_RDONLY | no_follow)
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_mode & (stat.S_IRWXG | stat.S_IRWXO)
                or (hasattr(os, "geteuid") and info.st_uid != os.geteuid())
                or not 1 <= info.st_size <= 64 * 1024
            ):
                raise TargetRuntimeError("result-file")
            raw = os.read(descriptor, info.st_size + 1)
            if len(raw) != info.st_size:
                raise TargetRuntimeError("result-file")
            value = json.loads(raw.decode("utf-8", "strict"))
        except TargetRuntimeError:
            raise
        except Exception:
            raise TargetRuntimeError("result-file") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
        result = _parse_result(value)
        if raw != _canonical_result(result):
            raise TargetRuntimeError("result-canonical")
        return result
