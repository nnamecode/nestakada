from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from django.core import signing
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole, staff_session_required

from .delete import ServiceRequestDeleteError, delete_service_request
from .read import ServiceRequestReadError, load_request_detail, load_request_page


_CURSOR = re.compile(r"\A[0-9]{8}T[0-9]{6}\.[0-9]{6}Z_[0-9a-f-]{36}\Z")
_STAMP = "%Y%m%dT%H%M%S.%fZ"
_SIGNER = signing.TimestampSigner(salt="estakada.service-request-delete.v1")
_CONFIRMATION_MAX_AGE = 600


def _request_authority():
    """Production remains fail-closed until IMP-005 supplies reviewed authority."""
    return None


def _authority_or_503():
    authority = _request_authority()
    if authority is None:
        raise ServiceRequestReadError("PRIVATE_DATA_UNAVAILABLE")
    return authority


def _parse_cursor(request: HttpRequest):
    raw = request.META.get("QUERY_STRING", "")
    if type(raw) is not str or len(raw) > 128 or any(key != "before" for key in request.GET):
        raise ServiceRequestReadError("INVALID_CURSOR")
    values = request.GET.getlist("before")
    if not values:
        return None
    value = values[0]
    if len(values) != 1 or _CURSOR.fullmatch(value) is None:
        raise ServiceRequestReadError("INVALID_CURSOR")
    stamp, request_id = value.split("_", 1)
    parsed = datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)
    parsed_id = uuid.UUID(request_id)
    if parsed.strftime(_STAMP) != stamp or str(parsed_id) != request_id:
        raise ServiceRequestReadError("INVALID_CURSOR")
    return parsed, parsed_id


def _cursor_url(cursor) -> str:
    if cursor is None:
        return ""
    created_at, request_id = cursor
    token = f"{created_at.astimezone(UTC).strftime(_STAMP)}_{request_id}"
    return "?" + urlencode({"before": token})


def _confirmation(request_id: uuid.UUID, created_at: datetime) -> str:
    stamp = created_at.astimezone(UTC).strftime(_STAMP)
    return _SIGNER.sign(f"{request_id}|{stamp}")


def _unsign_confirmation(value: object, request_id: uuid.UUID) -> datetime:
    if type(value) is not str or not 1 <= len(value) <= 256:
        raise ValueError
    raw = _SIGNER.unsign(value, max_age=_CONFIRMATION_MAX_AGE)
    identifier, stamp = raw.split("|", 1)
    parsed_id = uuid.UUID(identifier)
    created_at = datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)
    if parsed_id != request_id or str(parsed_id) != identifier or created_at.strftime(_STAMP) != stamp:
        raise ValueError
    return created_at


@require_GET
@staff_session_required
def request_list_view(request: HttpRequest) -> HttpResponse:
    try:
        before = _parse_cursor(request)
        ledger, independent = _authority_or_503()
        page = load_request_page(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            ledger=ledger,
            independent=independent,
            before=before,
        )
    except ServiceRequestReadError as exc:
        if exc.code == "INVALID_CURSOR":
            return HttpResponse("INVALID_REQUEST_QUERY", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except (RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent,
            ValueError, TypeError, OverflowError, UnicodeError):
        return HttpResponse("INVALID_REQUEST_QUERY", status=400, content_type="text/plain")
    return render(request, "service_requests/list.html", {
        "rows": page.rows,
        "next_url": _cursor_url(page.next_cursor),
    })


@require_GET
@staff_session_required
def request_detail_view(request: HttpRequest, request_id: uuid.UUID) -> HttpResponse:
    try:
        ledger, independent = _authority_or_503()
        row = load_request_detail(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            request_id=request_id,
            ledger=ledger,
            independent=independent,
        )
    except ServiceRequestReadError as exc:
        status = 404 if exc.code == "REQUEST_NOT_FOUND" else 503
        body = "REQUEST_NOT_FOUND" if status == 404 else "PRIVATE_DATA_UNAVAILABLE"
        return HttpResponse(body, status=status, content_type="text/plain")
    confirmation = (
        _confirmation(row.id, row.created_at)
        if request.staff_actor.role == StaffRole.OWNER
        else ""
    )
    return render(request, "service_requests/detail.html", {
        "row": row,
        "delete_confirmation": confirmation,
    })


@require_POST
@staff_session_required
def request_delete_view(request: HttpRequest, request_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError
        post = request.POST
        keys = frozenset(post)
        if keys not in ({"confirmation"}, {"confirmation", "csrfmiddlewaretoken"}):
            raise ValueError
        if len(post.getlist("confirmation")) != 1:
            raise ValueError
        created_at = _unsign_confirmation(post["confirmation"], request_id)
        ledger, independent = _authority_or_503()
        delete_service_request(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            request_id=request_id,
            expected_created_at=created_at,
            ledger=ledger,
            independent=independent,
        )
    except (RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent, signing.BadSignature,
            ValueError, TypeError, OverflowError):
        return HttpResponse("INVALID_DELETE_CONFIRMATION", status=400, content_type="text/plain")
    except ServiceRequestReadError:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except ServiceRequestDeleteError as exc:
        status = 404 if exc.code == "REQUEST_NOT_FOUND" else 409 if exc.code == "CONFIRMATION_STALE" else 503
        body = (
            "REQUEST_NOT_FOUND"
            if status == 404
            else "DELETE_CONFLICT"
            if status == 409
            else "PRIVATE_DATA_UNAVAILABLE"
        )
        return HttpResponse(body, status=status, content_type="text/plain")
    return redirect("manage-service-requests")
