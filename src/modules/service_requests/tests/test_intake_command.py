from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import IntegrityError
from django.test import TestCase

from modules.audit.models import Action, ActorKind, AuditEvent, TargetType
from modules.service_requests.commands import (
    IntakePersistenceError,
    IntakeResult,
    accept_submission,
)
from modules.service_requests.intake import IntakeConfig, normalize_submission
from modules.service_requests.models import ServiceRequest


CONFIG = IntakeConfig(
    form_version="request-v1",
    consent_text_version="consent-v1",
    consent_text_sha256="a" * 64,
)


def _submission(*, name: str = "Иван"):
    return normalize_submission(
        {
            "form_version": "request-v1",
            "submission_id": "12345678-1234-4abc-8def-1234567890ab",
            "name": name,
            "phone": "+7 (999) 123-45-67",
            "vehicle_make": "Лада",
            "vehicle_model": "Веста",
            "vehicle_year": "2024",
            "comment": "Не заводится",
            "consent_text_version": "consent-v1",
            "consent": "yes",
        },
        CONFIG,
    )


class IntakeCommandTests(TestCase):
    def test_accept_creates_one_row_safe_audit_and_one_commit_callback(self) -> None:
        callback = Mock()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = accept_submission(_submission(), after_commit=callback)
        self.assertEqual(result, IntakeResult.ACCEPTED)
        self.assertEqual(len(callbacks), 1)
        callback.assert_called_once_with(_submission().submission_id)
        row = ServiceRequest.objects.get()
        self.assertEqual(row.id, _submission().submission_id)
        self.assertEqual(row.phone, "+79991234567")
        event = AuditEvent.objects.get()
        self.assertEqual(
            (event.action, event.actor_kind, event.target_type, event.target_uuid, event.detail),
            (
                Action.SERVICE_REQUEST_ACCEPTED,
                ActorKind.ANONYMOUS,
                TargetType.SERVICE_REQUEST,
                row.id,
                {},
            ),
        )

    def test_equal_replay_is_accepted_without_second_side_effect(self) -> None:
        callback = Mock()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(
                accept_submission(_submission(), after_commit=callback),
                IntakeResult.ACCEPTED,
            )
        callback.reset_mock()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = accept_submission(_submission(), after_commit=callback)
        self.assertEqual(result, IntakeResult.ACCEPTED_REPLAY)
        self.assertEqual(len(callbacks), 0)
        callback.assert_not_called()
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_mismatched_replay_is_constant_conflict_without_side_effect(self) -> None:
        with self.captureOnCommitCallbacks(execute=True):
            accept_submission(_submission(), after_commit=Mock())
        callback = Mock()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            result = accept_submission(_submission(name="Пётр"), after_commit=callback)
        self.assertEqual(result, IntakeResult.CONFLICT)
        self.assertEqual(len(callbacks), 0)
        callback.assert_not_called()
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_audit_failure_rolls_back_row_and_does_not_register_callback(self) -> None:
        callback = Mock()
        with (
            patch(
                "modules.service_requests.commands.append_event",
                side_effect=RuntimeError("audit fault"),
            ),
            self.captureOnCommitCallbacks(execute=True) as callbacks,
            self.assertRaises(RuntimeError),
        ):
            accept_submission(_submission(), after_commit=callback)
        self.assertEqual(len(callbacks), 0)
        callback.assert_not_called()
        self.assertEqual(ServiceRequest.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_callback_failure_cannot_change_committed_acceptance(self) -> None:
        callback = Mock(side_effect=RuntimeError("private transport detail"))
        with self.captureOnCommitCallbacks(execute=True):
            result = accept_submission(_submission(), after_commit=callback)
        self.assertEqual(result, IntakeResult.ACCEPTED)
        callback.assert_called_once()
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_non_primary_key_integrity_error_is_not_a_replay(self) -> None:
        private_detail = "Иван +79991234567 private comment"
        error = IntegrityError(private_detail)
        cause = Exception(private_detail)
        cause.diag = SimpleNamespace(  # type: ignore[attr-defined]
            constraint_name="request_phone_canonical"
        )
        error.__cause__ = cause
        with patch(
            "modules.service_requests.commands.ServiceRequest.objects.create",
            side_effect=error,
        ):
            with self.assertRaises(IntakePersistenceError) as raised:
                accept_submission(_submission(), after_commit=Mock())
        self.assertEqual(str(raised.exception), "PERSISTENCE_FAILURE")
        self.assertNotIn(private_detail, str(raised.exception))
        self.assertIs(raised.exception.__suppress_context__, True)
        self.assertEqual(ServiceRequest.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
