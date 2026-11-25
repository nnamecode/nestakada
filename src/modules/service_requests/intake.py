from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Mapping


_FIELDS = frozenset(
    {
        "form_version",
        "submission_id",
        "name",
        "phone",
        "vehicle_make",
        "vehicle_model",
        "vehicle_year",
        "comment",
        "consent_text_version",
        "consent",
    }
)
_SHA256 = re.compile(r"\A[0-9a-f]{64}\Z")
_YEAR = re.compile(r"\A[0-9]{4}\Z")
_PHONE_COMPACT = re.compile(r"\A(?:\+7|8)([0-9]{10})\Z")
_PHONE_PAREN = re.compile(r"\A(?:\+7|8) \(([0-9]{3})\) ([0-9]{3})-([0-9]{2})-([0-9]{2})\Z")
_PHONE_SPACED = re.compile(r"\A(?:\+7|8) ([0-9]{3}) ([0-9]{3})-([0-9]{2})-([0-9]{2})\Z")


class IntakeValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IntakeConfig:
    form_version: str
    consent_text_version: str
    consent_text_sha256: str


@dataclass(frozen=True, slots=True)
class CanonicalSubmission:
    submission_id: uuid.UUID
    name: str
    phone: str
    vehicle_make: str
    vehicle_model: str
    vehicle_year: str
    comment: str
    consent_text_version: str
    consent_text_sha256: str


def _text(
    raw: str,
    *,
    minimum: int,
    maximum: int,
    strip: bool,
    allow_lf: bool = False,
) -> str:
    value = raw.strip() if strip else raw
    if not minimum <= len(value) <= maximum or unicodedata.normalize("NFC", value) != value:
        raise IntakeValidationError("INVALID_INPUT")
    for char in value:
        if char == "\n" and allow_lf:
            continue
        if unicodedata.category(char) in {"Cc", "Cf", "Cs"} or unicodedata.combining(char):
            raise IntakeValidationError("INVALID_INPUT")
    return value


def _phone(raw: str) -> str:
    value = raw.strip()
    match = _PHONE_COMPACT.fullmatch(value)
    if match is not None:
        return "+7" + match.group(1)
    for pattern in (_PHONE_PAREN, _PHONE_SPACED):
        match = pattern.fullmatch(value)
        if match is not None:
            return "+7" + "".join(match.groups())
    raise IntakeValidationError("INVALID_INPUT")


def _comment(raw: str) -> str:
    value = raw.replace("\r\n", "\n")
    if "\r" in value:
        raise IntakeValidationError("INVALID_INPUT")
    return _text(value, minimum=0, maximum=4000, strip=False, allow_lf=True)


def _configuration(config: IntakeConfig) -> None:
    for value in (config.form_version, config.consent_text_version):
        if type(value) is not str or not 1 <= len(value) <= 64 or not value.isascii():
            raise IntakeValidationError("INVALID_CONFIGURATION")
    if type(config.consent_text_sha256) is not str or _SHA256.fullmatch(config.consent_text_sha256) is None:
        raise IntakeValidationError("INVALID_CONFIGURATION")


def normalize_submission(
    raw: Mapping[str, object],
    config: IntakeConfig,
) -> CanonicalSubmission:
    _configuration(config)
    if frozenset(raw) != _FIELDS or any(type(value) is not str for value in raw.values()):
        raise IntakeValidationError("INVALID_INPUT")
    values = {key: value for key, value in raw.items() if isinstance(value, str)}
    if (
        values["form_version"] != config.form_version
        or values["consent_text_version"] != config.consent_text_version
        or values["consent"] != "yes"
    ):
        raise IntakeValidationError("INVALID_INPUT")
    try:
        submission_id = uuid.UUID(values["submission_id"])
    except (ValueError, AttributeError) as exc:
        raise IntakeValidationError("INVALID_INPUT") from exc
    if submission_id.version != 4 or str(submission_id) != values["submission_id"]:
        raise IntakeValidationError("INVALID_INPUT")
    name = _text(values["name"], minimum=1, maximum=100, strip=True)
    vehicle_make = _text(values["vehicle_make"], minimum=0, maximum=100, strip=True)
    vehicle_model = _text(values["vehicle_model"], minimum=0, maximum=100, strip=True)
    vehicle_year = _text(values["vehicle_year"], minimum=0, maximum=4, strip=True)
    if vehicle_year and _YEAR.fullmatch(vehicle_year) is None:
        raise IntakeValidationError("INVALID_INPUT")
    comment = _comment(values["comment"])
    if len(" ".join(filter(None, (vehicle_make, vehicle_model, vehicle_year)))) > 300:
        raise IntakeValidationError("INVALID_INPUT")
    return CanonicalSubmission(
        submission_id=submission_id,
        name=name,
        phone=_phone(values["phone"]),
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        comment=comment,
        consent_text_version=config.consent_text_version,
        consent_text_sha256=config.consent_text_sha256,
    )


def canonical_fingerprint(value: CanonicalSubmission) -> str:
    fields = (
        ("submission_id", str(value.submission_id)),
        ("name", value.name),
        ("phone", value.phone),
        ("vehicle_make", value.vehicle_make),
        ("vehicle_model", value.vehicle_model),
        ("vehicle_year", value.vehicle_year),
        ("comment", value.comment),
        ("consent_text_version", value.consent_text_version),
        ("consent_text_sha256", value.consent_text_sha256),
    )
    envelope = bytearray(b"estakada.service-request.v1\n")
    for key, field_value in fields:
        encoded = field_value.encode("utf-8")
        envelope.extend(f"{key}:{len(encoded)}\n".encode("ascii"))
        envelope.extend(encoded)
        envelope.extend(b"\n")
    return hashlib.sha256(envelope).hexdigest()
