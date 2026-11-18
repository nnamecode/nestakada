import uuid

from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.audit.models import Action, ActorKind, AuditEvent, TargetType


class AuditContractTests(TestCase):
    def test_page_content_event_accepts_only_safe_exact_detail(self) -> None:
        event = AuditEvent(
            action=Action.PAGE_CONTENT_SAVED,
            actor_kind=ActorKind.USER,
            actor_uuid=uuid.uuid4(),
            actor_role="OWNER",
            target_type=TargetType.PAGE,
            target_uuid=uuid.uuid4(),
            detail={
                "operation_id": str(uuid.uuid4()),
                "generation": 2,
                "current_hash": "a" * 64,
            },
        )
        event.full_clean()

    def test_private_or_unknown_detail_is_rejected(self) -> None:
        event = AuditEvent(
            action=Action.PAGE_CONTENT_SAVED,
            actor_kind=ActorKind.USER,
            actor_uuid=uuid.uuid4(),
            actor_role="OWNER",
            target_type=TargetType.PAGE,
            target_uuid=uuid.uuid4(),
            detail={
                "operation_id": str(uuid.uuid4()),
                "generation": 2,
                "current_hash": "a" * 64,
                "name": "private",
            },
        )
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_anonymous_request_acceptance_has_no_actor_snapshot(self) -> None:
        event = AuditEvent(
            action=Action.SERVICE_REQUEST_ACCEPTED,
            actor_kind=ActorKind.ANONYMOUS,
            target_type=TargetType.SERVICE_REQUEST,
            target_uuid=uuid.uuid4(),
            detail={},
        )
        event.full_clean()

    def test_employee_cannot_delete_service_request(self) -> None:
        event = AuditEvent(
            action=Action.SERVICE_REQUEST_DELETED,
            actor_kind=ActorKind.USER,
            actor_uuid=uuid.uuid4(),
            actor_role="EMPLOYEE",
            target_type=TargetType.SERVICE_REQUEST,
            target_uuid=uuid.uuid4(),
            detail={"reason": "OWNER"},
        )
        with self.assertRaises(ValidationError):
            event.full_clean()
