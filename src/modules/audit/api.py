from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Mapping

from .models import ActorKind, ActorRole, AuditEvent, TargetType


@dataclass(frozen=True, slots=True)
class ActorRef:
    kind: str
    uuid: uuid.UUID | None = None
    role: str | None = None

    @classmethod
    def user(cls, actor_uuid: uuid.UUID, role: str) -> "ActorRef":
        if role not in ActorRole.values:
            raise ValueError("Unknown actor role.")
        return cls(ActorKind.USER, actor_uuid, role)

    @classmethod
    def system(cls) -> "ActorRef":
        return cls(ActorKind.SYSTEM)

    @classmethod
    def anonymous(cls) -> "ActorRef":
        return cls(ActorKind.ANONYMOUS)


def append_event(
    *,
    action: str,
    actor: ActorRef,
    target_type: str,
    target_uuid: uuid.UUID | None,
    secondary_uuid: uuid.UUID | None = None,
    detail: Mapping[str, object] | None = None,
) -> AuditEvent:
    if target_type not in TargetType.values:
        raise ValueError("Unknown audit target type.")
    event = AuditEvent(
        action=action,
        actor_kind=actor.kind,
        actor_uuid=actor.uuid,
        actor_role=actor.role,
        target_type=target_type,
        target_uuid=target_uuid,
        secondary_uuid=secondary_uuid,
        detail=dict(detail or {}),
    )
    event.full_clean()
    event.save(force_insert=True)
    return event
