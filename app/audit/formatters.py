"""Privacy boundary for process logs: never render free text or tracebacks.

Callers provide a stable event_code and optional canonical audit references in
LogRecord extras. The message, args, request object, arbitrary extras and
exc_info/stack_info are deliberately not formatted or traversed.
"""
from datetime import datetime, timezone
import json
import logging
import math
from uuid import UUID

from django.core.exceptions import ValidationError

from .constants import Category, Level, Result, Source
from .safety import code, formatted_reference, object_kind, positive_id, related_ip


def _member(enum, value, default):
    if isinstance(value, str) and value in enum.values:
        return value
    return default


class SafeJsonFormatter(logging.Formatter):
    """Fixed output schema; omitted user material never enters a log string."""

    def format(self, record):
        try:
            return self._format(record)
        except Exception:
            # Raising here lets logging's error handler print raw msg/args.
            # This constant fallback contains no repr/str from the record.
            return '{"category":"site_errors","level":"ERROR","event_code":"LOG_RECORD_REJECTED","source":"application","result":"FAILURE"}'

    def _format(self, record):
        data = vars(record)
        if type(data) is not dict:
            raise ValueError("LOG_RECORD_INVALID")
        numeric_level = data.get("levelno")
        if type(numeric_level) is not int:
            numeric_level = logging.ERROR
        level = (Level.CRITICAL if numeric_level >= logging.CRITICAL else
                 Level.ERROR if numeric_level >= logging.ERROR else
                 Level.WARNING if numeric_level >= logging.WARNING else Level.INFO)
        created = data.get("created")
        if type(created) not in (int, float) or not math.isfinite(created):
            raise ValueError("LOG_TIME_INVALID")
        result = {
            "occurred_at": datetime.fromtimestamp(created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "category": _member(Category, data.get("category"), Category.SITE_ERRORS if numeric_level >= logging.ERROR else Category.SERVICE),
            "level": level,
            "event_code": "PROCESS_MESSAGE",
            "source": _member(Source, data.get("source"), Source.APPLICATION),
            "result": _member(Result, data.get("result"), Result.UNKNOWN),
        }
        try:
            result["event_code"] = code(data.get("event_code"))
        except ValidationError:
            pass
        try:
            result['occurrence_count'] = positive_id(data.get('occurrence_count', 1))
        except ValidationError:
            result['occurrence_count'] = 1
        result['count_is_lower_bound'] = data.get('count_is_lower_bound') is True
        for field in ("event_id", "request_id"):
            value = data.get(field)
            # Only typed internal UUIDs; do not accept arbitrary token strings.
            if type(value) is UUID:
                result[field] = str(value)
        if data.get("actor_id") is not None:
            try:
                result["actor_id"] = positive_id(data["actor_id"])
            except ValidationError:
                pass
        if data.get("object_ref"):
            try:
                reference = formatted_reference(data["object_ref"])
                kind = object_kind(data.get("object_kind", ""))
                if kind:
                    result.update(object_ref=reference, object_kind=kind)
            except ValidationError:
                pass
        if data.get("ip_address") is not None:
            try:
                result["ip_address"] = related_ip(data["ip_address"], data.get("ip_related"))
            except ValidationError:
                pass
        return json.dumps(result, ensure_ascii=True, separators=(",", ":"), allow_nan=False)

    def formatException(self, ei):
        return "[REDACTED]"

    def formatStack(self, stack_info):
        return "[REDACTED]"
