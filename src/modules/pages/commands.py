from __future__ import annotations

import copy
import re
import unicodedata
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from modules.accounts.api import StaffAccessError, StaffRole, lock_staff_session
from modules.audit.api import Action, ActorRef, TargetType, append_event
from modules.audit.models import AuditEvent
from modules.media.api import (
    MediaUsageError,
    replace_page_usages,
    verify_page_current_usages,
)
from modules.media.models import AssetUsage, UsageScope

from .content import (
    FIELD_SETS,
    MEDIA_SLOTS,
    RICH_BY_KIND,
    ContentValidationError,
    canonical_payload_hash,
    validate_payload,
)
from .grants import eligible_grant_groups
from .models import (
    LastOperationAction,
    Page,
    PageContent,
    PageGrant,
    PageKind,
    Route,
    RouteMode,
    SiteSettings,
)


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


@dataclass(frozen=True, slots=True)
class MoveResult:
    structure_generation: int
    parent_id: uuid.UUID | None
    position: int


@dataclass(frozen=True, slots=True)
class ReorderResult:
    structure_generation: int
    parent_id: uuid.UUID | None
    count: int


@dataclass(frozen=True, slots=True)
class CreateResult:
    page_id: uuid.UUID
    structure_generation: int
    content_generation: int
    current_hash: str
    replayed: bool = False


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


def _create_name(value: object) -> str:
    try:
        value = validate_page_name(value)
    except PageCommandError as exc:
        if exc.code == "INVALID_PAGE_NAME":
            raise PageCommandError("INVALID_PAGE_CREATE") from None
        raise
    if len(value) > 255:
        raise PageCommandError("INVALID_PAGE_CREATE")
    return value


def _create_uuid(value: object, *, nullable: bool, code: str) -> uuid.UUID | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise PageCommandError(code)
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise PageCommandError(code) from None


def _create_path(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 2048
        or unicodedata.normalize("NFC", value) != value
        or re.search(r"%(?![0-9A-Fa-f]{2})", value)
    ):
        raise PageCommandError("INVALID_PAGE_CREATE")
    try:
        parsed = urlsplit(value)
        decoded = unquote(parsed.path, errors="strict")
    except (UnicodeDecodeError, ValueError) as exc:
        raise PageCommandError("INVALID_PAGE_CREATE") from exc
    if (
        not value.startswith("/")
        or value.startswith("//")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or "\\" in value
        or "\\" in decoded
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value + decoded)
        or any(segment in {".", ".."} for segment in decoded.split("/"))
        or decoded == "/manage"
        or decoded.startswith("/manage/")
    ):
        raise PageCommandError("INVALID_PAGE_CREATE")
    return value


def initial_page_payload(kind: object, name: object) -> dict[str, Any]:
    valid_name = _create_name(name)
    kinds = tuple(PageKind.values)
    if (
        len(kinds) != 19
        or len(set(kinds)) != 19
        or set(kinds) != set(FIELD_SETS)
        or not set(RICH_BY_KIND).issubset(kinds)
        or not set(MEDIA_SLOTS).issubset(kinds)
        or {
            current_kind for current_kind, fields in FIELD_SETS.items() if "media" in fields
        } != set(MEDIA_SLOTS)
        or kind not in kinds
    ):
        raise PageCommandError("CREATE_UNAVAILABLE")
    fields: dict[str, Any] = {
        "seo": {"title": valid_name, "description": "", "allow_index": False},
        "heading": {"h1": valid_name},
    }
    for field in RICH_BY_KIND.get(kind, set()):
        fields[field] = ""
    for field in (
        "service_refs", "brand_refs", "review_refs", "process_steps",
        "actions", "reviews", "links",
    ):
        if field in FIELD_SETS[kind]:
            fields[field] = []
    if "price_rows" in FIELD_SETS[kind]:
        fields["price_rows"] = {"columns": [], "rows": []}
    if "media" in FIELD_SETS[kind]:
        fields["media"] = {
            slot: None if slot == "hero" else []
            for slot in MEDIA_SLOTS[kind]
        }
    payload = {
        "schema": "estakada.page-content",
        "schema_version": 1,
        "kind": kind,
        "fields": fields,
    }
    try:
        media = validate_payload(payload, kind)
    except ContentValidationError as exc:
        raise PageCommandError("CREATE_UNAVAILABLE") from exc
    if any(media.values()):
        raise PageCommandError("CREATE_UNAVAILABLE")
    return payload


