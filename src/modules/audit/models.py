from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ActorKind(models.TextChoices):
    USER = "USER"
    SYSTEM = "SYSTEM"
    ANONYMOUS = "ANONYMOUS"


class ActorRole(models.TextChoices):
    OWNER = "OWNER"
    EMPLOYEE = "EMPLOYEE"


class TargetType(models.TextChoices):
    USER = "USER"
    PAGE = "PAGE"
    ASSET = "ASSET"
    GALLERY = "GALLERY"
    SERVICE_REQUEST = "SERVICE_REQUEST"
    SITE_SETTINGS = "SITE_SETTINGS"
    AUDIT = "AUDIT"


class Action(models.TextChoices):
    AUTH_LOGIN_SUCCEEDED = "AUTH_LOGIN_SUCCEEDED"
    AUTH_LOGIN_FAILED = "AUTH_LOGIN_FAILED"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_PASSWORD_CHANGED = "AUTH_PASSWORD_CHANGED"
    STAFF_CREATED = "STAFF_CREATED"
    STAFF_REACTIVATED = "STAFF_REACTIVATED"
    STAFF_DEACTIVATED = "STAFF_DEACTIVATED"
    PAGE_GRANT_SET = "PAGE_GRANT_SET"
    PAGE_GRANT_REVOKED = "PAGE_GRANT_REVOKED"
    PAGE_CREATED = "PAGE_CREATED"
    PAGE_RENAMED = "PAGE_RENAMED"
    PAGE_MOVED = "PAGE_MOVED"
    PAGE_REORDERED = "PAGE_REORDERED"
    PAGE_PUBLICATION_CHANGED = "PAGE_PUBLICATION_CHANGED"
    PAGE_URL_CHANGED = "PAGE_URL_CHANGED"
    PAGE_CONTENT_SAVED = "PAGE_CONTENT_SAVED"
    PAGE_CONTENT_UNDONE = "PAGE_CONTENT_UNDONE"
    PAGE_DELETED = "PAGE_DELETED"
    SITE_SETTINGS_CHANGED = "SITE_SETTINGS_CHANGED"
    ASSET_UPLOADED = "ASSET_UPLOADED"
    ASSET_REPLACED = "ASSET_REPLACED"
    ASSET_DELETED = "ASSET_DELETED"
    GALLERY_CHANGED = "GALLERY_CHANGED"
    GALLERY_DELETED = "GALLERY_DELETED"
    SERVICE_REQUEST_ACCEPTED = "SERVICE_REQUEST_ACCEPTED"
    SERVICE_REQUEST_DELETED = "SERVICE_REQUEST_DELETED"
    SERVICE_REQUEST_RETENTION_BATCH = "SERVICE_REQUEST_RETENTION_BATCH"
    AUDIT_RETENTION_BATCH = "AUDIT_RETENTION_BATCH"


@dataclass(frozen=True)
class DetailRule:
    target: str
    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    target_uuid: str = "required"
    secondary_uuid: str = "absent"
    actors: frozenset[str] = frozenset({ActorKind.USER})


