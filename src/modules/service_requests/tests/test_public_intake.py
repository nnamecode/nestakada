from __future__ import annotations

import hashlib
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

from django.db import transaction
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings

from modules.audit.models import Action, AuditEvent
from modules.service_requests.ledger import PrimaryLedger, SyntheticIndependentLedger
from modules.service_requests.models import ServiceRequest
from modules.service_requests.public import (
    form_projection,
    intake_configuration,
    submit_service_request,
)


CONSENT = "Я согласен на обработку данных в течение 30 дней."
PRIVACY = "Данные доступны владельцу и сотрудникам; копия передаётся в Telegram."
ENABLED = {
    "SERVICE_REQUESTS_ENABLED": True,
    "SERVICE_REQUEST_FORM_VERSION": "v1",
    "SERVICE_REQUEST_CONSENT_VERSION": "legal-v1",
    "SERVICE_REQUEST_CONSENT_TEXT": CONSENT,
    "SERVICE_REQUEST_CONSENT_SHA256": hashlib.sha256(CONSENT.encode()).hexdigest(),
    "SERVICE_REQUEST_PRIVACY_TEXT": PRIVACY,
    "SERVICE_REQUEST_PRIVACY_SHA256": hashlib.sha256(PRIVACY.encode()).hexdigest(),
    "SERVICE_REQUEST_TELEGRAM_TOKEN_FILE": "/run/secrets/telegram-token",
    "SERVICE_REQUEST_TELEGRAM_CHAT_ID": "-1001234567890",
    "SERVICE_REQUEST_LEDGER_ROOT": "/srv/estakada/private/request-ledger",
    "SERVICE_REQUEST_INDEPENDENT_ADAPTER": "external-v1",
}


@override_settings(**ENABLED)
class PublicIntakeIntegrationTests(TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name))
        self.independent = SyntheticIndependentLedger()
        with self.ledger.locked() as session:
            self.independent.publish_and_verify(session.snapshot())
        self.authority = patch(
            "modules.service_requests.public._request_authority",
            return_value=(self.ledger, self.independent),
        )
        self.authority.start()
        self.addCleanup(self.authority.stop)
        self.factory = RequestFactory()

    def _data(self):
        return {
            "form_version": "v1",
            "submission_id": str(uuid.uuid4()),
            "name": "Иван",
            "phone": "+7 (999) 123-45-67",
            "vehicle_make": "",
            "vehicle_model": "",
            "vehicle_year": "",
            "comment": "Synthetic only",
            "consent_text_version": "legal-v1",
            "consent": "yes",
        }

    def test_full_exact_configuration_and_ready_authority_project_form(self) -> None:
        config = intake_configuration()
        self.assertIsNotNone(config)
        projection = form_projection()
        self.assertEqual(projection["form_version"], "v1")
        self.assertEqual(projection["consent_text_version"], "legal-v1")
        self.assertEqual(projection["consent_text"], CONSENT)
        self.assertEqual(projection["privacy_text"], PRIVACY)
        self.assertEqual(str(uuid.UUID(projection["submission_id"])), projection["submission_id"])

    def test_valid_post_is_guarded_committed_once_then_attempts_telegram(self) -> None:
        data = self._data()
        request = self.factory.post(
            "/request/submit/",
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )
        with patch("modules.service_requests.public.attempt_telegram_delivery") as delivery:
            with self.captureOnCommitCallbacks(execute=True):
                response = submit_service_request(request)
        self.assertEqual((response.status_code, response.content), (200, b"REQUEST_ACCEPTED"))
        self.assertEqual(response["Cache-Control"], "private, no-store")
        row = ServiceRequest.objects.get()
        self.assertEqual((row.id, row.phone), (uuid.UUID(data["submission_id"]), "+79991234567"))
        self.assertEqual(AuditEvent.objects.get().action, Action.SERVICE_REQUEST_ACCEPTED)
        delivery.assert_called_once_with(row.id, intake_configuration().telegram)

    def test_missing_authority_rejects_before_form_parse_or_mutation(self) -> None:
        with patch("modules.service_requests.public._request_authority", return_value=None):
            self.assertIsNone(form_projection())
            response = submit_service_request(
                self.factory.post("/request/submit/", b"PRIVATE=VALUE",
                                  content_type="application/x-www-form-urlencoded")
            )
        self.assertEqual((response.status_code, response.content), (503, b"REQUESTS_UNAVAILABLE"))
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())

    def test_duplicate_or_extra_wire_fields_fail_without_mutation(self) -> None:
        request = self.factory.post(
            "/request/submit/",
            "form_version=v1&form_version=v1&extra=PRIVATE",
            content_type="application/x-www-form-urlencoded",
        )
        response = submit_service_request(request)
        self.assertEqual((response.status_code, response.content), (400, b"INVALID_REQUEST_INPUT"))
        self.assertFalse(ServiceRequest.objects.exists())