def validate_page_create_input(
    kind: object,
    name: object,
    primary_path: object,
) -> tuple[str, str, str]:
    if kind not in PageKind.values:
        raise PageCommandError("INVALID_PAGE_CREATE")
    valid_name = _create_name(name)
    valid_path = _create_path(primary_path)
    initial_page_payload(kind, valid_name)
    return kind, valid_name, valid_path


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


_CREATE_GRAPH_CAP = 512


def _create_graph() -> tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...]:
    rows = tuple(
        Page.objects.order_by("id").values_list("id", "parent_id", "position")[:513]
    )
    if len(rows) > _CREATE_GRAPH_CAP:
        raise PageCommandError("CREATE_UNAVAILABLE")
    ids = {row[0] for row in rows}
    parents = {row[0]: row[1] for row in rows}
    if any(parent_id is not None and parent_id not in ids for parent_id in parents.values()):
        raise PageCommandError("CREATE_UNAVAILABLE")
    for page_id in ids:
        seen: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = page_id
        while current_id is not None:
            if current_id in seen:
                raise PageCommandError("CREATE_UNAVAILABLE")
            seen.add(current_id)
            current_id = parents[current_id]
    return rows


def _create_affected(
    graph: tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
    *,
    page_id: uuid.UUID,
    parent_id: uuid.UUID | None,
) -> tuple[set[uuid.UUID], tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...]]:
    by_id = {row[0]: row for row in graph}
    if parent_id is not None and parent_id not in by_id:
        raise PageCommandError("INVALID_PARENT")
    target = by_id.get(page_id)
    relevant_parents = {parent_id}
    if target is not None:
        relevant_parents.add(target[1])
    affected = {
        row[0]
        for row in graph
        if row[1] in relevant_parents
    }
    if parent_id is not None:
        affected.add(parent_id)
    if target is not None and target[1] is not None:
        affected.add(target[1])
    if target is not None:
        affected.add(page_id)
    snapshot = tuple(row for row in graph if row[0] in affected)
    return affected, snapshot


def _create_replay(
    *,
    actor: Any,
    settings: SiteSettings,
    page: Page,
    page_id: uuid.UUID,
    parent_id: uuid.UUID | None,
    kind: str,
    name: str,
    primary_path: str,
    base_structure_generation: int,
    payload: dict[str, Any],
    current_hash: str,
    graph: tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
) -> CreateResult:
    try:
        content = PageContent.objects.select_for_update().get(page_id=page_id)
    except PageContent.DoesNotExist:
        raise PageCommandError("CREATE_UNAVAILABLE") from None
    routes = list(Route.objects.filter(page_id=page_id)[:2])
    siblings = [row for row in graph if row[1] == parent_id and row[0] != page_id]
    expected_position = max((row[2] for row in siblings), default=-1) + 1
    if (
        len(routes) != 1
        or routes[0].mode != RouteMode.PRIMARY
        or routes[0].target != primary_path
        or routes[0].outcome != kind
        or page.kind != kind
        or page.name != name
        or page.parent_id != parent_id
        or page.position != expected_position
        or page.is_published
        or content.generation != 1
        or content.current_payload != payload
        or content.current_hash != current_hash
        or content.current_author_id != actor.id
        or content.previous_payload is not None
        or content.previous_hash is not None
        or content.previous_author_id is not None
        or content.previous_created_at is not None
        or content.last_operation_id is not None
        or content.last_operation_action is not None
        or content.last_result_generation is not None
        or content.last_result_hash is not None
    ):
        raise PageCommandError("PAGE_ID_CONFLICT")
    if AssetUsage.objects.filter(
        target_uuid=page_id,
        scope__in=(UsageScope.PAGE_CURRENT, UsageScope.PAGE_PREVIOUS),
    ).exists():
        raise PageCommandError("CREATE_UNAVAILABLE")
    events = list(
        AuditEvent.objects.filter(
            action=Action.PAGE_CREATED,
            target_uuid=page_id,
        )[:2]
    )
    if len(events) != 1:
        raise PageCommandError("CREATE_UNAVAILABLE")
    event = events[0]
    audit_generation = base_structure_generation + 1
    if (
        event.detail != {"generation": audit_generation}
        or event.actor_uuid != actor.id
        or event.actor_role != actor.role
        or settings.structure_generation < audit_generation
    ):
        raise PageCommandError("PAGE_ID_CONFLICT")
    return CreateResult(page_id, audit_generation, 1, current_hash, True)


