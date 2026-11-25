from __future__ import annotations

"""HTTP composition for owner-only audit reads."""

import json
import re
import uuid
from datetime import date, datetime, time, timedelta, timezone as datetime_timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.core.exceptions import SuspiciousOperation, ValidationError
from django.db import DatabaseError
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from modules.accounts.api import StaffRole, staff_session_required

from modules.audit.models import Action, ActorKind, AuditEvent, TargetType


PAGE_SIZE = 50
QUERY_CAP = 512
DETAIL_CAP = 2048
_CURSOR = re.compile(
    r"\A[0-9]{8}T[0-9]{6}\.[0-9]{6}Z_[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
)
_MSK = ZoneInfo("Europe/Moscow")
_UTC = datetime_timezone.utc


def _canonical_uuid(value: str) -> uuid.UUID:
    parsed = uuid.UUID(value)
    if str(parsed) != value:
        raise ValueError("uuid")
    return parsed


def _parse_cursor(value: str) -> tuple[datetime, uuid.UUID]:
    if len(value.encode("ascii")) != 60 or _CURSOR.fullmatch(value) is None:
        raise ValueError("cursor")
    timestamp_token, uuid_token = value.split("_", 1)
    timestamp = datetime.strptime(timestamp_token, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=_UTC)
    if timestamp.strftime("%Y%m%dT%H%M%S.%fZ") != timestamp_token:
        raise ValueError("cursor")
    return timestamp, _canonical_uuid(uuid_token)


def _cursor(row: AuditEvent) -> str:
    timestamp = row.occurred_at.astimezone(_UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{timestamp}_{row.id}"


def _parameters(request: HttpRequest) -> tuple[dict[str, str], Q, tuple[datetime, uuid.UUID] | None]:
    raw_query = request.META.get("QUERY_STRING", "")
    if type(raw_query) is not str:
        raise ValueError("query")
    try:
        if len(raw_query.encode("ascii")) > QUERY_CAP:
            raise ValueError("query")
    except UnicodeEncodeError:
        raise ValueError("query") from None
    allowed = ("action", "date", "target", "before")
    if any(key not in allowed or len(request.GET.getlist(key)) != 1 for key in request.GET):
        raise ValueError("query")
    filters: dict[str, str] = {}
    query = Q()
    action = request.GET.get("action")
    if action is not None:
        if action not in Action.values:
            raise ValueError("action")
        filters["action"] = action
        query &= Q(action=action)
    day_token = request.GET.get("date")
    if day_token is not None:
        if len(day_token) != 10:
            raise ValueError("date")
        day = date.fromisoformat(day_token)
        if day.isoformat() != day_token:
            raise ValueError("date")
        start = datetime.combine(day, time.min, tzinfo=_MSK)
        end = start + timedelta(days=1)
        filters["date"] = day_token
        query &= Q(occurred_at__gte=start, occurred_at__lt=end)
    target_token = request.GET.get("target")
    if target_token is not None:
        target = _canonical_uuid(target_token)
        filters["target"] = target_token
        query &= Q(target_uuid=target)
    cursor_token = request.GET.get("before")
    before = None
    if cursor_token is not None:
        before = _parse_cursor(cursor_token)
    return filters, query, before


def _audit_rows(query: Q, before: tuple[datetime, uuid.UUID] | None) -> list[AuditEvent]:
    rows = AuditEvent.objects.filter(query)
    if before is not None:
        timestamp, event_id = before
        rows = rows.filter(Q(occurred_at__lt=timestamp) | Q(occurred_at=timestamp, id__lt=event_id))
    return list(rows.order_by("-occurred_at", "-id")[: PAGE_SIZE + 1])


@require_GET
@staff_session_required
def audit_event_list_view(request: HttpRequest) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    try:
        filters, query, before = _parameters(request)
    except (SuspiciousOperation, TypeError, ValueError, OverflowError, UnicodeError):
        return HttpResponse("INVALID_AUDIT_QUERY", status=400, content_type="text/plain")
    try:
        selected = _audit_rows(query, before)
        rows = selected[:PAGE_SIZE]
        projected = []
        for row in rows:
            row.clean()
            detail = json.dumps(
                row.detail,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if len(detail.encode("utf-8")) > DETAIL_CAP:
                raise ValidationError("detail")
            projected.append({"event": row, "detail": detail})
        next_url = ""
        if len(selected) == PAGE_SIZE + 1:
            next_url = "?" + urlencode({**filters, "before": _cursor(rows[-1])})
    except (DatabaseError, ValidationError, TypeError, ValueError, OverflowError, UnicodeError):
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return render(
        request,
        "audit/events.html",
        {
            "rows": projected,
            "filters": filters,
            "next_url": next_url,
            "actions": Action.choices,
        },
    )
