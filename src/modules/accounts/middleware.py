from __future__ import annotations

import ipaddress
import re
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


_LOGIN_PATH = "/manage/login/"
_PRIVATE_PREFIX = "/manage/"
_PAGE_SAVE_PATH = re.compile(
    r"\A/manage/pages/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/save/\Z"
)
_PAGE_SAVE_MAX_BODY = 4_194_304
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


class PrivateIngressMiddleware:
    """Exact private ingress guard and cache boundary; no general policy engine."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.method == "POST" and _PAGE_SAVE_PATH.fullmatch(request.path_info):
            length = request.META.get("CONTENT_LENGTH")
            if (
                not isinstance(length, str)
                or not length.isascii()
                or not length.isdecimal()
                or str(int(length)) != length
                or int(length) > _PAGE_SAVE_MAX_BODY
            ):
                response = HttpResponse("INVALID_EDITOR_INPUT", status=400, content_type="text/plain")
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