def create_page(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    base_structure_generation: object,
    kind: object,
    name: object,
    parent_id: object,
    primary_path: object,
) -> CreateResult:
    if type(base_structure_generation) is not int or base_structure_generation < 1:
        raise PageCommandError("INVALID_BASIS")
    valid_page_id = _create_uuid(page_id, nullable=False, code="INVALID_PAGE_CREATE")
    valid_parent_id = _create_uuid(parent_id, nullable=True, code="INVALID_PAGE_CREATE")
    if valid_page_id == valid_parent_id:
        raise PageCommandError("INVALID_PARENT")
    kind, valid_name, valid_path = validate_page_create_input(kind, name, primary_path)
    payload = initial_page_payload(kind, valid_name)
    current_hash = canonical_payload_hash(payload)
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
            discovered = _create_graph()
            affected_ids, affected_snapshot = _create_affected(
                discovered,
                page_id=valid_page_id,
                parent_id=valid_parent_id,
            )
            locked = list(
                Page.objects.select_for_update()
                .filter(pk__in=affected_ids)
                .order_by("id")
            )
            if len(locked) != len(affected_ids):
                raise PageCommandError("CREATE_UNAVAILABLE")
            revalidated = _create_graph()
            _, revalidated_snapshot = _create_affected(
                revalidated,
                page_id=valid_page_id,
                parent_id=valid_parent_id,
            )
            if revalidated_snapshot != affected_snapshot:
                raise PageCommandError("CREATE_UNAVAILABLE")
            existing = next((page for page in locked if page.id == valid_page_id), None)
            if existing is not None:
                return _create_replay(
                    actor=actor,
                    settings=settings,
                    page=existing,
                    page_id=valid_page_id,
                    parent_id=valid_parent_id,
                    kind=kind,
                    name=valid_name,
                    primary_path=valid_path,
                    base_structure_generation=base_structure_generation,
                    payload=payload,
                    current_hash=current_hash,
                    graph=revalidated,
                )
            if settings.structure_generation != base_structure_generation:
                raise PageCommandError(
                    "STALE_STRUCTURE", generation=settings.structure_generation
                )
            siblings = [row for row in revalidated if row[1] == valid_parent_id]
            position = max((row[2] for row in siblings), default=-1) + 1
            if position > _PAGE_POSITION_MAX:
                raise PageCommandError("CREATE_UNAVAILABLE")
            if Route.objects.filter(target=valid_path).exists():
                raise PageCommandError("PATH_OCCUPIED")
            page = Page(
                id=valid_page_id,
                name=valid_name,
                kind=kind,
                parent_id=valid_parent_id,
                position=position,
                is_published=False,
            )
            page.full_clean()
            page.save(force_insert=True)
            route = Route(
                page=page,
                target=valid_path,
                mode=RouteMode.PRIMARY,
                outcome=kind,
            )
            route.full_clean()
            route.save(force_insert=True)
            now = timezone.now()
            content = PageContent(
                page=page,
                generation=1,
                current_payload=payload,
                current_hash=current_hash,
                current_author=actor,
                current_created_at=now,
            )
            content.full_clean()
            content.save(force_insert=True)
            settings.structure_generation += 1
            settings.save(update_fields=("structure_generation",))
            append_event(
                action=Action.PAGE_CREATED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=page.id,
                detail={"generation": settings.structure_generation},
            )
            return CreateResult(
                page.id,
                settings.structure_generation,
                content.generation,
                current_hash,
            )
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc


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


