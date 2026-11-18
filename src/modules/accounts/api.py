from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.db.models import QuerySet

from .models import StaffRole, User


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
