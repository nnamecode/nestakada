from __future__ import annotations

import uuid
from typing import Any

from django.contrib.auth import logout
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent
from django.db.models import Prefetch
from django.http import HttpRequest, HttpResponse
from django.http.multipartparser import MultiPartParserError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from modules.accounts.api import SESSION_GENERATION_KEY, StaffRole, staff_session_required

from .commands import PageCommandError, save_page_content, undo_page_content
from .editor import (
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
from .models import Page, PageGrant, Route, RouteMode


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
    return render(request, "pages/page_list.html", {"rows": rows})


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


def _save_wire(post: Any, snapshot: Any, *, is_owner: bool) -> tuple[tuple[uuid.UUID, int, str], object]:
    basis_keys = {"operation_id", "base_generation", "base_current_hash"}
    scalar_keys = {"seo.title", "seo.description", "seo.allow_index", "heading.h1"} if is_owner else set()
    flag_keys = {f"rich.{name}.changed" for name in snapshot.rich_names}
    value_keys = {f"rich.{name}.value" for name in snapshot.rich_names}
    price_keys = {"price.changed", "price.column", "price.row", "price.cell"} if snapshot.can_edit_prices else set()
    process_keys = {"process.changed", "process.step"} if snapshot.can_edit_process else set()
    links_keys = {"links.changed", "links.item"} if snapshot.can_edit_links else set()
    submitted = set(post) - {"csrfmiddlewaretoken"}
    required = (
        basis_keys
        | scalar_keys
        | flag_keys
        | ({"price.changed"} if snapshot.can_edit_prices else set())
        | ({"process.changed"} if snapshot.can_edit_process else set())
        | ({"links.changed"} if snapshot.can_edit_links else set())
    )
    allowed = required | value_keys | price_keys | process_keys | links_keys
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