class PublicIntakeConfigurationFailureTests(TestCase):
    @override_settings(**(ENABLED | {"SERVICE_REQUEST_CONSENT_SHA256": "f" * 64}))
    def test_hash_mismatch_fails_closed(self) -> None:
        self.assertIsNone(intake_configuration())

    @override_settings(**(ENABLED | {"SERVICE_REQUEST_INDEPENDENT_ADAPTER": "disabled"}))
    def test_disabled_or_unknown_adapter_fails_closed(self) -> None:
        self.assertIsNone(intake_configuration())

    def test_malformed_unicode_fails_closed_without_exception(self) -> None:
        for field in (
            "SERVICE_REQUEST_FORM_VERSION",
            "SERVICE_REQUEST_CONSENT_TEXT",
            "SERVICE_REQUEST_PRIVACY_TEXT",
        ):
            with self.subTest(field=field), self.settings(**(ENABLED | {field: "\ud800"})):
                self.assertIsNone(intake_configuration())


@override_settings(**ENABLED)
class PublicIntakeCommitBoundaryTests(TransactionTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = PrimaryLedger(Path(self.temporary.name))
        self.independent = SyntheticIndependentLedger()
        with self.ledger.locked() as session:
            self.independent.publish_and_verify(session.snapshot())
        self.authority = patch(
            "modules.service_requests.public._request_authority",
            return_value=(self.ledger, self.independent),
        )
        self.authority.start()
        self.addCleanup(self.authority.stop)
        self.factory = RequestFactory()

    def _request(self):
        data = {
            "form_version": "v1",
            "submission_id": str(uuid.uuid4()),
            "name": "Иван",
            "phone": "+79991234567",
            "vehicle_make": "",
            "vehicle_model": "",
            "vehicle_year": "",
            "comment": "Synthetic",
            "consent_text_version": "legal-v1",
            "consent": "yes",
        }
        return self.factory.post(
            "/request/submit/",
            urlencode(data),
            content_type="application/x-www-form-urlencoded",
        )

    def test_delivery_waits_for_outer_commit(self) -> None:
        with patch("modules.service_requests.public.attempt_telegram_delivery") as delivery:
            with transaction.atomic():
                response = submit_service_request(self._request())
                self.assertEqual(response.status_code, 200)
                delivery.assert_not_called()
            delivery.assert_called_once()
        self.assertEqual(ServiceRequest.objects.count(), 1)

    def test_outer_rollback_discards_row_audit_and_delivery(self) -> None:
        with patch("modules.service_requests.public.attempt_telegram_delivery") as delivery:
            with self.assertRaisesMessage(RuntimeError, "rollback"):
                with transaction.atomic():
                    response = submit_service_request(self._request())
                    self.assertEqual(response.status_code, 200)
                    delivery.assert_not_called()
                    raise RuntimeError("rollback")
            delivery.assert_not_called()
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertFalse(AuditEvent.objects.exists())
