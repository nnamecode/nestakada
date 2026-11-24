from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Linux runtime is mandatory for mutations.
    fcntl = None


ROOT = Path("/selector")
PROJECT = Path("/project")
AUTHORITY = Path("/authority")
HEX32 = re.compile(r"[0-9a-f]{32}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
CONTAINER_ID = re.compile(r"[0-9a-f]{64}\Z")
SCOPE = re.compile(r"(?:local|rehearsal:[0-9a-f]{32})\Z")
ROLE_ALIAS = {"old": "r7c-old-app", "new": "r7c-new-app"}
ROLE_MEDIA_ROOT = {"old": "/srv/media-old", "new": "/srv/media-new"}
ROLE_STATIC_ROOT = {
    "old": "/srv/source-old/modules/pages/static",
    "new": "/srv/source-new/modules/pages/static",
}
BITMAP_KEYS = ("admin", "cleanup", "editor", "request", "scheduler", "upload")
JOURNAL_KEYS = {
    "schema",
    "scope",
    "runId",
    "phase",
    "ingressId",
    "oldTargetId",
    "newTargetId",
    "oldStorageBindingSha256",
    "newStorageBindingSha256",
    "expectedSelector",
    "candidateSelectorSha256",
    "implementationImageBindingSha256",
    "mutationBitmap",
}
JOURNAL_NEXT = {
    "PREPARED": {"INGRESS_STOPPED"},
    "INGRESS_STOPPED": {"SELECTOR_COMMITTED"},
    "SELECTOR_COMMITTED": {"INGRESS_STARTED"},
    "INGRESS_STARTED": {"OBSERVED_OLD", "OBSERVED_NEW"},
    "OBSERVED_OLD": {"CONFIRMED", "ROLLED_BACK"},
    "OBSERVED_NEW": {"CONFIRMED", "ROLLED_BACK"},
    "CONFIRMED": set(),
    "ROLLED_BACK": set(),
    "UNKNOWN": set(),
}
IMPLEMENTATION_FILES = (
    "environment/foundation/requirements.lock",
    "environment/foundation/runtime-images.lock.json",
    "environment/rebuild7-cutover/compose.yaml",
    "environment/rebuild7-cutover/http.conf",
    "environment/rebuild7-cutover/nginx.conf",
    "environment/rebuild7-cutover/nginx-validate.conf",
    "scripts/rebuild7-selector.ps1",
    "scripts/setup-rebuild7-selector-synthetic.ps1",
    "scripts/test-rebuild7-selector.ps1",
    "src/config/local_cutover_identity.py",
    "src/config/settings/local_cutover.py",
    "src/config/urls_local_cutover.py",
    "tools/rebuild7_generation.py",
    "tools/rebuild7_media.py",
    "tools/rebuild7_selector.py",
    "tools/rebuild7_selector_fixture.py",
    "tools/rebuild7_selector_probe.py",
)


def fail(code: str = "R7C_SELECTOR_UNAVAILABLE") -> None:
    raise RuntimeError(code)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require_sha(value: object) -> str:
    if type(value) is not str or HEX64.fullmatch(value) is None:
        fail()
    return value


def require_scope(value: object) -> str:
    if type(value) is not str or SCOPE.fullmatch(value) is None:
        fail()
    return value


def require_run_id(value: object) -> str:
    if type(value) is not str or HEX32.fullmatch(value) is None:
        fail()
    return value


def require_container_id(value: object) -> str:
    if type(value) is not str or CONTAINER_ID.fullmatch(value) is None:
        fail()
    return value


def selector_owner_uid() -> int:
    value = os.environ.get("ESTAKADA_R7C_SELECTOR_OWNER_UID")
    if value is None:
        return os.geteuid()
    if value != "0":
        fail("R7C_SELECTOR_OWNER_INVALID")
    return 0


def validate_bitmap(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != set(BITMAP_KEYS):
        fail()
    if any(value[key] != "CLOSED" for key in BITMAP_KEYS):
        fail()
    return {key: "CLOSED" for key in BITMAP_KEYS}


def render_selector(scope: str, role: str, generation: str) -> bytes:
    scope = require_scope(scope)
    generation = require_sha(generation)
    if role not in ROLE_ALIAS:
        fail()
    alias = ROLE_ALIAS[role]
    media_root = ROLE_MEDIA_ROOT[role]
    static_root = ROLE_STATIC_ROOT[role]
    return (
        "# estakada.r7c-selector-v1\n"
        f"# scope={scope}\n"
        f"# role={role}\n"
        f"# generation={generation}\n"
        "map $host $r7c_media_root {\n"
        f"    default {media_root};\n"
        "}\n"
        "map $host $r7c_static_root {\n"
        f"    default {static_root};\n"
        "}\n"
        "upstream r7c_active {\n"
        f"    server {alias}:8000;\n"
        "}\n"
    ).encode("ascii")


def parse_selector(value: bytes) -> dict[str, str]:
    if type(value) is not bytes or len(value) > 4096:
        fail()
    try:
        text = value.decode("ascii")
    except UnicodeDecodeError:
        fail()
    match = re.fullmatch(
        r"# estakada\.r7c-selector-v1\n"
        r"# scope=(local|rehearsal:[0-9a-f]{32})\n"
        r"# role=(old|new)\n"
        r"# generation=([0-9a-f]{64})\n"
        r"map \$host \$r7c_media_root \{\n"
        r"    default (/srv/media-old|/srv/media-new);\n"
        r"\}\n"
        r"map \$host \$r7c_static_root \{\n"
        r"    default (/srv/source-old/modules/pages/static|/srv/source-new/modules/pages/static);\n"
        r"\}\n"
        r"upstream r7c_active \{\n"
        r"    server (r7c-old-app|r7c-new-app):8000;\n"
        r"\}\n",
        text,
    )
    if match is None:
        fail()
    scope, role, generation, media_root, static_root, alias = match.groups()
    if (
        ROLE_ALIAS[role] != alias
        or ROLE_MEDIA_ROOT[role] != media_root
        or ROLE_STATIC_ROOT[role] != static_root
        or render_selector(scope, role, generation) != value
    ):
        fail()
    return {
        "schema": "estakada.r7c-selector-v1",
        "scope": scope,
        "role": role,
        "generation": generation,
        "alias": alias,
        "mediaRoot": media_root,
        "staticRoot": static_root,
        "sha256": sha256(value),
    }


def selector_render_args(parsed: dict[str, str]) -> dict[str, str]:
    return {
        "scope": parsed["scope"],
        "role": parsed["role"],
        "generation": parsed["generation"],
    }


def _root_fd(root: Path) -> int:
    if not root.is_dir() or root.is_symlink():
        fail()
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(root, flags)


def _lock_root(root_fd: int) -> None:
    if fcntl is None:
        fail("R7C_LINUX_LOCK_UNAVAILABLE")
    try:
        fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fail("R7C_SELECTOR_LOCK_FAILED")


def _open_dir(parent_fd: int, name: str, create: bool) -> int:
    if name not in {"selectors", "staging"}:
        fail()
    if create:
        try:
            os.mkdir(name, 0o755, dir_fd=parent_fd)
        except FileExistsError:
            pass
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        fail()
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode) or info.st_nlink < 1:
        os.close(descriptor)
        fail()
    return descriptor


def _read_file(
    directory_fd: int, name: str, cap: int, expected_mode: int | None = None
) -> bytes:
    if "/" in name or "\\" in name or name in {"", ".", ".."}:
        fail()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, dir_fd=directory_fd)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > cap
            or info.st_uid != selector_owner_uid()
            or (expected_mode is not None and stat.S_IMODE(info.st_mode) != expected_mode)
        ):
            fail()
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(descriptor, min(65536, cap + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > cap:
                fail()
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _fault(stage: str) -> None:
    requested = os.environ.get("ESTAKADA_R7C_TEST_FAULT")
    testing = os.environ.get("ESTAKADA_R7C_TESTING")
    if requested is not None and testing != "1":
        fail("R7C_TEST_FAULT_MARKER_FORBIDDEN")
    if requested == stage:
        fail("R7C_INJECTED_FAULT")


def _atomic_write(
    directory_fd: int, name: str, value: bytes, cap: int, mode: int = 0o600
) -> None:
    if not value or len(value) > cap:
        fail()
    temporary = ".tmp-" + uuid.uuid4().hex
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(temporary, flags, mode, dir_fd=directory_fd)
    try:
        offset = 0
        while offset < len(value):
            offset += os.write(descriptor, value[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fault("after-file-fsync")
    if _read_file(directory_fd, temporary, cap, mode) != value:
        fail()
    _fault("before-replace")
    os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
    _fault("after-replace")
    os.fsync(directory_fd)
    _fault("after-parent-fsync")
    if _read_file(directory_fd, name, cap, mode) != value:
        fail()


def _inventory(root: Path) -> bool:
    allowed_root = {"selectors", "staging", "journal.json", "receipt.json"}
    try:
        root_entries = list(root.iterdir())
    except OSError:
        return False
    root_info = root.stat()
    owner_uid = selector_owner_uid()
    if root_info.st_uid != owner_uid or stat.S_IMODE(root_info.st_mode) & 0o022:
        return False
    if any(entry.name not in allowed_root or entry.is_symlink() for entry in root_entries):
        return False
    selectors = root / "selectors"
    staging = root / "staging"
    if selectors.exists():
        selector_info = selectors.stat()
        if not selectors.is_dir() or selectors.is_symlink() or selector_info.st_uid != owner_uid or stat.S_IMODE(selector_info.st_mode) != 0o755:
            return False
        if any(entry.name != "active.conf" or entry.is_symlink() for entry in selectors.iterdir()):
            return False
    if staging.exists():
        staging_info = staging.stat()
        if not staging.is_dir() or staging.is_symlink() or staging_info.st_uid != owner_uid or stat.S_IMODE(staging_info.st_mode) != 0o755:
            return False
        entries = list(staging.iterdir())
        if len(entries) > 2 or any(
            re.fullmatch(r"[0-9a-f]{32}\.conf", entry.name) is None
            or entry.is_symlink()
            for entry in entries
        ):
            return False
    for name in ("journal.json", "receipt.json"):
        path = root / name
        if path.exists():
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != 0o600:
                return False
    for directory in (selectors, staging):
        if directory.exists():
            for entry in directory.iterdir():
                info = entry.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != 0o644:
                    return False
    return True


def _ensure_layout(root: Path) -> None:
    root_fd = _root_fd(root)
    try:
        for name in ("selectors", "staging"):
            descriptor = _open_dir(root_fd, name, True)
            os.close(descriptor)
    finally:
        os.close(root_fd)
    if not _inventory(root):
        fail()


def inspect_selector(root: Path = ROOT) -> dict[str, object]:
    if not root.is_dir() or root.is_symlink() or not _inventory(root):
        return {"schema": "estakada.r7c-selector-state-v1", "state": "UNKNOWN"}
    path = root / "selectors" / "active.conf"
    if not path.exists():
        return {"schema": "estakada.r7c-selector-state-v1", "state": "ABSENT"}
    try:
        root_fd = _root_fd(root)
        directory_fd = _open_dir(root_fd, "selectors", False)
        try:
            parsed = parse_selector(_read_file(directory_fd, "active.conf", 4096, 0o644))
        finally:
            os.close(directory_fd)
            os.close(root_fd)
    except (OSError, RuntimeError):
        return {"schema": "estakada.r7c-selector-state-v1", "state": "UNKNOWN"}
    return {
        "schema": "estakada.r7c-selector-state-v1",
        "state": "PRESENT",
        "selector": parsed,
    }


def inspect_state(root: Path = ROOT) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": "estakada.r7c-state-v1",
        "selector": inspect_selector(root),
        "journal": None,
        "receipt": None,
    }
    for name, validator, key in (
        ("journal.json", validate_journal, "journal"),
        ("receipt.json", validate_receipt, "receipt"),
    ):
        path = root / name
        if not path.exists():
            continue
        try:
            value, digest = _read_root_json(root, name, 16384)
            validated = validator(value)
        except (OSError, RuntimeError):
            result[key] = {"state": "UNKNOWN"}
        else:
            entry = {
                "state": "PRESENT",
                "sha256": digest,
                "phase" if key == "journal" else "result": validated[
                    "phase" if key == "journal" else "result"
                ],
                "runId": validated["runId"],
                "scope": validated["scope"],
            }
            if key == "journal":
                entry["ingressId"] = validated["ingressId"]
                entry["value"] = validated
            result[key] = entry
    return result


def render_candidate(
    root: Path, run_id: str, scope: str, role: str, generation: str
) -> Path:
    run_id = require_run_id(run_id)
    _ensure_layout(root)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    candidate = root / "staging" / f"{run_id}.conf"
    staging_fd = _open_dir(root_fd, "staging", False)
    try:
        try:
            os.stat(f"{run_id}.conf", dir_fd=staging_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            fail()
        _atomic_write(
            staging_fd,
            f"{run_id}.conf",
            render_selector(scope, role, generation),
            4096,
            0o644,
        )
    finally:
        os.close(staging_fd)
        os.close(root_fd)
    return candidate


def selector_cas(root: Path, expected: str, candidate: Path) -> dict[str, object]:
    _ensure_layout(root)
    if candidate.parent != root / "staging" or re.fullmatch(
        r"[0-9a-f]{32}\.conf", candidate.name
    ) is None:
        fail()
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    staging_fd = _open_dir(root_fd, "staging", False)
    try:
        candidate_bytes = _read_file(staging_fd, candidate.name, 4096, 0o644)
        parsed = parse_selector(candidate_bytes)
        current = inspect_selector(root)
        actual = (
            "ABSENT"
            if current["state"] == "ABSENT"
            else current.get("selector", {}).get("sha256")
            if current["state"] == "PRESENT"
            else "UNKNOWN"
        )
        if expected != actual or (expected != "ABSENT" and HEX64.fullmatch(expected) is None):
            fail("R7C_SELECTOR_STALE")
        selectors_fd = _open_dir(root_fd, "selectors", False)
        _atomic_write(selectors_fd, "active.conf", candidate_bytes, 4096, 0o644)
    finally:
        if 'selectors_fd' in locals():
            os.close(selectors_fd)
        os.close(staging_fd)
        os.close(root_fd)
    result = inspect_selector(root)
    if result.get("state") != "PRESENT" or result.get("selector") != parsed:
        fail()
    return result


def selector_unlink(root: Path, expected: str) -> dict[str, object]:
    require_sha(expected)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    selectors_fd = _open_dir(root_fd, "selectors", False)
    try:
        current = inspect_selector(root)
        if (
            current.get("state") != "PRESENT"
            or current.get("selector", {}).get("sha256") != expected
        ):
            fail("R7C_SELECTOR_STALE")
        info = os.stat("active.conf", dir_fd=selectors_fd, follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail()
        os.unlink("active.conf", dir_fd=selectors_fd)
        os.fsync(selectors_fd)
    finally:
        os.close(selectors_fd)
        os.close(root_fd)
    result = inspect_selector(root)
    if result.get("state") != "ABSENT":
        fail()
    return result


def validate_journal(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != JOURNAL_KEYS:
        fail()
    if value["schema"] != "estakada.r7c-journal-v1":
        fail()
    result = dict(value)
    result["scope"] = require_scope(value["scope"])
    result["runId"] = require_run_id(value["runId"])
    if value["phase"] not in JOURNAL_NEXT:
        fail()
    for key in ("ingressId", "oldTargetId", "newTargetId"):
        result[key] = require_container_id(value[key])
    if len({result["ingressId"], result["oldTargetId"], result["newTargetId"]}) != 3:
        fail()
    for key in (
        "oldStorageBindingSha256",
        "newStorageBindingSha256",
        "candidateSelectorSha256",
        "implementationImageBindingSha256",
    ):
        result[key] = require_sha(value[key])
    expected = value["expectedSelector"]
    if expected != "ABSENT":
        require_sha(expected)
    result["mutationBitmap"] = validate_bitmap(value["mutationBitmap"])
    return result


def transition_journal(value: dict[str, Any], phase: str) -> dict[str, Any]:
    current = validate_journal(value)
    if phase == "UNKNOWN":
        if current["phase"] in {"CONFIRMED", "ROLLED_BACK", "UNKNOWN"}:
            fail()
    elif phase not in JOURNAL_NEXT[current["phase"]]:
        fail()
    result = dict(current)
    result["phase"] = phase
    return validate_journal(result)


def _read_root_json(root: Path, name: str, cap: int) -> tuple[dict[str, Any], str]:
    root_fd = _root_fd(root)
    try:
        raw = _read_file(root_fd, name, cap, 0o600)
    finally:
        os.close(root_fd)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail()
    if type(value) is not dict or canonical(value) != raw:
        fail()
    return value, sha256(raw)


def create_journal(root: Path, payload: object) -> dict[str, Any]:
    _ensure_layout(root)
    value = validate_journal(payload)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    try:
        if value["phase"] != "PREPARED" or (root / "journal.json").exists():
            fail()
        _atomic_write(root_fd, "journal.json", canonical(value), 16384)
    finally:
        os.close(root_fd)
    stored, digest = _read_root_json(root, "journal.json", 16384)
    result = validate_journal(stored)
    result["sha256"] = digest
    return result


def update_journal(root: Path, expected_digest: str, phase: str) -> dict[str, Any]:
    require_sha(expected_digest)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    try:
        stored, digest = _read_root_json(root, "journal.json", 16384)
        if digest != expected_digest:
            fail("R7C_JOURNAL_STALE")
        updated = transition_journal(validate_journal(stored), phase)
        _atomic_write(root_fd, "journal.json", canonical(updated), 16384)
    finally:
        os.close(root_fd)
    stored, digest = _read_root_json(root, "journal.json", 16384)
    result = validate_journal(stored)
    result["sha256"] = digest
    return result


def recover_precommit_journal(
    root: Path, expected_digest: str, selector_digest: str, phase: str
) -> dict[str, Any]:
    require_sha(expected_digest)
    require_sha(selector_digest)
    if phase not in {"OBSERVED_OLD", "OBSERVED_NEW"}:
        fail("R7C_RECOVERY_TRANSITION_INVALID")
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    try:
        stored, digest = _read_root_json(root, "journal.json", 16384)
        journal = validate_journal(stored)
        selector = inspect_selector(root)
        expected_role = "old" if phase == "OBSERVED_OLD" else "new"
        if (
            digest != expected_digest
            or journal["phase"] not in {"PREPARED", "INGRESS_STOPPED"}
            or journal["expectedSelector"] == "ABSENT"
            or journal["expectedSelector"] != selector_digest
            or selector.get("state") != "PRESENT"
            or selector.get("selector", {}).get("sha256") != selector_digest
            or selector.get("selector", {}).get("role") != expected_role
        ):
            fail("R7C_RECOVERY_TRANSITION_INVALID")
        updated = dict(journal)
        updated["phase"] = phase
        _atomic_write(root_fd, "journal.json", canonical(updated), 16384)
    finally:
        os.close(root_fd)
    stored, digest = _read_root_json(root, "journal.json", 16384)
    result = validate_journal(stored)
    result["sha256"] = digest
    return result


RECEIPT_KEYS = {
    "schema",
    "scope",
    "runId",
    "result",
    "journalSha256",
    "selectorSha256",
    "implementationImageBindingSha256",
    "ingressId",
    "oldTargetId",
    "newTargetId",
    "expectedSelector",
    "observedRole",
    "observedGenerationSha256",
    "storageBindingSha256",
    "mutationBitmap",
    "cleanup",
}


def validate_receipt(value: object) -> dict[str, Any]:
    if type(value) is not dict or set(value) != RECEIPT_KEYS:
        fail()
    result = dict(value)
    if value["schema"] != "estakada.r7c-receipt-v1":
        fail()
    result["scope"] = require_scope(value["scope"])
    result["runId"] = require_run_id(value["runId"])
    if value["result"] not in {"CONFIRMED", "ROLLED_BACK"}:
        fail()
    for key in (
        "journalSha256",
        "selectorSha256",
        "implementationImageBindingSha256",
        "observedGenerationSha256",
        "storageBindingSha256",
    ):
        result[key] = require_sha(value[key])
    for key in ("ingressId", "oldTargetId", "newTargetId"):
        result[key] = require_container_id(value[key])
    if len({result["ingressId"], result["oldTargetId"], result["newTargetId"]}) != 3:
        fail()
    if value["expectedSelector"] != "ABSENT":
        result["expectedSelector"] = require_sha(value["expectedSelector"])
    if value["observedRole"] not in ROLE_ALIAS or value["cleanup"] != "EXACT":
        fail()
    result["mutationBitmap"] = validate_bitmap(value["mutationBitmap"])
    return result


def finalize_receipt(root: Path, payload: object) -> dict[str, Any]:
    _ensure_layout(root)
    receipt = validate_receipt(payload)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    try:
        if (root / "receipt.json").exists():
            fail()
        journal, journal_digest = _read_root_json(root, "journal.json", 16384)
        journal = validate_journal(journal)
        selector = inspect_selector(root)
        if (
            journal_digest != receipt["journalSha256"]
            or journal["phase"] != receipt["result"]
            or journal["scope"] != receipt["scope"]
            or journal["runId"] != receipt["runId"]
            or journal["implementationImageBindingSha256"]
            != receipt["implementationImageBindingSha256"]
            or journal["ingressId"] != receipt["ingressId"]
            or journal["oldTargetId"] != receipt["oldTargetId"]
            or journal["newTargetId"] != receipt["newTargetId"]
            or journal["expectedSelector"] != receipt["expectedSelector"]
            or selector.get("state") != "PRESENT"
            or selector.get("selector", {}).get("sha256")
            != receipt["selectorSha256"]
            or selector.get("selector", {}).get("role") != receipt["observedRole"]
            or selector.get("selector", {}).get("generation")
            != receipt["observedGenerationSha256"]
            or receipt["storageBindingSha256"]
            != journal[
                "oldStorageBindingSha256"
                if receipt["observedRole"] == "old"
                else "newStorageBindingSha256"
            ]
            or (
                receipt["result"] == "CONFIRMED"
                and receipt["selectorSha256"] != journal["candidateSelectorSha256"]
            )
            or (
                receipt["result"] == "ROLLED_BACK"
                and (
                    journal["expectedSelector"] == "ABSENT"
                    or receipt["selectorSha256"] != journal["expectedSelector"]
                )
            )
        ):
            fail("R7C_RECEIPT_AUTHORITY_MISMATCH")
        _atomic_write(root_fd, "receipt.json", canonical(receipt), 16384)
    finally:
        os.close(root_fd)
    stored, digest = _read_root_json(root, "receipt.json", 16384)
    result = validate_receipt(stored)
    result["sha256"] = digest
    return result


def close_operation(
    root: Path,
    expected_receipt_digest: str,
    expected_journal_digest: str,
    external_receipt: object,
) -> dict[str, str]:
    require_sha(expected_receipt_digest)
    require_sha(expected_journal_digest)
    if type(external_receipt) is not dict or set(external_receipt) != RECEIPT_KEYS | {
        "sha256"
    }:
        fail("R7C_OPERATION_CLOSE_AUTHORITY_MISMATCH")
    external_digest = external_receipt["sha256"]
    external_value = validate_receipt(
        {key: value for key, value in external_receipt.items() if key != "sha256"}
    )
    if (
        external_digest != expected_receipt_digest
        or sha256(canonical(external_value)) != expected_receipt_digest
    ):
        fail("R7C_OPERATION_CLOSE_AUTHORITY_MISMATCH")
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    try:
        journal_raw, journal_digest = _read_root_json(root, "journal.json", 16384)
        journal = validate_journal(journal_raw)
        if journal_digest != expected_journal_digest or journal["phase"] not in {
            "CONFIRMED",
            "ROLLED_BACK",
        }:
            fail("R7C_OPERATION_CLOSE_AUTHORITY_MISMATCH")
        if (
            external_value["journalSha256"] != journal_digest
            or external_value["runId"] != journal["runId"]
            or external_value["scope"] != journal["scope"]
            or external_value["result"] != journal["phase"]
        ):
            fail("R7C_OPERATION_CLOSE_AUTHORITY_MISMATCH")
        receipt_path = root / "receipt.json"
        if receipt_path.exists():
            receipt_raw, receipt_digest = _read_root_json(root, "receipt.json", 16384)
            receipt = validate_receipt(receipt_raw)
            if (
                receipt_digest != expected_receipt_digest
                or receipt["journalSha256"] != journal_digest
                or receipt["runId"] != journal["runId"]
                or receipt["scope"] != journal["scope"]
                or receipt["result"] != journal["phase"]
            ):
                fail("R7C_OPERATION_CLOSE_AUTHORITY_MISMATCH")
        if receipt_path.exists():
            os.unlink("receipt.json", dir_fd=root_fd)
            os.fsync(root_fd)
        os.unlink("journal.json", dir_fd=root_fd)
        os.fsync(root_fd)
    except OSError:
        fail("R7C_OPERATION_CLOSE_FAILED")
    finally:
        os.close(root_fd)
    return {"schema": "estakada.r7c-operation-close-v1", "state": "ABSENT"}


def verify_external_receipt(value: object) -> dict[str, str]:
    if type(value) is not dict or set(value) != RECEIPT_KEYS | {"sha256"}:
        fail("R7C_EXTERNAL_RECEIPT_INVALID")
    digest = require_sha(value["sha256"])
    receipt = validate_receipt({key: item for key, item in value.items() if key != "sha256"})
    if sha256(canonical(receipt)) != digest:
        fail("R7C_EXTERNAL_RECEIPT_INVALID")
    return {"schema": "estakada.r7c-external-receipt-check-v1", "sha256": digest}


def rollback_run_id(run_id: str) -> str:
    run_id = require_run_id(run_id)
    return sha256(("rollback:" + run_id).encode("ascii"))[:32]


def cleanup_staging(root: Path, run_id: str) -> None:
    run_id = require_run_id(run_id)
    root_fd = _root_fd(root)
    _lock_root(root_fd)
    staging_fd = _open_dir(root_fd, "staging", False)
    try:
        journal, _digest = _read_root_json(root, "journal.json", 16384)
        journal = validate_journal(journal)
        if (
            run_id not in {journal["runId"], rollback_run_id(journal["runId"])}
            or journal["phase"] not in {"CONFIRMED", "ROLLED_BACK"}
        ):
            fail()
        name = f"{run_id}.conf"
        try:
            info = os.stat(name, dir_fd=staging_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            fail()
        os.unlink(name, dir_fd=staging_fd)
        os.fsync(staging_fd)
    finally:
        os.close(staging_fd)
        os.close(root_fd)


def _closed_mapping(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        fail()
    return dict(value)


def storage_binding(value: object) -> dict[str, object]:
    top = _closed_mapping(value, {"capture", "mediaCheck"})
    capture = _closed_mapping(
        top["capture"],
        {
            "schema",
            "sourceSha256",
            "releaseSha256",
            "schemaFingerprintSha256",
            "appliedMigrationsSha256",
            "tableCountsSha256",
            "tableContentSha256",
            "mediaInventorySha256",
            "mediaFiles",
            "mediaBytes",
        },
    )
    media = _closed_mapping(
        top["mediaCheck"],
        {
            "schema",
            "verifierContainerId",
            "verifierImageId",
            "mediaMountToken",
            "authorityFileSha256",
            "authorityCanonicalSha256",
            "inventorySha256",
            "files",
            "bytes",
            "result",
        },
    )
    if capture["schema"] != "estakada.r7-binding-capture-v1" or media["schema"] != "estakada.r7-media-check-v1":
        fail()
    for key in (
        "sourceSha256",
        "releaseSha256",
        "schemaFingerprintSha256",
        "appliedMigrationsSha256",
        "tableCountsSha256",
        "tableContentSha256",
        "mediaInventorySha256",
    ):
        require_sha(capture[key])
    require_container_id(media["verifierContainerId"])
    if type(media["verifierImageId"]) is not str or IMAGE_ID.fullmatch(media["verifierImageId"]) is None:
        fail()
    for key in (
        "mediaMountToken",
        "authorityFileSha256",
        "authorityCanonicalSha256",
        "inventorySha256",
    ):
        require_sha(media[key])
    for key in ("mediaFiles", "mediaBytes"):
        if type(capture[key]) is not int or capture[key] < 0:
            fail()
    for key in ("files", "bytes"):
        if type(media[key]) is not int or media[key] < 0:
            fail()
    if (
        media["result"] != "PASS"
        or capture["mediaInventorySha256"] != media["inventorySha256"]
        or capture["mediaFiles"] != media["files"]
        or capture["mediaBytes"] != media["bytes"]
    ):
        fail("R7C_STORAGE_BINDING_MISMATCH")
    stable_media = {
        key: item for key, item in media.items() if key != "verifierContainerId"
    }
    authority = {"capture": capture, "mediaCheck": stable_media}
    return {
        "schema": "estakada.r7-storage-binding-v1",
        "storageBindingSha256": sha256(canonical(authority)),
        "mediaFiles": capture["mediaFiles"],
        "mediaBytes": capture["mediaBytes"],
    }


def media_authority(root: Path = AUTHORITY) -> dict[str, object]:
    path = root / "media-inventory.json"
    if not path.is_file() or path.is_symlink() or path.parent != root:
        fail()
    raw = path.read_bytes()
    if not raw or len(raw) > 16 * 1024 * 1024:
        fail()
    try:
        rows = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail()
    if type(rows) is not list:
        fail()
    previous = ""
    total = 0
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            fail()
        relative = row["path"]
        pure = PurePosixPath(relative) if type(relative) is str else None
        if (
            pure is None
            or pure.is_absolute()
            or ".." in pure.parts
            or "\\" in relative
            or relative <= previous
            or not valid_media_key(relative)
            or type(row["sha256"]) is not str
            or HEX64.fullmatch(row["sha256"]) is None
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
        ):
            fail()
        previous = relative
        total += row["bytes"]
    canonical_rows = canonical(rows)
    return {
        "schema": "estakada.r7-media-authority-v1",
        "authorityFileSha256": sha256(raw),
        "authorityCanonicalSha256": sha256(canonical_rows),
        "inventorySha256": sha256(canonical_rows),
        "files": len(rows),
        "bytes": total,
    }


def valid_media_key(value: str) -> bool:
    uuid = r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    return re.fullmatch(
        rf"(?:img/{uuid}/(?:main|preview|legacy-public)\.(?:jpg|jpeg|png|webp|svg)|"
        rf"private/sources/{uuid}/source\.(?:jpg|jpeg|png|webp))",
        value,
    ) is not None


def implementation_inventory(project: Path = PROJECT) -> dict[str, object]:
    rows = []
    for relative in IMPLEMENTATION_FILES:
        pure = PurePosixPath(relative)
        path = project.joinpath(*pure.parts)
        if not path.is_file() or path.is_symlink() or project.resolve() not in path.resolve().parents:
            fail("R7C_IMPLEMENTATION_INVENTORY_UNAVAILABLE")
        value = path.read_bytes()
        rows.append({"path": relative, "bytes": len(value), "sha256": sha256(value)})
    result = {
        "schema": "estakada.r7c-implementation-inventory-v1",
        "files": rows,
    }
    return {**result, "sha256": sha256(canonical(result))}


def _read_stdin_json() -> object:
    try:
        raw = sys.stdin.buffer.read(16385)
        if not raw or len(raw) > 16384:
            fail()
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail()
    return value


def emit(value: object) -> None:
    print(canonical(value).decode("utf-8"), end="")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    render = subparsers.add_parser("render-candidate")
    render.add_argument("--run", required=True)
    render.add_argument("--scope", required=True)
    render.add_argument("--role", required=True)
    render.add_argument("--generation", required=True)
    subparsers.add_parser("inspect")
    cas = subparsers.add_parser("selector-cas")
    cas.add_argument("--expected", required=True)
    cas.add_argument("--run", required=True)
    unlink = subparsers.add_parser("selector-unlink")
    unlink.add_argument("--expected", required=True)
    subparsers.add_parser("journal-create")
    transition = subparsers.add_parser("journal-transition")
    transition.add_argument("--expected", required=True)
    transition.add_argument("--phase", required=True)
    recover_transition = subparsers.add_parser("journal-recovery-transition")
    recover_transition.add_argument("--expected", required=True)
    recover_transition.add_argument("--selector", required=True)
    recover_transition.add_argument("--phase", required=True)
    subparsers.add_parser("storage-binding")
    subparsers.add_parser("implementation-inventory")
    subparsers.add_parser("media-authority")
    subparsers.add_parser("receipt-finalize")
    subparsers.add_parser("receipt-verify-external")
    close = subparsers.add_parser("operation-close")
    close.add_argument("--expected-receipt", required=True)
    close.add_argument("--expected-journal", required=True)
    cleanup = subparsers.add_parser("cleanup-staging")
    cleanup.add_argument("--run", required=True)
    args = parser.parse_args()

    if args.mode == "render-candidate":
        path = render_candidate(ROOT, args.run, args.scope, args.role, args.generation)
        emit({"schema": "estakada.r7c-candidate-v1", "sha256": sha256(path.read_bytes())})
    elif args.mode == "inspect":
        emit(inspect_state(ROOT))
    elif args.mode == "selector-cas":
        emit(selector_cas(ROOT, args.expected, ROOT / "staging" / f"{require_run_id(args.run)}.conf"))
    elif args.mode == "selector-unlink":
        emit(selector_unlink(ROOT, args.expected))
    elif args.mode == "journal-create":
        emit(create_journal(ROOT, _read_stdin_json()))
    elif args.mode == "journal-transition":
        emit(update_journal(ROOT, args.expected, args.phase))
    elif args.mode == "journal-recovery-transition":
        emit(
            recover_precommit_journal(
                ROOT, args.expected, args.selector, args.phase
            )
        )
    elif args.mode == "storage-binding":
        emit(storage_binding(_read_stdin_json()))
    elif args.mode == "implementation-inventory":
        emit(implementation_inventory(PROJECT))
    elif args.mode == "media-authority":
        emit(media_authority(AUTHORITY))
    elif args.mode == "receipt-finalize":
        emit(finalize_receipt(ROOT, _read_stdin_json()))
    elif args.mode == "receipt-verify-external":
        emit(verify_external_receipt(_read_stdin_json()))
    elif args.mode == "operation-close":
        emit(
            close_operation(
                ROOT,
                args.expected_receipt,
                args.expected_journal,
                _read_stdin_json(),
            )
        )
    else:
        cleanup_staging(ROOT, args.run)
        emit({"schema": "estakada.r7c-cleanup-v1", "staging": "ABSENT"})


if __name__ == "__main__":
    main()
