from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Sequence

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.accounts.api import StaffAccessError, lock_owner_and_employee
from modules.audit.api import Action, ActorRef, TargetType, append_event

from .models import Page, PageGrant, PageKind


_TEXT_KINDS = frozenset({
    PageKind.SERVICE_SECTION_OVERVIEW,
    PageKind.SERVICE_DETAIL,
    PageKind.ARTICLE,
    PageKind.LEGACY_NEWS_ARTICLE,
})
_CANONICAL_GROUPS = ((), ("prices",), ("text",), ("text", "prices"))


class GrantCommandError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        user_generation: int | None = None,
        grant_hash: str | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.user_generation = user_generation
        self.grant_hash = grant_hash


@dataclass(frozen=True, slots=True)
class GrantResult:
    user_generation: int
    grant_hash: str
    groups: tuple[str, ...]


def eligible_grant_groups(page_kind: str) -> tuple[str, ...]:
    if page_kind == PageKind.SERVICE_DETAIL:
        return ("text", "prices")
    if page_kind in _TEXT_KINDS:
        return ("text",)
    return ()


def _canonical_groups(groups: object, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(groups, (list, tuple)):
        raise GrantCommandError("INVALID_GROUPS")
    canonical = tuple(groups)
    if canonical not in _CANONICAL_GROUPS or (not allow_empty and not canonical):
        raise GrantCommandError("INVALID_GROUPS")
    return canonical


def grant_state_hash(
    staff_id: uuid.UUID,
    page_id: uuid.UUID,
    groups: Sequence[str],
) -> str:
    if not isinstance(staff_id, uuid.UUID) or not isinstance(page_id, uuid.UUID):
        raise GrantCommandError("INVALID_BASIS")
    canonical = _canonical_groups(groups)
    if canonical:
        encoded_groups = ",".join(f'"{group}"' for group in canonical)
        state = "PRESENT"
    else:
        encoded_groups = ""
        state = "ABSENT"
    envelope = (
        f'{{"domain":"estakada.page-grant.v1","staff_id":"{staff_id}",'
        f'"page_id":"{page_id}","state":"{state}","groups":[{encoded_groups}]}}\n'
    )
    return hashlib.sha256(envelope.encode("ascii")).hexdigest()


def _basis(base_user_generation: object, base_grant_hash: object) -> tuple[int, str]:
    if type(base_user_generation) is not int or base_user_generation < 1:
        raise GrantCommandError("INVALID_BASIS")
    if (
        not isinstance(base_grant_hash, str)
        or len(base_grant_hash) != 64
        or any(char not in "0123456789abcdef" for char in base_grant_hash)
    ):
        raise GrantCommandError("INVALID_BASIS")
    return base_user_generation, base_grant_hash


def _locked_page(page_id: object) -> Page:
    try:
        return Page.objects.select_for_update().get(pk=page_id)
    except (Page.DoesNotExist, TypeError, ValueError, ValidationError):
        raise GrantCommandError("PAGE_NOT_FOUND") from None


def _mutate_page_grant(
    *,
    actor_id: object,
    session_generation: object,
    staff_id: object,
    page_id: object,
    desired_groups: object,
    base_user_generation: object,
    base_grant_hash: object,
) -> GrantResult:
    desired = _canonical_groups(desired_groups)
    base_generation, base_hash = _basis(base_user_generation, base_grant_hash)
    try:
        with transaction.atomic():
            actor, employee = lock_owner_and_employee(
                actor_id=actor_id,
                session_generation=session_generation,
                employee_id=staff_id,
            )
            page = _locked_page(page_id)
            grant = (
                PageGrant.objects.select_for_update()
                .filter(staff=employee, page=page)
                .first()
            )
            current = _canonical_groups(grant.groups if grant is not None else ())
            eligible = eligible_grant_groups(page.kind)
            if any(group not in eligible for group in current):
                raise GrantCommandError("GRANT_CORRUPT")
            current_hash = grant_state_hash(employee.id, page.id, current)
            if employee.generation != base_generation or current_hash != base_hash:
                raise GrantCommandError(
                    "STALE_GRANT",
                    user_generation=employee.generation,
                    grant_hash=current_hash,
                )
            if any(group not in eligible for group in desired):
                raise GrantCommandError("INVALID_GROUPS")
            if desired == current:
                raise GrantCommandError(
                    "NO_CHANGE",
                    user_generation=employee.generation,
                    grant_hash=current_hash,
                )

            if desired:
                if grant is None:
                    grant = PageGrant(staff=employee, page=page, groups=list(desired))
                    grant.full_clean()
                    grant.save(force_insert=True)
                else:
                    grant.groups = list(desired)
                    grant.full_clean()
                    grant.save(update_fields=("groups",))
                action = Action.PAGE_GRANT_SET
            else:
                if grant is None:
                    raise GrantCommandError("NO_CHANGE")
                grant.delete()
                action = Action.PAGE_GRANT_REVOKED

            employee.generation += 1
            employee.save(update_fields=("generation",))
            append_event(
                action=action,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                secondary_uuid=employee.id,
                detail={"generation": employee.generation, "groups": list(desired)},
            )
            return GrantResult(
                employee.generation,
                grant_state_hash(employee.id, page.id, desired),
                desired,
            )
    except StaffAccessError as exc:
        raise GrantCommandError(exc.code) from exc


def set_page_grant(
    *,
    actor_id: object,
    session_generation: object,
    staff_id: object,
    page_id: object,
    desired_groups: object,
    base_user_generation: object,
    base_grant_hash: object,
) -> GrantResult:
    _canonical_groups(desired_groups, allow_empty=False)
    return _mutate_page_grant(
        actor_id=actor_id,
        session_generation=session_generation,
        staff_id=staff_id,
        page_id=page_id,
        desired_groups=desired_groups,
        base_user_generation=base_user_generation,
        base_grant_hash=base_grant_hash,
    )


def revoke_page_grant(
    *,
    actor_id: object,
    session_generation: object,
    staff_id: object,
    page_id: object,
    base_user_generation: object,
    base_grant_hash: object,
) -> GrantResult:
    return _mutate_page_grant(
        actor_id=actor_id,
        session_generation=session_generation,
        staff_id=staff_id,
        page_id=page_id,
        desired_groups=(),
        base_user_generation=base_user_generation,
        base_grant_hash=base_grant_hash,
    )
