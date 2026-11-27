from __future__ import annotations

import hashlib
import copy
import json
import os
import stat
import sys
import uuid
from pathlib import Path, PurePosixPath


PROJECT = Path("/source-authority")
RESTORED_MEDIA = Path("/restore-media")
BASELINE = Path("/projection-authority/baseline.json")
BASE_INVENTORY = Path("/base-authority/media-inventory.json")
USAGE_NAMESPACE = uuid.UUID("df7dbf40-c9f7-5e92-bb52-03bdb835bf93")
EXPECTED_BASE_FILES = 265
EXPECTED_BASE_BYTES = 48_667_032
EXPECTED_ADDED_BYTES = 4_084_666
FAILURE_STAGES = frozenset({
    "UNAVAILABLE",
    "SERVICE_AUTHORITY",
    "DB_CONTENT_LOAD",
    "DB_IDENTITY_PRESTATE",
    "DB_CONTENT_PRESTATE",
    "DB_PAYLOAD_BIND",
    "DB_BASELINE_WRITE",
    "DB_ASSET_CREATE",
    "DB_MAP019_RELOCATE",
    "DB_USAGE_BIND",
    "DB_POSTSTATE_REFRESH",
    "DB_BASELINE_READ",
    "DB_POSTSTATE_VERIFY",
    "PROBE_SNAPSHOT_BEFORE",
    "PROBE_APPLY",
    "PROBE_ROLLBACK_COMPARE",
})
FAILURE_STAGE = "UNAVAILABLE"
DIAGNOSTIC_CODE = "R7_OWNER_PROJECTION_DIAGNOSTIC_UNAVAILABLE"


def stage_code(value: str) -> str:
    if value not in FAILURE_STAGES:
        return DIAGNOSTIC_CODE
    if value == "UNAVAILABLE":
        return "R7_OWNER_PROJECTION_UNAVAILABLE"
    return f"R7_OWNER_PROJECTION_{value}_UNAVAILABLE"


FAILURE_CODES = frozenset(stage_code(value) for value in FAILURE_STAGES)


def fail() -> None:
    raise RuntimeError(stage_code(FAILURE_STAGE))


def set_stage(value: str) -> None:
    global FAILURE_STAGE
    if value not in FAILURE_STAGES:
        raise RuntimeError(DIAGNOSTIC_CODE)
    FAILURE_STAGE = value


def normalized_failure(exc: BaseException) -> str:
    code = str(exc)
    if code in FAILURE_CODES or code == DIAGNOSTIC_CODE:
        return code
    return stage_code(FAILURE_STAGE)


def storage_key(row: dict[str, object]) -> str:
    asset_id = uuid.UUID(str(row["asset_id"]))
    source = PurePosixPath(str(row["source_path"]))
    if source.is_absolute() or ".." in source.parts or source.suffix != ".webp":
        fail()
    return f"img/{asset_id}/main.webp"


def usage_id(row: dict[str, object]) -> uuid.UUID:
    return uuid.uuid5(USAGE_NAMESPACE, f"hero:{row['page_id']}:{row['asset_id']}")


def canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError):
        fail()


def value_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def write_baseline(value: dict[str, object]) -> None:
    if BASELINE.name != "baseline.json":
        fail()
    root_fd = open_root(BASELINE.parent)
    try:
        fd = os.open(
            BASELINE.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=root_fd,
        )
    except OSError:
        os.close(root_fd)
        fail()
    os.close(root_fd)
    try:
        write_all(fd, canonical(value) + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)


