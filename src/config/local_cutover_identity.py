from __future__ import annotations

import re
from collections.abc import Mapping

from django.conf import settings
from django.http import HttpRequest, HttpResponse


PROBE_HOST = "r7c-probe.invalid"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def reject_restore_write_escape(environment: Mapping[str, str]) -> None:
    if "ESTAKADA_RESTORE_VERIFY_WRITE" in environment:
        raise RuntimeError("Restore write override is forbidden for local cutover.")


def validate_identity_environment(environment: Mapping[str, str]) -> tuple[str, str, str]:
    role = environment.get("ESTAKADA_R7C_ROLE", "")
    generation = environment.get("ESTAKADA_R7C_GENERATION_SHA256", "")
    storage = environment.get("ESTAKADA_R7C_STORAGE_BINDING_SHA256", "")
    if role not in {"old", "new"} or HEX64.fullmatch(generation) is None or HEX64.fullmatch(storage) is None:
        raise RuntimeError("Exact local-cutover identity is required.")
    return role, generation, storage


def target_identity_view(request: HttpRequest) -> HttpResponse:
    if request.META.get("HTTP_HOST") != PROBE_HOST:
        return HttpResponse(status=400)
    if request.method not in {"GET", "HEAD"}:
        response = HttpResponse(status=405)
        response["Allow"] = "GET, HEAD"
        return response
    response = HttpResponse(status=204)
    response["X-Estakada-R7C-Role"] = settings.R7C_ROLE
    response["X-Estakada-R7C-Generation"] = settings.R7C_GENERATION_SHA256
    response["X-Estakada-R7C-Storage-Binding"] = settings.R7C_STORAGE_BINDING_SHA256
    response["Cache-Control"] = "no-store"
    return response
