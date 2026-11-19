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
