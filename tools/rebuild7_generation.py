from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import uuid
from pathlib import Path, PurePosixPath

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_restore")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.sessions.models import Session  # noqa: E402
from django.db import IntegrityError, connection, transaction  # noqa: E402
from django.db.models import F  # noqa: E402
from django.db.migrations.recorder import MigrationRecorder  # noqa: E402

from modules.audit.models import AuditEvent  # noqa: E402
from modules.media.models import AssetFile, AssetState  # noqa: E402


SCHEMA = "estakada.r7-local-generation-v5"
PROJECT = Path("/project")
OUTPUT = Path("/output")
AUTHORITY = Path("/authority")
APP_SOURCE = Path("/app")
SOURCE_ROOTS = ("src",)
PROJECT_APP_LABELS = frozenset({"accounts", "audit", "gallery", "media", "pages"})
SOURCE_FILES = (
    "docs/clean-rebuild-7-local-restore-plan.md",
    "environment/foundation/requirements.lock",
    "scripts/rebuild7-local-restore.ps1",
    "tools/rebuild7_generation.py",
    "tools/test_rebuild7_generation_diagnostic.py",
    "tools/rebuild7_http_smoke.py",
    "tools/rebuild7_media.py",
    "tools/rebuild7_pg.sh",
)
KEY_RE = re.compile(
    r"(?:img/[0-9a-f-]{36}/(?:main|preview|legacy-public)\.(?:jpg|jpeg|png|webp|svg)|"
    r"private/sources/[0-9a-f-]{36}/source\.(?:jpg|jpeg|png|webp))\Z"
)
AUDIT_ACTOR_CONSTRAINT = "audit_actor_shape"
COLUMN_FIELD_NAMES = (
    "ordinal",
    "type",
    "typmod",
    "notnull",
    "identity",
    "generated",
    "storage",
    "compression",
    "collation",
    "default",
)
CONSTRAINT_FIELD_NAMES = (
    "type",
    "definition",
    "deferrable",
    "deferred",
    "validated",
    "noinherit",
    "key_columns",
)
RESTORE_CONSTRAINT_DEFINITION_SENTINEL = (
    "R7_RESTORE_CONSTRAINT_DEFINITION_NONAUTHORITY_V1"
)
RESTORE_SOURCE_CAPTURE_SENTINEL = "R7_RESTORE_SOURCE_CAPTURE_NONAUTHORITY_V1"
RELEASE_KEYS = (
    "schema",
    "releaseId",
    "source",
    "dependencies",
    "runtime",
    "migrationFiles",
    "appliedMigrations",
    "schemaFingerprint",
    "contracts",
    "configuration",
)


def fail(message: str = "R7_LOCAL_GENERATION_UNAVAILABLE") -> None:
    raise RuntimeError(message)


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def restore_semantic_constraint(row: list[object]) -> list[object]:
    if len(row) != 9 or type(row[2]) is not str:
        fail()
    semantic = list(row)
    if row[2] == "c":
        semantic[3] = RESTORE_CONSTRAINT_DEFINITION_SENTINEL
    return semantic


