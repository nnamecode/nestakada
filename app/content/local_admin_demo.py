"""One-shot, dev-only assembly of the reviewed local admin demo.

This is deliberately not a management command or reusable importer.  The host
wrapper supplies one closed set of paths and admission values.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import unittest
from unittest.mock import patch
from uuid import UUID

import django
django.setup()

from django.conf import settings
from django.db import connection, models, transaction

from media_library import services as media_services
from media_library.models import Asset, AssetFile, MediaFolder
from media_library.storage import MediaStorage
from shared_content import policy as shared_policy
from shared_content.models import SharedBlock, SharedBudget, SharedIdentityReservation
from shared_content.simple_commands import _insert_revision

from .models import Route
from . import dev09_migration_apply as migration
from . import dev10_gallery_apply as gallery
from . import dev12_home_apply as home
from .test_test08_fixture import _counts, build_test08_fixture


SCHEMA = "local-admin-demo-result-v1"
LOGO_BYTES = 30190
LOGO_SHA256 = "39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5"
LOGO_FOLDER_ID = UUID("3d45dce7-78da-4ec8-8a64-eae75c64616b")
LOGO_ASSET_ID = UUID("106e33f5-3ac4-48e2-aa7c-5d299b20cf22")
LOGO_FILE_ID = UUID("ff79e2e4-392c-4455-88bd-d80f4c36b96c")
LOGO_KEY = "img/106e33f5-3ac4-48e2-aa7c-5d299b20cf22/original.png"
HEADER_BLOCK_ID = UUID("8dcee2c6-185c-5980-a335-c2179c2b0eb3")
FOOTER_BLOCK_ID = UUID("e1106b9c-8b0b-56a9-9b05-50211192e0ae")
EXPECTED_MEDIA_COUNT = 238
EXPECTED_MEDIA_BYTES = 45094933
FORBIDDEN_CURRENT = (
    "synthetic", "+70000000001", "t.me/", "max.ru/", "instagram.com/",
)


def _sha_json(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _raw(model):
    return models.QuerySet(model=model, using="default")


def _header_html(asset_id):
    marker = str(asset_id)
    brand = (
        '<a class="es-brand" href="/" aria-label="Эстакада">'
        f'<img data-es-shared-asset="{marker}" alt="Автосервис Эстакада"></a>'
    )
    return (
        '<header class="es-header">' + brand
        + '<button class="es-menu-button" type="button" aria-expanded="false" '
          'aria-controls="es-nav"><span></span><span></span><span></span><b>Меню</b></button>'
          '<nav id="es-nav" aria-label="Основное меню"></nav>'
          '<div class="es-header-contacts"><div class="es-header-socials"></div>'
          '<a class="es-header-address" href="https://yandex.ru/maps/org/57771430682">'
          '<b>Москва</b><span>Проспект 60-летия Октября, 15Б</span></a>'
          '<a class="es-header-phone" href="tel:+74991102552">'
          '<strong>+7 (499) 110-25-52</strong><span>Ежедневно с 9:00 до 21:00</span>'
          '</a></div></header>'
    )


def _footer_html(asset_id):
    marker = str(asset_id)
    brand = (
        '<a class="es-brand" href="/" aria-label="Эстакада">'
        f'<img data-es-shared-asset="{marker}" alt="Автосервис Эстакада"></a>'
    )
    return (
        '<footer class="es-footer"><div class="es-footer-left">' + brand
        + '<p>ООО «Эстакада»</p></div><div class="es-footer-legal">'
          '<span>Политика конфиденциальности</span>'
          '<span>Условия использования файлов cookie</span>'
          '<span class="es-footer-credit">Сделано в <b>noname</b></span>'
          '</div></footer>'
    )


def _regular_file(path, expected_size=None, expected_sha=None):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise RuntimeError("LOCAL_DEMO_REGULAR_FILE_REQUIRED")
        digest = hashlib.file_digest(source, "sha256").hexdigest()
        after = os.fstat(source.fileno())
        if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_ino, after.st_size, after.st_mtime_ns):
            raise RuntimeError("LOCAL_DEMO_FILE_CHANGED")
        if expected_size is not None and after.st_size != expected_size:
            raise RuntimeError("LOCAL_DEMO_FILE_SIZE_MISMATCH")
        if expected_sha is not None and digest != expected_sha:
            raise RuntimeError("LOCAL_DEMO_FILE_HASH_MISMATCH")
        source.seek(0)
        return source.read(), {"byte_size": after.st_size, "sha256": digest}


def _safe_empty_root(path):
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("LOCAL_DEMO_STATE_ROOT_REJECTED")
    if path.resolve() != path:
        raise RuntimeError("LOCAL_DEMO_STATE_ROOT_REJECTED")


def _database_identity(test_mode):
    expected = (("estakada_foundation_unit", "app_migrator") if test_mode
                else ("estakada_foundation", "app_runtime"))
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_user")
        actual = cursor.fetchone()
    if actual != expected:
        raise RuntimeError("LOCAL_DEMO_DATABASE_IDENTITY_REJECTED")


def _make_staging(state_root, run_id):
    staging_parent = state_root / "local-admin-demo-staging"
    staging_parent.mkdir(mode=0o700, exist_ok=True)
    if staging_parent.is_symlink() or staging_parent.resolve().parent != state_root:
        raise RuntimeError("LOCAL_DEMO_STAGING_PARENT_REJECTED")
    staging = staging_parent / run_id
    staging.mkdir(mode=0o700)
    return staging


def _copy_declared_media(source_root, staging):
    total = 0
    rows = list(AssetFile.objects.order_by("key").values(
        "key", "byte_size", "sha256"))
    if len(rows) != EXPECTED_MEDIA_COUNT:
        raise RuntimeError("LOCAL_DEMO_MEDIA_COUNT_MISMATCH")
    for row in rows:
        relative = Path(row["key"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("LOCAL_DEMO_MEDIA_KEY_REJECTED")
        source = source_root.joinpath(relative)
        data, actual = _regular_file(source, row["byte_size"], row["sha256"])
        destination = staging.joinpath(relative)
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                     | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        _regular_file(destination, actual["byte_size"], actual["sha256"])
        total += actual["byte_size"]
    if total != EXPECTED_MEDIA_BYTES:
        raise RuntimeError("LOCAL_DEMO_MEDIA_BYTES_MISMATCH")
    for directory, names, _ in os.walk(staging, topdown=False):
        if any(Path(directory, name).is_symlink() for name in names):
            raise RuntimeError("LOCAL_DEMO_STAGING_LINK_REJECTED")
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return {"count": len(rows), "bytes": total}


def _verify_staging(staging):
    declared = {
        row["key"]: {"byte_size": row["byte_size"], "sha256": row["sha256"]}
        for row in AssetFile.objects.order_by("key").values(
            "key", "byte_size", "sha256")
    }
    expected_dirs = set()
    for key in declared:
        parent = Path(key).parent
        while parent != Path('.'):
            expected_dirs.add(parent.as_posix())
            parent = parent.parent
    actual_dirs, actual_files = set(), set()
    for root, directories, files in os.walk(staging, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in directories:
            path = root_path / name
            if path.is_symlink():
                raise RuntimeError("LOCAL_DEMO_STAGING_LINK_REJECTED")
            actual_dirs.add(path.relative_to(staging).as_posix())
        for name in files:
            path = root_path / name
            if path.is_symlink():
                raise RuntimeError("LOCAL_DEMO_STAGING_LINK_REJECTED")
            actual_files.add(path.relative_to(staging).as_posix())
    if actual_dirs != expected_dirs or actual_files != set(declared):
        raise RuntimeError("LOCAL_DEMO_STAGING_INVENTORY_MISMATCH")
    total = 0
    count = 0
    projection = []
    for key, expected in sorted(declared.items()):
        _, actual = _regular_file(
            staging / key, expected["byte_size"], expected["sha256"])
        count += 1
        total += actual["byte_size"]
        projection.append({"key": key, **actual})
    if (count, total) != (EXPECTED_MEDIA_COUNT, EXPECTED_MEDIA_BYTES):
        raise RuntimeError("LOCAL_DEMO_STAGING_PROJECTION_MISMATCH")
    return {"count": count, "bytes": total,
            "projection_sha256": _sha_json(projection)}


def _remove_owned_tree(path, parent):
    if not path.exists():
        return
    if path.is_symlink() or path.parent.resolve() != parent.resolve():
        raise RuntimeError("LOCAL_DEMO_CLEANUP_SCOPE_REJECTED")
    for item in path.rglob("*"):
        if item.is_symlink():
            raise RuntimeError("LOCAL_DEMO_CLEANUP_LINK_REJECTED")
    shutil.rmtree(path)


def _create_logo(logo_path, storage):
    data, _ = _regular_file(logo_path, LOGO_BYTES, LOGO_SHA256)
    folder = MediaFolder(id=LOGO_FOLDER_ID, path="legacy/shared")
    folder.save()
    asset = Asset(
        id=LOGO_ASSET_ID, folder=folder, provenance="MED-0105 local demo logo",
        is_legacy=True, source_url="https://estakada-service.ru/",
        source_sha256=LOGO_SHA256,
    )
    asset.save()
    file_row = media_services.write_file(
        asset_id=asset.pk, file_id=LOGO_FILE_ID,
        kind=AssetFile.Kind.LEGACY_PUBLIC, key=LOGO_KEY,
        chunks=data, storage=storage,
    )
    if (file_row.byte_size, file_row.sha256) != (LOGO_BYTES, LOGO_SHA256):
        raise RuntimeError("LOCAL_DEMO_LOGO_WRITE_MISMATCH")
    media_services.mark_ready(asset_id=asset.pk, storage=storage)
    return asset


def _publish_real_shared(owner, logo):
    current_html = []
    for kind, source in (("header", _header_html(logo.pk)),
                         ("footer", _footer_html(logo.pk))):
        normalized = shared_policy.normalize_html(source, kind)
        block = SharedBlock.objects.select_for_update().get(kind=kind)
        _insert_revision(
            block=block, actor=owner, kind=kind, html=normalized["html"],
            bindings=normalized["bindings"],
        )
        current_html.append(normalized["html"])
    joined = "\n".join(current_html).lower()
    if any(value in joined for value in FORBIDDEN_CURRENT):
        raise RuntimeError("LOCAL_DEMO_SYNTHETIC_CURRENT_REJECTED")


def _fixture_shared_commit(*, actor, kind, expected_generation, session_key,
                           expected_current_id, html, bindings):
    """Transaction-compatible seam for the exact fixture's initial revisions."""
    if expected_generation != 1 or not session_key:
        raise RuntimeError("LOCAL_DEMO_FIXTURE_SHARED_ADMISSION_REJECTED")
    block = SharedBlock.objects.select_for_update().get(kind=kind)
    if block.current_revision_id != expected_current_id:
        raise RuntimeError("LOCAL_DEMO_FIXTURE_SHARED_CURRENT_CHANGED")
    return _insert_revision(
        block=block, actor=actor, kind=kind, html=html, bindings=bindings,
    )


