from __future__ import annotations

from typing import Any

from modules.pages.api import (
    FIELD_SETS,
    MEDIA_SLOTS,
    RICH_BY_KIND,
    ContentValidationError,
)
from modules.pages.api import validate_https as _validate_https
from modules.pages.api import validate_payload as _validate_payload

from .errors import ManifestError


def validate_https(value: Any, code: str, *, nullable: bool = False) -> str | None:
    try:
        return _validate_https(value, code, nullable=nullable)
    except ContentValidationError as exc:
        raise ManifestError(str(exc)) from exc


def validate_payload(payload: Any, expected_kind: str) -> dict[str, list[str]]:
    try:
        return _validate_payload(payload, expected_kind)
    except ContentValidationError as exc:
        raise ManifestError(str(exc)) from exc


__all__ = (
    "FIELD_SETS",
    "MEDIA_SLOTS",
    "RICH_BY_KIND",
    "validate_https",
    "validate_payload",
)
