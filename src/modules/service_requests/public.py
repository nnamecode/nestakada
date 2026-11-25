from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST

from .commands import IntakePersistenceError, IntakeResult, accept_submission_guarded
from .intake import IntakeConfig, IntakeValidationError, normalize_submission
from .lifecycle import requests_ready
from .telegram import TelegramConfig, attempt_telegram_delivery
from .web import _request_authority


_FIELDS = frozenset({
    "form_version", "submission_id", "name", "phone", "vehicle_make",
    "vehicle_model", "vehicle_year", "comment", "consent_text_version", "consent",
})


@dataclass(frozen=True, slots=True)
class PublicIntakeConfiguration:
    intake: IntakeConfig
    consent_text: str
    privacy_text: str
    telegram: TelegramConfig
    ledger_root: Path
    independent_adapter: str


def intake_configuration() -> PublicIntakeConfiguration | None:
    validator = getattr(settings, "SERVICE_REQUEST_CONFIGURATION_VALIDATOR", None)
    if not callable(validator) or not validator(settings):
        return None
    return PublicIntakeConfiguration(
        intake=IntakeConfig(
            settings.SERVICE_REQUEST_FORM_VERSION,
            settings.SERVICE_REQUEST_CONSENT_VERSION,
            settings.SERVICE_REQUEST_CONSENT_SHA256,
        ),
        consent_text=settings.SERVICE_REQUEST_CONSENT_TEXT,
        privacy_text=settings.SERVICE_REQUEST_PRIVACY_TEXT,
        telegram=TelegramConfig(
            Path(settings.SERVICE_REQUEST_TELEGRAM_TOKEN_FILE),
            settings.SERVICE_REQUEST_TELEGRAM_CHAT_ID,
        ),
        ledger_root=Path(settings.SERVICE_REQUEST_LEDGER_ROOT),
        independent_adapter=settings.SERVICE_REQUEST_INDEPENDENT_ADAPTER,
    )


def form_projection() -> dict[str, object] | None:
    config = intake_configuration()
    if config is None:
        return None
    authority = _request_authority()
    if (
        authority is None
        or not requests_ready(ledger=authority[0], independent=authority[1])
    ):
        return None
    return {
        "form_version": config.intake.form_version,
        "submission_id": str(uuid.uuid4()),
        "consent_text_version": config.intake.consent_text_version,
        "consent_text": config.consent_text,
        "privacy_text": config.privacy_text,
    }


def _constant(body: str, status: int) -> HttpResponse:
    response = HttpResponse(body, status=status, content_type="text/plain")
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def submit_service_request(request: HttpRequest) -> HttpResponse:
    config = intake_configuration()
    if config is None:
        return _constant("NOT_FOUND", 404)
    authority = _request_authority()
    if (
        authority is None
        or not requests_ready(ledger=authority[0], independent=authority[1])
    ):
        return _constant("REQUESTS_UNAVAILABLE", 503)
    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise IntakeValidationError("INVALID_INPUT")
        post = request.POST
        if frozenset(post) != _FIELDS or any(len(post.getlist(key)) != 1 for key in _FIELDS):
            raise IntakeValidationError("INVALID_INPUT")
        submission = normalize_submission(
            {key: post[key] for key in _FIELDS},
            config.intake,
        )
        result = accept_submission_guarded(
            submission,
            after_commit=lambda request_id: attempt_telegram_delivery(
                request_id, config.telegram
            ),
            ledger=authority[0],
            independent=authority[1],
        )
    except (IntakeValidationError, RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent,
            ValueError, TypeError, UnicodeError):
        return _constant("INVALID_REQUEST_INPUT", 400)
    except IntakePersistenceError:
        return _constant("REQUESTS_UNAVAILABLE", 503)
    if result == IntakeResult.CONFLICT:
        return _constant("REQUEST_CONFLICT", 409)
    return _constant("REQUEST_ACCEPTED", 200)