def read_baseline() -> dict[str, object]:
    root_fd = open_root(BASELINE.parent)
    try:
        fd = open_relative_file(root_fd, BASELINE.name)
    finally:
        os.close(root_fd)
    try:
        raw = b""
        while chunk := os.read(fd, 1024 * 1024):
            raw += chunk
    except OSError:
        os.close(fd)
        fail()
    os.close(fd)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        fail()
    if canonical(value) + b"\n" != raw:
        fail()
    if type(value) is not dict or set(value) != {"schema", "pages"}:
        fail()
    if value["schema"] != "estakada.r7-owner-projection-baseline-v1":
        fail()
    pages = value["pages"]
    if type(pages) is not dict or len(pages) != 23:
        fail()
    for key, row in pages.items():
        if (
            type(key) is not str
            or type(row) is not dict
            or set(row) != {"kind", "untouched_sha256", "projected_current_sha256"}
            or type(row["kind"]) is not str
            or type(row["untouched_sha256"]) is not str
            or len(row["untouched_sha256"]) != 64
            or type(row["projected_current_sha256"]) is not str
            or len(row["projected_current_sha256"]) != 64
        ):
            fail()
    return value


def relative_parts(value: str) -> tuple[str, ...]:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or "\\" in value or not pure.parts:
        fail()
    return pure.parts


def open_root(path: Path) -> int:
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        fail()


def open_relative_file(root_fd: int, value: str, flags: int = os.O_RDONLY) -> int:
    parts = relative_parts(value)
    parent_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child_fd = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd
            )
            os.close(parent_fd)
            parent_fd = child_fd
        result = os.open(parts[-1], flags | os.O_NOFOLLOW, dir_fd=parent_fd)
    except OSError:
        os.close(parent_fd)
        fail()
    os.close(parent_fd)
    try:
        mode = os.fstat(result).st_mode
    except OSError:
        os.close(result)
        fail()
    if not stat.S_ISREG(mode):
        os.close(result)
        fail()
    return result


def checked_source(row: dict[str, object]) -> int:
    relative = PurePosixPath(str(row["source_path"]))
    if relative.suffix != ".webp":
        fail()
    root_fd = open_root(PROJECT)
    try:
        return open_relative_file(root_fd, str(row["source_path"]))
    finally:
        os.close(root_fd)


