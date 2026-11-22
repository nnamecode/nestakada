from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone
from unittest.mock import patch

from django.db import DatabaseError
from django.test import Client, TestCase

from modules.accounts.api import SESSION_GENERATION_KEY
from modules.accounts.models import StaffRole, User

from ..models import Action, ActorKind, AuditEvent, TargetType


UTC = datetime_timezone.utc
PASSWORD = "Unique!Audit-2026"


class AuditHttpTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(
            username="nesadmin", password=PASSWORD, role=StaffRole.OWNER
        )
        self.employee = User.objects.create_user(
            username="audit-employee", password=PASSWORD, role=StaffRole.EMPLOYEE
        )
        self.path = "/manage/audit/"

    def _login(self, actor: User) -> Client:
        client = Client(); client.force_login(actor)
        session = client.session; session[SESSION_GENERATION_KEY] = actor.generation; session.save()
        return client

    def _events(self, count: int, *, target: uuid.UUID, occurred_at: datetime) -> list[AuditEvent]:
        rows = AuditEvent.objects.bulk_create([
            AuditEvent(
                id=uuid.uuid4(), action=Action.PAGE_RENAMED,
                actor_kind=ActorKind.USER, actor_uuid=self.owner.id,
                actor_role=StaffRole.OWNER, target_type=TargetType.PAGE,
                target_uuid=target, detail={"generation": index + 1},
            )
            for index in range(count)
        ])
        AuditEvent.objects.filter(pk__in=[row.pk for row in rows]).update(occurred_at=occurred_at)
        return rows

    def _event(
        self,
        *,
        target: uuid.UUID,
        occurred_at: datetime,
        action: str = Action.PAGE_RENAMED,
    ) -> AuditEvent:
        detail = {"generation": 1}
        if action == Action.PAGE_PUBLICATION_CHANGED:
            detail["state"] = "PUBLISHED"
        row = AuditEvent.objects.create(
            action=action, actor_kind=ActorKind.USER, actor_uuid=self.owner.id,
            actor_role=StaffRole.OWNER, target_type=TargetType.PAGE,
            target_uuid=target, detail=detail,
        )
        AuditEvent.objects.filter(pk=row.pk).update(occurred_at=occurred_at)
        row.refresh_from_db()
        return row

    def test_owner_only_read_boundary_and_methods_are_private(self):
        anonymous = Client().get(self.path)
        self.assertEqual((anonymous.status_code, anonymous["Location"]), (302, "/manage/login/"))
        employee = self._login(self.employee)
        with patch("modules.audit.web._audit_rows") as projection:
            denied = employee.get(self.path)
        self.assertEqual((denied.status_code, denied.content), (403, b"FORBIDDEN"))
        projection.assert_not_called()
        owner = self._login(self.owner)
        self.assertEqual(owner.get(self.path).status_code, 200)
        for method in ("post", "put", "patch", "delete"):
            response = getattr(owner, method)(self.path)
            self.assertEqual((response.status_code, response["Allow"]), (405, "GET"))
            self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_filters_equal_timestamp_keyset_and_canonical_continuation(self):
        target = uuid.uuid4()
        moment = datetime(2026, 11, 21, 9, 30, 0, 123456, tzinfo=UTC)
        matching = self._events(55, target=target, occurred_at=moment)
        msk_start = datetime(2026, 11, 20, 21, 0, tzinfo=UTC)
        matching.extend((
            self._event(target=target, occurred_at=msk_start),
            self._event(target=target, occurred_at=msk_start + timedelta(days=1, microseconds=-1)),
        ))
        distractors = (
            self._event(target=target, occurred_at=moment,
                        action=Action.PAGE_PUBLICATION_CHANGED),
            self._event(target=uuid.uuid4(), occurred_at=moment),
            self._event(target=target, occurred_at=msk_start - timedelta(microseconds=1)),
            self._event(target=target, occurred_at=msk_start + timedelta(days=1)),
        )
        client = self._login(self.owner)
        response = client.get(self.path, {
            "action": Action.PAGE_RENAMED, "date": "2026-11-21", "target": str(target),
        })
        self.assertEqual(response.status_code, 200)
        first_ids = [row["event"].id for row in response.context["rows"]]
        self.assertEqual(len(first_ids), 50)
        next_url = response.context["next_url"]
        self.assertRegex(
            next_url,
            r"^\?action=PAGE_RENAMED&date=2026-11-21&target=[0-9a-f-]{36}"
            r"&before=[0-9]{8}T[0-9]{6}\.[0-9]{6}Z_[0-9a-f-]{36}$",
        )
        second = client.get(self.path + next_url)
        second_ids = [row["event"].id for row in second.context["rows"]]
        self.assertEqual(len(second_ids), 7)
        actual_order = [
            (row["event"].occurred_at, row["event"].id)
            for current in (response, second)
            for row in current.context["rows"]
        ]
        self.assertEqual(actual_order, sorted(actual_order, reverse=True))
        self.assertFalse(set(first_ids) & set(second_ids))
        self.assertEqual(set(first_ids) | set(second_ids), {row.id for row in matching})
        self.assertFalse((set(first_ids) | set(second_ids)) & {row.id for row in distractors})

    def test_invalid_queries_are_constant_nonreflecting_400(self):
        client = self._login(self.owner)
        invalid = (
            "action=", "action=UNKNOWN", "action=PAGE_RENAMED&action=PAGE_RENAMED",
            "date=2026-02-30", "target=" + uuid.uuid4().hex,
            "before=20261121T093000.123456Z_" + str(uuid.uuid4()).upper(),
            "extra=PRIVATE-CANARY", "action=" + "A" * 513,
        )
        for query in invalid:
            with self.subTest(query=query):
                response = client.get(self.path + "?" + query)
                self.assertEqual((response.status_code, response.content),
                                 (400, b"INVALID_AUDIT_QUERY"))
                self.assertNotContains(response, "PRIVATE-CANARY", status_code=400)
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_safe_snapshot_projection_and_faults_do_not_disclose(self):
        target = uuid.uuid4()
        rows = self._events(1, target=target, occurred_at=datetime(2026, 11, 21, 9, tzinfo=UTC))
        client = self._login(self.owner)
        response = client.get(self.path)
        self.assertContains(response, str(self.owner.id))
        self.assertContains(response, StaffRole.OWNER)
        self.assertNotContains(response, self.owner.username)
        self.assertNotContains(response, '<form method="post" action="/manage/audit/"')
        AuditEvent.objects.filter(pk=rows[0].pk).update(detail={"name": "<script>PRIVATE</script>"})
        corrupt = client.get(self.path)
        self.assertEqual((corrupt.status_code, corrupt.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        AuditEvent.objects.filter(pk=rows[0].pk).update(
            action=Action.AUTH_LOGIN_FAILED,
            actor_kind=ActorKind.ANONYMOUS,
            actor_uuid=None,
            actor_role=None,
            target_type=TargetType.USER,
            target_uuid=None,
            detail={"reason": "x" * 2049},
        )
        oversize = client.get(self.path)
        self.assertEqual((oversize.status_code, oversize.content),
                         (503, b"PRIVATE_DATA_UNAVAILABLE"))
        AuditEvent.objects.filter(pk=rows[0].pk).update(
            action=Action.PAGE_RENAMED,
            actor_kind=ActorKind.USER,
            actor_uuid=self.owner.id,
            actor_role=StaffRole.OWNER,
            target_type=TargetType.PAGE,
            target_uuid=target,
            detail={"generation": 1},
        )
        with patch("modules.audit.web._audit_rows", side_effect=DatabaseError("PRIVATE-DB")):
            fault = client.get(self.path + "?action=PAGE_RENAMED")
        self.assertEqual((fault.status_code, fault.content), (503, b"PRIVATE_DATA_UNAVAILABLE"))
        self.assertNotContains(fault, "PRIVATE", status_code=503)
