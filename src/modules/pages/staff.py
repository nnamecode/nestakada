from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Sequence

from django.db import transaction

from modules.accounts.api import (
    StaffAccessError,
    deactivate_and_bump,
    lock_owner_and_employee_state,
    reactivate_and_bump,
)
from modules.audit.api import Action, ActorRef, TargetType, append_event

from .grants import GrantCommandError
from .models import Page, PageGrant


class StaffLifecycleError(RuntimeError):
    def __init__(self, code: str, *, generation: int | None = None):
        super().__init__(code)
        self.code = code
        self.generation = generation


@dataclass(frozen=True, slots=True)
class StaffLifecycleResult:
    employee_id: uuid.UUID
    generation: int
    is_active: bool
    removed_grants: int


def _groups(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise StaffLifecycleError("GRANT_CORRUPT")
    groups = tuple(value)
    if groups not in (("prices",), ("text",), ("text", "prices")):
        raise StaffLifecycleError("GRANT_CORRUPT")
    return groups


def staff_grants_digest(
    staff_id: uuid.UUID,
    grants: Sequence[tuple[uuid.UUID, Sequence[str]]],
) -> str:
    if not isinstance(staff_id, uuid.UUID):
        raise StaffLifecycleError("INVALID_BASIS")
    ordered = sorted(grants, key=lambda item: str(item[0]))
    if len({page_id for page_id, _ in ordered}) != len(ordered):
        raise StaffLifecycleError("GRANT_CORRUPT")
    items = []
    for page_id, raw_groups in ordered:
        if not isinstance(page_id, uuid.UUID):
            raise StaffLifecycleError("GRANT_CORRUPT")
        groups = _groups(raw_groups)
        encoded_groups = ",".join(f'"{group}"' for group in groups)
        items.append(f'{{"page_id":"{page_id}","groups":[{encoded_groups}]}}')
    envelope = (
        f'{{"domain":"estakada.staff-grants.v1","staff_id":"{staff_id}",'
        f'"grants":[{",".join(items)}]}}\n'
    )
    return hashlib.sha256(envelope.encode("utf-8")).hexdigest()


def _basis(generation: object, digest: object | None = None) -> tuple[int, str | None]:
    if type(generation) is not int or generation < 1:
        raise StaffLifecycleError("INVALID_BASIS")
    if digest is not None and (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise StaffLifecycleError("INVALID_BASIS")
    return generation, digest


def deactivate_employee(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    base_user_generation: object,
    base_grants_digest: object,
) -> StaffLifecycleResult:
    base_generation, base_digest = _basis(base_user_generation, base_grants_digest)
    try:
        with transaction.atomic():
            actor, employee = lock_owner_and_employee_state(
                actor_id=actor_id,
                session_generation=session_generation,
                employee_id=employee_id,
                require_employee_active=True,
            )
            if employee.generation != base_generation:
                raise StaffLifecycleError("STALE_STAFF", generation=employee.generation)
            page_ids = list(
                PageGrant.objects.filter(staff=employee)
                .order_by("page_id")
                .values_list("page_id", flat=True)
            )
            if page_ids:
                locked_pages = list(
                    Page.objects.select_for_update().filter(pk__in=page_ids).order_by("id")
                )
                if [page.id for page in locked_pages] != page_ids:
                    raise StaffLifecycleError("GRANT_CORRUPT")
            grants = list(
                PageGrant.objects.select_for_update()
                .filter(staff=employee)
                .order_by("page_id")
            )
            current = [(grant.page_id, _groups(grant.groups)) for grant in grants]
            current_digest = staff_grants_digest(employee.id, current)
            if current_digest != base_digest:
                raise StaffLifecycleError("STALE_STAFF", generation=employee.generation)
            removed = len(grants)
            if grants:
                PageGrant.objects.filter(pk__in=[grant.pk for grant in grants]).delete()
            deactivate_and_bump(employee=employee)
            append_event(
                action=Action.STAFF_DEACTIVATED,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.USER,
                target_uuid=employee.id,
                detail={"generation": employee.generation, "count": removed},
            )
            return StaffLifecycleResult(employee.id, employee.generation, False, removed)
    except StaffAccessError as exc:
        raise StaffLifecycleError(exc.code) from exc
    except GrantCommandError as exc:
        raise StaffLifecycleError(exc.code) from exc


def reactivate_employee(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    base_user_generation: object,
) -> StaffLifecycleResult:
    base_generation, _ = _basis(base_user_generation)
    try:
        with transaction.atomic():
            actor, employee = lock_owner_and_employee_state(
                actor_id=actor_id,
                session_generation=session_generation,
                employee_id=employee_id,
                require_employee_active=False,
            )
            if employee.generation != base_generation:
                raise StaffLifecycleError("STALE_STAFF", generation=employee.generation)
            grants = list(PageGrant.objects.select_for_update().filter(staff=employee)[:1])
            if grants:
                raise StaffLifecycleError("GRANT_CORRUPT")
            reactivate_and_bump(employee=employee)
            append_event(
                action=Action.STAFF_REACTIVATED,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.USER,
                target_uuid=employee.id,
                detail={"generation": employee.generation},
            )
            return StaffLifecycleResult(employee.id, employee.generation, True, 0)
    except StaffAccessError as exc:
        raise StaffLifecycleError(exc.code) from exc