def _baseline_manage_route():
    counts = _counts()
    allowed = {
        "auditEvents", "routes", "sharedBlocks", "sharedBudgets",
        "sharedIdentityReservations",
    }
    if (counts["routes"] != 1 or counts["sharedBlocks"] != 2
            or counts["sharedBudgets"] != 1
            or counts["sharedIdentityReservations"] != 2
            or any(value != 0 for key, value in counts.items() if key not in allowed)):
        raise RuntimeError("LOCAL_DEMO_NONEMPTY_DATABASE")
    blocks = list(SharedBlock.objects.select_for_update().order_by("kind").values_list(
        "id", "kind", "generation", "current_revision_id"))
    expected_blocks = [
        (FOOTER_BLOCK_ID, "footer", 1, None),
        (HEADER_BLOCK_ID, "header", 1, None),
    ]
    if blocks != expected_blocks:
        raise RuntimeError("LOCAL_DEMO_SHARED_SEED_MISMATCH")
    identities = set(SharedIdentityReservation.objects.values_list(
        "id", "kind", "block_id"))
    expected_identities = {
        (FOOTER_BLOCK_ID, "sharedblock", FOOTER_BLOCK_ID),
        (HEADER_BLOCK_ID, "sharedblock", HEADER_BLOCK_ID),
    }
    if identities != expected_identities:
        raise RuntimeError("LOCAL_DEMO_SHARED_IDENTITY_SEED_MISMATCH")
    budget = SharedBudget.objects.values_list(
        "singleton", "snapshot_count", "charged_bytes",
        "accounting_version", "retained_debt_bytes").get()
    if budget != (True, 0, 0, "unvetted", 0):
        raise RuntimeError("LOCAL_DEMO_SHARED_BUDGET_SEED_MISMATCH")
    routes = list(Route.objects.select_for_update().filter(
        target="/manage/", kind=Route.Kind.SYSTEM, page_id=None))
    if len(routes) != 1 or Route.objects.count() != 1:
        raise RuntimeError("LOCAL_DEMO_MANAGE_ROUTE_MISMATCH")
    route = routes[0]
    return (route.pk, route.target, route.kind, route.page_id, route.is_legacy)


