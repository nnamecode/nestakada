from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.db.models import Q


class StaffRole(models.TextChoices):
    OWNER = "OWNER"
    EMPLOYEE = "EMPLOYEE"


class StaffUserManager(UserManager):
    use_in_migrations = True

    def _create_user(self, username, email, password, **extra_fields):
        role = extra_fields.get("role")
        if role not in StaffRole.values:
            raise ValueError("An exact staff role is required.")
        if role == StaffRole.OWNER:
            if username != "nesadmin":
                raise ValueError("The owner username is fixed.")
            extra_fields["is_staff"] = True
            extra_fields["is_superuser"] = True
        else:
            if username == "nesadmin":
                raise ValueError("The owner username is reserved.")
            extra_fields["is_staff"] = True
            extra_fields["is_superuser"] = False
        return super()._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username="nesadmin", email=None, password=None, **extra_fields):
        if username != "nesadmin" or extra_fields.get("role", StaffRole.OWNER) != StaffRole.OWNER:
            raise ValueError("createsuperuser can create only the fixed owner.")
        extra_fields["role"] = StaffRole.OWNER
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=16, choices=StaffRole.choices)
    generation = models.PositiveBigIntegerField(default=1)
    objects = StaffUserManager()

    REQUIRED_FIELDS: list[str] = []

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(generation__gte=1),
                name="accounts_user_generation_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        role=StaffRole.OWNER,
                        username="nesadmin",
                        is_staff=True,
                        is_superuser=True,
                    )
                    | Q(
                        role=StaffRole.EMPLOYEE,
                        is_staff=True,
                        is_superuser=False,
                    )
                    & ~Q(username="nesadmin")
                ),
                name="accounts_user_role_username",
            ),
            models.UniqueConstraint(
                fields=("role",),
                condition=Q(role=StaffRole.OWNER, is_active=True),
                name="accounts_one_active_owner_at_most",
            ),
        ]