_PAGE_POSITION_MAX = 2_147_483_647
_MOVE_GRAPH_CAP = 512


def _move_uuid(value: object, *, nullable: bool, code: str) -> uuid.UUID | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool):
        raise PageCommandError(code)
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
    except (AttributeError, TypeError, ValueError):
        raise PageCommandError(code) from None


def _move_row(page_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID | None, int] | None:
    row = Page.objects.filter(pk=page_id).values_list("id", "parent_id", "position").first()
    return None if row is None else (row[0], row[1], row[2])


def _move_siblings(parent_id: uuid.UUID | None) -> tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...]:
    return tuple(
        Page.objects.filter(parent_id=parent_id)
        .order_by("position", "id")
        .values_list("id", "parent_id", "position")
    )


def _move_ancestry(
    destination_parent_id: uuid.UUID | None,
    *,
    target_id: uuid.UUID,
) -> tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...]:
    result: list[tuple[uuid.UUID, uuid.UUID | None, int]] = []
    seen: set[uuid.UUID] = set()
    current_id = destination_parent_id
    while current_id is not None:
        if current_id in seen or len(result) >= _MOVE_GRAPH_CAP:
            raise PageCommandError("TREE_UNAVAILABLE")
        if current_id == target_id:
            raise PageCommandError("INVALID_PLACEMENT")
        seen.add(current_id)
        row = _move_row(current_id)
        if row is None:
            raise PageCommandError("INVALID_PLACEMENT")
        result.append(row)
        current_id = row[1]
    return tuple(result)


def _move_snapshot(
    *,
    target_id: uuid.UUID,
    destination_parent_id: uuid.UUID | None,
    before_page_id: uuid.UUID | None,
    missing_target_code: str,
) -> tuple[
    tuple[uuid.UUID, uuid.UUID | None, int],
    tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
    tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
    tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
]:
    target = _move_row(target_id)
    if target is None:
        raise PageCommandError(missing_target_code)
    ancestry = _move_ancestry(destination_parent_id, target_id=target_id)
    source = _move_siblings(target[1])
    destination = source if target[1] == destination_parent_id else _move_siblings(destination_parent_id)
    if before_page_id is not None and before_page_id not in {row[0] for row in destination}:
        raise PageCommandError("INVALID_PLACEMENT")
    return target, ancestry, source, destination


def _save_position(page: Page, position: int) -> None:
    page.position = position
    page.save(update_fields=("position",))


