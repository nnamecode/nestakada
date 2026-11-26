from __future__ import annotations

import contextlib
import io
import runpy
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import django


django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.http import HttpRequest  # noqa: E402
from django.middleware.csrf import get_token  # noqa: E402
from modules.audit.models import AuditEvent  # noqa: E402


BASE = "http://localhost:8000"
EXPECTED_SMOKE = (
    "R7_HTTP_SMOKE_OK routes=115 requests=230 get200=114 "
    "head200=114 redirects=2 private_denial=1"
)
REQUEST_TABLES = (
    "service_requests_servicerequest",
    "service_requests_servicerequestdeletionprojection",
)
FORM_MARKERS = (
    b'/request/submit/',
    b'name="submission_id"',
    b'name="consent"',
)


def fetch(
    target: str,
    method: str,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    headers = {"X-Estakada-Request-Target": target}
    if extra_headers is not None:
        headers.update(extra_headers)
    request = Request(
        BASE + target,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def request_row_counts() -> tuple[int, int]:
    tables = frozenset(connection.introspection.table_names())
    counts: list[int] = []
    with connection.cursor() as cursor:
        for table in REQUEST_TABLES:
            if table not in tables:
                counts.append(0)
                continue
            cursor.execute(f'SELECT count(*) FROM "{table}"')
            row = cursor.fetchone()
            if row is None or type(row[0]) is not int or row[0] < 0:
                raise RuntimeError("CORE18_REQUEST_COUNT_INVALID")
            counts.append(row[0])
    return counts[0], counts[1]


if settings.SERVICE_REQUESTS_ENABLED is not False:
    raise RuntimeError("CORE18_DEFAULT_OFF_REQUIRED")

before_requests = request_row_counts()
before_audit = AuditEvent.objects.count()
if before_requests != (0, 0):
    raise RuntimeError("CORE18_DEFAULT_OFF_ROWS_PRESENT")

captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    runpy.run_path("/tools/rebuild7_http_smoke.py", run_name="__main__")
if captured.getvalue().strip() != EXPECTED_SMOKE:
    raise RuntimeError("CORE18_EXACT115_RESULT_INVALID")

home_status, home_body = fetch("/", "GET")
if home_status != 200 or any(marker in home_body for marker in FORM_MARKERS):
    raise RuntimeError("CORE18_DEFAULT_OFF_FORM_EXPOSED")
for method in ("GET", "POST"):
    csrf_headers = None
    if method == "POST":
        csrf_request = HttpRequest()
        csrf_token = get_token(csrf_request)
        csrf_secret = csrf_request.META.get("CSRF_COOKIE")
        if not isinstance(csrf_secret, str) or not csrf_secret:
            raise RuntimeError("CORE18_CSRF_FIXTURE_INVALID")
        csrf_headers = {
            "Cookie": f"{settings.CSRF_COOKIE_NAME}={csrf_secret}",
            "X-CSRFToken": csrf_token,
        }
    status, _ = fetch("/request/submit/", method, csrf_headers)
    if status != 404:
        raise RuntimeError("CORE18_DEFAULT_OFF_ROUTE_EXPOSED")

after_requests = request_row_counts()
after_audit = AuditEvent.objects.count()
if after_requests != before_requests or after_audit != before_audit:
    raise RuntimeError("CORE18_DEFAULT_OFF_MUTATION")

print(
    "CORE18_EXACT115_OK routes=115 requests=230 default_off=1 "
    "request_rows=0 audit_mutation=0 external_network=0"
)
