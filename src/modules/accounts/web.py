from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from modules.audit.api import Action, ActorRef, TargetType, append_event

from .api import SESSION_GENERATION_KEY, current_staff_session
from .models import StaffRole, User


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
