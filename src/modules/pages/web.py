from __future__ import annotations

import re
import uuid
from typing import Any

from django.contrib.auth import logout
from django.core.exceptions import (
    RequestDataTooBig,
    SuspiciousOperation,
    TooManyFieldsSent,
    ValidationError,
)
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole, User, staff_session_required
from modules.media.api import project_site_logo_options

from .commands import (
    PageCommandError,
    change_primary_url,
    create_page,
    delete_leaf_page,
    load_page_delete_preview,
    move_page,
    rename_page,
    reorder_children,
    save_page_content,
    set_page_publication,
    undo_page_content,
    validate_page_create_input,
    validate_page_name,
)
from .editor import (
    action_copy_control,
    EditorProjectionError,
    deferred_fields,
    employee_patch,
    load_editor_snapshot,
    owner_candidate,
    partner_links_control,
    price_control,
    process_control,
    rich_controls,
    validate_editor_changes,
)
from .grants import (
    GrantCommandError,
    eligible_grant_groups,
    grant_state_hash,
    revoke_page_grant,
    set_page_grant,
)
from .models import Page, PageGrant, PageKind, Route, RouteMode, RouteOutcome, SiteSettings
from .site_settings import SiteSettingsCommandError, update_site_settings
from .staff import (
    StaffLifecycleError,
    deactivate_employee,
    reactivate_employee,
    staff_grants_digest,
)


_RICH_ACTIONS = (
    ("p", "Абзац"), ("h2", "H2"), ("h3", "H3"), ("strong", "Жирный"),
    ("em", "Курсив"), ("u", "Подчёркнутый"), ("s", "Зачёркнутый"),
    ("blockquote", "Цитата"), ("ul", "Список"), ("ol", "Нумерация"),
    ("link", "Ссылка"), ("unlink", "Убрать ссылку"),
)


@require_GET
@staff_session_required
def page_list_view(request: HttpRequest) -> HttpResponse:
    actor = request.staff_actor
    pages = Page.objects.select_related("content").prefetch_related(
        Prefetch(
            "routes",
            queryset=Route.objects.filter(mode=RouteMode.PRIMARY),
            to_attr="private_primary_routes",
        )
    )
    if actor.role == StaffRole.EMPLOYEE:
        pages = pages.filter(grants__staff=actor).prefetch_related(
            Prefetch(
                "grants",
                queryset=PageGrant.objects.filter(staff=actor),
                to_attr="private_actor_grants",
            )
        )
    try:
        selected = list(pages)
        rows = []
        for page in selected:
            routes = page.private_primary_routes
            if len(routes) != 1:
                raise ValueError("page-composition")
            content = page.content
            if actor.role == StaffRole.OWNER:
                groups = ("all",)
            else:
                grants = page.private_actor_grants
                if len(grants) != 1:
                    raise ValueError("page-composition")
                groups = tuple(grants[0].groups)
            rows.append({
                "id": page.id,
                "name": page.name,
                "path": routes[0].target,
                "kind": page.kind,
                "published": page.is_published,
                "generation": content.generation,
                "groups": groups,
            })
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return render(
        request,
        "pages/page_list.html",
        {
            "rows": rows,
            "can_create": actor.role == StaffRole.OWNER,
            "can_reorder": actor.role == StaffRole.OWNER,
            "can_view_audit": actor.role == StaffRole.OWNER,
        },
    )


def _projection_error(exc: EditorProjectionError) -> HttpResponse:
    if exc.code == "FORBIDDEN":
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if exc.code == "PAGE_NOT_FOUND":
        return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
    return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")


@require_GET
@staff_session_required
def page_editor_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    try:
        snapshot = load_editor_snapshot(actor=request.staff_actor, page_id=page_id)
    except EditorProjectionError as exc:
        return _projection_error(exc)
    fields = snapshot.content.current_payload["fields"]
    can_save = (
        request.staff_actor.role == StaffRole.OWNER
        or bool(snapshot.rich_names)
        or snapshot.can_edit_prices
    )
    context = {
        "page": snapshot.page,
        "primary_path": snapshot.primary_path,
        "generation": snapshot.content.generation,
        "base_current_hash": snapshot.content.current_hash,
        "grant_groups": snapshot.grant_groups,
        "is_owner": request.staff_actor.role == StaffRole.OWNER,
        "can_change_url": (
            request.staff_actor.role == StaffRole.OWNER
            and snapshot.page.primary_url_mutable is True
        ),
        "can_save": can_save,
        "save_operation_id": uuid.uuid4() if can_save else None,
        "undo_operation_id": (
            uuid.uuid4()
            if request.staff_actor.role == StaffRole.OWNER and snapshot.has_valid_previous
            else None
        ),
        "seo": fields["seo"] if request.staff_actor.role == StaffRole.OWNER else None,
        "heading": fields["heading"] if request.staff_actor.role == StaffRole.OWNER else None,
        "rich_controls": rich_controls(snapshot),
        "rich_actions": _RICH_ACTIONS,
        "price_control": price_control(snapshot),
        "process_control": process_control(snapshot),
        "partner_links_control": partner_links_control(snapshot),
        "action_copy_control": action_copy_control(snapshot),
        "prices_only": (
            request.staff_actor.role == StaffRole.EMPLOYEE
            and snapshot.can_edit_prices
            and not snapshot.rich_names
        ),
        "deferred_fields": (
            deferred_fields(snapshot) if request.staff_actor.role == StaffRole.OWNER else ()
        ),
    }
    return render(request, "pages/page_editor.html", context)


def _single(post: Any, key: str) -> str:
    values = post.getlist(key)
    if len(values) != 1:
        raise ValueError("wire")
    return values[0]


def _canonical_create_uuid(value: str) -> uuid.UUID:
    parsed = uuid.UUID(value)
    if str(parsed) != value:
        raise ValueError("uuid")
    return parsed


def _page_create_form_context() -> dict[str, Any]:
    with transaction.atomic():
        settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
        pages = list(Page.objects.order_by("id")[:513])
        if len(pages) > 512:
            raise ValueError("graph")
        page_by_id = {page.id: page for page in pages}
        for page in pages:
            if page.parent_id is not None and page.parent_id not in page_by_id:
                raise ValueError("graph")
            seen: set[uuid.UUID] = set()
            current: Page | None = page
            while current is not None:
                if current.id in seen:
                    raise ValueError("graph")
                seen.add(current.id)
                current = (
                    None if current.parent_id is None else page_by_id[current.parent_id]
                )
        return {
            "page_id": uuid.uuid4(),
            "structure_generation": settings.structure_generation,
            "kinds": tuple(PageKind.values),
            "parents": pages,
        }