def move_page(
    *,
    actor_id: object,
    session_generation: object,
    page_id: object,
    base_structure_generation: object,
    destination_parent_id: object,
    before_page_id: object,
) -> MoveResult:
    if type(base_structure_generation) is not int or base_structure_generation < 1:
        raise PageCommandError("INVALID_BASIS")
    target_id = _move_uuid(page_id, nullable=False, code="PAGE_NOT_FOUND")
    destination_id = _move_uuid(
        destination_parent_id, nullable=True, code="INVALID_PLACEMENT"
    )
    before_id = _move_uuid(before_page_id, nullable=True, code="INVALID_PLACEMENT")
    if target_id in {destination_id, before_id}:
        raise PageCommandError("INVALID_PLACEMENT")

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
            if settings.structure_generation != base_structure_generation:
                raise PageCommandError(
                    "STALE_STRUCTURE", generation=settings.structure_generation
                )

            discovered = _move_snapshot(
                target_id=target_id,
                destination_parent_id=destination_id,
                before_page_id=before_id,
                missing_target_code="PAGE_NOT_FOUND",
            )
            target_row, ancestry_rows, source_rows, destination_rows = discovered
            affected_ids = {
                target_id,
                *(row[0] for row in ancestry_rows),
                *(row[0] for row in source_rows),
                *(row[0] for row in destination_rows),
            }
            locked_pages = list(
                Page.objects.select_for_update()
                .filter(pk__in=affected_ids)
                .order_by("id")
            )
            if len(locked_pages) != len(affected_ids):
                raise PageCommandError("TREE_UNAVAILABLE")
            try:
                revalidated = _move_snapshot(
                    target_id=target_id,
                    destination_parent_id=destination_id,
                    before_page_id=before_id,
                    missing_target_code="TREE_UNAVAILABLE",
                )
            except PageCommandError as exc:
                if exc.code in {"PAGE_NOT_FOUND", "INVALID_PLACEMENT"}:
                    raise PageCommandError("TREE_UNAVAILABLE") from None
                raise
            if revalidated != discovered:
                raise PageCommandError("TREE_UNAVAILABLE")

            page_by_id = {page.id: page for page in locked_pages}
            source_ids = [row[0] for row in source_rows]
            destination_ids = [row[0] for row in destination_rows if row[0] != target_id]
            if before_id is None:
                insertion = len(destination_ids)
            else:
                try:
                    insertion = destination_ids.index(before_id)
                except ValueError:
                    raise PageCommandError("INVALID_PLACEMENT") from None
            final_destination_ids = [
                *destination_ids[:insertion], target_id, *destination_ids[insertion:]
            ]
            same_parent = target_row[1] == destination_id
            if same_parent:
                contiguous = [row[2] for row in source_rows] == list(range(len(source_rows)))
                if final_destination_ids == source_ids and contiguous:
                    raise PageCommandError(
                        "NO_CHANGE", generation=settings.structure_generation
                    )
                count = len(source_ids)
                base = max(max(row[2] for row in source_rows), count - 1) + 1
                highest = base + count - 1
                if highest > _PAGE_POSITION_MAX:
                    raise PageCommandError("POSITION_UNAVAILABLE")
                for offset, current_id in enumerate(source_ids):
                    _save_position(page_by_id[current_id], base + offset)
                for position, current_id in enumerate(final_destination_ids):
                    _save_position(page_by_id[current_id], position)
            else:
                final_source_ids = [current_id for current_id in source_ids if current_id != target_id]
                source_count = len(source_ids)
                destination_count = len(destination_rows)
                max_current = max(page.position for page in locked_pages)
                base = max(max_current, source_count - 2, destination_count) + 1
                special = base + max(source_count - 1, destination_count)
                if special > _PAGE_POSITION_MAX:
                    raise PageCommandError("POSITION_UNAVAILABLE")
                for offset, current_id in enumerate(final_source_ids):
                    _save_position(page_by_id[current_id], base + offset)
                for offset, current_id in enumerate(destination_ids):
                    _save_position(page_by_id[current_id], base + offset)
                target = page_by_id[target_id]
                _save_position(target, special)
                target.parent_id = destination_id
                target.save(update_fields=("parent",))
                for position, current_id in enumerate(final_source_ids):
                    _save_position(page_by_id[current_id], position)
                for position, current_id in enumerate(final_destination_ids):
                    _save_position(page_by_id[current_id], position)

            target = page_by_id[target_id]
            settings.structure_generation += 1
            settings.save(update_fields=("structure_generation",))
            append_event(
                action=Action.PAGE_MOVED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=target.id,
                detail={"generation": settings.structure_generation},
            )
            return MoveResult(
                settings.structure_generation,
                target.parent_id,
                target.position,
            )
    except StaffAccessError as exc:
        raise PageCommandError(exc.code) from exc


def _reorder_snapshot(
    parent_id: uuid.UUID | None,
) -> tuple[
    tuple[uuid.UUID, uuid.UUID | None, int] | None,
    tuple[tuple[uuid.UUID, uuid.UUID | None, int], ...],
]:
    parent = None
    if parent_id is not None:
        parent = _move_row(parent_id)
        if parent is None:
            raise PageCommandError("PARENT_NOT_FOUND")
    children = tuple(
        Page.objects.filter(parent_id=parent_id)
        .order_by("id")
        .values_list("id", "parent_id", "position")[: _MOVE_GRAPH_CAP + 1]
    )
    if len(children) > _MOVE_GRAPH_CAP:
        raise PageCommandError("REORDER_UNAVAILABLE")
    return parent, children