_PAGE_STRUCTURE = frozenset(
    {
        Action.PAGE_CREATED,
        Action.PAGE_RENAMED,
        Action.PAGE_MOVED,
        Action.PAGE_URL_CHANGED,
        Action.PAGE_DELETED,
    }
)
RULES: dict[str, DetailRule] = {
    Action.AUTH_LOGIN_SUCCEEDED: DetailRule(TargetType.USER, frozenset()),
    Action.AUTH_LOGOUT: DetailRule(TargetType.USER, frozenset()),
    Action.AUTH_LOGIN_FAILED: DetailRule(
        TargetType.USER,
        frozenset({"reason"}),
        target_uuid="absent",
        actors=frozenset({ActorKind.ANONYMOUS}),
    ),
    Action.AUTH_PASSWORD_CHANGED: DetailRule(TargetType.USER, frozenset({"generation"})),
    Action.STAFF_CREATED: DetailRule(TargetType.USER, frozenset({"generation"})),
    Action.STAFF_REACTIVATED: DetailRule(TargetType.USER, frozenset({"generation"})),
    Action.STAFF_DEACTIVATED: DetailRule(TargetType.USER, frozenset({"generation", "count"})),
    Action.PAGE_GRANT_SET: DetailRule(
        TargetType.PAGE,
        frozenset({"generation", "groups"}),
        secondary_uuid="required",
    ),
    Action.PAGE_GRANT_REVOKED: DetailRule(
        TargetType.PAGE,
        frozenset({"generation", "groups"}),
        secondary_uuid="required",
    ),
    **{
        action: DetailRule(TargetType.PAGE, frozenset({"generation"}))
        for action in _PAGE_STRUCTURE
    },
    Action.PAGE_REORDERED: DetailRule(TargetType.PAGE, frozenset({"generation", "count"})),
    Action.PAGE_PUBLICATION_CHANGED: DetailRule(
        TargetType.PAGE, frozenset({"generation", "state"})
    ),
    Action.PAGE_CONTENT_SAVED: DetailRule(
        TargetType.PAGE,
        frozenset({"operation_id", "generation", "current_hash"}),
        frozenset({"previous_hash"}),
    ),
    Action.PAGE_CONTENT_UNDONE: DetailRule(
        TargetType.PAGE,
        frozenset({"operation_id", "generation", "current_hash", "previous_hash"}),
    ),
    Action.SITE_SETTINGS_CHANGED: DetailRule(
        TargetType.SITE_SETTINGS, frozenset({"generation"}), target_uuid="absent"
    ),
    Action.ASSET_UPLOADED: DetailRule(TargetType.ASSET, frozenset({"state"})),
    Action.ASSET_REPLACED: DetailRule(TargetType.ASSET, frozenset({"state"})),
    Action.ASSET_DELETED: DetailRule(TargetType.ASSET, frozenset({"state"})),
    Action.GALLERY_CHANGED: DetailRule(TargetType.GALLERY, frozenset({"generation"})),
    Action.GALLERY_DELETED: DetailRule(TargetType.GALLERY, frozenset({"generation"})),
    Action.SERVICE_REQUEST_ACCEPTED: DetailRule(
        TargetType.SERVICE_REQUEST,
        frozenset(),
        actors=frozenset({ActorKind.ANONYMOUS}),
    ),
    Action.SERVICE_REQUEST_DELETED: DetailRule(
        TargetType.SERVICE_REQUEST, frozenset({"reason"})
    ),
    Action.SERVICE_REQUEST_RETENTION_BATCH: DetailRule(
        TargetType.SERVICE_REQUEST,
        frozenset({"reason", "count"}),
        target_uuid="absent",
        actors=frozenset({ActorKind.SYSTEM}),
    ),
    Action.AUDIT_RETENTION_BATCH: DetailRule(
        TargetType.AUDIT,
        frozenset({"reason", "count"}),
        target_uuid="absent",
        actors=frozenset({ActorKind.SYSTEM}),
    ),
}


