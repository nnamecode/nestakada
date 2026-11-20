from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any

from django.utils.safestring import SafeString, mark_safe

from modules.accounts.api import StaffRole

from .content import FIELD_SETS, RICH_BY_KIND, canonical_payload_hash, validate_payload
from .grants import eligible_grant_groups
from .models import Page, PageContent, PageGrant, Route, RouteMode

_DEFERRED_LABELS = {
    "service_refs": "Связанные услуги",
    "process_steps": "Этапы работы",
    "brand_refs": "Марки",
    "review_refs": "Отзывы",
    "actions": "Акции",
    "reviews": "Отзывы",
    "links": "Ссылки",
    "price_rows": "Прайс",
    "media": "Медиа",
}
_RICH_LABELS = {
    "lead": "Краткое описание",
    "about": "О компании",
    "contact_text": "Контактный текст",
    "intro": "Вводный текст",
    "body": "Основной текст",
}


class EditorProjectionError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class RichControl:
    name: str
    label: str
    html: SafeString


@dataclass(frozen=True, slots=True)
class DeferredField:
    label: str
    count: int


@dataclass(frozen=True, slots=True)
class PriceColumn:
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class PriceCell:
    column_id: str
    kind: str
    text: str
    amount: str
    from_amount: bool


@dataclass(frozen=True, slots=True)
class PriceRow:
    id: str
    label: str
    cells: tuple[PriceCell, ...]


@dataclass(frozen=True, slots=True)
class PriceControl:
    columns: tuple[PriceColumn, ...]
    rows: tuple[PriceRow, ...]


@dataclass(frozen=True, slots=True)
class ProcessStep:
    title: str
    body: str


@dataclass(frozen=True, slots=True)
class ProcessControl:
    steps: tuple[ProcessStep, ...]


@dataclass(frozen=True, slots=True)
class PartnerLink:
    label: str
    https_url: str


@dataclass(frozen=True, slots=True)
class PartnerLinksControl:
    links: tuple[PartnerLink, ...]


@dataclass(frozen=True, slots=True)
class ActionCopy:
    index: int
    title: str
    body: SafeString
    internal_url: str


@dataclass(frozen=True, slots=True)
class ActionCopyControl:
    actions: tuple[ActionCopy, ...]


@dataclass(frozen=True, slots=True)
class EditorSnapshot:
    page: Page
    content: PageContent
    primary_path: str
    rich_names: tuple[str, ...]
    grant_groups: tuple[str, ...]
    can_edit_prices: bool
    can_edit_process: bool
    can_edit_links: bool
    can_edit_action_copy: bool
    has_valid_previous: bool


def _page_for_actor(*, actor: Any, page_id: object) -> tuple[Page, PageGrant | None]:
    try:
        page = Page.objects.get(pk=page_id)
    except (Page.DoesNotExist, TypeError, ValueError):
        if actor.role == StaffRole.EMPLOYEE:
            raise EditorProjectionError("FORBIDDEN") from None
        raise EditorProjectionError("PAGE_NOT_FOUND") from None
    if actor.role == StaffRole.OWNER:
        return page, None
    try:
        grant = PageGrant.objects.get(staff=actor, page=page)
    except PageGrant.DoesNotExist:
        raise EditorProjectionError("FORBIDDEN") from None
    if grant.groups not in (["prices"], ["text"], ["text", "prices"]):
        raise EditorProjectionError("FORBIDDEN")
    return page, grant


def load_editor_snapshot(*, actor: Any, page_id: object) -> EditorSnapshot:
    page, grant = _page_for_actor(actor=actor, page_id=page_id)
    routes = list(Route.objects.filter(page=page, mode=RouteMode.PRIMARY).values_list("target", flat=True))
    if len(routes) != 1:
        raise EditorProjectionError("UNAVAILABLE")
    try:
        content = PageContent.objects.get(page=page)
    except PageContent.DoesNotExist:
        raise EditorProjectionError("UNAVAILABLE") from None
    try:
        validate_payload(content.current_payload, page.kind)
        if canonical_payload_hash(content.current_payload) != content.current_hash:
            raise EditorProjectionError("UNAVAILABLE")
        has_previous = content.previous_payload is not None
        if actor.role == StaffRole.OWNER and has_previous:
            validate_payload(content.previous_payload, page.kind)
            if canonical_payload_hash(content.previous_payload) != content.previous_hash:
                raise EditorProjectionError("UNAVAILABLE")
    except (TypeError, ValueError):
        raise EditorProjectionError("UNAVAILABLE") from None

    if actor.role == StaffRole.OWNER:
        rich_names = tuple(sorted(RICH_BY_KIND.get(page.kind, set())))
        groups = ("all",)
        can_edit_prices = page.kind == "service_detail"
        can_edit_process = page.kind == "home"
        can_edit_links = page.kind == "legacy_partner_links"
        can_edit_action_copy = page.kind == "actions"
    else:
        groups = tuple(grant.groups)
        rich_names = (
            ("intro", "body")
            if "text" in grant.groups and "text" in eligible_grant_groups(page.kind)
            else ()
        )
        can_edit_prices = "prices" in grant.groups and "prices" in eligible_grant_groups(page.kind)
        can_edit_process = False
        can_edit_links = False
        can_edit_action_copy = False
    return EditorSnapshot(
        page,
        content,
        routes[0],
        rich_names,
        groups,
        can_edit_prices,
        can_edit_process,
        can_edit_links,
        can_edit_action_copy,
        has_previous,
    )


