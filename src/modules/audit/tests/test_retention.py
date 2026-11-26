from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, connection, connections, models
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

    def test_two_commands_observe_lock_wait_then_delete_disjoint_batches(self):
        old_rows = self._old_rows(10_001)
        old_ids = {row.pk for row in old_rows}
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
        user = User.objects.create_user(username="retention-concurrency", role=StaffRole.EMPLOYEE)
        user_before = User.objects.values().get(pk=user.pk)

        first_locked = threading.Event()
        second_entered = threading.Event()
        release_first = threading.Event()
        observer_backoff = threading.Event()
        worker_pids: dict[str, int] = {}
        worker_outputs: dict[str, str] = {}
        worker_errors: dict[str, str] = {}
        fetch_counts = {"audit-retention-1": 0, "audit-retention-2": 0}
        original_fetch_all = models.QuerySet._fetch_all

        def controlled_fetch_all(queryset):
            worker_name = threading.current_thread().name
            is_lock_query = queryset.model is AuditEvent and queryset.query.select_for_update is True
            if not is_lock_query:
                return original_fetch_all(queryset)
            where_children = tuple(queryset.query.where.children)
            target = getattr(getattr(where_children[0], "lhs", None), "target", None) if where_children else None
            exact_shape = (
                worker_name in fetch_counts
                and queryset.query.low_mark == 0
                and queryset.query.high_mark == cleanup_audit.BATCH_SIZE
                and tuple(queryset.query.order_by) == ("occurred_at", "id")
                and tuple(queryset.query.values_select) == ("id",)
                and len(where_children) == 1
                and getattr(where_children[0], "lookup_name", None) == "lt"
                and getattr(target, "name", None) == "occurred_at"
            )
            if not exact_shape:
                raise RuntimeError("unexpected retention lock query")
            if queryset._result_cache is not None:
                return original_fetch_all(queryset)
            fetch_counts[worker_name] += 1
            if fetch_counts[worker_name] != 1:
                raise RuntimeError("unexpected retention lock query")
            if worker_name == "audit-retention-2":
                second_entered.set()
            original_fetch_all(queryset)
            if worker_name == "audit-retention-1":
                first_locked.set()
                if not release_first.wait(timeout=10):
                    raise RuntimeError("retention lock release timeout")

        def run_worker(name: str) -> None:
            close_old_connections()
            output = StringIO()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    worker_pids[name] = int(cursor.fetchone()[0])
                call_command("cleanup_audit", stdout=output)
                worker_outputs[name] = output.getvalue()
            except BaseException as exc:  # fixed type only; never retain private message
                worker_errors[name] = type(exc).__name__
            finally:
                connections.close_all()

        first = threading.Thread(target=run_worker, args=("first",), name="audit-retention-1")
        second = threading.Thread(target=run_worker, args=("second",), name="audit-retention-2")
        observed_lock_wait = False
        probes = 0
        with (
            patch.object(cleanup_audit.timezone, "now", return_value=NOW),
            patch.object(models.QuerySet, "_fetch_all", controlled_fetch_all),
        ):
            first.start()
            try:
                self.assertTrue(first_locked.wait(timeout=10))
                second.start()
                self.assertTrue(second_entered.wait(timeout=10))
                deadline = time.monotonic() + 10
                while probes < 500 and time.monotonic() < deadline:
                    probes += 1
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                            [worker_pids["second"]],
                        )
                        row = cursor.fetchone()
                    if row == ("Lock",):
                        observed_lock_wait = True
                        break
                    observer_backoff.wait(timeout=0.01)
            finally:
                release_first.set()
                first.join(timeout=15)
                if second.ident is not None:
                    second.join(timeout=15)
                connection.close()

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertTrue(observed_lock_wait)
        self.assertGreaterEqual(probes, 1)
        self.assertEqual(worker_errors, {})
        self.assertEqual(fetch_counts, {"audit-retention-1": 1, "audit-retention-2": 1})
        self.assertEqual(
            sorted(worker_outputs.values()),
            ["AUDIT_RETENTION_OK deleted=5000\n", "AUDIT_RETENTION_OK deleted=5000\n"],
        )
        remaining_old = set(
            AuditEvent.objects.filter(
                pk__in=old_ids,
                occurred_at__lt=NOW - timedelta(days=180),
            ).values_list("id", flat=True)
        )
        self.assertEqual(len(remaining_old), 1)
        batches = list(AuditEvent.objects.filter(action=Action.AUDIT_RETENTION_BATCH))
        self.assertEqual(len(batches), 2)
        self.assertEqual([row.detail for row in batches].count({"reason": "RETENTION", "count": 5000}), 2)
        self.assertEqual(sum(row.detail["count"] for row in batches), 10_000)
        self.assertEqual(AuditEvent.objects.filter(pk__in=(boundary.pk, recent.pk)).count(), 2)
        self.assertEqual(User.objects.values().get(pk=user.pk), user_before)
