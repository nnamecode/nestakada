from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
from pathlib import Path, PurePosixPath


SOURCE = Path("/media-source")
RESTORE = Path("/restore-media")
AUTHORITY = Path("/authority")
OUTPUT = Path("/output")


def fail(message: str = "R7_MEDIA_UNAVAILABLE") -> None:
    raise RuntimeError(message)


def inventory() -> list[dict[str, object]]:
    path = AUTHORITY / "media-inventory.json"
    if not path.is_file() or path.is_symlink() or path.parent != AUTHORITY:
        fail()
    rows = json.loads(path.read_text(encoding="utf-8"))
    if type(rows) is not list:
        fail()
    previous = ""
    for row in rows:
        if type(row) is not dict or set(row) != {"path", "sha256", "bytes"}:
            fail()
        pure = PurePosixPath(row["path"])
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in row["path"]
            or row["path"] <= previous
            or type(row["bytes"]) is not int
            or row["bytes"] < 1
            or type(row["sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None
        ):
            fail()
        previous = row["path"]
    return rows


def checked_source(root: Path, relative: str) -> Path:
    path = root.joinpath(*PurePosixPath(relative).parts)
    resolved = path.resolve()
    if root.resolve() not in resolved.parents or not path.is_file() or path.is_symlink():
        fail()
    return path


def copy_hash(source, destination, expected_size: int, expected_hash: str) -> None:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = source.read(1024 * 1024)
        if not chunk:
            break
        destination.write(chunk)
        digest.update(chunk)
        size += len(chunk)
    if size != expected_size or digest.hexdigest() != expected_hash:
        fail("R7_MEDIA_DIGEST_MISMATCH")


def pack() -> None:
    rows = inventory()
    archive = OUTPUT / "media.tar"
    if archive.exists() or not OUTPUT.is_dir():
        fail()
    with tarfile.open(archive, "x", format=tarfile.PAX_FORMAT) as target:
        for row in rows:
            source = checked_source(SOURCE, row["path"])
            with source.open("rb") as check_stream, open(os.devnull, "wb") as sink:
                copy_hash(check_stream, sink, int(row["bytes"]), str(row["sha256"]))
            info = tarfile.TarInfo(row["path"])
            info.size = int(row["bytes"])
            info.mode = 0o600
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with source.open("rb") as stream:
                target.addfile(info, stream)
    if not archive.is_file() or archive.is_symlink() or archive.stat().st_size < 1024:
        fail()
    print(f"R7_MEDIA_PACK_OK files={len(rows)} bytes={sum(int(row['bytes']) for row in rows)}")


def check() -> None:
    rows = inventory()
    for row in rows:
        source = checked_source(SOURCE, row["path"])
        with source.open("rb") as stream, open(os.devnull, "wb") as sink:
            copy_hash(stream, sink, int(row["bytes"]), str(row["sha256"]))
    print(f"R7_MEDIA_CHECK_OK files={len(rows)} bytes={sum(int(row['bytes']) for row in rows)}")


def verify() -> None:
    rows = inventory()
    expected = {row["path"]: row for row in rows}
    archive = AUTHORITY / "media.tar"
    if not archive.is_file() or archive.is_symlink() or not RESTORE.is_dir():
        fail()
    seen: set[str] = set()
    with tarfile.open(archive, "r:") as source:
        members = source.getmembers()
        if [member.name for member in members] != list(expected):
            fail()
        for member in members:
            row = expected.get(member.name)
            pure = PurePosixPath(member.name)
            if (
                row is None
                or not member.isfile()
                or member.size != row["bytes"]
                or pure.is_absolute()
                or ".." in pure.parts
                or member.name in seen
            ):
                fail()
            seen.add(member.name)
            destination = RESTORE.joinpath(*pure.parts)
            if RESTORE.resolve() not in destination.resolve().parents or destination.exists():
                fail()
            destination.parent.mkdir(parents=True, exist_ok=True)
            stream = source.extractfile(member)
            if stream is None:
                fail()
            with stream, destination.open("xb") as output:
                copy_hash(stream, output, int(row["bytes"]), str(row["sha256"]))
    if seen != set(expected):
        fail()
    print(f"R7_MEDIA_RESTORE_OK files={len(rows)} bytes={sum(int(row['bytes']) for row in rows)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("pack", "check", "verify"))
    args = parser.parse_args()
    if args.mode == "pack":
        pack()
    elif args.mode == "check":
        check()
    else:
        verify()


if __name__ == "__main__":
    main()