def digest_fd(fd: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        os.lseek(fd, 0, os.SEEK_SET)
    except OSError:
        fail()
    return size, digest.hexdigest()


def write_all(fd: int, value: bytes) -> None:
    view = memoryview(value)
    while view:
        try:
            written = os.write(fd, view)
        except OSError:
            fail()
        if written < 1:
            fail()
        view = view[written:]


def copy_files(rows: tuple[dict[str, object], ...]) -> None:
    restore_fd = open_root(RESTORED_MEDIA)
    try:
        img_fd = os.open("img", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=restore_fd)
    except OSError:
        os.close(restore_fd)
        fail()
    try:
        for row in rows:
            source_fd = checked_source(row)
            source_size, source_digest = digest_fd(source_fd)
            if source_size != row["byte_size"] or source_digest != row["sha256"]:
                os.close(source_fd)
                fail()
            asset_component = str(uuid.UUID(str(row["asset_id"])))
            asset_fd = None
            try:
                os.mkdir(asset_component, mode=0o755, dir_fd=img_fd)
                asset_fd = os.open(
                    asset_component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=img_fd,
                )
                destination_fd = os.open(
                    "main.webp",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o644,
                    dir_fd=asset_fd,
                )
            except OSError:
                if asset_fd is not None:
                    os.close(asset_fd)
                os.close(source_fd)
                fail()
            digest = hashlib.sha256()
            size = 0
            try:
                while chunk := os.read(source_fd, 1024 * 1024):
                    write_all(destination_fd, chunk)
                    digest.update(chunk)
                    size += len(chunk)
                os.fsync(destination_fd)
            except OSError:
                fail()
            finally:
                os.close(source_fd)
                os.close(destination_fd)
                os.close(asset_fd)
            if size != row["byte_size"] or digest.hexdigest() != row["sha256"]:
                fail()
    finally:
        os.close(img_fd)
        os.close(restore_fd)


def read_base_inventory() -> tuple[dict[str, object], ...]:
    root_fd = open_root(BASE_INVENTORY.parent)
    try:
        fd = open_relative_file(root_fd, BASE_INVENTORY.name)
    finally:
        os.close(root_fd)
    try:
        raw = b""
        while chunk := os.read(fd, 1024 * 1024):
            raw += chunk
    except OSError:
        os.close(fd)
        fail()
    os.close(fd)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        fail()
    if type(value) is not list or len(value) != EXPECTED_BASE_FILES:
        fail()
    previous = ""
    rows = []
    for row in value:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            fail()
        path = row["path"]
        if (
            type(path) is not str
            or path <= previous
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
        ):
            fail()
        relative_parts(path)
        previous = path
        rows.append(row)
    if sum(row["bytes"] for row in rows) != EXPECTED_BASE_BYTES:
        fail()
    return tuple(rows)


def walk_inventory(fd: int, prefix: str = "") -> dict[str, tuple[int, str]]:
    result: dict[str, tuple[int, str]] = {}
    try:
        names = sorted(os.listdir(fd))
    except OSError:
        fail()
    for name in names:
        if name in {"", ".", ".."} or "/" in name or "\\" in name:
            fail()
        try:
            child_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except OSError:
            fail()
        try:
            mode = os.fstat(child_fd).st_mode
            relative = f"{prefix}/{name}" if prefix else name
            if stat.S_ISDIR(mode):
                result.update(walk_inventory(child_fd, relative))
            elif stat.S_ISREG(mode):
                result[relative] = digest_fd(child_fd)
            else:
                fail()
        finally:
            os.close(child_fd)
    return result


def verify_files(rows: tuple[dict[str, object], ...]) -> tuple[int, int, str]:
    base = read_base_inventory()
    expected = {
        row["path"]: (row["bytes"], row["sha256"])
        for row in base
    }
    for row in rows:
        key = storage_key(row)
        if key in expected:
            fail()
        expected[key] = (row["byte_size"], row["sha256"])
    if len(expected) != EXPECTED_BASE_FILES + 23:
        fail()
    restore_fd = open_root(RESTORED_MEDIA)
    try:
        actual = walk_inventory(restore_fd)
    finally:
        os.close(restore_fd)
    if actual != expected:
            fail()
    inventory = [
        {"path": path, "bytes": expected[path][0], "sha256": expected[path][1]}
        for path in sorted(expected)
    ]
    byte_count = sum(row["bytes"] for row in inventory)
    if byte_count != EXPECTED_BASE_BYTES + EXPECTED_ADDED_BYTES:
        fail()
    return len(inventory), byte_count, hashlib.sha256(canonical(inventory)).hexdigest()


def database_projection(rows: tuple[dict[str, object], ...], *, apply: bool) -> None:
    from django.db import transaction

    from modules.media.models import (
        Asset,
        AssetFile,
        AssetPurpose,
        AssetState,
        AssetUsage,
        FileKind,
        MediaType,
        UsageScope,
    )
    from modules.pages.content import canonical_payload_hash, validate_payload
    from modules.pages.models import PageContent
    from rebuild3_importer.service_media import (
        INFOGRAPHIC_ASSET_ID,
        MAP019_PAGE_ID,
        bind_service_media,
    )

    page_ids = [uuid.UUID(str(row["page_id"])) for row in rows]
    asset_ids = [uuid.UUID(str(row["asset_id"])) for row in rows]
    file_ids = [uuid.UUID(str(row["file_id"])) for row in rows]
    projected_usage_ids = [usage_id(row) for row in rows]

    def usage_projection(page_id: uuid.UUID, scope: str) -> tuple[tuple[str, str, int], ...]:
        return tuple(sorted(
            (str(asset_id), str(slot), int(position))
            for asset_id, slot, position in AssetUsage.objects.filter(
                scope=scope, target_uuid=page_id
            ).values_list("asset_id", "slot", "position")
        ))

    def expected_projection(payload: dict[str, object], kind: str) -> tuple[tuple[str, str, int], ...]:
        references = validate_payload(payload, kind)
        return tuple(sorted(
            (str(asset_id), slot, position)
            for slot, values in references.items()
            for position, asset_id in enumerate(values)
        ))

    def untouched_digest(content: object) -> str:
        previous_usages = usage_projection(content.page_id, UsageScope.PAGE_PREVIOUS)
        value = {
            "page_id": str(content.page_id),
            "generation": int(content.generation),
            "current_author_id": value_text(content.current_author_id),
            "current_created_at": value_text(content.current_created_at),
            "previous_payload": content.previous_payload,
            "previous_hash": content.previous_hash,
            "previous_author_id": value_text(content.previous_author_id),
            "previous_created_at": value_text(content.previous_created_at),
            "previous_usages": previous_usages,
            "last_operation_id": value_text(content.last_operation_id),
            "last_operation_action": content.last_operation_action,
            "last_result_generation": content.last_result_generation,
            "last_result_hash": content.last_result_hash,
        }
        return hashlib.sha256(canonical(value)).hexdigest()

    set_stage("DB_CONTENT_LOAD")
    with transaction.atomic():
        contents = {
            str(content.page_id): content
            for content in PageContent.objects.select_for_update().select_related("page").filter(
                page_id__in=page_ids
            )
        }
        if len(contents) != 23:
            fail()

        if apply:
            set_stage("DB_IDENTITY_PRESTATE")
            if (
                Asset.objects.filter(id__in=asset_ids).exists()
                or AssetFile.objects.filter(id__in=file_ids).exists()
                or AssetUsage.objects.filter(id__in=projected_usage_ids).exists()
            ):
                fail()
            candidates: dict[str, tuple[object, dict[str, object], str, tuple[object, ...]]] = {}
            for row in rows:
                content = contents[str(row["page_id"])]
                set_stage("DB_CONTENT_PRESTATE")
                if (
                    canonical_payload_hash(content.current_payload) != content.current_hash
                    or any(value is not None for value in (
                        content.last_operation_id,
                        content.last_operation_action,
                        content.last_result_generation,
                        content.last_result_hash,
                    ))
                    or usage_projection(content.page_id, UsageScope.PAGE_CURRENT)
                    != expected_projection(content.current_payload, content.page.kind)
                ):
                    fail()
                if content.previous_payload is None:
                    if any(value is not None for value in (
                        content.previous_hash,
                        content.previous_author_id,
                        content.previous_created_at,
                    )) or usage_projection(content.page_id, UsageScope.PAGE_PREVIOUS):
                        fail()
                elif (
                    canonical_payload_hash(content.previous_payload) != content.previous_hash
                    or usage_projection(content.page_id, UsageScope.PAGE_PREVIOUS)
                    != expected_projection(content.previous_payload, content.page.kind)
                ):
                    fail()
                set_stage("DB_PAYLOAD_BIND")
                candidate = bind_service_media(content.current_payload, str(content.page_id))
                validate_payload(candidate, content.page.kind)
                candidates[str(content.page_id)] = (
                    content,
                    candidate,
                    canonical_payload_hash(candidate),
                    (
                        copy.deepcopy(content.previous_payload),
                        content.previous_hash,
                        content.previous_author_id,
                        content.previous_created_at,
                    ),
                )

            set_stage("DB_BASELINE_WRITE")
            write_baseline({
                "schema": "estakada.r7-owner-projection-baseline-v1",
                "pages": {
                    page_id: {
                        "kind": str(candidates[page_id][0].page.kind),
                        "untouched_sha256": untouched_digest(candidates[page_id][0]),
                        "projected_current_sha256": candidates[page_id][2],
                    }
                    for page_id in sorted(candidates)
                },
            })
            baseline = read_baseline()

            set_stage("DB_ASSET_CREATE")
            for row in rows:
                Asset.objects.create(
                    id=uuid.UUID(str(row["asset_id"])),
                    purpose=AssetPurpose.CONTENT,
                    source_sha256=str(row["sha256"]),
                    state=AssetState.READY,
                )
                AssetFile.objects.create(
                    id=uuid.UUID(str(row["file_id"])),
                    asset_id=uuid.UUID(str(row["asset_id"])),
                    kind=FileKind.MAIN,
                    storage_key=storage_key(row),
                    sha256=str(row["sha256"]),
                    byte_size=int(row["byte_size"]),
                    mime_type=MediaType.WEBP,
                    width=None,
                    height=None,
                )

            set_stage("DB_MAP019_RELOCATE")
            infographic_usage = AssetUsage.objects.select_for_update().filter(
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=uuid.UUID(MAP019_PAGE_ID),
                asset_id=uuid.UUID(INFOGRAPHIC_ASSET_ID),
                slot="hero",
                position=0,
            )
            if infographic_usage.count() != 1 or AssetUsage.objects.filter(
                scope=UsageScope.PAGE_CURRENT,
                target_uuid=uuid.UUID(MAP019_PAGE_ID),
                slot="body",
                position=0,
            ).exists():
                fail()
            infographic_usage.update(slot="body")

            set_stage("DB_USAGE_BIND")
            for row in rows:
                content, candidate, current_hash, _previous = candidates[str(row["page_id"])]
                AssetUsage.objects.create(
                    id=usage_id(row),
                    asset_id=uuid.UUID(str(row["asset_id"])),
                    scope=UsageScope.PAGE_CURRENT,
                    target_uuid=content.page_id,
                    slot="hero",
                    position=0,
                )
                content.current_payload = candidate
                content.current_hash = current_hash
                content.save(update_fields=("current_payload", "current_hash"))

            set_stage("DB_POSTSTATE_REFRESH")
            refreshed = {
                str(content.page_id): content
                for content in PageContent.objects.select_related("page").filter(page_id__in=page_ids)
            }
            for page_id, (_content, _candidate, _current_hash, previous) in candidates.items():
                content = refreshed[page_id]
                if (
                    content.previous_payload,
                    content.previous_hash,
                    content.previous_author_id,
                    content.previous_created_at,
                ) != previous:
                    fail()
            contents = refreshed
        else:
            set_stage("DB_BASELINE_READ")
            baseline = read_baseline()

        set_stage("DB_POSTSTATE_VERIFY")
        for page_id in sorted(contents):
            baseline_row = baseline["pages"].get(page_id)
            content = contents[page_id]
            if (
                type(baseline_row) is not dict
                or baseline_row["kind"] != content.page.kind
                or baseline_row["untouched_sha256"] != untouched_digest(content)
                or baseline_row["projected_current_sha256"] != content.current_hash
            ):
                fail()

        assets = {
            str(item.id): item
            for item in Asset.objects.filter(id__in=asset_ids)
        }
        files = {
            str(item.id): item
            for item in AssetFile.objects.filter(id__in=file_ids)
        }
        if len(assets) != 23 or len(files) != 23:
            fail()
        for row in rows:
            content = contents[str(row["page_id"])]
            try:
                media = content.current_payload["fields"]["media"]
            except (KeyError, TypeError):
                fail()
            if media["hero"] != row["asset_id"] or (
                str(content.page_id) == MAP019_PAGE_ID
                and media["body"] != [INFOGRAPHIC_ASSET_ID]
            ):
                fail()
            if (
                canonical_payload_hash(content.current_payload) != content.current_hash
                or usage_projection(content.page_id, UsageScope.PAGE_CURRENT)
                != expected_projection(content.current_payload, content.page.kind)
            ):
                fail()
            if content.previous_payload is None:
                if any(value is not None for value in (
                    content.previous_hash,
                    content.previous_author_id,
                    content.previous_created_at,
                )):
                    fail()
            elif (
                canonical_payload_hash(content.previous_payload) != content.previous_hash
                or usage_projection(content.page_id, UsageScope.PAGE_PREVIOUS)
                != expected_projection(content.previous_payload, content.page.kind)
            ):
                fail()
            asset = assets[str(row["asset_id"])]
            file = files[str(row["file_id"])]
            if (
                asset.purpose != AssetPurpose.CONTENT
                or asset.source_sha256 != row["sha256"]
                or asset.state != AssetState.READY
                or str(file.asset_id) != row["asset_id"]
                or file.kind != FileKind.MAIN
                or file.storage_key != storage_key(row)
                or file.sha256 != row["sha256"]
                or file.byte_size != row["byte_size"]
                or file.mime_type != MediaType.WEBP
                or file.width is not None
                or file.height is not None
            ):
                fail()
        if AssetUsage.objects.filter(id__in=projected_usage_ids).count() != 23:
            fail()
        for row in rows:
            projected = AssetUsage.objects.filter(id=usage_id(row)).values_list(
                "asset_id", "scope", "target_uuid", "slot", "position"
            )
            if list(projected) != [(
                uuid.UUID(str(row["asset_id"])),
                UsageScope.PAGE_CURRENT,
                uuid.UUID(str(row["page_id"])),
                "hero",
                0,
            )]:
                fail()


def database_rollback_probe(rows: tuple[dict[str, object], ...]) -> None:
    from django.db import transaction

    from modules.media.models import Asset, AssetFile, AssetUsage
    from modules.pages.models import PageContent

    page_ids = [uuid.UUID(str(row["page_id"])) for row in rows]
    asset_ids = [uuid.UUID(str(row["asset_id"])) for row in rows]
    file_ids = [uuid.UUID(str(row["file_id"])) for row in rows]
    usage_ids = [usage_id(row) for row in rows]

    def normalize(value: object) -> object:
        if isinstance(value, dict):
            return {str(key): normalize(item) for key, item in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        if value is None or type(value) in {str, int, bool}:
            return value
        return str(value)

    def snapshot() -> str:
        value = {
            "content": list(PageContent.objects.filter(page_id__in=page_ids).order_by("page_id").values()),
            "assets": list(Asset.objects.filter(id__in=asset_ids).order_by("id").values()),
            "files": list(AssetFile.objects.filter(id__in=file_ids).order_by("id").values()),
            "usages": list(AssetUsage.objects.filter(target_uuid__in=page_ids).order_by("id").values()),
            "projected_usages": list(AssetUsage.objects.filter(id__in=usage_ids).order_by("id").values()),
        }
        return hashlib.sha256(canonical(normalize(value))).hexdigest()

    set_stage("PROBE_SNAPSHOT_BEFORE")
    before = snapshot()

    class RollbackProbe(Exception):
        pass

    try:
        with transaction.atomic():
            set_stage("PROBE_APPLY")
            database_projection(rows, apply=True)
            raise RollbackProbe
    except RollbackProbe:
        pass
    set_stage("PROBE_ROLLBACK_COMPARE")
    if snapshot() != before:
        fail()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"apply", "verify", "probe"}:
        fail()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_restore")
    import django

    django.setup()
    from rebuild3_importer.service_media import service_media_rows

    set_stage("SERVICE_AUTHORITY")
    rows = service_media_rows()
    if sys.argv[1] == "probe":
        database_rollback_probe(rows)
        print("R7_OWNER_PROJECTION_PROBE_OK cases=transaction-map019-history-rollback")
    elif sys.argv[1] == "apply":
        copy_files(rows)
        database_projection(rows, apply=True)
        files, byte_count, digest = verify_files(rows)
        print(
            "R7_OWNER_PROJECTION_APPLY_OK assets=23 files=23 usages=23 "
            f"media_files={files} media_bytes={byte_count} media_sha256={digest}"
        )
    else:
        database_projection(rows, apply=False)
        files, byte_count, digest = verify_files(rows)
        print(
            "R7_OWNER_PROJECTION_VERIFY_OK assets=23 files=23 usages=23 "
            f"media_files={files} media_bytes={byte_count} media_sha256={digest}"
        )


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        raise RuntimeError(normalized_failure(exc)) from None
