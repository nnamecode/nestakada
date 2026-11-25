from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import stat
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import ServiceRequest, TelegramOutcome


_TOKEN = re.compile(r"\A[1-9][0-9]{5,19}:[A-Za-z0-9_-]{20,200}\Z")
_CHAT_ID = re.compile(r"\A-?[1-9][0-9]{0,19}\Z")
_TIMEOUT = 5.0
_RESPONSE_CAP = 4096
_TOKEN_CAP = 221


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    token_file: Path
    chat_id: str


@dataclass(frozen=True, slots=True)
class TelegramSnapshot:
    request_id: uuid.UUID
    created_at: Any
    name: str
    phone: str
    vehicle_make: str
    vehicle_model: str
    vehicle_year: str
    comment: str


def claim_telegram(request_id: uuid.UUID) -> TelegramSnapshot | None:
    attempted_at = timezone.now()
    with transaction.atomic():
        updated = ServiceRequest.objects.filter(
            pk=request_id,
            telegram_outcome=TelegramOutcome.NOT_ATTEMPTED,
            telegram_attempted_at__isnull=True,
        ).update(
            telegram_outcome=TelegramOutcome.IN_PROGRESS,
            telegram_attempted_at=attempted_at,
        )
        if updated != 1:
            return None
        row = ServiceRequest.objects.get(pk=request_id)
        return TelegramSnapshot(
            request_id=row.id,
            created_at=row.created_at,
            name=row.name,
            phone=row.phone,
            vehicle_make=row.vehicle_make,
            vehicle_model=row.vehicle_model,
            vehicle_year=row.vehicle_year,
            comment=row.comment,
        )


def finish_telegram(request_id: uuid.UUID, outcome: str) -> bool:
    if outcome not in {TelegramOutcome.SENT, TelegramOutcome.FAILED}:
        raise ValueError("INVALID_TELEGRAM_OUTCOME")
    with transaction.atomic():
        return (
            ServiceRequest.objects.filter(
                pk=request_id,
                telegram_outcome=TelegramOutcome.IN_PROGRESS,
                telegram_attempted_at__isnull=False,
            ).update(telegram_outcome=outcome)
            == 1
        )


def _remaining(deadline: float, monotonic: Callable[[], float]) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _read_token(path: Path) -> str:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    nonblock = getattr(os, "O_NONBLOCK", None)
    if nofollow is None or nonblock is None:
        raise OSError
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | nofollow | nonblock)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > _TOKEN_CAP:
            raise OSError
        raw = os.read(descriptor, _TOKEN_CAP + 1)
        if len(raw) > _TOKEN_CAP or os.read(descriptor, 1) != b"":
            raise OSError
        return raw.decode("ascii")
    finally:
        os.close(descriptor)


def _decode_response(body: bytes) -> object:
    def closed_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    return json.loads(body.decode("utf-8"), object_pairs_hook=closed_object)


def _message(snapshot: TelegramSnapshot) -> str:
    vehicle = " ".join(
        filter(
            None,
            (snapshot.vehicle_make, snapshot.vehicle_model, snapshot.vehicle_year),
        )
    )
    parts = (
        f"Заявка {snapshot.request_id}",
        f"Время: {snapshot.created_at.isoformat()}",
        f"Имя: {snapshot.name}",
        f"Телефон: {snapshot.phone}",
        f"Автомобиль: {vehicle}" if vehicle else "",
        f"Комментарий: {snapshot.comment}" if snapshot.comment else "",
    )
    return "\n".join(part for part in parts if part)


def send_telegram(
    snapshot: TelegramSnapshot,
    config: TelegramConfig,
    *,
    connection_factory: Callable[..., Any] = http.client.HTTPSConnection,
    monotonic: Callable[[], float] = time.monotonic,
) -> bool:
    connection = None
    try:
        token = _read_token(config.token_file)
        if _TOKEN.fullmatch(token) is None or _CHAT_ID.fullmatch(config.chat_id) is None:
            return False
        deadline = monotonic() + _TIMEOUT
        context = ssl.create_default_context()
        connection = connection_factory(
            "api.telegram.org",
            443,
            context=context,
            timeout=_remaining(deadline, monotonic),
        )
        connection.connect()
        connection.sock.settimeout(_remaining(deadline, monotonic))
        payload = json.dumps(
            {"chat_id": config.chat_id, "text": _message(snapshot)},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        connection.request(
            "POST",
            f"/bot{token}/sendMessage",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        connection.sock.settimeout(_remaining(deadline, monotonic))
        response = connection.getresponse()
        connection.sock.settimeout(_remaining(deadline, monotonic))
        body = response.read(_RESPONSE_CAP + 1)
        if response.status != 200 or len(body) > _RESPONSE_CAP:
            return False
        decoded = _decode_response(body)
        return type(decoded) is dict and decoded.get("ok") is True
    except Exception:
        return False
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def attempt_telegram_delivery(request_id: uuid.UUID, config: TelegramConfig) -> None:
    snapshot = claim_telegram(request_id)
    if snapshot is None:
        return
    outcome = TelegramOutcome.SENT if send_telegram(snapshot, config) else TelegramOutcome.FAILED
    try:
        finish_telegram(request_id, outcome)
    except Exception:
        # Unknown terminal persistence leaves IN_PROGRESS and is never retried.
        return