def safe_project_file(relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        fail()
    path = PROJECT.joinpath(*pure.parts)
    if not path.is_file() or path.is_symlink() or PROJECT not in path.resolve().parents:
        fail()
    return path


def safe_inventory_file(relative: str) -> Path:
    source_override = os.environ.get("ESTAKADA_R7_APP_SOURCE")
    if source_override not in {None, "/app"}:
        fail()
    if source_override != "/app" or not relative.startswith("src/"):
        return safe_project_file(relative)
    pure = PurePosixPath(relative)
    path = APP_SOURCE.joinpath(*pure.parts[1:])
    if not path.is_file() or path.is_symlink() or APP_SOURCE not in path.resolve().parents:
        fail()
    return path


def source_inventory() -> list[dict[str, object]]:
    names: set[str] = set(SOURCE_FILES)
    for root_name in SOURCE_ROOTS:
        source_override = os.environ.get("ESTAKADA_R7_APP_SOURCE")
        if source_override not in {None, "/app"}:
            fail()
        if source_override == "/app":
            root = safe_inventory_file(root_name + "/manage.py").parent
            relative_root = APP_SOURCE
        else:
            root = safe_project_file(root_name + "/manage.py").parent
            relative_root = PROJECT
        for path in root.rglob("*"):
            if path.is_symlink():
                fail()
            if path.is_dir():
                continue
            relative = (
                "src/" + path.relative_to(relative_root).as_posix()
                if relative_root == APP_SOURCE
                else path.relative_to(PROJECT).as_posix()
            )
            if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                continue
            names.add(relative)
    rows = []
    for name in sorted(names):
        data = safe_inventory_file(name).read_bytes()
        rows.append({"path": name, "bytes": len(data), "sha256": digest_bytes(data)})
    return rows


def migration_files(inventory: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {"path": str(row["path"]), "sha256": str(row["sha256"])}
        for row in inventory
        if re.fullmatch(r"src/modules/[a-z_]+/migrations/[0-9][0-9a-z_]*\.py", str(row["path"]))
    ]


def schema_projection() -> dict[str, object]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema(), current_setting('server_version')")
        schema, postgres_version = cursor.fetchone()
        if schema != "app":
            fail()
        cursor.execute(
            """
            SELECT r.relname, a.attname,
                   row_number() OVER (PARTITION BY r.oid ORDER BY a.attnum) AS live_ordinal,
                   tn.nspname, t.typname, a.atttypmod, a.attnotnull,
                   a.attidentity, a.attgenerated, a.attstorage, a.attcompression,
                   COALESCE(cn.nspname, ''), COALESCE(co.collname, ''),
                   COALESCE(pg_get_expr(d.adbin, d.adrelid, false), '')
            FROM pg_attribute a
            JOIN pg_class r ON r.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = r.relnamespace
            JOIN pg_type t ON t.oid = a.atttypid
            JOIN pg_namespace tn ON tn.oid = t.typnamespace
            LEFT JOIN pg_attrdef d
              ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            LEFT JOIN pg_collation co ON co.oid = a.attcollation
            LEFT JOIN pg_namespace cn ON cn.oid = co.collnamespace
            WHERE n.nspname = current_schema()
              AND r.relkind IN ('r', 'p')
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY r.relname, a.attnum
            """
        )
        columns = [list(row) for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT r.relname, c.conname, c.contype,
                   CASE
                       WHEN r.relname = 'audit_auditevent'
                        AND c.conname = 'audit_actor_shape'
                        AND c.contype = 'c'
                       THEN 'R7_AUDIT_ACTOR_SHAPE_BEHAVIOR_V1'
                       ELSE pg_get_constraintdef(c.oid, false)
                   END,
                   c.condeferrable, c.condeferred, c.convalidated, c.connoinherit,
                   COALESCE(
                       ARRAY(
                           SELECT a.attname
                           FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                           JOIN pg_attribute a
                             ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                           ORDER BY k.ord
                       ),
                       ARRAY[]::name[]
                   )
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            JOIN pg_class r ON r.oid = c.conrelid
            WHERE n.nspname = current_schema()
            ORDER BY 1, 2
            """
        )
        constraints = [list(row) for row in cursor.fetchall()]
        semantic_constraints = [
            restore_semantic_constraint(row) for row in constraints
        ]
        cursor.execute(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
            ORDER BY tablename, indexname
            """
        )
        indexes = [list(row) for row in cursor.fetchall()]
    table_names = sorted({str(row[0]) for row in columns})
    if not table_names or any(
        re.fullmatch(r"[a-z0-9_]+", table) is None for table in table_names
    ):
        fail()
    groups = {
        "columns": columns,
        "constraints": semantic_constraints,
        "indexes": indexes,
    }
    components: dict[str, str] = {}
    table_components: dict[str, dict[str, str]] = {
        table: {} for table in table_names
    }
    object_components: dict[str, dict[str, dict[str, str]]] = {
        table: {name: {} for name in groups} for table in table_names
    }
    column_field_components: dict[str, dict[str, dict[str, str]]] = {
        table: {} for table in table_names
    }
    constraint_field_components: dict[str, dict[str, dict[str, str]]] = {
        table: {} for table in table_names
    }
    for name, rows in groups.items():
        if any(str(row[0]) not in table_components for row in rows):
            fail()
        components[name] = digest_bytes(canonical(rows))
        for table in table_names:
            table_rows = [row for row in rows if str(row[0]) == table]
            table_components[table][name] = digest_bytes(canonical(table_rows))
            for row in table_rows:
                object_name = str(row[1])
                if (
                    re.fullmatch(r"[a-z0-9_]+", object_name) is None
                    or object_name in object_components[table][name]
                ):
                    fail()
                object_components[table][name][object_name] = digest_bytes(
                    canonical(row)
                )
                if name == "columns":
                    if len(row) != 14:
                        fail()
                    field_values = {
                        "ordinal": row[2],
                        "type": [row[3], row[4]],
                        "typmod": row[5],
                        "notnull": row[6],
                        "identity": row[7],
                        "generated": row[8],
                        "storage": row[9],
                        "compression": row[10],
                        "collation": [row[11], row[12]],
                        "default": row[13],
                    }
                    if tuple(field_values) != COLUMN_FIELD_NAMES:
                        fail()
                    column_field_components[table][object_name] = {
                        field: digest_bytes(canonical(value))
                        for field, value in field_values.items()
                    }
                if name == "constraints":
                    if len(row) != 9:
                        fail()
                    field_values = {
                        "type": row[2],
                        "definition": row[3],
                        "deferrable": row[4],
                        "deferred": row[5],
                        "validated": row[6],
                        "noinherit": row[7],
                        "key_columns": row[8],
                    }
                    if tuple(field_values) != CONSTRAINT_FIELD_NAMES:
                        fail()
                    constraint_field_components[table][object_name] = {
                        field: digest_bytes(canonical(value))
                        for field, value in field_values.items()
                    }
    source_projection = {
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
    }
    projection = {
        "columns": columns,
        "constraints": semantic_constraints,
        "indexes": indexes,
    }
    return {
        "postgres": ".".join(str(postgres_version).split(".")[:2]),
        "sourceCaptureSha256": digest_bytes(canonical(source_projection)),
        "sha256": digest_bytes(canonical(projection)),
        "tables": len(table_names),
        "components": components,
        "tableComponents": table_components,
        "objectComponents": object_components,
        "columnFieldComponents": column_field_components,
        "constraintFieldComponents": constraint_field_components,
    }


def applied_migrations() -> list[str]:
    return sorted(f"{app}.{name}" for app, name in MigrationRecorder(connection).applied_migrations())


def table_counts() -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
        counts = {}
        for table in tables:
            cursor.execute(f"SELECT count(*) FROM {connection.ops.quote_name(table)}")
            counts[table] = int(cursor.fetchone()[0])
    return counts


def table_content_hashes() -> dict[str, str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
    result = {}
    for table in tables:
        digest = hashlib.sha256()
        quoted = connection.ops.quote_name(table)
        with connection.cursor() as cursor:
            cursor.execute(
                f'SELECT to_jsonb(row_value)::text FROM {quoted} AS row_value '
                'ORDER BY to_jsonb(row_value)::text COLLATE "C"'
            )
            while True:
                rows = cursor.fetchmany(512)
                if not rows:
                    break
                for (row_json,) in rows:
                    digest.update(row_json.encode("utf-8"))
                    digest.update(b"\n")
        result[table] = digest.hexdigest()
    return result


def dependency_profile(inventory: list[dict[str, object]]) -> dict[str, object]:
    lock_row = next(
        row for row in inventory if row["path"] == "environment/foundation/requirements.lock"
    )
    lock_path = safe_project_file(str(lock_row["path"]))
    expected: dict[str, str] = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(
            r"([A-Za-z0-9_.-]+)==([^\s]+) --hash=sha256:[0-9a-f]{64}", line
        )
        if match is None:
            fail()
        name = re.sub(r"[-_.]+", "-", match.group(1)).lower()
        if name in expected:
            fail()
        expected[name] = match.group(2)
    if not expected:
        fail()
    installed = []
    for name, expected_version in sorted(expected.items()):
        try:
            actual_version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            fail()
        if actual_version != expected_version:
            fail("R7_DEPENDENCY_LOCK_MISMATCH")
        installed.append({"name": name, "version": actual_version})
    return {"lock": lock_row, "installed": installed}


def media_inventory() -> list[dict[str, object]]:
    rows = list(
        AssetFile.objects.filter(asset__state=AssetState.READY)
        .values("storage_key", "sha256", "byte_size")
        .order_by("storage_key")
    )
    seen: set[str] = set()
    result = []
    for row in rows:
        key = row["storage_key"]
        if (
            type(key) is not str
            or key in seen
            or KEY_RE.fullmatch(key) is None
            or type(row["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None
            or type(row["byte_size"]) is not int
            or row["byte_size"] < 1
        ):
            fail()
        seen.add(key)
        result.append({"path": key, "sha256": row["sha256"], "bytes": row["byte_size"]})
    return result


def build_release() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    inventory = source_inventory()
    schema = schema_projection()
    migrations = applied_migrations()
    files = migration_files(inventory)
    project_migrations = {
        f"{PurePosixPath(row['path']).parts[2]}.{PurePosixPath(row['path']).stem}"
        for row in files
    }
    applied_project_migrations = {
        migration for migration in migrations if migration.split(".", 1)[0] in PROJECT_APP_LABELS
    }
    if not files or project_migrations != applied_project_migrations:
        fail()
    image_digest = os.environ.get("ESTAKADA_APP_IMAGE_DIGEST", "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None:
        fail()
    release = {
        "schema": SCHEMA,
        "releaseId": "src-" + digest_bytes(canonical(inventory))[:16],
        "source": {"files": len(inventory), "sha256": digest_bytes(canonical(inventory))},
        "dependencies": dependency_profile(inventory),
        "runtime": {
            "image": image_digest,
            "python": ".".join(platform.python_version().split(".")[:2]),
            "django": ".".join(django.get_version().split(".")[:2]),
            "postgresql": schema["postgres"],
        },
        "migrationFiles": files,
        "appliedMigrations": migrations,
        "schemaFingerprint": schema,
        "contracts": {
            "content": "pages-current-previous-v1",
            "routes": "exact115-v1",
            "media": "ready-asset-files-v1",
            "requests": "absent-default-off",
        },
        "configuration": {
            "required": sorted(
                [
                    "ESTAKADA_ALLOWED_HOSTS",
                    "ESTAKADA_APP_IMAGE_DIGEST",
                    "ESTAKADA_DB_HOST",
                    "ESTAKADA_DB_NAME",
                    "ESTAKADA_DB_PASSWORD_FILE",
                    "ESTAKADA_DB_PORT",
                    "ESTAKADA_DB_SSLROOTCERT",
                    "ESTAKADA_DB_USER",
                    "ESTAKADA_DJANGO_SECRET",
                    "ESTAKADA_LOCAL_RESTORE",
                ]
            ),
            "optional": [
                "ESTAKADA_PUBLIC_ORIGIN",
                "ESTAKADA_RESTORE_VERIFY_WRITE",
                "ESTAKADA_SEO_ROBOTS_PROFILE",
            ],
        },
    }
    media = media_inventory()
    facts = {
        "schema": SCHEMA,
        "releaseSha256": restore_release_sha256(release),
        "tableCounts": table_counts(),
        "tableContentSha256": table_content_hashes(),
        "media": {
            "files": len(media),
            "bytes": sum(int(row["bytes"]) for row in media),
            "inventorySha256": digest_bytes(canonical(media)),
        },
    }
    return release, facts, media


def restore_release_sha256(release: dict[str, object]) -> str:
    schema = release.get("schemaFingerprint")
    if type(schema) is not dict or "sourceCaptureSha256" not in schema:
        fail()
    semantic_release = dict(release)
    semantic_schema = dict(schema)
    semantic_schema["sourceCaptureSha256"] = RESTORE_SOURCE_CAPTURE_SENTINEL
    semantic_release["schemaFingerprint"] = semantic_schema
    return digest_bytes(canonical(semantic_release))


def write_new(path: Path, value: object) -> None:
    if path.exists() or path.parent != OUTPUT or not OUTPUT.is_dir():
        fail()
    path.write_bytes(canonical(value))


def build_release_snapshot() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE, READ ONLY, DEFERRABLE"
            )
        return build_release()


def capture() -> None:
    release, facts, media = build_release_snapshot()
    write_new(OUTPUT / "release-manifest.json", release)
    write_new(OUTPUT / "capture-facts.json", facts)
    write_new(OUTPUT / "media-inventory.json", media)
    print(
        f"R7_GENERATION_CAPTURE_OK tables={len(facts['tableCounts'])} "
        f"media_files={facts['media']['files']} media_bytes={facts['media']['bytes']}"
    )


def read_authority(name: str) -> object:
    path = AUTHORITY / name
    if not path.is_file() or path.is_symlink() or path.parent != AUTHORITY:
        fail()
    return json.loads(path.read_text(encoding="utf-8"))


def safe_table_token(value: object) -> str:
    if type(value) is not str or re.fullmatch(r"[a-z0-9_]+", value) is None:
        fail("R7_RESTORE_DIAGNOSTIC_UNAVAILABLE")
    return value.upper()


def first_mapping_difference(expected: object, actual: object) -> str | None:
    if type(expected) is not dict or type(actual) is not dict:
        fail("R7_RESTORE_DIAGNOSTIC_UNAVAILABLE")
    keys = set(expected) | set(actual)
    if any(
        type(key) is not str or re.fullmatch(r"[a-z0-9_]+", key) is None
        for key in keys
    ):
        fail("R7_RESTORE_DIAGNOSTIC_UNAVAILABLE")
    for key in sorted(keys):
        if expected.get(key) != actual.get(key):
            return safe_table_token(key)
    return None


def valid_sha256(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def binding_capture_value(
    release: object, facts: object
) -> dict[str, object]:
    if type(release) is not dict or type(facts) is not dict:
        fail("R7_BINDING_CAPTURE_UNAVAILABLE")
    source = release.get("source")
    schema = release.get("schemaFingerprint")
    migrations = release.get("appliedMigrations")
    media = facts.get("media")
    if (
        type(source) is not dict
        or not valid_sha256(source.get("sha256"))
        or type(schema) is not dict
        or type(migrations) is not list
        or not valid_sha256(facts.get("releaseSha256"))
        or type(facts.get("tableCounts")) is not dict
        or type(facts.get("tableContentSha256")) is not dict
        or type(media) is not dict
        or set(media) != {"files", "bytes", "inventorySha256"}
        or type(media.get("files")) is not int
        or media["files"] < 0
        or type(media.get("bytes")) is not int
        or media["bytes"] < 0
        or not valid_sha256(media.get("inventorySha256"))
    ):
        fail("R7_BINDING_CAPTURE_UNAVAILABLE")
    return {
        "schema": "estakada.r7-binding-capture-v1",
        "sourceSha256": source["sha256"],
        "releaseSha256": facts["releaseSha256"],
        "schemaFingerprintSha256": digest_bytes(canonical(schema)),
        "appliedMigrationsSha256": digest_bytes(canonical(migrations)),
        "tableCountsSha256": digest_bytes(canonical(facts["tableCounts"])),
        "tableContentSha256": digest_bytes(
            canonical(facts["tableContentSha256"])
        ),
        "mediaInventorySha256": media["inventorySha256"],
        "mediaFiles": media["files"],
        "mediaBytes": media["bytes"],
    }


def binding_capture() -> None:
    release, facts, _media = build_release_snapshot()
    print(canonical(binding_capture_value(release, facts)).decode("utf-8"), end="")


def verify_schema_fingerprint(expected: object, actual: object) -> None:
    if type(expected) is not dict or type(actual) is not dict:
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    keys = {
        "postgres",
        "sourceCaptureSha256",
        "sha256",
        "tables",
        "components",
        "tableComponents",
        "objectComponents",
        "columnFieldComponents",
        "constraintFieldComponents",
    }
    if set(expected) != keys or set(actual) != keys:
        fail("R7_RESTORE_SCHEMA_SHAPE_MISMATCH")
    for name in ("postgres", "tables"):
        if expected[name] != actual[name]:
            fail(f"R7_RESTORE_SCHEMA_{name.upper()}_MISMATCH")
    if any(
        not valid_sha256(value)
        for value in (
            expected["sourceCaptureSha256"],
            actual["sourceCaptureSha256"],
            expected["sha256"],
            actual["sha256"],
        )
    ):
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    component_names = {"columns", "constraints", "indexes"}
    expected_components = expected["components"]
    actual_components = actual["components"]
    if (
        type(expected_components) is not dict
        or type(actual_components) is not dict
        or set(expected_components) != component_names
        or set(actual_components) != component_names
        or any(
            not valid_sha256(value)
            for value in (*expected_components.values(), *actual_components.values())
        )
    ):
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    expected_tables = expected["tableComponents"]
    actual_tables = actual["tableComponents"]
    expected_objects = expected["objectComponents"]
    actual_objects = actual["objectComponents"]
    expected_column_fields = expected["columnFieldComponents"]
    actual_column_fields = actual["columnFieldComponents"]
    expected_constraint_fields = expected["constraintFieldComponents"]
    actual_constraint_fields = actual["constraintFieldComponents"]
    if type(expected_tables) is not dict or type(actual_tables) is not dict:
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    if type(expected_objects) is not dict or type(actual_objects) is not dict:
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    if type(expected_column_fields) is not dict or type(actual_column_fields) is not dict:
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    if type(expected_constraint_fields) is not dict or type(actual_constraint_fields) is not dict:
        fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    for tables, table_count in (
        (expected_tables, expected["tables"]),
        (actual_tables, actual["tables"]),
    ):
        if type(table_count) is not int or len(tables) != table_count:
            fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
        for table, values in tables.items():
            if (
                type(table) is not str
                or re.fullmatch(r"[a-z0-9_]+", table) is None
                or type(values) is not dict
                or set(values) != component_names
                or any(not valid_sha256(value) for value in values.values())
            ):
                fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    for objects, table_count in (
        (expected_objects, expected["tables"]),
        (actual_objects, actual["tables"]),
    ):
        if type(table_count) is not int or len(objects) != table_count:
            fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
        for table, values in objects.items():
            if (
                type(table) is not str
                or re.fullmatch(r"[a-z0-9_]+", table) is None
                or type(values) is not dict
                or set(values) != component_names
            ):
                fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
            for object_hashes in values.values():
                if type(object_hashes) is not dict or any(
                    type(name) is not str
                    or re.fullmatch(r"[a-z0-9_]+", name) is None
                    or not valid_sha256(value)
                    for name, value in object_hashes.items()
                ):
                    fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    column_field_names = set(COLUMN_FIELD_NAMES)
    for fields, objects, table_count in (
        (expected_column_fields, expected_objects, expected["tables"]),
        (actual_column_fields, actual_objects, actual["tables"]),
    ):
        if (
            type(table_count) is not int
            or len(fields) != table_count
            or set(fields) != set(objects)
        ):
            fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
        for table, columns in fields.items():
            expected_columns = objects[table]["columns"]
            if type(columns) is not dict or set(columns) != set(expected_columns):
                fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
            for column, field_hashes in columns.items():
                if (
                    type(column) is not str
                    or re.fullmatch(r"[a-z0-9_]+", column) is None
                    or type(field_hashes) is not dict
                    or set(field_hashes) != column_field_names
                    or any(not valid_sha256(value) for value in field_hashes.values())
                ):
                    fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    constraint_field_names = set(CONSTRAINT_FIELD_NAMES)
    for fields, objects, table_count in (
        (expected_constraint_fields, expected_objects, expected["tables"]),
        (actual_constraint_fields, actual_objects, actual["tables"]),
    ):
        if (
            type(table_count) is not int
            or len(fields) != table_count
            or set(fields) != set(objects)
        ):
            fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
        for table, constraints in fields.items():
            expected_constraints = objects[table]["constraints"]
            if type(constraints) is not dict or set(constraints) != set(expected_constraints):
                fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
            for constraint, field_hashes in constraints.items():
                if (
                    type(constraint) is not str
                    or re.fullmatch(r"[a-z0-9_]+", constraint) is None
                    or type(field_hashes) is not dict
                    or set(field_hashes) != constraint_field_names
                    or any(not valid_sha256(value) for value in field_hashes.values())
                ):
                    fail("R7_RESTORE_SCHEMA_DIAGNOSTIC_UNAVAILABLE")
    table_token = first_mapping_difference(expected_tables, actual_tables)
    if table_token is not None:
        table = table_token.lower()
        expected_table = expected_tables.get(table)
        actual_table = actual_tables.get(table)
        if type(expected_table) is dict and type(actual_table) is dict:
            for component in ("columns", "constraints", "indexes"):
                if expected_table.get(component) != actual_table.get(component):
                    expected_object_hashes = expected_objects.get(table, {}).get(
                        component
                    )
                    actual_object_hashes = actual_objects.get(table, {}).get(component)
                    object_token = first_mapping_difference(
                        expected_object_hashes, actual_object_hashes
                    )
                    if object_token is not None:
                        if component == "columns":
                            expected_field_hashes = expected_column_fields.get(
                                table, {}
                            ).get(object_token.lower())
                            actual_field_hashes = actual_column_fields.get(
                                table, {}
                            ).get(object_token.lower())
                            if (
                                type(expected_field_hashes) is dict
                                and type(actual_field_hashes) is dict
                            ):
                                field_token = first_mapping_difference(
                                    expected_field_hashes, actual_field_hashes
                                )
                                if field_token is not None:
                                    fail(
                                        f"R7_RESTORE_SCHEMA_COLUMNS_{table_token}_"
                                        f"{object_token}_{field_token}_MISMATCH"
                                    )
                        if component == "constraints":
                            expected_field_hashes = expected_constraint_fields.get(
                                table, {}
                            ).get(object_token.lower())
                            actual_field_hashes = actual_constraint_fields.get(
                                table, {}
                            ).get(object_token.lower())
                            if (
                                type(expected_field_hashes) is dict
                                and type(actual_field_hashes) is dict
                            ):
                                field_token = first_mapping_difference(
                                    expected_field_hashes, actual_field_hashes
                                )
                                if field_token is not None:
                                    fail(
                                        f"R7_RESTORE_SCHEMA_CONSTRAINTS_{table_token}_"
                                        f"{object_token}_{field_token}_MISMATCH"
                                    )
                        fail(
                            f"R7_RESTORE_SCHEMA_{component.upper()}_"
                            f"{table_token}_{object_token}_MISMATCH"
                        )
                    fail(
                        f"R7_RESTORE_SCHEMA_{component.upper()}_{table_token}_MISMATCH"
                    )
        fail(f"R7_RESTORE_SCHEMA_TABLE_{table_token}_MISMATCH")
    for component in ("columns", "constraints", "indexes"):
        if expected_components[component] != actual_components[component]:
            fail(f"R7_RESTORE_SCHEMA_{component.upper()}_MISMATCH")
    if expected["sha256"] != actual["sha256"]:
        fail("R7_RESTORE_SCHEMA_COMBINED_SHA_MISMATCH")


def verify_raw_snapshot(
    expected_release: object,
    expected_facts: object,
    expected_media: object,
    release: object,
    facts: object,
    media: object,
) -> None:
    if type(expected_release) is not dict or type(release) is not dict:
        fail("R7_RESTORE_DIAGNOSTIC_UNAVAILABLE")
    if set(expected_release) != set(RELEASE_KEYS) or set(release) != set(RELEASE_KEYS):
        fail("R7_RESTORE_RELEASE_SHAPE_MISMATCH")
    for key in RELEASE_KEYS:
        if expected_release[key] != release[key]:
            if key == "schemaFingerprint":
                verify_schema_fingerprint(expected_release[key], release[key])
                continue
            fail(f"R7_RESTORE_RELEASE_{key.upper()}_MISMATCH")

    if type(expected_facts) is not dict or type(facts) is not dict:
        fail("R7_RESTORE_DIAGNOSTIC_UNAVAILABLE")
    fact_keys = {
        "schema",
        "releaseSha256",
        "tableCounts",
        "tableContentSha256",
        "media",
    }
    if set(expected_facts) != fact_keys or set(facts) != fact_keys:
        fail("R7_RESTORE_FACTS_SHAPE_MISMATCH")
    if expected_facts["schema"] != facts["schema"]:
        fail("R7_RESTORE_FACTS_SCHEMA_MISMATCH")
    if expected_facts["releaseSha256"] != facts["releaseSha256"]:
        fail("R7_RESTORE_FACTS_RELEASE_SHA_MISMATCH")
    count_table = first_mapping_difference(
        expected_facts["tableCounts"], facts["tableCounts"]
    )
    if count_table is not None:
        fail(f"R7_RESTORE_TABLE_COUNT_{count_table}_MISMATCH")
    content_table = first_mapping_difference(
        expected_facts["tableContentSha256"], facts["tableContentSha256"]
    )
    if content_table is not None:
        fail(f"R7_RESTORE_TABLE_CONTENT_{content_table}_MISMATCH")
    if expected_facts["media"] != facts["media"]:
        fail("R7_RESTORE_MEDIA_FACTS_MISMATCH")
    if expected_media != media:
        fail("R7_RESTORE_MEDIA_INVENTORY_MISMATCH")


def verify_audit_actor_shape() -> None:
    before = AuditEvent.objects.count()
    actor_kinds = ("USER", "SYSTEM", "ANONYMOUS", "UNKNOWN")
    for index, (actor_kind, has_uuid, has_role) in enumerate(
        (
            (actor_kind, has_uuid, has_role)
            for actor_kind in actor_kinds
            for has_uuid in (False, True)
            for has_role in (False, True)
        )
    ):
        should_accept = (
            actor_kind == "USER" and has_uuid and has_role
        ) or (
            actor_kind in {"SYSTEM", "ANONYMOUS"}
            and not has_uuid
            and not has_role
        )
        probe_id = uuid.uuid5(uuid.NAMESPACE_URL, f"estakada-r7-audit-shape-{index}")
        if AuditEvent.objects.filter(pk=probe_id).exists():
            fail("R7_RESTORE_AUDIT_CONSTRAINT_PROBE_UNAVAILABLE")
        try:
            with transaction.atomic():
                AuditEvent.objects.create(
                    id=probe_id,
                    action="AUTH_LOGIN_SUCCEEDED",
                    actor_kind=actor_kind,
                    actor_uuid=(uuid.uuid4() if has_uuid else None),
                    actor_role=("OWNER" if has_role else None),
                    target_type="USER",
                    target_uuid=None,
                    secondary_uuid=None,
                    detail={},
                )
                transaction.set_rollback(True)
        except IntegrityError as error:
            if should_accept:
                fail("R7_RESTORE_AUDIT_CONSTRAINT_VALID_REJECTED")
            cause = error.__cause__
            diagnostic = getattr(cause, "diag", None)
            if getattr(diagnostic, "constraint_name", None) != AUDIT_ACTOR_CONSTRAINT:
                fail("R7_RESTORE_AUDIT_CONSTRAINT_PROBE_UNAVAILABLE")
        else:
            if not should_accept:
                fail("R7_RESTORE_AUDIT_CONSTRAINT_INVALID_ACCEPTED")
    if AuditEvent.objects.count() != before:
        fail("R7_RESTORE_AUDIT_CONSTRAINT_PROBE_DRIFT")


def verify() -> None:
    expected_release = read_authority("release-manifest.json")
    expected_facts = read_authority("capture-facts.json")
    expected_media = read_authority("media-inventory.json")
    release, facts, media = build_release_snapshot()
    verify_raw_snapshot(
        expected_release, expected_facts, expected_media, release, facts, media
    )
    verify_audit_actor_shape()
    raw_counts = dict(facts["tableCounts"])
    raw_content_hashes = dict(facts["tableContentSha256"])
    User = get_user_model()
    with transaction.atomic():
        sessions_deleted, _ = Session.objects.all().delete()
        before_users = list(User.objects.order_by("pk").values_list("pk", "generation"))
        staff_count = len(before_users)
        updated = User.objects.update(generation=F("generation") + 1)
        after_users = list(User.objects.order_by("pk").values_list("pk", "generation"))
        exact_generation_bump = len(after_users) == staff_count and all(
            before_id == after_id and after_generation == before_generation + 1
            for (before_id, before_generation), (after_id, after_generation) in zip(
                before_users, after_users, strict=True
            )
        )
        if updated != staff_count or not exact_generation_bump or Session.objects.exists():
            fail("R7_RESTORE_RECONCILIATION_FAILED")
    result = {
        "schema": SCHEMA,
        "releaseSha256": facts["releaseSha256"],
        "rawTableCountsSha256": digest_bytes(canonical(raw_counts)),
        "rawTableContentSha256": digest_bytes(canonical(raw_content_hashes)),
        "mediaInventorySha256": facts["media"]["inventorySha256"],
        "mediaFiles": facts["media"]["files"],
        "mediaBytes": facts["media"]["bytes"],
        "sessionsDeleted": sessions_deleted,
        "staffGenerationsBumped": staff_count,
    }
    write_new(OUTPUT / "restore-result.json", result)
    print(
        f"R7_GENERATION_RESTORE_OK tables={len(raw_counts)} "
        f"media_files={result['mediaFiles']} sessions_deleted={sessions_deleted} "
        f"staff_bumped={staff_count}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("capture", "verify", "binding-capture"))
    args = parser.parse_args()
    if settings.SERVICE_REQUESTS_ENABLED is not False:
        fail()
    if args.mode == "capture":
        capture()
    elif args.mode == "verify":
        verify()
    else:
        binding_capture()


if __name__ == "__main__":
    main()
