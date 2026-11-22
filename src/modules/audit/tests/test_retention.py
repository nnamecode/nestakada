from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, models
from django.test import TransactionTestCase

from modules.accounts.models import StaffRole, User

from ..management.commands import cleanup_audit
from ..models import Action, ActorKind, AuditEvent, TargetType


UTC = datetime_timezone.utc
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


class AuditRetentionTests(TransactionTestCase):
    def _event(self) -> AuditEvent:
        return AuditEvent(
            id=uuid.uuid4(), action=Action.PAGE_RENAMED,
            actor_kind=ActorKind.USER, actor_uuid=uuid.uuid4(),
            actor_role=StaffRole.OWNER, target_type=TargetType.PAGE,
            target_uuid=uuid.uuid4(), detail={"generation": 1},
        )

    def _old_rows(self, count: int) -> list[AuditEvent]:
        rows = AuditEvent.objects.bulk_create([self._event() for _ in range(count)])
        AuditEvent.objects.filter(pk__in=[row.pk for row in rows]).update(
            occurred_at=NOW - timedelta(days=181)
        )
        return rows

    def _run(self) -> str:
        output = StringIO()
        with patch.object(cleanup_audit.timezone, "now", return_value=NOW):
            call_command("cleanup_audit", stdout=output)
        return output.getvalue()

    def test_batch_boundary_repeat_and_zero_event_are_exact(self):
        old_rows = self._old_rows(5_001)
        survivor = max(row.pk for row in old_rows)
        boundary = AuditEvent.objects.create(**{
            key: value for key, value in self._event().__dict__.items()
            if not key.startswith("_") and key not in {"id", "occurred_at"}
        })
        recent = AuditEvent.objects.create(**{
            key: value for key, value in self._event().__dict__.items()
            if not key.startswith("_") and key not in {"id", "occurred_at"}
        })
        AuditEvent.objects.filter(pk=boundary.pk).update(occurred_at=NOW - timedelta(days=180))
        AuditEvent.objects.filter(pk=recent.pk).update(occurred_at=NOW - timedelta(days=1))
        self.assertEqual(self._run(), "AUDIT_RETENTION_OK deleted=5000\n")
        first = AuditEvent.objects.get(action=Action.AUDIT_RETENTION_BATCH)
        self.assertEqual(first.detail, {"reason": "RETENTION", "count": 5000})
        self.assertEqual(
            set(AuditEvent.objects.filter(occurred_at__lt=NOW - timedelta(days=180))
                .values_list("id", flat=True)),
            {survivor},
        )
        self.assertEqual(
            (first.actor_kind, first.actor_uuid, first.actor_role, first.target_type,
             first.target_uuid, first.secondary_uuid),
            (ActorKind.SYSTEM, None, None, TargetType.AUDIT, None, None),
        )
        self.assertEqual(self._run(), "AUDIT_RETENTION_OK deleted=1\n")
        batches = list(AuditEvent.objects.filter(action=Action.AUDIT_RETENTION_BATCH))
        self.assertEqual(
            sorted((row.detail["reason"], row.detail["count"]) for row in batches),
            [("RETENTION", 1), ("RETENTION", 5000)],
        )
        for row in batches:
            self.assertEqual(
                (row.actor_kind, row.actor_uuid, row.actor_role, row.target_type,
                 row.target_uuid, row.secondary_uuid),
                (ActorKind.SYSTEM, None, None, TargetType.AUDIT, None, None),
            )
        self.assertEqual(self._run(), "AUDIT_RETENTION_OK deleted=0\n")
        self.assertEqual(AuditEvent.objects.filter(action=Action.AUDIT_RETENTION_BATCH).count(), 2)
        self.assertEqual(AuditEvent.objects.filter(pk__in=(boundary.pk, recent.pk)).count(), 2)

    def test_command_changes_only_audit_and_has_no_scope_options(self):
        user = User.objects.create_user(username="retention-user", role=StaffRole.EMPLOYEE)
        self._old_rows(1)
        before = User.objects.values().get(pk=user.pk)
        self.assertEqual(self._run(), "AUDIT_RETENTION_OK deleted=1\n")
        self.assertEqual(User.objects.values().get(pk=user.pk), before)
        self.assertNotIn("add_arguments", cleanup_audit.Command.__dict__)

    def test_delete_fault_rolls_back_with_constant_error(self):
        rows = self._old_rows(2)
        actual_delete = models.QuerySet.delete

        def delete_then_fail(queryset):
            actual_delete(queryset)
            raise DatabaseError("PRIVATE-DELETE")

        with (
            patch.object(cleanup_audit.timezone, "now", return_value=NOW),
            patch.object(models.QuerySet, "delete", delete_then_fail),
            self.assertRaises(CommandError) as raised,
        ):
            call_command("cleanup_audit")
        self.assertEqual(str(raised.exception), cleanup_audit.FAILURE)
        self.assertEqual(AuditEvent.objects.filter(pk__in=[row.pk for row in rows]).count(), 2)
        self.assertFalse(AuditEvent.objects.filter(action=Action.AUDIT_RETENTION_BATCH).exists())

    def test_audit_insert_fault_rolls_back_deleted_rows(self):
        rows = self._old_rows(2)
        with (
            patch.object(cleanup_audit.timezone, "now", return_value=NOW),
            patch.object(cleanup_audit, "append_event", side_effect=DatabaseError("PRIVATE-AUDIT")),
            self.assertRaises(CommandError) as raised,
        ):
            call_command("cleanup_audit")
        self.assertEqual(str(raised.exception), cleanup_audit.FAILURE)
        self.assertEqual(AuditEvent.objects.filter(pk__in=[row.pk for row in rows]).count(), 2)
        self.assertFalse(AuditEvent.objects.filter(action=Action.AUDIT_RETENTION_BATCH).exists())