def _restore_manage_route(values):
    route = Route(id=values[0], target=values[1], kind=values[2],
                  page_id=values[3], is_legacy=values[4])
    _raw(Route).bulk_create([route])
    actual = Route.objects.filter(pk=values[0]).values_list(
        "id", "target", "kind", "page_id", "is_legacy").get()
    if actual != values:
        raise RuntimeError("LOCAL_DEMO_MANAGE_ROUTE_RESTORE_MISMATCH")


def _reuse_fixture_block(*, kind):
    if kind not in ("header", "footer"):
        raise RuntimeError("LOCAL_DEMO_FIXTURE_BLOCK_REUSE_REJECTED")
    return SharedBlock.objects.get(kind=kind, generation=1, current_revision_id=None)


def _reuse_fixture_budget(*, singleton):
    if singleton is not True:
        raise RuntimeError("LOCAL_DEMO_FIXTURE_BUDGET_REUSE_REJECTED")
    return SharedBudget.objects.get(
        singleton=True, snapshot_count=0, charged_bytes=0,
        accounting_version="unvetted", retained_debt_bytes=0,
    )


def assemble_demo(*, state_root, logo_path, run_id, test_mode=False,
                  fail_after_publish=False):
    """Assemble once.  ``test_mode`` only relaxes runtime identity checks."""
    state_root = Path(state_root)
    logo_path = Path(logo_path)
    UUID(run_id)
    if str(UUID(run_id)) != run_id:
        raise RuntimeError("LOCAL_DEMO_RUN_ID_REJECTED")
    if settings.ENVIRONMENT != "dev":
        raise RuntimeError("LOCAL_DEMO_DEV_ONLY")
    if os.environ.get("ESTAKADA_LOCAL_DEMO_APPLY_ENABLED") != "1":
        raise RuntimeError("LOCAL_DEMO_APPLY_NOT_ENABLED")
    db = connection.settings_dict
    if not test_mode and (db.get("NAME") != "estakada_foundation"
                          or db.get("USER") != "app_runtime"):
        raise RuntimeError("LOCAL_DEMO_DATABASE_IDENTITY_REJECTED")
    _database_identity(test_mode)
    _safe_empty_root(state_root)
    final_root = state_root / "media"
    if final_root.exists() or final_root.is_symlink():
        raise RuntimeError("LOCAL_DEMO_MEDIA_ALREADY_EXISTS")
    staging = None
    published = False
    try:
        with transaction.atomic():
            manage_route = _baseline_manage_route()
            staging = _make_staging(state_root, run_id)
            deleted, _ = _raw(Route).filter(pk=manage_route[0]).delete()
            if deleted != 1 or Route.objects.exists():
                raise RuntimeError("LOCAL_DEMO_MANAGE_ROUTE_DELETE_MISMATCH")
            credentials = {
                "owner": secrets.token_urlsafe(32),
                "employee": secrets.token_urlsafe(32),
            }
            fixture_count_calls = 0

            def fixture_counts_view():
                nonlocal fixture_count_calls
                values = _counts()
                if fixture_count_calls == 0:
                    for key in ("auditEvents", "sharedBlocks", "sharedBudgets",
                                "sharedIdentityReservations"):
                        values[key] = 0
                fixture_count_calls += 1
                return values

            with patch("content.test_test08_fixture.commit_normalized_current",
                       side_effect=_fixture_shared_commit), patch(
                       "content.test_test08_fixture._counts",
                       side_effect=fixture_counts_view), patch.object(
                       SharedBlock.objects, "create",
                       side_effect=_reuse_fixture_block), patch.object(
                       SharedBudget.objects, "create",
                       side_effect=_reuse_fixture_budget), patch.object(
                       migration, "_enabled", return_value=None), patch.object(
                       migration, "_identity", return_value=None), patch.object(
                       gallery, "_enabled", return_value=None), patch.object(
                       gallery, "_identity", return_value=None), patch.object(
                       home, "_enabled", return_value=None), patch.object(
                       home, "_identity", return_value=None):
                with build_test08_fixture(unittest.TestCase(), credentials=credentials) as fixture:
                    storage = MediaStorage()
                    logo = _create_logo(logo_path, storage)
                    _publish_real_shared(fixture["owner"], logo)
                    media = _copy_declared_media(Path(fixture["mediaRoot"]), staging)
            verified_media = _verify_staging(staging)
            _restore_manage_route(manage_route)
            counts = _counts()
            if ((counts["pages"], counts["routes"], counts["assets"], counts["files"],
                 counts["requests"], counts["users"], counts["profiles"])
                    != (112, 115, 238, 238, 0, 2, 2)):
                raise RuntimeError("LOCAL_DEMO_FINAL_COUNTS_MISMATCH")
            os.rename(staging, final_root)
            published = True
            if fail_after_publish:
                raise RuntimeError("LOCAL_DEMO_CONTROLLED_FAILURE")
            route_targets = list(Route.objects.order_by("target").values_list(
                "target", flat=True))
            shared_current = list(SharedBlock.objects.order_by("kind").values_list(
                "kind", "current_revision__payload_hash"))
            database_projection = {
                "assets": counts["assets"], "files": counts["files"],
                "pages": counts["pages"], "profiles": counts["profiles"],
                "published": 112, "requests": counts["requests"],
                "routes": route_targets, "sharedCurrent": shared_current,
                "users": counts["users"],
            }
        return {
            "schema": SCHEMA, "runId": run_id,
            "pages": 112, "routes": 115, "published": 112,
            "assets": 238, "files": 238, "media": media,
            "requests": 0, "users": 2, "profiles": 2,
            "owner": "nesadmin", "socialLinks": 0,
            "sourceManifestSha256": os.environ["ESTAKADA_TEST08_SOURCE_MANIFEST_SHA256"],
            "routeMapSha256": os.environ["ESTAKADA_TEST08_ROUTE_SHA256"],
            "mediaProjectionSha256": verified_media["projection_sha256"],
            "databaseProjectionSha256": _sha_json(database_projection),
        }
    except BaseException:
        target = final_root if published else staging
        if target is not None:
            _remove_owned_tree(target, state_root if published else staging.parent)
        raise


def main():
    result = assemble_demo(
        state_root=os.environ.get("ESTAKADA_LOCAL_DEMO_STATE_ROOT", ""),
        logo_path=os.environ.get("ESTAKADA_LOCAL_DEMO_LOGO", ""),
        run_id=os.environ.get("ESTAKADA_LOCAL_DEMO_RUN_ID", ""),
    )
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    print("LOCAL_ADMIN_DEMO_RESULT="
          + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="), flush=True)


if __name__ == "__main__":
    main()