def _page_create_conflict(request: HttpRequest) -> HttpResponse:
    return render(request, "pages/page_create_conflict.html", status=409)


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_create_view(request: HttpRequest) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            context = _page_create_form_context()
        except Exception:
            return HttpResponse(
                "PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain"
            )
        return render(request, "pages/page_create.html", context)

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        expected = {
            "page_id", "base_structure_generation", "kind", "name",
            "parent_id", "primary_path",
        }
        keys = set(post)
        if keys not in (expected, expected | {"csrfmiddlewaretoken"}):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        page_id = _canonical_create_uuid(_single(post, "page_id"))
        raw_generation = _single(post, "base_structure_generation")
        generation = int(raw_generation)
        if generation < 1 or str(generation) != raw_generation:
            raise ValueError("wire")
        kind = _single(post, "kind")
        name = _single(post, "name")
        primary_path = _single(post, "primary_path")
        parent_token = _single(post, "parent_id")
        parent_id = (
            None if parent_token == "root" else _canonical_create_uuid(parent_token)
        )
        validate_page_create_input(kind, name, primary_path)
    except PageCommandError as exc:
        if exc.code == "CREATE_UNAVAILABLE":
            return HttpResponse(
                "PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain"
            )
        return HttpResponse(
            "INVALID_PAGE_CREATE_INPUT", status=400, content_type="text/plain"
        )
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse(
            "INVALID_PAGE_CREATE_INPUT", status=400, content_type="text/plain"
        )
    try:
        result = create_page(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            kind=kind,
            name=name,
            parent_id=parent_id,
            primary_path=primary_path,
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code in {
            "STALE_STRUCTURE", "PATH_OCCUPIED", "INVALID_PARENT", "PAGE_ID_CONFLICT",
        }:
            return _page_create_conflict(request)
        if exc.code in {"INVALID_BASIS", "INVALID_PAGE_CREATE"}:
            return HttpResponse(
                "INVALID_PAGE_CREATE_INPUT", status=400, content_type="text/plain"
            )
        return HttpResponse(
            "PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain"
        )
    except Exception:
        return HttpResponse(
            "PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain"
        )
    return redirect("manage-page-editor", page_id=result.page_id)


def _basis(post: Any) -> tuple[uuid.UUID, int, str]:
    operation_value = _single(post, "operation_id")
    generation_value = _single(post, "base_generation")
    current_hash = _single(post, "base_current_hash")
    try:
        operation_id = uuid.UUID(operation_value)
        generation = int(generation_value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("basis") from None
    if (
        str(operation_id) != operation_value
        or generation < 1
        or str(generation) != generation_value
        or len(current_hash) != 64
        or any(char not in "0123456789abcdef" for char in current_hash)
    ):
        raise ValueError("basis")
    return operation_id, generation, current_hash


def _multipart(request: HttpRequest) -> Any:
    if request.content_type != "multipart/form-data":
        raise ValueError("wire")
    post = request.POST
    if request.FILES:
        raise ValueError("wire")
    if "csrfmiddlewaretoken" in post and len(post.getlist("csrfmiddlewaretoken")) != 1:
        raise ValueError("wire")
    return post


def _canonical_uuid(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("price-uuid") from None
    if str(parsed) != value:
        raise ValueError("price-uuid")
    return value


def _price_wire(post: Any, *, changed: str) -> dict | None:
    if changed == "0":
        if any(name in post for name in ("price.column", "price.row", "price.cell")):
            raise ValueError("price-wire")
        return None
    if changed != "1":
        raise ValueError("price-wire")

    column_records = post.getlist("price.column")
    row_records = post.getlist("price.row")
    cell_records = post.getlist("price.cell")
    if len(column_records) > 32 or len(row_records) > 500 or len(cell_records) > 10_000:
        raise ValueError("price-cap")

    columns: list[dict[str, str]] = []
    column_ids: list[str] = []
    for record in column_records:
        parts = record.split("\t")
        if len(parts) != 2:
            raise ValueError("price-column")
        identifier = _canonical_uuid(parts[0])
        columns.append({"id": identifier, "label": parts[1]})
        column_ids.append(identifier)
    if len(column_ids) != len(set(column_ids)):
        raise ValueError("price-column")

    rows: list[dict[str, Any]] = []
    row_ids: list[str] = []
    for record in row_records:
        parts = record.split("\t")
        if len(parts) != 2:
            raise ValueError("price-row")
        identifier = _canonical_uuid(parts[0])
        rows.append({"id": identifier, "label": parts[1], "cells": []})
        row_ids.append(identifier)
    if len(row_ids) != len(set(row_ids)) or set(row_ids) & set(column_ids):
        raise ValueError("price-row")

    cells: dict[tuple[str, str], dict[str, object]] = {}
    for record in cell_records:
        parts = record.split("\t")
        if len(parts) not in (4, 5):
            raise ValueError("price-cell")
        row_id, column_id, kind = parts[:3]
        _canonical_uuid(row_id)
        _canonical_uuid(column_id)
        key = (row_id, column_id)
        if row_id not in row_ids or column_id not in column_ids or key in cells:
            raise ValueError("price-cell")
        if kind == "text" and len(parts) == 4:
            cell: dict[str, object] = {
                "column_id": column_id,
                "kind": "text",
                "text": parts[3],
            }
        elif kind == "amount" and len(parts) == 5 and parts[4] in {"0", "1"}:
            cell = {
                "column_id": column_id,
                "kind": "amount",
                "amount": parts[3],
                "from": parts[4] == "1",
            }
        else:
            raise ValueError("price-cell")
        cells[key] = cell

    for row, row_id in zip(rows, row_ids, strict=True):
        row["cells"] = [cells[(row_id, column_id)] for column_id in column_ids if (row_id, column_id) in cells]
    return {"columns": columns, "rows": rows}


def _process_wire(post: Any, *, changed: str) -> list[dict[str, str]] | None:
    if changed == "0":
        if "process.step" in post:
            raise ValueError("process-wire")
        return None
    if changed != "1":
        raise ValueError("process-wire")
    records = post.getlist("process.step")
    if len(records) > 12:
        raise ValueError("process-cap")
    steps: list[dict[str, str]] = []
    for record in records:
        parts = record.split("\t")
        if len(parts) != 2:
            raise ValueError("process-step")
        steps.append({"title": parts[0], "body": parts[1]})
    return steps


def _links_wire(post: Any, *, changed: str) -> list[dict[str, str]] | None:
    if changed == "0":
        if "links.item" in post:
            raise ValueError("links-wire")
        return None
    if changed != "1":
        raise ValueError("links-wire")
    records = post.getlist("links.item")
    if len(records) > 64:
        raise ValueError("links-cap")
    links: list[dict[str, str]] = []
    for record in records:
        parts = record.split("\t")
        if len(parts) != 2:
            raise ValueError("links-item")
        links.append({"label": parts[0], "https_url": parts[1]})
    return links


def _action_copy_wire(post: Any, snapshot: Any) -> list[dict[str, str]] | None:
    if not snapshot.can_edit_action_copy:
        return None
    current = snapshot.content.current_payload["fields"]["actions"]
    if len(current) > 32:
        raise ValueError("actions-cap")
    actions: list[dict[str, str]] = []
    for index, item in enumerate(current):
        title = _single(post, f"actions.{index}.title")
        flag = _single(post, f"actions.{index}.body.changed")
        value_key = f"actions.{index}.body.value"
        if flag == "0":
            if value_key in post:
                raise ValueError("actions-wire")
            body = item["body"]
        elif flag == "1":
            body = _single(post, value_key)
            if len(body.encode("utf-8")) > 1_048_576:
                raise ValueError("actions-wire")
        else:
            raise ValueError("actions-wire")
        actions.append({
            "title": title,
            "body": body,
            "internal_url": item["internal_url"],
        })
    return actions


def _save_wire(post: Any, snapshot: Any, *, is_owner: bool) -> tuple[tuple[uuid.UUID, int, str], object]:
    basis_keys = {"operation_id", "base_generation", "base_current_hash"}
    scalar_keys = {"seo.title", "seo.description", "seo.allow_index", "heading.h1"} if is_owner else set()
    flag_keys = {f"rich.{name}.changed" for name in snapshot.rich_names}
    value_keys = {f"rich.{name}.value" for name in snapshot.rich_names}
    price_keys = {"price.changed", "price.column", "price.row", "price.cell"} if snapshot.can_edit_prices else set()
    process_keys = {"process.changed", "process.step"} if snapshot.can_edit_process else set()
    links_keys = {"links.changed", "links.item"} if snapshot.can_edit_links else set()
    action_required = {
        key
        for index in range(len(snapshot.content.current_payload["fields"].get("actions", ())))
        for key in (f"actions.{index}.title", f"actions.{index}.body.changed")
    } if snapshot.can_edit_action_copy else set()
    action_values = {
        f"actions.{index}.body.value"
        for index in range(len(snapshot.content.current_payload["fields"].get("actions", ())))
    } if snapshot.can_edit_action_copy else set()
    submitted = set(post) - {"csrfmiddlewaretoken"}
    required = (
        basis_keys
        | scalar_keys
        | flag_keys
        | ({"price.changed"} if snapshot.can_edit_prices else set())
        | ({"process.changed"} if snapshot.can_edit_process else set())
        | ({"links.changed"} if snapshot.can_edit_links else set())
        | action_required
    )
    allowed = required | value_keys | price_keys | process_keys | links_keys | action_values
    if not required <= submitted or not submitted <= allowed:
        raise ValueError("wire")

    scalar = {key: _single(post, key) for key in scalar_keys}
    if is_owner and scalar["seo.allow_index"] not in {"0", "1"}:
        raise ValueError("wire")
    rich: dict[str, str] = {}
    for name in snapshot.rich_names:
        flag = _single(post, f"rich.{name}.changed")
        value_key = f"rich.{name}.value"
        if flag == "0":
            if value_key in post:
                raise ValueError("wire")
        elif flag == "1":
            rich[name] = _single(post, value_key)
            if len(rich[name].encode("utf-8")) > 1_048_576:
                raise ValueError("wire")
        else:
            raise ValueError("wire")
    prices = (
        _price_wire(post, changed=_single(post, "price.changed"))
        if snapshot.can_edit_prices
        else None
    )
    process_steps = (
        _process_wire(post, changed=_single(post, "process.changed"))
        if snapshot.can_edit_process
        else None
    )
    links = (
        _links_wire(post, changed=_single(post, "links.changed"))
        if snapshot.can_edit_links
        else None
    )
    action_copy = _action_copy_wire(post, snapshot)
    if not is_owner and not snapshot.rich_names and prices is None:
        raise ValueError("empty-patch")
    basis = _basis(post)
    changes = (
        owner_candidate(
            snapshot,
            scalar=scalar,
            rich=rich,
            prices=prices,
            process_steps=process_steps,
            links=links,
            action_copy=action_copy,
        )
        if is_owner
        else employee_patch(snapshot, rich=rich, prices=prices)
    )
    validate_editor_changes(snapshot, changes=changes, is_owner=is_owner)
    return basis, changes


def _command_error(request: HttpRequest, exc: PageCommandError, *, page_id: uuid.UUID) -> HttpResponse:
    if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
        logout(request)
        return redirect("manage-login")
    if exc.code == "FORBIDDEN":
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if exc.code == "PAGE_NOT_FOUND":
        return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
    if exc.code in {"STALE_CONTENT", "OPERATION_CONFLICT"}:
        return render(
            request,
            "pages/page_conflict.html",
            {"page_id": page_id, "generation": exc.generation, "current_hash": exc.current_hash},
            status=409,
        )
    if exc.code == "NO_PREVIOUS":
        return HttpResponse("NO_PREVIOUS", status=409, content_type="text/plain")
    if exc.code in {
        "INVALID_OPERATION",
        "INVALID_BASIS",
        "INVALID_PATCH",
        "INVALID_CONTENT",
    }:
        return HttpResponse("INVALID_EDITOR_INPUT", status=400, content_type="text/plain")
    return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")


def _publication_conflict(
    request: HttpRequest,
    *,
    page_id: uuid.UUID,
    generation: int | None,
) -> HttpResponse:
    return render(
        request,
        "pages/page_publication_conflict.html",
        {"page_id": page_id, "generation": generation},
        status=409,
    )


def _rename_conflict(
    request: HttpRequest,
    *,
    page_id: uuid.UUID,
    generation: int | None,
) -> HttpResponse:
    return render(
        request,
        "pages/page_rename_conflict.html",
        {"page_id": page_id, "generation": generation},
        status=409,
    )


def _url_conflict(request: HttpRequest, *, page_id: uuid.UUID) -> HttpResponse:
    return render(
        request,
        "pages/page_url_conflict.html",
        {"reload_url": f"/manage/pages/{page_id}/url/"},
        status=409,
    )


def _move_conflict(
    request: HttpRequest,
    *,
    page_id: uuid.UUID,
    generation: int | None,
) -> HttpResponse:
    return render(
        request,
        "pages/page_move_conflict.html",
        {"page_id": page_id, "generation": generation},
        status=409,
    )


def _canonical_move_uuid(token: str) -> uuid.UUID:
    if type(token) is not str or len(token) != 36:
        raise ValueError("wire")
    parsed = uuid.UUID(token)
    if str(parsed) != token:
        raise ValueError("wire")
    return parsed


def _move_form_context(page_id: uuid.UUID) -> dict[str, Any]:
    with transaction.atomic():
        settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
        pages = list(Page.objects.order_by("id")[:513])
        if len(pages) > 512:
            raise ValueError("graph")
        page_by_id = {page.id: page for page in pages}
        if page_id not in page_by_id:
            raise PageCommandError("PAGE_NOT_FOUND")
        if len(page_by_id) != len(pages):
            raise ValueError("graph")
        children: dict[uuid.UUID | None, list[Page]] = {}
        for page in pages:
            if page.parent_id == page.id:
                raise ValueError("graph")
            if page.parent_id is not None and page.parent_id not in page_by_id:
                raise ValueError("graph")
            children.setdefault(page.parent_id, []).append(page)
        for page in pages:
            seen: set[uuid.UUID] = set()
            current: Page | None = page
            while current is not None:
                if current.id in seen:
                    raise ValueError("graph")
                seen.add(current.id)
                current = (
                    None
                    if current.parent_id is None
                    else page_by_id[current.parent_id]
                )
        descendants: set[uuid.UUID] = set()
        pending = list(children.get(page_id, ()))
        while pending:
            current = pending.pop()
            if current.id in descendants:
                raise ValueError("graph")
            descendants.add(current.id)
            pending.extend(children.get(current.id, ()))
        for siblings in children.values():
            siblings.sort(key=lambda page: (page.position, page.id))

        options: list[dict[str, str]] = []
        parent_candidates: list[Page | None] = [None]
        parent_candidates.extend(
            page for page in pages
            if page.id != page_id and page.id not in descendants
        )
        for parent in parent_candidates:
            siblings = [
                child for child in children.get(None if parent is None else parent.id, ())
                if child.id != page_id
            ]
            parent_token = "root" if parent is None else str(parent.id)
            parent_label = "Корень" if parent is None else parent.name
            for child in siblings:
                options.append({
                    "value": f"{parent_token}|{child.id}",
                    "label": f"{parent_label}: перед «{child.name}»",
                })
            options.append({
                "value": f"{parent_token}|end",
                "label": f"{parent_label}: в конец",
            })
        if len(options) > 2 * len(pages) + 1:
            raise ValueError("graph")
        return {
            "page": page_by_id[page_id],
            "structure_generation": settings.structure_generation,
            "placement_options": options,
        }


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_move_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            context = _move_form_context(page_id)
        except PageCommandError as exc:
            if exc.code == "PAGE_NOT_FOUND":
                return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        except Exception:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(request, "pages/page_move.html", context)

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        keys = set(post)
        if keys not in (
            {"base_structure_generation", "placement"},
            {"csrfmiddlewaretoken", "base_structure_generation", "placement"},
        ):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        generation_value = _single(post, "base_structure_generation")
        placement = _single(post, "placement")
        generation = int(generation_value)
        if (
            generation < 1
            or str(generation) != generation_value
            or not 8 <= len(placement) <= 73
            or placement.count("|") != 1
        ):
            raise ValueError("wire")
        parent_token, before_token = placement.split("|")
        destination_parent_id = (
            None if parent_token == "root" else _canonical_move_uuid(parent_token)
        )
        before_page_id = (
            None if before_token == "end" else _canonical_move_uuid(before_token)
        )
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_PAGE_MOVE_INPUT", status=400, content_type="text/plain")
    try:
        move_page(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            destination_parent_id=destination_parent_id,
            before_page_id=before_page_id,
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code == "PAGE_NOT_FOUND":
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "NO_CHANGE", "INVALID_PLACEMENT"}:
            return _move_conflict(
                request, page_id=page_id, generation=exc.generation
            )
        if exc.code == "INVALID_BASIS":
            return HttpResponse("INVALID_PAGE_MOVE_INPUT", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


def _canonical_reorder_uuid(token: str) -> uuid.UUID:
    try:
        value = uuid.UUID(token)
    except (AttributeError, TypeError, ValueError):
        raise ValueError("uuid") from None
    if str(value) != token:
        raise ValueError("uuid")
    return value


def _reorder_web_snapshot(
    parent_id: uuid.UUID | None,
) -> tuple[
    tuple[uuid.UUID, uuid.UUID | None, int, str] | None,
    tuple[tuple[uuid.UUID, uuid.UUID | None, int, str], ...],
]:
    parent = None
    if parent_id is not None:
        parent = (
            Page.objects.filter(pk=parent_id)
            .values_list("id", "parent_id", "position", "name")
            .first()
        )
        if parent is None:
            raise PageCommandError("PARENT_NOT_FOUND")
    children = tuple(
        Page.objects.filter(parent_id=parent_id)
        .order_by("id")
        .values_list("id", "parent_id", "position", "name")[:513]
    )
    if len(children) > 512:
        raise PageCommandError("REORDER_UNAVAILABLE")
    return parent, children


def _reorder_form_context(parent_id: uuid.UUID | None) -> dict[str, Any]:
    with transaction.atomic():
        settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
        discovered = _reorder_web_snapshot(parent_id)
        parent, child_rows = discovered
        affected_ids = {row[0] for row in child_rows}
        if parent is not None:
            affected_ids.add(parent[0])
        locked = list(
            Page.objects.select_for_update().filter(pk__in=affected_ids).order_by("id")
        )
        if len(locked) != len(affected_ids):
            raise PageCommandError("REORDER_UNAVAILABLE")
        if _reorder_web_snapshot(parent_id) != discovered:
            raise PageCommandError("REORDER_UNAVAILABLE")
        ordered = sorted(child_rows, key=lambda row: (row[2], row[0]))
        return {
            "parent_name": None if parent is None else parent[3],
            "parent_token": "root" if parent_id is None else str(parent_id),
            "structure_generation": settings.structure_generation,
            "children": [
                {
                    "id": row[0], "name": row[3],
                    "can_up": index > 0, "can_down": index + 1 < len(ordered),
                }
                for index, row in enumerate(ordered)
            ],
        }


def _reorder_location(parent_token: str) -> str:
    return f"/manage/pages/reorder/?parent={parent_token}"


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_reorder_view(request: HttpRequest) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            if set(request.GET) != {"parent"} or len(request.GET.getlist("parent")) != 1:
                raise ValueError("query")
            parent_token = request.GET["parent"]
            parent_id = (
                None if parent_token == "root" else _canonical_reorder_uuid(parent_token)
            )
            context = _reorder_form_context(parent_id)
        except ValueError:
            return HttpResponse(
                "INVALID_PAGE_REORDER_INPUT", status=400, content_type="text/plain"
            )
        except PageCommandError as exc:
            if exc.code == "PARENT_NOT_FOUND":
                return HttpResponse("PARENT_NOT_FOUND", status=404, content_type="text/plain")
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        except Exception:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(request, "pages/page_reorder.html", context)

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        keys = set(post)
        if keys not in (
            {"base_structure_generation", "parent", "child_id", "move"},
            {"csrfmiddlewaretoken", "base_structure_generation", "parent", "child_id", "move"},
        ):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        generation_value = _single(post, "base_structure_generation")
        parent_token = _single(post, "parent")
        move_token = _single(post, "move")
        generation = int(generation_value)
        if generation < 1 or str(generation) != generation_value:
            raise ValueError("wire")
        parent_id = (
            None if parent_token == "root" else _canonical_reorder_uuid(parent_token)
        )
        child_tokens = post.getlist("child_id")
        if not 1 <= len(child_tokens) <= 512:
            raise ValueError("wire")
        child_ids = [_canonical_reorder_uuid(token) for token in child_tokens]
        if len(set(child_ids)) != len(child_ids):
            raise ValueError("wire")
        if move_token.count("|") != 1 or len(move_token) not in {39, 41}:
            raise ValueError("wire")
        move_id_token, direction = move_token.split("|")
        move_id = _canonical_reorder_uuid(move_id_token)
        if direction not in {"up", "down"} or move_id not in child_ids:
            raise ValueError("wire")
        index = child_ids.index(move_id)
        other = index - 1 if direction == "up" else index + 1
        if other < 0 or other >= len(child_ids):
            raise ValueError("wire")
        child_ids[index], child_ids[other] = child_ids[other], child_ids[index]
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse(
            "INVALID_PAGE_REORDER_INPUT", status=400, content_type="text/plain"
        )
    try:
        reorder_children(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            base_structure_generation=generation,
            parent_id=parent_id,
            ordered_child_ids=child_ids,
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code == "PARENT_NOT_FOUND":
            return HttpResponse("PARENT_NOT_FOUND", status=404, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "NO_CHANGE", "CHILD_SET_CONFLICT"}:
            return render(
                request,
                "pages/page_reorder_conflict.html",
                {"reload_url": _reorder_location(parent_token)},
                status=409,
            )
        if exc.code == "INVALID_PAGE_REORDER":
            return HttpResponse(
                "INVALID_PAGE_REORDER_INPUT", status=400, content_type="text/plain"
            )
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    response = HttpResponse(status=302)
    response["Location"] = _reorder_location(parent_token)
    return response


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_rename_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            with transaction.atomic():
                settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
                page = Page.objects.select_for_update().get(pk=page_id)
                context = {
                    "page": page,
                    "structure_generation": settings.structure_generation,
                }
        except Page.DoesNotExist:
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        except Exception:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(request, "pages/page_rename.html", context)

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        keys = set(post)
        if keys not in (
            {"base_structure_generation", "name"},
            {"csrfmiddlewaretoken", "base_structure_generation", "name"},
        ):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        generation_value = _single(post, "base_structure_generation")
        name = _single(post, "name")
        generation = int(generation_value)
        if generation < 1 or str(generation) != generation_value:
            raise ValueError("wire")
        validate_page_name(name)
    except (
        PageCommandError,
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_PAGE_RENAME_INPUT", status=400, content_type="text/plain")
    try:
        rename_page(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            name=name,
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code == "PAGE_NOT_FOUND":
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "NO_CHANGE"}:
            return _rename_conflict(
                request,
                page_id=page_id,
                generation=exc.generation,
            )
        if exc.code in {"INVALID_BASIS", "INVALID_PAGE_NAME"}:
            return HttpResponse("INVALID_PAGE_RENAME_INPUT", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


def _page_url_form_context(page_id: uuid.UUID) -> dict[str, Any]:
    with transaction.atomic():
        settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
        page = Page.objects.select_for_update().get(pk=page_id)
        routes = list(
            Route.objects.select_for_update().filter(page=page).order_by("id")[:513]
        )
        primary = [route for route in routes if route.mode == RouteMode.PRIMARY]
        try:
            for route in routes:
                route.clean()
        except ValidationError as exc:
            raise ValueError("composition") from exc
        if page.primary_url_mutable is not True:
            raise PageCommandError("LEGACY_URL_PROTECTED")
        if (
            len(routes) >= 512
            or len(primary) != 1
            or any(route.mode not in RouteMode.values for route in routes)
            or any(route.outcome not in RouteOutcome.values for route in routes)
            or any(
                route.mode == RouteMode.REDIRECT and route.target == primary[0].target
                for route in routes
            )
        ):
            raise ValueError("composition")
        return {
            "page": page,
            "primary_path": primary[0].target,
            "structure_generation": settings.structure_generation,
        }


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_url_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            return render(request, "pages/page_url.html", _page_url_form_context(page_id))
        except Page.DoesNotExist:
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        except PageCommandError as exc:
            if exc.code == "LEGACY_URL_PROTECTED":
                return HttpResponse(exc.code, status=403, content_type="text/plain")
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        except Exception:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        keys = set(post)
        if keys not in (
            {"base_structure_generation", "new_path"},
            {"csrfmiddlewaretoken", "base_structure_generation", "new_path"},
        ):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        generation_value = _single(post, "base_structure_generation")
        new_path = _single(post, "new_path")
        generation = int(generation_value)
        if generation < 1 or str(generation) != generation_value:
            raise ValueError("wire")
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_PAGE_URL_INPUT", status=400, content_type="text/plain")
    try:
        change_primary_url(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            new_path=new_path,
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code in {"FORBIDDEN", "LEGACY_URL_PROTECTED"}:
            return HttpResponse(exc.code, status=403, content_type="text/plain")
        if exc.code == "PAGE_NOT_FOUND":
            return HttpResponse(exc.code, status=404, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "NO_CHANGE", "PATH_OCCUPIED"}:
            return _url_conflict(request, page_id=page_id)
        if exc.code in {"INVALID_BASIS", "INVALID_PAGE_URL"}:
            return HttpResponse("INVALID_PAGE_URL_INPUT", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


def _delete_conflict(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    return render(
        request, "pages/page_delete_conflict.html",
        {"reload_url": f"/manage/pages/{page_id}/delete/"}, status=409,
    )


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_delete_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            preview = load_page_delete_preview(
                actor_id=request.staff_actor.id,
                session_generation=request.session.get(SESSION_GENERATION_KEY),
                page_id=page_id,
            )
        except PageCommandError as exc:
            if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
                logout(request); return redirect("manage-login")
            if exc.code == "PAGE_NOT_FOUND":
                return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
            if exc.code == "GALLERY_DELETE_REQUIRED":
                return HttpResponse("GALLERY_DELETE_REQUIRED", status=409, content_type="text/plain")
            if exc.code == "PAGE_HAS_CHILDREN":
                return _delete_conflict(request, page_id)
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        except Exception:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(request, "pages/page_delete.html", {"preview": preview})

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        required = {
            "base_structure_generation", "composition_digest", "expected_name",
            "expected_primary_path", "current_password", "confirm_delete",
        }
        keys = set(post)
        if keys not in (required, required | {"csrfmiddlewaretoken"}):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        values = {key: _single(post, key) for key in required}
        generation = int(values["base_structure_generation"])
        if (generation < 1 or str(generation) != values["base_structure_generation"]
                or len(values["expected_name"]) > 500
                or len(values["expected_primary_path"]) > 2048
                or re.fullmatch(r"[0-9a-f]{64}", values["composition_digest"]) is None
                or not 1 <= len(values["current_password"]) <= 4096
                or values["confirm_delete"] != "1"):
            raise ValueError("wire")
    except (ValueError, RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
        return HttpResponse("INVALID_PAGE_DELETE_INPUT", status=400, content_type="text/plain")
    try:
        delete_leaf_page(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            expected_name=values["expected_name"],
            expected_primary_path=values["expected_primary_path"],
            expected_composition_digest=values["composition_digest"],
            current_password=values["current_password"],
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request); return redirect("manage-login")
        if exc.code in {"FORBIDDEN", "CURRENT_PASSWORD_INVALID"}:
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code == "PAGE_NOT_FOUND":
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        if exc.code == "GALLERY_DELETE_REQUIRED":
            return HttpResponse("GALLERY_DELETE_REQUIRED", status=409, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "DELETE_CONFIRMATION_STALE", "PAGE_HAS_CHILDREN"}:
            return _delete_conflict(request, page_id)
        if exc.code in {"INVALID_BASIS", "INVALID_PAGE_DELETE"}:
            return HttpResponse("INVALID_PAGE_DELETE_INPUT", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-pages")


@require_http_methods(["GET", "POST"])
@staff_session_required
def page_publication_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if request.method == "GET":
        try:
            page = Page.objects.get(pk=page_id)
        except Page.DoesNotExist:
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        try:
            settings = SiteSettings.objects.get(singleton_key=True)
        except SiteSettings.DoesNotExist:
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(
            request,
            "pages/page_publication.html",
            {"page": page, "structure_generation": settings.structure_generation},
        )

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        keys = set(post)
        if keys not in (
            {"base_structure_generation", "desired_published"},
            {"csrfmiddlewaretoken", "base_structure_generation", "desired_published"},
        ):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        generation_value = _single(post, "base_structure_generation")
        desired_value = _single(post, "desired_published")
        generation = int(generation_value)
        if generation < 1 or str(generation) != generation_value or desired_value not in {"0", "1"}:
            raise ValueError("wire")
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_PUBLICATION_INPUT", status=400, content_type="text/plain")
    try:
        set_page_publication(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            base_structure_generation=generation,
            desired_published=desired_value == "1",
        )
    except PageCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code == "PAGE_NOT_FOUND":
            return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
        if exc.code in {"STALE_STRUCTURE", "NO_CHANGE"}:
            return _publication_conflict(
                request,
                page_id=page_id,
                generation=exc.generation,
            )
        if exc.code in {"INVALID_BASIS", "INVALID_PUBLICATION"}:
            return HttpResponse("INVALID_PUBLICATION_INPUT", status=400, content_type="text/plain")
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


_SETTINGS_FIELDS = (
    "organization_name",
    "phone_display",
    "phone_e164",
    "address",
    "opening_hours",
    "contact_email",
    "map_url",
)


@require_http_methods(["GET", "POST"])
@staff_session_required
def site_settings_view(request: HttpRequest) -> HttpResponse:
    actor = request.staff_actor
    if request.method == "POST" and actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")

    if request.method == "GET":
        try:
            settings = SiteSettings.objects.get(singleton_key=True)
            logo_options = project_site_logo_options(
                settings_id=settings.id,
                current_logo_id=settings.logo_asset_id,
                include_options=actor.role == StaffRole.OWNER,
            )
            current_logo = next(
                option for option in logo_options if option.asset_id == settings.logo_asset_id
            )
        except Exception:
            return HttpResponse(
                "PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain"
            )
        return render(
            request,
            "pages/site_settings.html",
            {
                "settings": settings,
                "current_logo": current_logo,
                "logo_options": logo_options if actor.role == StaffRole.OWNER else (),
                "can_edit": actor.role == StaffRole.OWNER,
            },
        )

    try:
        if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
            raise ValueError("wire")
        post = request.POST
        expected = {"base_settings_generation", *_SETTINGS_FIELDS, "logo_asset_id"}
        keys = set(post)
        if keys not in (expected, expected | {"csrfmiddlewaretoken"}):
            raise ValueError("wire")
        if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
            raise ValueError("wire")
        raw_generation = _single(post, "base_settings_generation")
        generation = int(raw_generation)
        if generation < 1 or str(generation) != raw_generation:
            raise ValueError("wire")
        raw_logo_id = _single(post, "logo_asset_id")
        logo_id = uuid.UUID(raw_logo_id)
        if str(logo_id) != raw_logo_id:
            raise ValueError("wire")
        values = {name: _single(post, name) for name in _SETTINGS_FIELDS}
    except (
        ValueError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_SETTINGS_INPUT", status=400, content_type="text/plain")

    try:
        update_site_settings(
            actor_id=actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            base_settings_generation=generation,
            logo_asset_id=logo_id,
            **values,
        )
    except SiteSettingsCommandError as exc:
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        if exc.code == "FORBIDDEN":
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        if exc.code in {"STALE_SETTINGS", "NO_CHANGE"}:
            return render(
                request,
                "pages/site_settings_conflict.html",
                {"generation": exc.generation},
                status=409,
            )
        if exc.code in {"INVALID_BASIS", "INVALID_SETTINGS"}:
            return HttpResponse(
                "INVALID_SETTINGS_INPUT", status=400, content_type="text/plain"
            )
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-site-settings")


@require_POST
@staff_session_required
def page_save_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    try:
        snapshot = load_editor_snapshot(actor=request.staff_actor, page_id=page_id)
        if (
            request.staff_actor.role == StaffRole.EMPLOYEE
            and not snapshot.rich_names
            and not snapshot.can_edit_prices
        ):
            return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
        post = _multipart(request)
        basis, changes = _save_wire(
            post,
            snapshot,
            is_owner=request.staff_actor.role == StaffRole.OWNER,
        )
    except EditorProjectionError as exc:
        return _projection_error(exc)
    except (ValueError, RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
        return HttpResponse("INVALID_EDITOR_INPUT", status=400, content_type="text/plain")
    try:
        save_page_content(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            operation_id=basis[0],
            base_generation=basis[1],
            base_current_hash=basis[2],
            changes=changes,
        )
    except PageCommandError as exc:
        return _command_error(request, exc, page_id=page_id)
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


@require_POST
@staff_session_required
def page_undo_view(request: HttpRequest, page_id: uuid.UUID) -> HttpResponse:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    try:
        post = _multipart(request)
        if set(post) - {"csrfmiddlewaretoken"} != {"operation_id", "base_generation", "base_current_hash"}:
            raise ValueError("wire")
        basis = _basis(post)
    except (ValueError, RequestDataTooBig, TooManyFieldsSent, MultiPartParserError, SuspiciousOperation):
        return HttpResponse("INVALID_EDITOR_INPUT", status=400, content_type="text/plain")
    try:
        undo_page_content(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            page_id=page_id,
            operation_id=basis[0],
            base_generation=basis[1],
            base_current_hash=basis[2],
        )
    except PageCommandError as exc:
        return _command_error(request, exc, page_id=page_id)
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-page-editor", page_id=page_id)


def _owner_only(request: HttpRequest) -> HttpResponse | None:
    if request.staff_actor.role != StaffRole.OWNER:
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    return None


def _employee_target(staff_id: uuid.UUID) -> User | None:
    try:
        return User.objects.get(
            pk=staff_id,
            role=StaffRole.EMPLOYEE,
            is_active=True,
            is_staff=True,
            is_superuser=False,
        )
    except User.DoesNotExist:
        return None


def _employee_state(staff_id: uuid.UUID, *, active: bool) -> User | None:
    try:
        return User.objects.get(
            pk=staff_id,
            role=StaffRole.EMPLOYEE,
            is_active=active,
            is_staff=True,
            is_superuser=False,
        )
    except User.DoesNotExist:
        return None


@require_GET
@staff_session_required
def grant_staff_list_view(request: HttpRequest) -> HttpResponse:
    denied = _owner_only(request)
    if denied is not None:
        return denied
    try:
        selected = list(
            User.objects.filter(
                role=StaffRole.EMPLOYEE,
                is_active=True,
                is_staff=True,
                is_superuser=False,
            ).order_by("username", "id")[:101]
        )
        if len(selected) > 100:
            raise ValueError("staff-cap")
        rows = tuple(
            {"id": employee.id, "username": employee.username, "generation": employee.generation}
            for employee in selected
        )
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return render(request, "pages/grant_staff_list.html", {"rows": rows})


def _grant_page_rows(employee: User) -> tuple[dict[str, object], ...]:
    eligible_kinds = tuple(kind for kind in PageKind.values if eligible_grant_groups(kind))
    pages = (
        Page.objects.filter(kind__in=eligible_kinds)
        .prefetch_related(
            Prefetch(
                "routes",
                queryset=Route.objects.filter(mode=RouteMode.PRIMARY),
                to_attr="grant_primary_routes",
            ),
            Prefetch(
                "grants",
                queryset=PageGrant.objects.filter(staff=employee),
                to_attr="grant_target_rows",
            ),
        )
        .order_by("position", "id")[:501]
    )
    selected = list(pages)
    if len(selected) > 500:
        raise ValueError("page-cap")
    rows: list[dict[str, object]] = []
    for page in selected:
        routes = page.grant_primary_routes
        grants = page.grant_target_rows
        if len(routes) != 1 or len(grants) > 1:
            raise ValueError("grant-composition")
        groups = tuple(grants[0].groups) if grants else ()
        if any(group not in eligible_grant_groups(page.kind) for group in groups):
            raise ValueError("grant-composition")
        rows.append({
            "id": page.id,
            "name": page.name,
            "path": routes[0].target,
            "kind": page.kind,
            "groups": groups,
        })
    return tuple(rows)


@require_GET
@staff_session_required
def grant_employee_view(request: HttpRequest, staff_id: uuid.UUID) -> HttpResponse:
    denied = _owner_only(request)
    if denied is not None:
        return denied
    employee = _employee_target(staff_id)
    if employee is None:
        return HttpResponse("STAFF_NOT_FOUND", status=404, content_type="text/plain")
    try:
        rows = _grant_page_rows(employee)
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return render(
        request,
        "pages/grant_employee.html",
        {"employee": employee, "rows": rows},
    )


def _grant_form_projection(
    employee: User,
    page_id: uuid.UUID,
) -> tuple[Page, str, tuple[str, ...], tuple[str, ...], str] | None:
    try:
        page = Page.objects.prefetch_related(
            Prefetch(
                "routes",
                queryset=Route.objects.filter(mode=RouteMode.PRIMARY),
                to_attr="grant_primary_routes",
            ),
            Prefetch(
                "grants",
                queryset=PageGrant.objects.filter(staff=employee),
                to_attr="grant_target_rows",
            ),
        ).get(pk=page_id)
    except Page.DoesNotExist:
        return None
    eligible = eligible_grant_groups(page.kind)
    if not eligible:
        return None
    routes = page.grant_primary_routes
    grants = page.grant_target_rows
    if len(routes) != 1 or len(grants) > 1:
        raise ValueError("grant-composition")
    groups = tuple(grants[0].groups) if grants else ()
    if any(group not in eligible for group in groups):
        raise ValueError("grant-composition")
    return page, routes[0].target, groups, eligible, grant_state_hash(employee.id, page.id, groups)


def _grant_command_error(
    request: HttpRequest,
    exc: GrantCommandError,
    *,
    staff_id: uuid.UUID,
    page_id: uuid.UUID,
) -> HttpResponse:
    if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
        logout(request)
        return redirect("manage-login")
    if exc.code == "FORBIDDEN":
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if exc.code == "PAGE_NOT_FOUND":
        return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
    if exc.code in {"STALE_GRANT", "NO_CHANGE"}:
        return render(
            request,
            "pages/grant_conflict.html",
            {
                "staff_id": staff_id,
                "page_id": page_id,
                "generation": exc.user_generation,
                "grant_hash": exc.grant_hash,
            },
            status=409,
        )
    if exc.code in {"INVALID_BASIS", "INVALID_GROUPS"}:
        return HttpResponse("INVALID_GRANT_INPUT", status=400, content_type="text/plain")
    return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")


@require_http_methods(["GET", "POST"])
@staff_session_required
def grant_form_view(
    request: HttpRequest,
    staff_id: uuid.UUID,
    page_id: uuid.UUID,
) -> HttpResponse:
    denied = _owner_only(request)
    if denied is not None:
        return denied
    employee = _employee_target(staff_id)
    if employee is None:
        return HttpResponse("STAFF_NOT_FOUND", status=404, content_type="text/plain")
    try:
        projection = _grant_form_projection(employee, page_id)
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    if projection is None:
        return HttpResponse("PAGE_NOT_FOUND", status=404, content_type="text/plain")
    page, primary_path, groups, eligible, current_hash = projection
    if request.method == "GET":
        return render(
            request,
            "pages/grant_form.html",
            {
                "employee": employee,
                "page": page,
                "primary_path": primary_path,
                "groups": groups,
                "eligible_groups": eligible,
                "base_grant_hash": current_hash,
            },
        )

    try:
        if request.FILES:
            raise ValueError("files")
        post = request.POST
        submitted = set(post) - {"csrfmiddlewaretoken"}
        required = {"base_user_generation", "base_grant_hash"}
        if not required <= submitted or not submitted <= required | {"group"}:
            raise ValueError("wire")
        generation_value = _single(post, "base_user_generation")
        base_hash = _single(post, "base_grant_hash")
        generation = int(generation_value)
        if generation < 1 or str(generation) != generation_value:
            raise ValueError("basis")
        desired = post.getlist("group")
    except (
        ValueError,
        TypeError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_GRANT_INPUT", status=400, content_type="text/plain")
    try:
        command: Any = set_page_grant if desired else revoke_page_grant
        kwargs = {
            "actor_id": request.staff_actor.id,
            "session_generation": request.session.get(SESSION_GENERATION_KEY),
            "staff_id": staff_id,
            "page_id": page_id,
            "base_user_generation": generation,
            "base_grant_hash": base_hash,
        }
        if desired:
            kwargs["desired_groups"] = desired
        command(**kwargs)
    except GrantCommandError as exc:
        return _grant_command_error(request, exc, staff_id=staff_id, page_id=page_id)
    except Exception:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-grant-employee", staff_id=staff_id)


def _staff_lifecycle_error(request: HttpRequest, exc: StaffLifecycleError) -> HttpResponse:
    if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
        logout(request)
        return redirect("manage-login")
    if exc.code in {"STALE_STAFF", "NO_CHANGE"}:
        return render(
            request,
            "accounts/staff_conflict.html",
            {"generation": exc.generation},
            status=409,
        )
    if exc.code == "FORBIDDEN":
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    if exc.code == "INVALID_BASIS":
        return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
    return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")


def _staff_lifecycle_post(request: HttpRequest, keys: set[str]) -> Any:
    if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
        raise ValueError("wire")
    post = request.POST
    actual = set(post)
    allowed = (keys, keys | {"csrfmiddlewaretoken"})
    if actual not in allowed:
        raise ValueError("wire")
    if "csrfmiddlewaretoken" in actual and len(post.getlist("csrfmiddlewaretoken")) != 1:
        raise ValueError("wire")
    if any(len(post.getlist(key)) != 1 for key in keys):
        raise ValueError("wire")
    return post


@require_http_methods(["GET", "POST"])
@staff_session_required
def staff_deactivate_view(request: HttpRequest, staff_id: uuid.UUID) -> HttpResponse:
    denied = _owner_only(request)
    if denied is not None:
        return denied
    employee = _employee_state(staff_id, active=True)
    if employee is None:
        return HttpResponse("STAFF_NOT_FOUND", status=404, content_type="text/plain")
    current = list(
        PageGrant.objects.filter(staff=employee)
        .order_by("page_id")
        .values_list("page_id", "groups")
    )
    try:
        digest = staff_grants_digest(employee.id, current)
    except StaffLifecycleError:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    if request.method == "GET":
        return render(
            request,
            "accounts/staff_deactivate.html",
            {"employee": employee, "grant_count": len(current), "base_grants_digest": digest},
        )
    try:
        post = _staff_lifecycle_post(
            request, {"base_user_generation", "base_grants_digest"}
        )
        value = _single(post, "base_user_generation")
        generation = int(value)
        if generation < 1 or str(generation) != value:
            raise ValueError("basis")
        deactivate_employee(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            employee_id=staff_id,
            base_user_generation=generation,
            base_grants_digest=_single(post, "base_grants_digest"),
        )
    except (
        ValueError,
        TypeError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
    except StaffLifecycleError as exc:
        return _staff_lifecycle_error(request, exc)
    return redirect("manage-staff")


@require_http_methods(["GET", "POST"])
@staff_session_required
def staff_reactivate_view(request: HttpRequest, staff_id: uuid.UUID) -> HttpResponse:
    denied = _owner_only(request)
    if denied is not None:
        return denied
    employee = _employee_state(staff_id, active=False)
    if employee is None:
        return HttpResponse("STAFF_NOT_FOUND", status=404, content_type="text/plain")
    if request.method == "GET":
        if PageGrant.objects.filter(staff=employee).exists():
            return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
        return render(request, "accounts/staff_reactivate.html", {"employee": employee})
    try:
        post = _staff_lifecycle_post(request, {"base_user_generation"})
        value = _single(post, "base_user_generation")
        generation = int(value)
        if generation < 1 or str(generation) != value:
            raise ValueError("basis")
        reactivate_employee(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            employee_id=staff_id,
            base_user_generation=generation,
        )
    except (
        ValueError,
        TypeError,
        RequestDataTooBig,
        TooManyFieldsSent,
        MultiPartParserError,
        SuspiciousOperation,
    ):
        return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
    except StaffLifecycleError as exc:
        return _staff_lifecycle_error(request, exc)
    return redirect("manage-staff")
