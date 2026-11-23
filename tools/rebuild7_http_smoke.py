from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener


BASE = "http://localhost:8000"
ROUTES = Path("/authority/analytics-route-map.csv")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


opener = build_opener(NoRedirect)


def fetch(target: str, method: str) -> tuple[int, object, bytes]:
    request = Request(
        BASE + target,
        method=method,
        headers={"X-Estakada-Request-Target": target},
    )
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except HTTPError as exc:
        return exc.code, exc.headers, exc.read()


with ROUTES.open(encoding="utf-8-sig", newline="") as stream:
    rows = list(csv.DictReader(stream))
expected_ids = {f"MAP-{index:03d}" for index in range(1, 116)}
if (
    len(rows) != 115
    or {row["map_id"] for row in rows} != expected_ids
    or len({row["requested_path"] for row in rows}) != 115
):
    raise RuntimeError("R7_HTTP_ROUTE_AUTHORITY_INVALID")

get_200 = head_200 = redirects = 0
for row in rows:
    target = row["requested_path"]
    is_page_one = target == "/gallery-of-works/?page=1"
    expected_status = 302 if is_page_one else 200
    for method in ("GET", "HEAD"):
        status, headers, body = fetch(target, method)
        if status != expected_status or (method == "HEAD" and body):
            raise RuntimeError(f"R7_HTTP_STATUS:{row['map_id']}:{method}:{status}")
        if headers.get("Set-Cookie") or "cookie" in headers.get("Vary", "").lower():
            raise RuntimeError(f"R7_HTTP_COOKIE:{row['map_id']}:{method}")
        if is_page_one:
            if headers.get("Location") != "/gallery-of-works/":
                raise RuntimeError(f"R7_HTTP_REDIRECT:{row['map_id']}:{method}")
            redirects += 1
            continue
        directives = sorted(part.strip().lower() for part in headers.get("Cache-Control", "").split(","))
        if directives != ["max-age=0", "must-revalidate", "public"]:
            raise RuntimeError(f"R7_HTTP_CACHE:{row['map_id']}:{method}")
        if method == "GET":
            get_200 += 1
            html = body.decode("utf-8")
            canonical = re.search(r'<link rel="canonical" href="([^"]+)">', html)
            expected_canonical = (
                "/gallery-of-works/"
                if row["map_id"] == "MAP-018"
                else "/services/avtomojka"
                if row["map_id"] == "MAP-088"
                else target
            )
            if canonical is None or canonical.group(1) != expected_canonical:
                raise RuntimeError(f"R7_HTTP_CANONICAL:{row['map_id']}")
            if re.search(r"(?i)<iframe\b|\s(?:src|poster)=[\"']https?://|<link\b[^>]*\shref=[\"']https?://", html):
                raise RuntimeError(f"R7_HTTP_EXTERNAL:{row['map_id']}")
        else:
            head_200 += 1

private_status, private_headers, _ = fetch("/manage/pages/", "GET")
if private_status != 302 or not private_headers.get("Location", "").startswith("/manage/login/"):
    raise RuntimeError("R7_HTTP_PRIVATE_DENIAL")

print(
    "R7_HTTP_SMOKE_OK "
    f"routes=115 requests=230 get200={get_200} head200={head_200} redirects={redirects} "
    "private_denial=1"
)
