from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from modules.audit.api import Action, ActorRef, TargetType, append_event

from .api import (
    StaffAccessError,
    bump_employee_password_generation,
    lock_owner_and_employee_state,
    lock_staff_session,
)
from .models import StaffRole, User


class StaffCommandError(RuntimeError):
    def __init__(self, code: str, *, generation: int | None = None):
        super().__init__(code)
        self.code = code
        self.generation = generation


@dataclass(frozen=True, slots=True)
class StaffResult:
    employee_id: uuid.UUID
    generation: int
    is_active: bool


def _owner(actor: User, session_generation: object) -> None:
    if (
        actor.role != StaffRole.OWNER
        or actor.username != "nesadmin"
        or not actor.is_active
        or not actor.is_staff
        or not actor.is_superuser
        or type(session_generation) is not int
        or actor.generation != session_generation
    ):
        raise StaffCommandError("FORBIDDEN")


def _generation(value: object) -> int:
    if type(value) is not int or value < 1:
        raise StaffCommandError("INVALID_BASIS")
    return value


def _new_employee(employee_id: object, username: object) -> User:
    if not isinstance(employee_id, uuid.UUID):
        raise StaffCommandError("INVALID_EMPLOYEE")
    if (
        not isinstance(username, str)
        or not username
        or username != username.strip()
        or username == "nesadmin"
        or User.normalize_username(username) != username
    ):
        raise StaffCommandError("INVALID_USERNAME")
    employee = User(
        id=employee_id,
        username=username,
        email="",
        role=StaffRole.EMPLOYEE,
        is_active=True,
        is_staff=True,
        is_superuser=False,
        generation=1,
    )
    try:
        employee.full_clean(exclude=("password",), validate_unique=False)
    except ValidationError:
        raise StaffCommandError("INVALID_USERNAME") from None
    return employee


def _password(employee: User, password: object, confirmation: object) -> str:
    if not isinstance(password, str) or not isinstance(confirmation, str) or password != confirmation:
        raise StaffCommandError("INVALID_PASSWORD")
    try:
        validate_password(password, user=employee)
    except ValidationError:
        raise StaffCommandError("INVALID_PASSWORD") from None
    return password


def create_employee(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    username: object,
    password: object,
    confirmation: object,
) -> StaffResult:
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            _owner(actor, session_generation)
            employee = _new_employee(employee_id, username)
            if User.objects.filter(pk=employee.id).exists() or User.objects.filter(
                username=employee.username
            ).exists():
                raise StaffCommandError("CONFLICT")
            password_value = _password(employee, password, confirmation)
            employee.set_password(password_value)
            try:
                with transaction.atomic():
                    employee.save(force_insert=True)
            except IntegrityError:
                raise StaffCommandError("CONFLICT") from None
            append_event(
                action=Action.STAFF_CREATED,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.USER,
                target_uuid=employee.id,
                detail={"generation": 1},
            )
            return StaffResult(employee.id, 1, True)
    except StaffAccessError as exc:
        raise StaffCommandError(exc.code) from exc


def set_employee_password(
    *,
    actor_id: object,
    session_generation: object,
    employee_id: object,
    base_user_generation: object,
    password: object,
    confirmation: object,
) -> StaffResult:
    base_generation = _generation(base_user_generation)
    try:
        with transaction.atomic():
            actor, employee = lock_owner_and_employee_state(
                actor_id=actor_id,
                session_generation=session_generation,
                employee_id=employee_id,
                require_employee_active=None,
            )
            if employee.generation != base_generation:
                raise StaffCommandError("STALE_STAFF", generation=employee.generation)
            password_value = _password(employee, password, confirmation)
            if employee.check_password(password_value):
                raise StaffCommandError("NO_CHANGE", generation=employee.generation)
            employee.set_password(password_value)
            bump_employee_password_generation(employee=employee)
            append_event(
                action=Action.AUTH_PASSWORD_CHANGED,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.USER,
                target_uuid=employee.id,
                detail={"generation": employee.generation},
            )
            return StaffResult(employee.id, employee.generation, employee.is_active)
    except StaffAccessError as exc:
        raise StaffCommandError(exc.code) from exc
