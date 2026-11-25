from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


_LOGIN_PATH = "/manage/login/"
_PRIVATE_PREFIX = "/manage/"
_PAGE_SAVE_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/save/\Z"
)
_PAGE_PUBLICATION_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/publication/\Z"
)
_PAGE_RENAME_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/rename/\Z"
)
_PAGE_MOVE_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/move/\Z"
)
_PAGE_DELETE_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/delete/\Z"
)
_PAGE_URL_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/url/\Z"
)
_PAGE_CREATE_PATH = "/manage/pages/new/"
_PAGE_REORDER_PATH = "/manage/pages/reorder/"
_PAGE_SAVE_MAX_BODY = 4_194_304
_STAFF_PASSWORD_PATH = re.compile(
    r"\A/manage/staff/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/password/\Z"
)
_STAFF_CREATE_PATH = "/manage/staff/new/"
_SITE_SETTINGS_PATH = "/manage/settings/"
_SERVICE_REQUEST_PATH = "/request/submit/"
_SERVICE_REQUEST_MAX_BODY = 8192
_SERVICE_REQUEST_DELETE_PATH = re.compile(
    r"\A/manage/requests/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}/delete/\Z"
)
_SERVICE_REQUEST_DELETE_MAX_BODY = 2048
_FORBIDDEN_FORWARDING = (
    "HTTP_FORWARDED",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_REAL_IP",
)


def _valid_ingress(meta: dict[str, object]) -> bool:
    if any(key in meta for key in _FORBIDDEN_FORWARDING):
        return False
    value = meta.get("HTTP_X_ESTAKADA_CLIENT_IP")
    if not isinstance(value, str) or not 1 <= len(value) <= 45:
        return False
    if any(char.isspace() for char in value) or any(char in value for char in (",", "%")):
        return False
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return False
    return str(parsed) == value


def _service_request_intake_configured() -> bool:
    validator = getattr(settings, "SERVICE_REQUEST_CONFIGURATION_VALIDATOR", None)
    return callable(validator) and validator(settings)


class PrivateIngressMiddleware:
    """Exact private ingress guard and cache boundary; no general policy engine."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and _SERVICE_REQUEST_DELETE_PATH.fullmatch(request.path_info):
            length = request.META.get("CONTENT_LENGTH")
            if (
                not isinstance(length, str) or not length.isascii() or not length.isdecimal()
                or len(length) > 4 or str(int(length)) != length
                or not 1 <= int(length) <= _SERVICE_REQUEST_DELETE_MAX_BODY
            ):
                response = HttpResponse("INVALID_DELETE_CONFIRMATION", status=400,
                                        content_type="text/plain")
                response["Cache-Control"] = "private, no-store"
                return response
        if (
            settings.SERVICE_REQUESTS_ENABLED
            and request.method == "POST"
            and request.path_info == _SERVICE_REQUEST_PATH
            and _service_request_intake_configured()
        ):
            length = request.META.get("CONTENT_LENGTH")
            if (
                not isinstance(length, str)
                or not length.isascii()
                or not length.isdecimal()
                or len(length) > 4
                or str(int(length)) != length
                or not 1 <= int(length) <= _SERVICE_REQUEST_MAX_BODY
            ):
                response = HttpResponse(
                    "INVALID_REQUEST_INPUT",
                    status=400,
                    content_type="text/plain",
                )
                response["Cache-Control"] = "private, no-store"
                return response
            if not _valid_ingress(request.META):
                response = HttpResponse("INVALID_INGRESS", status=400, content_type="text/plain")
                response["Cache-Control"] = "private, no-store"
                return response
        if request.method == "POST" and (
            _PAGE_SAVE_PATH.fullmatch(request.path_info)
            or _PAGE_PUBLICATION_PATH.fullmatch(request.path_info)
            or _PAGE_RENAME_PATH.fullmatch(request.path_info)
            or _PAGE_MOVE_PATH.fullmatch(request.path_info)
            or _PAGE_DELETE_PATH.fullmatch(request.path_info)
            or _PAGE_URL_PATH.fullmatch(request.path_info)
            or request.path_info == _PAGE_CREATE_PATH
            or request.path_info == _PAGE_REORDER_PATH
            or _STAFF_PASSWORD_PATH.fullmatch(request.path_info)
            or request.path_info == _STAFF_CREATE_PATH
            or request.path_info == _SITE_SETTINGS_PATH
        ):
            length = request.META.get("CONTENT_LENGTH")
            if (
                not isinstance(length, str)
                or not length.isascii()
                or not length.isdecimal()
                or str(int(length)) != length
                or int(length) > _PAGE_SAVE_MAX_BODY
            ):
                body = (
                    "INVALID_SETTINGS_INPUT"
                    if request.path_info == _SITE_SETTINGS_PATH
                    else "INVALID_PAGE_REORDER_INPUT"
                    if request.path_info == _PAGE_REORDER_PATH
                    else "INVALID_PAGE_MOVE_INPUT"
                    if _PAGE_MOVE_PATH.fullmatch(request.path_info)
                    else "INVALID_PAGE_CREATE_INPUT"
                    if request.path_info == _PAGE_CREATE_PATH
                    else "INVALID_PAGE_DELETE_INPUT"
                    if _PAGE_DELETE_PATH.fullmatch(request.path_info)
                    else "INVALID_PAGE_URL_INPUT"
                    if _PAGE_URL_PATH.fullmatch(request.path_info)
                    else "INVALID_PAGE_RENAME_INPUT"
                    if _PAGE_RENAME_PATH.fullmatch(request.path_info)
                    else "INVALID_EDITOR_INPUT"
                )
                response = HttpResponse(body, status=400, content_type="text/plain")
                response["Cache-Control"] = "private, no-store"
                return response
        if request.method == "POST" and request.path_info == _LOGIN_PATH:
            if not _valid_ingress(request.META):
                response = HttpResponse("INVALID_INGRESS", status=400, content_type="text/plain")
                response["Cache-Control"] = "private, no-store"
                return response
        response = self.get_response(request)
        if request.path_info.startswith(_PRIVATE_PREFIX):
            response["Cache-Control"] = "private, no-store"
        return response