def rich_controls(snapshot: EditorSnapshot) -> tuple[RichControl, ...]:
    fields = snapshot.content.current_payload["fields"]
    return tuple(
        RichControl(name, _RICH_LABELS[name], mark_safe(fields[name]))
        for name in snapshot.rich_names
    )


def deferred_fields(snapshot: EditorSnapshot) -> tuple[DeferredField, ...]:
    fields = snapshot.content.current_payload["fields"]
    deferred = FIELD_SETS[snapshot.page.kind] - {"seo", "heading"} - set(snapshot.rich_names)
    if snapshot.can_edit_prices:
        deferred.discard("price_rows")
    if snapshot.can_edit_process:
        deferred.discard("process_steps")
    if snapshot.can_edit_links:
        deferred.discard("links")
    if snapshot.can_edit_action_copy:
        deferred.discard("actions")
    rows: list[DeferredField] = []
    for name in sorted(deferred):
        value = fields[name]
        if name == "price_rows":
            count = len(value["rows"])
        elif name == "media":
            count = sum(1 if isinstance(item, str) else len(item) for item in value.values() if item)
        else:
            count = len(value)
        rows.append(DeferredField(_DEFERRED_LABELS[name], count))
    return tuple(rows)


def price_control(snapshot: EditorSnapshot) -> PriceControl | None:
    if not snapshot.can_edit_prices:
        return None
    value = snapshot.content.current_payload["fields"]["price_rows"]
    columns = tuple(PriceColumn(item["id"], item["label"]) for item in value["columns"])
    rows: list[PriceRow] = []
    for item in value["rows"]:
        by_column = {cell["column_id"]: cell for cell in item["cells"]}
        cells: list[PriceCell] = []
        for column in columns:
            cell = by_column.get(column.id)
            cells.append(PriceCell(
                column.id,
                "" if cell is None else cell["kind"],
                "" if cell is None or cell["kind"] != "text" else cell["text"],
                "" if cell is None or cell["kind"] != "amount" else cell["amount"],
                False if cell is None or cell["kind"] != "amount" else cell["from"],
            ))
        rows.append(PriceRow(item["id"], item["label"], tuple(cells)))
    return PriceControl(columns, tuple(rows))


def process_control(snapshot: EditorSnapshot) -> ProcessControl | None:
    if not snapshot.can_edit_process:
        return None
    value = snapshot.content.current_payload["fields"]["process_steps"]
    return ProcessControl(tuple(ProcessStep(item["title"], item["body"]) for item in value))


def partner_links_control(snapshot: EditorSnapshot) -> PartnerLinksControl | None:
    if not snapshot.can_edit_links:
        return None
    value = snapshot.content.current_payload["fields"]["links"]
    return PartnerLinksControl(tuple(PartnerLink(item["label"], item["https_url"]) for item in value))


def action_copy_control(snapshot: EditorSnapshot) -> ActionCopyControl | None:
    if not snapshot.can_edit_action_copy:
        return None
    value = snapshot.content.current_payload["fields"]["actions"]
    return ActionCopyControl(tuple(
        ActionCopy(index, item["title"], mark_safe(item["body"]), item["internal_url"])
        for index, item in enumerate(value)
    ))


def owner_candidate(
    snapshot: EditorSnapshot,
    *,
    scalar: dict[str, str],
    rich: dict[str, str],
    prices: dict | None = None,
    process_steps: list[dict[str, str]] | None = None,
    links: list[dict[str, str]] | None = None,
    action_copy: list[dict[str, str]] | None = None,
) -> dict:
    candidate = copy.deepcopy(snapshot.content.current_payload)
    fields = candidate["fields"]
    fields["seo"] = {
        "title": scalar["seo.title"],
        "description": scalar["seo.description"],
        "allow_index": scalar["seo.allow_index"] == "1",
    }
    fields["heading"] = {"h1": scalar["heading.h1"]}
    for name, value in rich.items():
        fields[name] = value
    if prices is not None:
        fields["price_rows"] = prices
    if process_steps is not None:
        fields["process_steps"] = process_steps
    if links is not None:
        fields["links"] = links
    if action_copy is not None:
        fields["actions"] = action_copy
    return candidate


def employee_patch(
    snapshot: EditorSnapshot,
    *,
    rich: dict[str, str],
    prices: dict | None,
) -> dict:
    fields = snapshot.content.current_payload["fields"]
    changes: dict[str, Any] = {}
    if snapshot.rich_names:
        changes["text"] = {
            "intro": rich.get("intro", fields["intro"]),
            "body": rich.get("body", fields["body"]),
        }
    if prices is not None:
        changes["prices"] = prices
    return changes


def validate_editor_changes(snapshot: EditorSnapshot, *, changes: dict, is_owner: bool) -> None:
    if is_owner:
        candidate = changes
    else:
        candidate = copy.deepcopy(snapshot.content.current_payload)
        if "text" in changes:
            candidate["fields"]["intro"] = changes["text"]["intro"]
            candidate["fields"]["body"] = changes["text"]["body"]
        if "prices" in changes:
            candidate["fields"]["price_rows"] = changes["prices"]
    validate_payload(candidate, snapshot.page.kind)
