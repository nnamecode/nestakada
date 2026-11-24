from __future__ import annotations

import argparse
import http.client
import json
import re


HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HOSTS = {"r7c-old-app": "old", "r7c-new-app": "new"}


def fail() -> None:
    raise RuntimeError("R7C_TARGET_PROBE_FAILED")


def probe(host: str, role: str, generation: str, storage: str) -> dict[str, str]:
    if (
        HOSTS.get(host) != role
        or HEX64.fullmatch(generation) is None
        or HEX64.fullmatch(storage) is None
    ):
        fail()
    connection = http.client.HTTPConnection(host, 8000, timeout=5)
    try:
        connection.request(
            "GET",
            "/__r7c_target_identity__",
            headers={
                "Host": "r7c-probe.invalid",
                "Connection": "close",
                "X-Estakada-R7C-Role": "client-value-must-not-return",
                "X-Estakada-R7C-Generation": "client-value-must-not-return",
                "X-Estakada-R7C-Storage-Binding": "client-value-must-not-return",
            },
        )
        response = connection.getresponse()
        body = response.read(1)
        headers = response.getheaders()
    finally:
        connection.close()
    expected = {
        "x-estakada-r7c-role": role,
        "x-estakada-r7c-generation": generation,
        "x-estakada-r7c-storage-binding": storage,
        "cache-control": "no-store",
    }
    lowered: dict[str, list[str]] = {}
    for name, value in headers:
        lowered.setdefault(name.lower(), []).append(value)
    if (
        response.status != 204
        or body != b""
        or any(lowered.get(name) != [value] for name, value in expected.items())
        or "set-cookie" in lowered
        or response.getheader("Location") is not None
    ):
        fail()
    return {
        "schema": "estakada.r7c-target-probe-v1",
        "role": role,
        "generationSha256": generation,
        "storageBindingSha256": storage,
        "result": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", choices=tuple(HOSTS), required=True)
    parser.add_argument("--role", choices=("old", "new"), required=True)
    parser.add_argument("--generation", required=True)
    parser.add_argument("--storage", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            probe(args.host, args.role, args.generation, args.storage),
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
