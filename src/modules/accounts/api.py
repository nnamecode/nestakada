from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from django.contrib.auth import SESSION_KEY as AUTH_SESSION_KEY, logout
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connections
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from .models import StaffRole, User


_View = TypeVar("_View", bound=Callable[..., HttpResponse])
SESSION_GENERATION_KEY = "staff_generation"


class StaffAccessError(PermissionError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def lock_staff_session(
    *,
    actor_id: object,
    session_generation: object,
    using: str = "default",
) -> User:
    """Lock and recheck one authenticated staff session inside its owner transaction."""

    if not connections[using].in_atomic_block:
        raise RuntimeError("Staff session must be checked inside an atomic transaction.")
    try:
        actor = User.objects.using(using).select_for_update().get(pk=actor_id)
    except (User.DoesNotExist, TypeError, ValueError, ValidationError):
        raise StaffAccessError("AUTH_REQUIRED") from None
    if (
        not actor.is_active
        or not actor.is_staff
        or actor.role not in StaffRole.values
        or type(session_generation) is not int
        or actor.generation != session_generation
    ):
        raise StaffAccessError("STALE_SESSION")
    return actor


def lock_active_owner(*, using: str = "default") -> User:
    if not connections[using].in_atomic_block:
        raise RuntimeError("Owner invariant must be checked inside an atomic transaction.")
    owners: QuerySet[User] = User.objects.using(using).filter(
        role=StaffRole.OWNER,
        is_active=True,
    )
    owners = owners.select_for_update()
    selected = list(owners[:2])
    if len(selected) != 1 or selected[0].username != "nesadmin":
        raise ImproperlyConfigured("Exactly one active owner is required.")
    return selected[0]


def lock_owner_and_employee(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    using: str = "default",
) -> tuple[User, User]:
    """Lock one owner actor and one employee target in canonical UUID order."""

    return lock_owner_and_employee_state(
        actor_id=actor_id,
        session_generation=session_generation,
        employee_id=employee_id,
        require_employee_active=True,
        using=using,
    )


def lock_owner_and_employee_state(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    require_employee_active: bool | None,
    using: str = "default",
) -> tuple[User, User]:
    """Lock an owner and employee; optionally require exact target active state."""

    if not connections[using].in_atomic_block:
        raise RuntimeError("Grant participants must be checked inside an atomic transaction.")
    if actor_id == employee_id:
        raise StaffAccessError("FORBIDDEN")
    try:
        selected = list(
            User.objects.using(using)
            .select_for_update()
            .filter(pk__in=(actor_id, employee_id))
            .order_by("id")
        )
    except (TypeError, ValueError, ValidationError):
        raise StaffAccessError("AUTH_REQUIRED") from None
    by_id = {user.id: user for user in selected}
    actor = by_id.get(actor_id)
    employee = by_id.get(employee_id)
    if actor is None:
        raise StaffAccessError("AUTH_REQUIRED")
    if (
        not actor.is_active
        or not actor.is_staff
        or not actor.is_superuser
        or actor.role != StaffRole.OWNER
        or actor.username != "nesadmin"
        or type(session_generation) is not int
        or actor.generation != session_generation
    ):
        raise StaffAccessError("STALE_SESSION")
    if (
        employee is None
        or not employee.is_staff
        or employee.is_superuser
        or employee.role != StaffRole.EMPLOYEE
        or employee.username == "nesadmin"
        or (
            require_employee_active is not None
            and employee.is_active is not require_employee_active
        )
    ):
        raise StaffAccessError("FORBIDDEN")
    return actor, employee


def bump_employee_password_generation(*, employee: User, using: str = "default") -> None:
    if not connections[using].in_atomic_block or employee._state.db != using:
        raise RuntimeError("Password participant requires its owner transaction.")
    if employee.role != StaffRole.EMPLOYEE or not employee.is_staff or employee.is_superuser:
        raise StaffAccessError("FORBIDDEN")
    employee.generation += 1
    employee.save(update_fields=("password", "generation"), using=using)


def deactivate_and_bump(*, employee: User, using: str = "default") -> None:
    if not connections[using].in_atomic_block or employee._state.db != using:
        raise RuntimeError("Deactivate participant requires its owner transaction.")
    if employee.role != StaffRole.EMPLOYEE or not employee.is_active:
        raise StaffAccessError("FORBIDDEN")
    employee.is_active = False
    employee.generation += 1
    employee.save(update_fields=("is_active", "generation"), using=using)


def reactivate_and_bump(*, employee: User, using: str = "default") -> None:
    if not connections[using].in_atomic_block or employee._state.db != using:
        raise RuntimeError("Reactivate participant requires its owner transaction.")
    if employee.role != StaffRole.EMPLOYEE or employee.is_active:
        raise StaffAccessError("FORBIDDEN")
    employee.is_active = True
    employee.generation += 1
    employee.save(update_fields=("is_active", "generation"), using=using)


def current_staff_session(request: HttpRequest, *, clear_invalid: bool = True) -> User | None:
    actor: Any = getattr(request, "user", None)
    generation = request.session.get(SESSION_GENERATION_KEY)
    valid = (
        actor is not None
        and actor.is_authenticated
        and actor.is_active
        and actor.is_staff
        and actor.role in StaffRole.values
        and type(generation) is int
        and actor.generation == generation
    )
    if valid:
        return actor
    if clear_invalid and (
        AUTH_SESSION_KEY in request.session or SESSION_GENERATION_KEY in request.session
    ):
        logout(request)
    return None


def staff_session_required(view: _View) -> _View:
    @wraps(view)
    def guarded(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        actor = current_staff_session(request)
        if actor is None:
            return redirect("manage-login")
        request.staff_actor = actor
        return view(request, *args, **kwargs)

    return guarded  # type: ignore[return-value]