def reorder_children(
    *,
    actor_id: object,
    session_generation: object,
    base_structure_generation: object,
    parent_id: object,
    ordered_child_ids: object,
) -> ReorderResult:
    if type(base_structure_generation) is not int or base_structure_generation < 1:
        raise PageCommandError("INVALID_PAGE_REORDER")
    if parent_id is not None and type(parent_id) is not uuid.UUID:
        raise PageCommandError("INVALID_PAGE_REORDER")
    if type(ordered_child_ids) not in {tuple, list} or len(ordered_child_ids) > _MOVE_GRAPH_CAP:
        raise PageCommandError("INVALID_PAGE_REORDER")
    requested = tuple(ordered_child_ids)
    if any(type(child_id) is not uuid.UUID for child_id in requested):
        raise PageCommandError("INVALID_PAGE_REORDER")
    if len(set(requested)) != len(requested):
        raise PageCommandError("INVALID_PAGE_REORDER")

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
            if settings.structure_generation != base_structure_generation:
                raise PageCommandError(
                    "STALE_STRUCTURE", generation=settings.structure_generation
                )

            discovered = _reorder_snapshot(parent_id)
            parent_row, child_rows = discovered
            affected_ids = {row[0] for row in child_rows}
            if parent_row is not None:
                affected_ids.add(parent_row[0])
            locked_pages = list(
                Page.objects.select_for_update()
                .filter(pk__in=affected_ids)
                .order_by("id")
            )
            if len(locked_pages) != len(affected_ids):
                raise PageCommandError("REORDER_UNAVAILABLE")
            try:
                revalidated = _reorder_snapshot(parent_id)
            except PageCommandError as exc:
                if exc.code == "PARENT_NOT_FOUND":
                    raise PageCommandError("REORDER_UNAVAILABLE") from None
                raise
            if revalidated != discovered:
                raise PageCommandError("REORDER_UNAVAILABLE")

            actual_rows = tuple(sorted(child_rows, key=lambda row: (row[2], row[0])))
            actual_ids = tuple(row[0] for row in actual_rows)
            if len(requested) != len(actual_ids) or set(requested) != set(actual_ids):
                raise PageCommandError("CHILD_SET_CONFLICT")
            contiguous = tuple(row[2] for row in actual_rows) == tuple(range(len(actual_rows)))
            if requested == actual_ids and contiguous:
                raise PageCommandError(
                    "NO_CHANGE", generation=settings.structure_generation
                )
            count = len(actual_rows)
            if count == 0:
                raise PageCommandError(
                    "NO_CHANGE", generation=settings.structure_generation
                )
            base = max(max(row[2] for row in actual_rows), count - 1) + 1
            highest = base + count - 1
            if highest > _PAGE_POSITION_MAX:
                raise PageCommandError("REORDER_UNAVAILABLE")

            page_by_id = {page.id: page for page in locked_pages}
            for offset, current_id in enumerate(sorted(actual_ids)):
                _save_position(page_by_id[current_id], base + offset)
            for position, current_id in enumerate(requested):
                _save_position(page_by_id[current_id], position)

            changed_target = next(
                (
                    current_id for position, current_id in enumerate(requested)
                    if actual_ids[position] != current_id
                ),
                actual_ids[0],
            )
            settings.structure_generation += 1
            settings.save(update_fields=("structure_generation",))
            append_event(
                action=Action.PAGE_REORDERED,
                actor=_actor_ref(actor),
                target_type=TargetType.PAGE,
                target_uuid=changed_target,
                detail={"generation": settings.structure_generation, "count": count},
            )
            return ReorderResult(settings.structure_generation, parent_id, count)
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
