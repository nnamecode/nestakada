from __future__ import annotations

import uuid

from django.test import SimpleTestCase

from modules.service_requests.intake import (
    IntakeConfig,
    IntakeValidationError,
    canonical_fingerprint,
    normalize_submission,
)


FORM_VERSION = "request-v1"
CONSENT_VERSION = "consent-v1"
CONSENT_SHA256 = "a" * 64


def _config() -> IntakeConfig:
    return IntakeConfig(
        form_version=FORM_VERSION,
        consent_text_version=CONSENT_VERSION,
        consent_text_sha256=CONSENT_SHA256,
    )


def _raw(**overrides: str) -> dict[str, str]:
    values = {
        "form_version": FORM_VERSION,
        "submission_id": "12345678-1234-4abc-8def-1234567890ab",
        "name": " Иван Иванов ",
        "phone": "+7 (999) 123-45-67",
        "vehicle_make": " Лада ",
        "vehicle_model": " Веста ",
        "vehicle_year": " 2024 ",
        "comment": "Первая строка\nВторая строка",
        "consent_text_version": CONSENT_VERSION,
        "consent": "yes",
    }
    values.update(overrides)
    return values


class IntakeValidationTests(SimpleTestCase):
    def test_normalizes_closed_projection(self) -> None:
        value = normalize_submission(_raw(), _config())
        self.assertEqual(value.submission_id, uuid.UUID("12345678-1234-4abc-8def-1234567890ab"))
        self.assertEqual(value.name, "Иван Иванов")
        self.assertEqual(value.phone, "+79991234567")
        self.assertEqual((value.vehicle_make, value.vehicle_model, value.vehicle_year), ("Лада", "Веста", "2024"))
        self.assertEqual(value.comment, "Первая строка\nВторая строка")
        self.assertEqual(value.consent_text_version, CONSENT_VERSION)
        self.assertEqual(value.consent_text_sha256, CONSENT_SHA256)

    def test_rejects_missing_extra_and_non_string_fields(self) -> None:
        missing = _raw()
        missing.pop("comment")
        extra = _raw(source="campaign")
        invalid_type: dict[str, object] = dict(_raw())
        invalid_type["name"] = ["Иван"]
        for value in (missing, extra, invalid_type):
            with self.subTest(keys=tuple(value)), self.assertRaises(IntakeValidationError):
                normalize_submission(value, _config())  # type: ignore[arg-type]

    def test_exact_versions_consent_and_submission_uuid(self) -> None:
        for field, value in (
            ("form_version", "request-v2"),
            ("consent_text_version", "consent-v0"),
            ("consent", "on"),
            ("consent", "YES"),
            ("submission_id", "{12345678-1234-4abc-8def-1234567890ab}"),
            ("submission_id", "1234567812344abc8def1234567890ab"),
            ("submission_id", "12345678-1234-1abc-8def-1234567890ab"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(IntakeValidationError):
                normalize_submission(_raw(**{field: value}), _config())

    def test_phone_accepts_only_closed_russian_display_matrix(self) -> None:
        accepted = {
            "+79991234567": "+79991234567",
            "+7 (999) 123-45-67": "+79991234567",
            "+7 999 123-45-67": "+79991234567",
            "89991234567": "+79991234567",
            "8 (999) 123-45-67": "+79991234567",
            "8 999 123-45-67": "+79991234567",
        }
        for raw, canonical in accepted.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_submission(_raw(phone=raw), _config()).phone, canonical)
        for raw in (
            "+1 (999) 123-45-67",
            "+7 999 123 45 67",
            "+7(999)123-45-67",
            "+7 (999) 123-4567",
            "+7 (９９９) 123-45-67",
            "+7999123456",
            "+799912345678",
        ):
            with self.subTest(raw=raw), self.assertRaises(IntakeValidationError):
                normalize_submission(_raw(phone=raw), _config())

    def test_character_limits_controls_nfc_and_vehicle_cap(self) -> None:
        accepted = normalize_submission(
            _raw(name="я" * 100, vehicle_make="м" * 100, vehicle_model="о" * 100, comment="к" * 4000),
            _config(),
        )
        self.assertEqual(len(accepted.comment), 4000)
        crlf = normalize_submission(_raw(comment="к" * 3999 + "\r\n"), _config())
        self.assertEqual(crlf.comment, "к" * 3999 + "\n")
        for field, value in (
            ("name", "я" * 101),
            ("name", " "),
            ("name", "Иван\tИванов"),
            ("name", "Ива\u0301н"),
            ("vehicle_make", "м" * 101),
            ("vehicle_model", "о" * 101),
            ("vehicle_year", "２０２４"),
            ("comment", "к" * 4001),
            ("comment", "строка\rстрока"),
            ("comment", "строка\x00строка"),
            ("comment", "к" * 4000 + "\r\n"),
        ):
            with self.subTest(field=field), self.assertRaises(IntakeValidationError):
                normalize_submission(_raw(**{field: value}), _config())
    def test_fingerprint_is_stable_and_length_unambiguous(self) -> None:
        first = normalize_submission(_raw(vehicle_make="ab", vehicle_model="c"), _config())
        same = normalize_submission(_raw(vehicle_make=" ab ", vehicle_model=" c "), _config())
        shifted = normalize_submission(_raw(vehicle_make="a", vehicle_model="bc"), _config())
        self.assertEqual(canonical_fingerprint(first), canonical_fingerprint(same))
        self.assertNotEqual(canonical_fingerprint(first), canonical_fingerprint(shifted))
        self.assertRegex(canonical_fingerprint(first), r"\A[0-9a-f]{64}\Z")
