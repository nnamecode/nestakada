"""Serve one validated local-preview export on loopback, read-only."""
from argparse import ArgumentParser
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from threading import Thread
from uuid import UUID


MAX_JSON = 2 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024
MAX_FILES = 4096
HEX = frozenset("0123456789abcdef")


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def is_hex(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def is_reparse(info):
    return bool(getattr(info, "st_file_attributes", 0) & 0x400)


def reject_link(path):
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or is_reparse(info):
        raise ValueError("LOCAL_PREVIEW_LINK_FORBIDDEN")
    return info


def load_canonical(path):
    info = reject_link(path)
    if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_JSON:
        raise ValueError("LOCAL_PREVIEW_JSON_INVALID")
    body = path.read_bytes()
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("LOCAL_PREVIEW_JSON_INVALID") from None
    if canonical(value) != body:
        raise ValueError("LOCAL_PREVIEW_JSON_NONCANONICAL")
    return value, body


def decode_canonical(body):
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError("LOCAL_PREVIEW_JSON_INVALID") from None
    if canonical(value) != body:
        raise ValueError("LOCAL_PREVIEW_JSON_NONCANONICAL")
    return value


class Export:
    def __init__(self, root):
        candidate = Path(root)
        if not candidate.is_absolute():
            raise ValueError("LOCAL_PREVIEW_ROOT_ABSOLUTE_REQUIRED")
        repo = Path(__file__).resolve().parents[1]
        local_preview = repo / "work" / "local-preview"
        runs = local_preview / "runs"
        if candidate.parent != runs:
            raise ValueError("LOCAL_PREVIEW_ROOT_SCOPE_INVALID")
        try:
            run_id = UUID(candidate.name)
        except ValueError:
            raise ValueError("LOCAL_PREVIEW_ROOT_SCOPE_INVALID") from None
        if str(run_id) != candidate.name:
            raise ValueError("LOCAL_PREVIEW_ROOT_SCOPE_INVALID")
        reject_link(local_preview)
        reject_link(runs)
        reject_link(candidate)
        self.root = candidate
        receipt, receipt_body = load_canonical(self.root / "receipt.json")
        index, index_body = load_canonical(self.root / "preview-index-v1.json")
        if set(receipt) != {
            "schema", "runId", "indexSha256", "reserveManifestSha256",
            "responses", "resources", "totals",
        } or receipt.get("schema") != "local-preview-host-receipt-v1":
            raise ValueError("LOCAL_PREVIEW_RECEIPT_INVALID")
        if receipt["runId"] != self.root.name:
            raise ValueError("LOCAL_PREVIEW_RECEIPT_RUN_INVALID")
        if hashlib.sha256(index_body).hexdigest() != receipt["indexSha256"]:
            raise ValueError("LOCAL_PREVIEW_INDEX_DIGEST_MISMATCH")
        self._validate_index(index, receipt)
        self.index = index
        self.receipt = receipt
        self.receipt_sha256 = hashlib.sha256(receipt_body).hexdigest()
        self.mapping = {}
        for row in index["responses"]:
            self.mapping[row["target"]] = ("response", row)
        for row in index["resources"]:
            if row["url"] in self.mapping:
                raise ValueError("LOCAL_PREVIEW_TARGET_DUPLICATE")
            self.mapping[row["url"]] = ("resource", row)
        for _kind, row in self.mapping.values():
            self.read_verified(row)

    def _validate_index(self, value, receipt):
        if not isinstance(value, dict) or set(value) != {
            "schema", "runId", "generation", "reserveManifest",
            "headerPolicy", "responses", "resources", "totals",
        } or value.get("schema") != "local-preview-index-v1":
            raise ValueError("LOCAL_PREVIEW_INDEX_INVALID")
        if value["runId"] != receipt["runId"]:
            raise ValueError("LOCAL_PREVIEW_INDEX_RUN_INVALID")
        manifest = value["reserveManifest"]
        if set(manifest) != {"path", "sha256"} or not is_hex(manifest["sha256"]):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_DESCRIPTOR_INVALID")
        if manifest["sha256"] != receipt["reserveManifestSha256"]:
            raise ValueError("LOCAL_PREVIEW_MANIFEST_DIGEST_MISMATCH")
        policy = value["headerPolicy"]
        if set(policy) != {
            "contentSecurityPolicy", "securityPolicies", "cachePolicies"
        } or set(policy["securityPolicies"]) != {"public-v1"} or set(
            policy["securityPolicies"]["public-v1"]
        ) != {"xContentTypeOptions"} or policy["securityPolicies"][
            "public-v1"
        ]["xContentTypeOptions"] != "nosniff" or policy[
            "cachePolicies"
        ] != {"reserve-v1": "no-cache"}:
            raise ValueError("LOCAL_PREVIEW_HEADER_POLICY_INVALID")
        if not isinstance(policy["contentSecurityPolicy"], str) or not policy[
            "contentSecurityPolicy"
        ]:
            raise ValueError("LOCAL_PREVIEW_HEADER_POLICY_INVALID")
        responses, resources = value["responses"], value["resources"]
        if len(responses) != receipt["responses"] or len(resources) != receipt[
            "resources"
        ] or len(responses) != 139 or len(responses) + len(resources) > MAX_FILES:
            raise ValueError("LOCAL_PREVIEW_COUNT_INVALID")
        if value["totals"] != receipt["totals"] or set(value["totals"]) != {
            "bytes", "files"
        } or value["totals"]["files"] != len(responses) + len(resources):
            raise ValueError("LOCAL_PREVIEW_TOTAL_INVALID")
        for row in responses:
            if set(row) != {
                "target", "path", "status", "location", "contentType",
                "xRobotsTag", "securityPolicyId", "cachePolicyId", "bytes",
                "sha256",
            } or row["status"] not in (200, 302) or row[
                "securityPolicyId"
            ] != "public-v1" or row["cachePolicyId"] != "reserve-v1" or row[
                "contentType"
            ] != "text/html; charset=utf-8" or not row["target"].startswith(
                "/"
            ) or (row["location"] is not None and not row["location"].startswith("/")):
                raise ValueError("LOCAL_PREVIEW_RESPONSE_INVALID")
            self._validate_file_row(row)
        for row in resources:
            if set(row) != {
                "url", "path", "contentType", "bytes", "sha256"
            } or not row["url"].startswith("/") or row["contentType"] not in {
                "text/css; charset=utf-8", "text/javascript; charset=utf-8",
                "image/webp", "image/jpeg", "image/png",
            }:
                raise ValueError("LOCAL_PREVIEW_RESOURCE_INVALID")
            self._validate_file_row(row)
        manifest_body = self.read_relative(manifest["path"], MAX_JSON)
        if hashlib.sha256(manifest_body).hexdigest() != manifest["sha256"]:
            raise ValueError("LOCAL_PREVIEW_MANIFEST_DIGEST_MISMATCH")
        reserve = decode_canonical(manifest_body)
        if not isinstance(reserve, dict) or set(reserve) != {
            "schema", "generation", "built_at", "source_stamp", "responses",
            "resources", "retained_asset_ids", "totals",
        } or reserve.get("schema") != "html-reserve-manifest-v1" or reserve.get(
            "generation"
        ) != value["generation"] or reserve.get("totals") != value["totals"]:
            raise ValueError("LOCAL_PREVIEW_MANIFEST_INVALID")
        expected_manifest_path = (
            f"reserve/generations/{value['generation']}/manifest.json"
        )
        if manifest["path"] != expected_manifest_path:
            raise ValueError("LOCAL_PREVIEW_MANIFEST_PATH_INVALID")
        if not isinstance(reserve["responses"], list) or not isinstance(
            reserve["resources"], list
        ):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_INVALID")
        response_keys = {
            "name", "target", "status", "location", "content_type",
            "x_robots_tag", "security_policy_id", "cache_policy_id", "sha256",
            "byte_size",
        }
        resource_keys = {"name", "url", "content_type", "sha256", "byte_size"}
        if any(not isinstance(row, dict) or set(row) != response_keys
               for row in reserve["responses"]):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_RESPONSE_MISMATCH")
        if any(not isinstance(row, dict) or set(row) != resource_keys
               for row in reserve["resources"]):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_RESOURCE_MISMATCH")
        reserve_responses = sorted(reserve["responses"], key=lambda row: row["target"])
        index_responses = sorted(responses, key=lambda row: row["target"])
        if len(reserve_responses) != len(index_responses):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_RESPONSE_MISMATCH")
        for source, indexed in zip(reserve_responses, index_responses):
            expected = {
                "target": source.get("target"),
                "path": (
                    f"reserve/generations/{value['generation']}/responses/"
                    f"{source.get('name')}"
                ),
                "status": source.get("status"),
                "location": source.get("location"),
                "contentType": source.get("content_type"),
                "xRobotsTag": source.get("x_robots_tag"),
                "securityPolicyId": source.get("security_policy_id"),
                "cachePolicyId": source.get("cache_policy_id"),
                "bytes": source.get("byte_size"),
                "sha256": source.get("sha256"),
            }
            if indexed != expected:
                raise ValueError("LOCAL_PREVIEW_MANIFEST_RESPONSE_MISMATCH")
        reserve_resources = sorted(reserve["resources"], key=lambda row: row["url"])
        index_resources = sorted(resources, key=lambda row: row["url"])
        if len(reserve_resources) != len(index_resources):
            raise ValueError("LOCAL_PREVIEW_MANIFEST_RESOURCE_MISMATCH")
        for source, indexed in zip(reserve_resources, index_resources):
            expected = {
                "url": source.get("url"),
                "path": (
                    f"reserve/generations/{value['generation']}/resources/"
                    f"{source.get('name')}"
                ),
                "contentType": source.get("content_type"),
                "bytes": source.get("byte_size"),
                "sha256": source.get("sha256"),
            }
            if indexed != expected:
                raise ValueError("LOCAL_PREVIEW_MANIFEST_RESOURCE_MISMATCH")

    def _validate_file_row(self, row):
        if not isinstance(row["bytes"], int) or not 0 <= row["bytes"] <= MAX_FILE:
            raise ValueError("LOCAL_PREVIEW_FILE_SIZE_INVALID")
        if not is_hex(row["sha256"]):
            raise ValueError("LOCAL_PREVIEW_FILE_DIGEST_INVALID")
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("LOCAL_PREVIEW_FILE_PATH_INVALID")

    def read_relative(self, relative, limit):
        parts = PurePosixPath(relative).parts
        if not parts or ".." in parts or PurePosixPath(relative).is_absolute():
            raise ValueError("LOCAL_PREVIEW_FILE_PATH_INVALID")
        if os.name == "posix":
            descriptor = os.open(
                self.root,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            )
            try:
                for part in parts[:-1]:
                    next_descriptor = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                    os.close(descriptor)
                    descriptor = next_descriptor
                file_descriptor = os.open(
                    parts[-1], os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                try:
                    info = os.fstat(file_descriptor)
                    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                        raise ValueError("LOCAL_PREVIEW_FILE_INVALID")
                    chunks, remaining = [], info.st_size
                    while remaining:
                        chunk = os.read(file_descriptor, min(65536, remaining))
                        if not chunk:
                            raise ValueError("LOCAL_PREVIEW_FILE_INVALID")
                        chunks.append(chunk)
                        remaining -= len(chunk)
                    if os.read(file_descriptor, 1):
                        raise ValueError("LOCAL_PREVIEW_FILE_INVALID")
                    return b"".join(chunks)
                finally:
                    os.close(file_descriptor)
            finally:
                os.close(descriptor)
        path = self.root
        for part in parts:
            path = path / part
            reject_link(path)
        before = os.lstat(path)
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        try:
            info = os.fstat(descriptor)
            after = os.lstat(path)
            if (not stat.S_ISREG(info.st_mode) or info.st_size > limit
                    or (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino)
                    or (after.st_dev, after.st_ino) != (info.st_dev, info.st_ino)
                    or is_reparse(info)):
                raise ValueError("LOCAL_PREVIEW_FILE_INVALID")
            body = os.read(descriptor, info.st_size + 1)
            if len(body) != info.st_size:
                raise ValueError("LOCAL_PREVIEW_FILE_INVALID")
            return body
        finally:
            os.close(descriptor)

    def read_verified(self, row):
        body = self.read_relative(row["path"], MAX_FILE)
        if len(body) != row["bytes"] or hashlib.sha256(body).hexdigest() != row[
            "sha256"
        ]:
            raise ValueError("LOCAL_PREVIEW_FILE_DIGEST_MISMATCH")
        return body


class Handler(BaseHTTPRequestHandler):
    server_version = "EstakadaLocalPreview/1"
    sys_version = ""

    def _serve(self, head=False):
        if self.headers.get("Range") is not None:
            self.send_error(416)
            return
        entry = self.server.export.mapping.get(self.path)
        if entry is None:
            self.send_error(404)
            return
        kind, row = entry
        try:
            body = self.server.export.read_verified(row)
        except (OSError, ValueError):
            self.send_error(503)
            return
        self.send_response(row.get("status", 200))
        if kind == "response":
            if row["location"] is not None:
                self.send_header("Location", row["location"])
            self.send_header("Content-Security-Policy", self.server.export.index[
                "headerPolicy"
            ]["contentSecurityPolicy"])
            if row["xRobotsTag"] is not None:
                self.send_header("X-Robots-Tag", row["xRobotsTag"])
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Type", row["contentType"])
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_GET(self):
        self._serve(False)

    def do_HEAD(self):
        self._serve(True)

    def do_POST(self):
        self.send_error(405)

    def log_message(self, _format, *_args):
        return


def smoke(export):
    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.export = export
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)

    def request(method, target, headers=None):
        connection.request(method, target, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        return response, body

    def assert_indexed_response(target, expected_status=200):
        row = next(
            (item for item in export.index["responses"] if item["target"] == target),
            None,
        )
        if row is None:
            raise ValueError("LOCAL_PREVIEW_SMOKE_TARGET_MISSING")
        response, body = request("GET", target)
        headers = {name.lower(): value for name, value in response.getheaders()}
        if (response.status != expected_status or len(body) != row["bytes"]
                or hashlib.sha256(body).hexdigest() != row["sha256"]
                or headers.get("content-type") != row["contentType"]
                or headers.get("content-length") != str(row["bytes"])
                or headers.get("x-content-type-options") != "nosniff"
                or headers.get("cache-control") != "no-cache"
                or headers.get("content-security-policy") != export.index[
                    "headerPolicy"
                ]["contentSecurityPolicy"]
                or headers.get("x-robots-tag") != row["xRobotsTag"]):
            raise ValueError("LOCAL_PREVIEW_SMOKE_PUBLIC_FAILED")
        return response, body

    def assert_indexed_resource(row):
        response, body = request("GET", row["url"])
        headers = {name.lower(): value for name, value in response.getheaders()}
        if (response.status != 200 or len(body) != row["bytes"]
                or hashlib.sha256(body).hexdigest() != row["sha256"]
                or headers.get("content-type") != row["contentType"]
                or headers.get("content-length") != str(row["bytes"])
                or headers.get("x-content-type-options") != "nosniff"
                or headers.get("cache-control") != "no-cache"):
            raise ValueError("LOCAL_PREVIEW_SMOKE_RESOURCE_FAILED")

    try:
        required = [
            "/", "/services/", "/articles/zamena-masla-v-dvigatele",
            "/contacts", "/gallery-of-works/", "/gallery-of-works/?page=2",
        ]
        album = next((row["target"] for row in export.index["responses"]
                      if row["target"].startswith("/gallery-of-works/")
                      and row["target"] != "/gallery-of-works/"), None)
        if album is None:
            raise ValueError("LOCAL_PREVIEW_SMOKE_ALBUM_MISSING")
        for target in required + [album]:
            assert_indexed_response(target)
        for content_type in (
            "text/css; charset=utf-8", "text/javascript; charset=utf-8", "image/jpeg",
        ):
            resource = next(
                (row for row in export.index["resources"]
                 if row["contentType"] == content_type),
                None,
            )
            if resource is None:
                raise ValueError("LOCAL_PREVIEW_SMOKE_RESOURCE_MISSING")
            assert_indexed_resource(resource)
        response, body = request("HEAD", "/")
        if response.status != 200 or body:
            raise ValueError("LOCAL_PREVIEW_SMOKE_HEAD_FAILED")
        response, _body = assert_indexed_response(
            "/gallery-of-works/?page=1", expected_status=302
        )
        redirect_row = next(
            row for row in export.index["responses"]
            if row["target"] == "/gallery-of-works/?page=1"
        )
        if response.getheader("Location") != redirect_row["location"]:
            raise ValueError("LOCAL_PREVIEW_SMOKE_REDIRECT_FAILED")
        multi_query = next(
            (row["target"] for row in export.index["responses"]
             if row["target"].startswith("/gallery-of-works/?page=2&album=")),
            None,
        )
        if multi_query is None:
            raise ValueError("LOCAL_PREVIEW_SMOKE_QUERY_TARGET_MISSING")
        query = multi_query.split("?", 1)[1].split("&")
        reversed_query = "/gallery-of-works/?" + "&".join(reversed(query))
        for method, target, expected, headers in (
            ("GET", "/manage/", 404, None),
            ("GET", "/does-not-exist/", 404, None),
            ("GET", "/gallery-of-works/?page=2&x=1", 404, None),
            ("GET", reversed_query, 404, None),
            ("GET", "/%2e%2e/receipt.json", 404, None),
            ("POST", "/", 405, None),
            ("GET", "/", 416, {"Range": "bytes=0-1"}),
        ):
            response, _body = request(method, target, headers)
            if response.status != expected:
                raise ValueError("LOCAL_PREVIEW_SMOKE_NEGATIVE_FAILED")

        home = next(row for row in export.index["responses"] if row["target"] == "/")
        target = export.root.joinpath(*PurePosixPath(home["path"]).parts)
        original = target.read_bytes()
        if not original or len(original) > MAX_FILE:
            raise ValueError("LOCAL_PREVIEW_SMOKE_TAMPER_TARGET_INVALID")
        try:
            changed = bytearray(original)
            changed[0] ^= 1
            target.write_bytes(changed)
            response, _body = request("GET", "/")
            if response.status != 503:
                raise ValueError("LOCAL_PREVIEW_SMOKE_TAMPER_FAILED")
        finally:
            target.write_bytes(original)
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        if thread.is_alive():
            raise ValueError("LOCAL_PREVIEW_SMOKE_SERVER_STOP_FAILED")
    Export(export.root)
    print(f"LOCAL_PREVIEW_SMOKE_PASS run={export.receipt['runId']}", flush=True)


def main(argv=None):
    parser = ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, default=8768)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("LOCAL_PREVIEW_PORT_INVALID")
    export = Export(args.root)
    if args.check and args.smoke:
        raise SystemExit("LOCAL_PREVIEW_MODE_INVALID")
    if args.smoke:
        smoke(export)
        return
    if args.check:
        print(
            f"LOCAL_PREVIEW_VALID run={export.receipt['runId']} "
            f"receipt={export.receipt_sha256}",
            flush=True,
        )
        return
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.export = export
    print(
        f"LOCAL_PREVIEW_READY=http://127.0.0.1:{args.port}/ "
        f"receipt={export.receipt_sha256}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        sys.stderr.write(str(error) + "\n")
        raise SystemExit(2) from None