def _validate_detail(action: str, detail: object) -> None:
    if type(detail) is not dict:
        raise ValidationError({"detail": "Audit detail must be an object."})
    rule = RULES.get(action)
    if rule is None or not rule.required.issubset(detail) or not set(detail).issubset(
        rule.required | rule.optional
    ):
        raise ValidationError({"detail": "Audit detail does not match its action."})
    if len(detail) > 8 or any(type(value) in {dict, list} for value in detail.values() if value is not None):
        if "groups" not in detail or any(
            type(value) in {dict, list} for key, value in detail.items() if key != "groups"
        ):
            raise ValidationError({"detail": "Audit detail depth is invalid."})
    encoded = json.dumps(detail, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > 2048:
        raise ValidationError({"detail": "Audit detail exceeds the byte cap."})
    if "operation_id" in detail:
        try:
            uuid.UUID(str(detail["operation_id"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError({"detail": "Invalid operation ID."}) from exc
    for key in ("generation", "count"):
        if key in detail and (type(detail[key]) is not int or detail[key] < 0):
            raise ValidationError({"detail": f"Invalid {key}."})
    if "count" in detail and detail["count"] > 1_000_000:
        raise ValidationError({"detail": "Invalid count."})
    for key in ("current_hash", "previous_hash"):
        if key in detail and (
            type(detail[key]) is not str
            or len(detail[key]) != 64
            or any(char not in "0123456789abcdef" for char in detail[key])
        ):
            raise ValidationError({"detail": f"Invalid {key}."})
    if "groups" in detail and detail["groups"] not in ([], ["prices"], ["text"], ["text", "prices"]):
        raise ValidationError({"detail": "Invalid groups."})
    if action == Action.AUTH_LOGIN_FAILED and detail.get("reason") not in {
        "INVALID_CREDENTIALS",
        "THROTTLED",
        "INACTIVE",
    }:
        raise ValidationError({"detail": "Invalid login reason."})
    if action == Action.SERVICE_REQUEST_DELETED and detail.get("reason") != "OWNER":
        raise ValidationError({"detail": "Invalid delete reason."})
    if action in {Action.SERVICE_REQUEST_RETENTION_BATCH, Action.AUDIT_RETENTION_BATCH} and detail.get(
        "reason"
    ) != "RETENTION":
        raise ValidationError({"detail": "Invalid retention reason."})
    if action == Action.PAGE_PUBLICATION_CHANGED and detail.get("state") not in {
        "PUBLISHED",
        "HIDDEN",
    }:
        raise ValidationError({"detail": "Invalid publication state."})
    if action in {Action.ASSET_UPLOADED, Action.ASSET_REPLACED} and detail.get("state") != "READY":
        raise ValidationError({"detail": "Invalid asset state."})
    if action == Action.ASSET_DELETED and detail.get("state") != "DELETED":
        raise ValidationError({"detail": "Invalid asset state."})


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=64, choices=Action.choices)
    actor_kind = models.CharField(max_length=16, choices=ActorKind.choices)
    actor_uuid = models.UUIDField(null=True, blank=True)
    actor_role = models.CharField(max_length=16, choices=ActorRole.choices, null=True, blank=True)
    target_type = models.CharField(max_length=24, choices=TargetType.choices)
    target_uuid = models.UUIDField(null=True, blank=True)
    secondary_uuid = models.UUIDField(null=True, blank=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(actor_kind=ActorKind.USER, actor_uuid__isnull=False, actor_role__isnull=False)
                    | Q(
                        actor_kind__in=(ActorKind.SYSTEM, ActorKind.ANONYMOUS),
                        actor_uuid__isnull=True,
                        actor_role__isnull=True,
                    )
                ),
                name="audit_actor_shape",
            )
        ]

    def clean(self) -> None:
        super().clean()
        rule = RULES.get(self.action)
        if rule is None or self.actor_kind not in rule.actors or self.target_type != rule.target:
            raise ValidationError("Audit actor or target does not match its action.")
        if (rule.target_uuid == "required") != (self.target_uuid is not None):
            raise ValidationError({"target_uuid": "Target UUID shape is invalid."})
        if (rule.secondary_uuid == "required") != (self.secondary_uuid is not None):
            raise ValidationError({"secondary_uuid": "Secondary UUID shape is invalid."})
        if self.actor_kind == ActorKind.USER:
            if self.actor_uuid is None or self.actor_role not in ActorRole.values:
                raise ValidationError("User actor snapshot is incomplete.")
        elif self.actor_uuid is not None or self.actor_role is not None:
            raise ValidationError("Non-user actor cannot have a user snapshot.")
        if self.action == Action.SERVICE_REQUEST_DELETED and self.actor_role != ActorRole.OWNER:
            raise ValidationError("Only an owner actor can delete a service request.")
        _validate_detail(self.action, self.detail)
