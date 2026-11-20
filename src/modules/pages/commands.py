from __future__ import annotations

import copy
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.accounts.api import StaffAccessError, StaffRole, lock_staff_session
from modules.audit.api import Action, ActorRef, TargetType, append_event
from modules.media.api import (
    MediaUsageError,
    replace_page_usages,
    verify_page_current_usages,
)

from .content import ContentValidationError, canonical_payload_hash, validate_payload
from .grants import eligible_grant_groups
from .models import LastOperationAction, Page, PageContent, PageGrant, Route, RouteMode, SiteSettings


class PageCommandError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        generation: int | None = None,
        current_hash: str | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.generation = generation
        self.current_hash = current_hash


@dataclass(frozen=True, slots=True)
class ContentResult:
    generation: int
    current_hash: str
    replayed: bool = False


@dataclass(frozen=True, slots=True)
class PublicationResult:
    structure_generation: int
    is_published: bool


@dataclass(frozen=True, slots=True)
class RenameResult:
    structure_generation: int
    name: str


def validate_page_name(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or len(value) > 500
        or value != value.strip()
        or not value.strip()
        or unicodedata.normalize("NFC", value) != value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise PageCommandError("INVALID_PAGE_NAME")
    return value


def _basis(operation_id: object, generation: object, current_hash: object) -> uuid.UUID:
    if not isinstance(operation_id, uuid.UUID):
        raise PageCommandError("INVALID_OPERATION")
    if type(generation) is not int or generation < 1:
        raise PageCommandError("INVALID_BASIS")
    if (
        not isinstance(current_hash, str)
        or len(current_hash) != 64
        or any(char not in "0123456789abcdef" for char in current_hash)
    ):
        raise PageCommandError("INVALID_BASIS")
    return operation_id


def _replay_or_conflict(
    content: PageContent,
    *,
    operation_id: uuid.UUID,
    action: str,
) -> ContentResult | None:
    if content.last_operation_id != operation_id:
        return None
    if content.last_operation_action != action:
        raise PageCommandError(
            "OPERATION_CONFLICT",
            generation=content.generation,
            current_hash=content.current_hash,
        )
    return ContentResult(
        content.last_result_generation,
        content.last_result_hash,
        replayed=True,
    )


def _cas(content: PageContent, *, generation: int, current_hash: str) -> None:
    if content.generation != generation or content.current_hash != current_hash:
        raise PageCommandError(
            "STALE_CONTENT",
            generation=content.generation,
            current_hash=content.current_hash,
        )


def _employee_payload(
    current: dict[str, Any],
    *,
    kind: str,
    changes: object,
    granted_groups: object,
) -> dict[str, Any]:
    if not isinstance(changes, dict) or not changes:
        raise PageCommandError("INVALID_PATCH")
    if granted_groups not in (["prices"], ["text"], ["text", "prices"]):
        raise PageCommandError("FORBIDDEN")
    if not set(changes).issubset(granted_groups):
        raise PageCommandError("FORBIDDEN")
    result = copy.deepcopy(current)
    fields = result.get("fields")
    if not isinstance(fields, dict):
        raise PageCommandError("CONTENT_CORRUPT")
    for group, value in changes.items():
        if group == "text":
            if (
                "text" not in eligible_grant_groups(kind)
                or not isinstance(value, dict)
                or set(value) != {"intro", "body"}
            ):
                raise PageCommandError("INVALID_PATCH")
            fields["intro"] = value["intro"]
            fields["body"] = value["body"]
        elif group == "prices":
            if "prices" not in eligible_grant_groups(kind):
                raise PageCommandError("INVALID_PATCH")
            fields["price_rows"] = value
        else:
            raise PageCommandError("FORBIDDEN")
    return result


def _content_lock(page: Page) -> PageContent:
    try:
        return PageContent.objects.select_for_update().get(page=page)
    except PageContent.DoesNotExist:
        raise PageCommandError("CONTENT_MISSING") from None


def _page_lock(page_id: object) -> Page:
    try:
        return Page.objects.select_for_update().get(pk=page_id)
    except (Page.DoesNotExist, TypeError, ValueError, ValidationError):
        raise PageCommandError("PAGE_NOT_FOUND") from None


def _actor_ref(actor: Any) -> ActorRef:
    return ActorRef.user(actor.id, actor.role)


def rename_page(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    base_structure_generation: object,
    name: object,
) -> RenameResult:
    if type(base_structure_generation) is not int or base_structure_generation < 1:
        raise PageCommandError("INVALID_BASIS")
    valid_name = validate_page_name(name)
    try:
        valid_page_id = page_id if isinstance(page_id, uuid.UUID) else uuid.UUID(page_id)
    except (AttributeError, TypeError, ValueError):
        raise PageCommandError("PAGE_NOT_FOUND") from None
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            if actor.role != StaffRole.OWNER:
                raise PageCommandError("FORBIDDEN")
            try:
                settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
            except SiteSettings.DoesNotExist:
                raise PageCommandError("SETTINGS_MISSING") from None
            page = _page_lock(valid_page_id)
            if settings.structure_generation != base_structure_generation:
                raise PageCommandError(
                    "STALE_STRUCTURE",
                    generation=settings.structure_generation,
                )
            if page.name == valid_name:
                raise PageCommandError(
                    "NO_CHANGE",
                    generation=settings.structure_generation,
                )
            page.name = valid_name
            page.save(update_fields=("name",))
            settings.structure_generation += 1
            settings.save(update_fields=("structure_generation",))
            append_event(
                action=Action.PAGE_RENAMED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                detail={"generation": settings.structure_generation},
            )
            return RenameResult(settings.structure_generation, valid_name)
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc


def set_page_publication(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    base_structure_generation: object,
    desired_published: object,
) -> PublicationResult:
    if type(base_structure_generation) is not int or base_structure_generation < 1:
        raise PageCommandError("INVALID_BASIS")
    if type(desired_published) is not bool:
        raise PageCommandError("INVALID_PUBLICATION")
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            if actor.role != StaffRole.OWNER:
                raise PageCommandError("FORBIDDEN")
            try:
                settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
            except SiteSettings.DoesNotExist:
                raise PageCommandError("SETTINGS_MISSING") from None
            page = _page_lock(page_id)
            if settings.structure_generation != base_structure_generation:
                raise PageCommandError(
                    "STALE_STRUCTURE",
                    generation=settings.structure_generation,
                )
            if page.is_published is desired_published:
                raise PageCommandError(
                    "NO_CHANGE",
                    generation=settings.structure_generation,
                )

            if desired_published:
                routes = list(
                    Route.objects.select_for_update().filter(page=page).order_by("id")
                )
                primary = [route for route in routes if route.mode == RouteMode.PRIMARY]
                if len(primary) != 1:
                    raise PageCommandError("ROUTE_CORRUPT")
                try:
                    primary[0].clean()
                except ValidationError:
                    raise PageCommandError("ROUTE_CORRUPT") from None
                content = _content_lock(page)
                if canonical_payload_hash(content.current_payload) != content.current_hash:
                    raise PageCommandError("CONTENT_CORRUPT")
                current_media = validate_payload(content.current_payload, page.kind)
                verify_page_current_usages(
                    page_id=page.id,
                    expected_media=current_media,
                )

            page.is_published = desired_published
            page.save(update_fields=("is_published",))
            settings.structure_generation += 1
            settings.save(update_fields=("structure_generation",))
            append_event(
                action=Action.PAGE_PUBLICATION_CHANGED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                detail={
                    "generation": settings.structure_generation,
                    "state": "PUBLISHED" if desired_published else "HIDDEN",
                },
            )
            return PublicationResult(settings.structure_generation, desired_published)
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc
    except MediaUsageError as exc:
        raise PageCommandError(exc.code) from exc
    except ContentValidationError as exc:
        raise PageCommandError("INVALID_CONTENT") from exc


def save_page_content(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    operation_id: object,
    base_generation: object,
    base_current_hash: object,
    changes: object,
) -> ContentResult:
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            page = _page_lock(page_id)
            grant = None
            if actor.role == StaffRole.EMPLOYEE:
                try:
                    grant = PageGrant.objects.select_for_update().get(
                        staff=actor,
                        page=page,
                    )
                except PageGrant.DoesNotExist:
                    raise PageCommandError("FORBIDDEN") from None
            operation_id = _basis(operation_id, base_generation, base_current_hash)
            content = _content_lock(page)
            replay = _replay_or_conflict(
                content,
                operation_id=operation_id,
                action=LastOperationAction.SAVE,
            )
            if replay is not None:
                return replay
            _cas(content, generation=base_generation, current_hash=base_current_hash)

            if canonical_payload_hash(content.current_payload) != content.current_hash:
                raise PageCommandError("CONTENT_CORRUPT")
            previous_media = validate_payload(content.current_payload, page.kind)
            if actor.role == StaffRole.OWNER:
                candidate = copy.deepcopy(changes)
            else:
                candidate = _employee_payload(
                    content.current_payload,
                    kind=page.kind,
                    changes=changes,
                    granted_groups=grant.groups,
                )
            current_media = validate_payload(candidate, page.kind)
            new_hash = canonical_payload_hash(candidate)
            now = timezone.now()

            content.previous_payload = content.current_payload
            content.previous_hash = content.current_hash
            content.previous_author = content.current_author
            content.previous_created_at = content.current_created_at
            content.current_payload = candidate
            content.current_hash = new_hash
            content.current_author = actor
            content.current_created_at = now
            content.generation += 1
            content.last_operation_id = operation_id
            content.last_operation_action = LastOperationAction.SAVE
            content.last_result_generation = content.generation
            content.last_result_hash = new_hash
            content.save()

            replace_page_usages(
                page_id=page.id,
                current=current_media,
                previous=previous_media,
            )
            append_event(
                action=Action.PAGE_CONTENT_SAVED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                detail={
                    "operation_id": str(operation_id),
                    "generation": content.generation,
                    "current_hash": new_hash,
                    "previous_hash": content.previous_hash,
                },
            )
            return ContentResult(content.generation, new_hash)
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc
    except MediaUsageError as exc:
        raise PageCommandError(exc.code) from exc
    except ContentValidationError as exc:
        raise PageCommandError("INVALID_CONTENT") from exc


def undo_page_content(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    operation_id: object,
    base_generation: object,
    base_current_hash: object,
) -> ContentResult:
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            if actor.role != StaffRole.OWNER:
                raise PageCommandError("FORBIDDEN")
            page = _page_lock(page_id)
            operation_id = _basis(operation_id, base_generation, base_current_hash)
            content = _content_lock(page)
            replay = _replay_or_conflict(
                content,
                operation_id=operation_id,
                action=LastOperationAction.UNDO,
            )
            if replay is not None:
                return replay
            _cas(content, generation=base_generation, current_hash=base_current_hash)
            if content.previous_payload is None:
                raise PageCommandError("NO_PREVIOUS")
            if (
                canonical_payload_hash(content.current_payload) != content.current_hash
                or canonical_payload_hash(content.previous_payload) != content.previous_hash
            ):
                raise PageCommandError("CONTENT_CORRUPT")
            new_current_media = validate_payload(content.previous_payload, page.kind)
            new_previous_media = validate_payload(content.current_payload, page.kind)

            old_current = (
                content.current_payload,
                content.current_hash,
                content.current_author,
                content.current_created_at,
            )
            content.current_payload = content.previous_payload
            content.current_hash = content.previous_hash
            content.current_author = content.previous_author
            content.current_created_at = content.previous_created_at
            (
                content.previous_payload,
                content.previous_hash,
                content.previous_author,
                content.previous_created_at,
            ) = old_current
            content.generation += 1
            content.last_operation_id = operation_id
            content.last_operation_action = LastOperationAction.UNDO
            content.last_result_generation = content.generation
            content.last_result_hash = content.current_hash
            content.save()

            replace_page_usages(
                page_id=page.id,
                current=new_current_media,
                previous=new_previous_media,
            )
            append_event(
                action=Action.PAGE_CONTENT_UNDONE,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                detail={
                    "operation_id": str(operation_id),
                    "generation": content.generation,
                    "current_hash": content.current_hash,
                    "previous_hash": content.previous_hash,
                },
            )
            return ContentResult(content.generation, content.current_hash)
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc
    except MediaUsageError as exc:
        raise PageCommandError(exc.code) from exc
    except ContentValidationError as exc:
        raise PageCommandError("INVALID_CONTENT") from exc
