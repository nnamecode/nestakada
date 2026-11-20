from __future__ import annotations

import uuid

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from modules.audit.api import Action, ActorRef, TargetType, append_event

from .api import SESSION_GENERATION_KEY, current_staff_session, staff_session_required
from .models import StaffRole, User
from .staff import StaffCommandError, create_employee, set_employee_password


_FORM_KEYS = frozenset({"username", "password"})
_FORM_KEYS_WITH_CSRF = frozenset({"csrfmiddlewaretoken", "username", "password"})


def _login_page(request: HttpRequest, *, error: bool = False, status: int = 200) -> HttpResponse:
    return render(request, "accounts/login.html", {"login_error": error}, status=status)


def _form_credentials(request: HttpRequest) -> tuple[str, str] | None:
    if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
        return None
    keys = frozenset(request.POST)
    if keys not in (_FORM_KEYS, _FORM_KEYS_WITH_CSRF):
        return None
    if "csrfmiddlewaretoken" in keys and len(request.POST.getlist("csrfmiddlewaretoken")) != 1:
        return None
    usernames = request.POST.getlist("username")
    passwords = request.POST.getlist("password")
    if len(usernames) != 1 or len(passwords) != 1:
        return None
    username, password = usernames[0], passwords[0]
    if not username or not password or len(username) > 150 or len(password) > 4096:
        return None
    return username, password


def _failed_login_audit() -> bool:
    try:
        append_event(
            action=Action.AUTH_LOGIN_FAILED,
            actor=ActorRef.anonymous(),
            target_type=TargetType.USER,
            target_uuid=None,
            detail={"reason": "INVALID_CREDENTIALS"},
        )
    except Exception:
        return False
    return True


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        if current_staff_session(request) is not None:
            return redirect("manage-pages")
        return _login_page(request)

    credentials = _form_credentials(request)
    if credentials is None:
        return _login_page(request, error=True)
    username, password = credentials
    try:
        candidate = authenticate(request, username=username, password=password)
    except Exception:
        return HttpResponse("AUTH_UNAVAILABLE", status=503, content_type="text/plain")
    if candidate is None:
        if not _failed_login_audit():
            return HttpResponse("AUTH_UNAVAILABLE", status=503, content_type="text/plain")
        return _login_page(request, error=True)

    backend = getattr(candidate, "backend", None)
    try:
        with transaction.atomic():
            locked = User.objects.select_for_update().get(pk=candidate.pk)
            coherent = (
                locked.is_active
                and locked.is_staff
                and locked.role in StaffRole.values
                and locked.generation == candidate.generation
                and locked.password == candidate.password
            )
            if not coherent:
                append_event(
                    action=Action.AUTH_LOGIN_FAILED,
                    actor=ActorRef.anonymous(),
                    target_type=TargetType.USER,
                    target_uuid=None,
                    detail={"reason": "INVALID_CREDENTIALS"},
                )
                locked = None
            else:
                append_event(
                    action=Action.AUTH_LOGIN_SUCCEEDED,
                    actor=ActorRef.user(locked.id, locked.role),
                    target_type=TargetType.USER,
                    target_uuid=locked.id,
                )
    except Exception:
        return HttpResponse("AUTH_UNAVAILABLE", status=503, content_type="text/plain")
    if locked is None:
        return _login_page(request, error=True)
    try:
        login(request, locked, backend=backend)
        request.session[SESSION_GENERATION_KEY] = locked.generation
    except Exception:
        logout(request)
        return HttpResponse("AUTH_UNAVAILABLE", status=503, content_type="text/plain")
    return redirect("manage-pages")


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    actor = current_staff_session(request, clear_invalid=False)
    actor_ref = None if actor is None else ActorRef.user(actor.id, actor.role)
    actor_id = None if actor is None else actor.id
    logout(request)
    if actor_ref is not None:
        try:
            append_event(
                action=Action.AUTH_LOGOUT,
                actor=actor_ref,
                target_type=TargetType.USER,
                target_uuid=actor_id,
            )
        except Exception:
            pass
    return redirect("manage-login")


def _owner(request: HttpRequest) -> HttpResponse | None:
    actor = request.staff_actor
    if (
        actor.role != StaffRole.OWNER
        or actor.username != "nesadmin"
        or not actor.is_superuser
    ):
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    return None


def _staff_post(request: HttpRequest, exact_keys: frozenset[str]) -> object:
    if request.content_type != "application/x-www-form-urlencoded" or request.FILES:
        raise ValueError("wire")
    try:
        post = request.POST
    except (RequestDataTooBig, SuspiciousOperation, TooManyFieldsSent):
        raise ValueError("wire") from None
    keys = frozenset(post)
    allowed = (exact_keys, exact_keys | {"csrfmiddlewaretoken"})
    if keys not in allowed:
        raise ValueError("wire")
    if "csrfmiddlewaretoken" in keys and len(post.getlist("csrfmiddlewaretoken")) != 1:
        raise ValueError("wire")
    if any(len(post.getlist(key)) != 1 for key in exact_keys):
        raise ValueError("wire")
    return post


def _staff_conflict(request: HttpRequest, generation: int | None = None) -> HttpResponse:
    return render(
        request,
        "accounts/staff_conflict.html",
        {"generation": generation},
        status=409,
    )


@require_GET
@staff_session_required
def staff_list_view(request: HttpRequest) -> HttpResponse:
    denied = _owner(request)
    if denied is not None:
        return denied
    selected = list(
        User.objects.filter(role=StaffRole.EMPLOYEE)
        .order_by("username", "id")
        .values("id", "username", "is_active", "generation")[:101]
    )
    if len(selected) > 100:
        return HttpResponse("PRIVATE_DATA_UNAVAILABLE", status=503, content_type="text/plain")
    return render(request, "accounts/staff_list.html", {"rows": selected})


@require_http_methods(["GET", "POST"])
@staff_session_required
def staff_create_view(request: HttpRequest) -> HttpResponse:
    denied = _owner(request)
    if denied is not None:
        return denied
    if request.method == "GET":
        return render(request, "accounts/staff_create.html", {"employee_id": uuid.uuid4()})
    try:
        post = _staff_post(
            request,
            frozenset({"employee_id", "username", "password", "password_confirmation"}),
        )
        employee_id_value = post.getlist("employee_id")[0]
        employee_id = uuid.UUID(employee_id_value)
        if str(employee_id) != employee_id_value:
            raise ValueError("wire")
        create_employee(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            employee_id=employee_id,
            username=post.getlist("username")[0],
            password=post.getlist("password")[0],
            confirmation=post.getlist("password_confirmation")[0],
        )
    except ValueError:
        return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
    except StaffCommandError as exc:
        if exc.code == "CONFLICT":
            return _staff_conflict(request)
        if exc.code in {"INVALID_EMPLOYEE", "INVALID_USERNAME", "INVALID_PASSWORD"}:
            return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    return redirect("manage-staff")


@require_http_methods(["GET", "POST"])
@staff_session_required
def staff_password_view(request: HttpRequest, staff_id: uuid.UUID) -> HttpResponse:
    denied = _owner(request)
    if denied is not None:
        return denied
    employee = User.objects.filter(pk=staff_id, role=StaffRole.EMPLOYEE).first()
    if employee is None:
        return HttpResponse("STAFF_NOT_FOUND", status=404, content_type="text/plain")
    if request.method == "GET":
        return render(request, "accounts/staff_password.html", {"employee": employee})
    try:
        post = _staff_post(
            request,
            frozenset({"base_user_generation", "password", "password_confirmation"}),
        )
        value = post.getlist("base_user_generation")[0]
        generation = int(value)
        if generation < 1 or str(generation) != value:
            raise ValueError("wire")
        set_employee_password(
            actor_id=request.staff_actor.id,
            session_generation=request.session.get(SESSION_GENERATION_KEY),
            employee_id=staff_id,
            base_user_generation=generation,
            password=post.getlist("password")[0],
            confirmation=post.getlist("password_confirmation")[0],
        )
    except ValueError:
        return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
    except StaffCommandError as exc:
        if exc.code in {"STALE_STAFF", "NO_CHANGE"}:
            return _staff_conflict(request, exc.generation)
        if exc.code == "INVALID_PASSWORD":
            return HttpResponse("INVALID_STAFF_INPUT", status=400, content_type="text/plain")
        if exc.code in {"AUTH_REQUIRED", "STALE_SESSION"}:
            logout(request)
            return redirect("manage-login")
        return HttpResponse("FORBIDDEN", status=403, content_type="text/plain")
    return redirect("manage-staff")
