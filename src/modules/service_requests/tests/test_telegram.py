from __future__ import annotations

import json
import os
import signal
import ssl
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from django.db import close_old_connections
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone

from modules.service_requests.models import ServiceRequest, TelegramOutcome
from modules.service_requests.telegram import (
    TelegramConfig,
    TelegramSnapshot,
    attempt_telegram_delivery,
    claim_telegram,
    finish_telegram,
    send_telegram,
)


def _request() -> ServiceRequest:
    return ServiceRequest.objects.create(
        id=uuid.UUID("12345678-1234-4abc-8def-1234567890ab"),
        name="Иван",
        phone="+79991234567",
        vehicle_make="Лада",
        vehicle_model="Веста",
        vehicle_year="2024",
        comment="Не заводится",
        consent_text_version="consent-v1",
        consent_text_sha256="a" * 64,
        consented_at=timezone.now(),
    )


class TelegramClaimTests(TransactionTestCase):
    def test_two_connections_claim_exactly_once_and_terminal_is_cas(self) -> None:
        request = _request()
        barrier = threading.Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return claim_telegram(request.id)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = [future.result(timeout=20) for future in (pool.submit(worker), pool.submit(worker))]
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        row = ServiceRequest.objects.get(pk=request.id)
        self.assertEqual(row.telegram_outcome, TelegramOutcome.IN_PROGRESS)
        self.assertIsNotNone(row.telegram_attempted_at)
        self.assertTrue(finish_telegram(request.id, TelegramOutcome.SENT))
        self.assertFalse(finish_telegram(request.id, TelegramOutcome.FAILED))
        self.assertIsNone(claim_telegram(request.id))
        self.assertEqual(ServiceRequest.objects.get(pk=request.id).telegram_outcome, TelegramOutcome.SENT)

    def test_failed_and_in_progress_are_never_reclaimed(self) -> None:
        request = _request()
        self.assertIsNotNone(claim_telegram(request.id))
        self.assertIsNone(claim_telegram(request.id))
        self.assertTrue(finish_telegram(request.id, TelegramOutcome.FAILED))
        self.assertIsNone(claim_telegram(request.id))

    def test_terminal_write_failure_leaves_in_progress_and_never_retries(self) -> None:
        request = _request()
        with (
            patch("modules.service_requests.telegram.send_telegram", return_value=True) as send,
            patch(
                "modules.service_requests.telegram.finish_telegram",
                side_effect=RuntimeError("private database detail"),
            ),
        ):
            attempt_telegram_delivery(request.id, TelegramConfig(Path("unused"), "1"))
        send.assert_called_once()
        self.assertEqual(
            ServiceRequest.objects.get(pk=request.id).telegram_outcome,
            TelegramOutcome.IN_PROGRESS,
        )
        with patch("modules.service_requests.telegram.send_telegram") as second_send:
            attempt_telegram_delivery(request.id, TelegramConfig(Path("unused"), "1"))
        second_send.assert_not_called()


class _Response:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self.body = body
        self.read_size = None

    def read(self, size: int) -> bytes:
        self.read_size = size
        return self.body


class _Socket:
    def __init__(self):
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)


class _Connection:
    def __init__(self, response: _Response):
        self.response = response
        self.sock = _Socket()
        self.request_args = None
        self.closed = False
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def request(self, method, path, *, body, headers) -> None:
        self.request_args = (method, path, body, headers)

    def getresponse(self) -> _Response:
        return self.response

    def close(self) -> None:
        self.closed = True


class TelegramTransportTests(SimpleTestCase):
    def _snapshot(self) -> TelegramSnapshot:
        return TelegramSnapshot(
            request_id=uuid.UUID("12345678-1234-4abc-8def-1234567890ab"),
            created_at=timezone.now(),
            name="Иван",
            phone="+79991234567",
            vehicle_make="Лада",
            vehicle_model="Веста",
            vehicle_year="2024",
            comment="Не заводится",
        )

    def _send(self, *, body: bytes = b'{"ok":true}', status: int = 200):
        temporary = tempfile.TemporaryDirectory()
        token_path = Path(temporary.name) / "token"
        token_path.write_text("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", encoding="ascii")
        response = _Response(status, body)
        connection = _Connection(response)
        captured = {}

        def factory(host, port, *, context, timeout):
            captured.update(host=host, port=port, context=context, timeout=timeout)
            return connection

        result = send_telegram(
            self._snapshot(),
            TelegramConfig(token_file=token_path, chat_id="-1001234567890"),
            connection_factory=factory,
            monotonic=iter((10.0, 10.1, 10.2, 10.3, 10.4)).__next__,
        )
        return temporary, result, response, connection, captured

    def test_exact_direct_https_request_and_bounded_response(self) -> None:
        temporary, result, response, connection, captured = self._send()
        self.addCleanup(temporary.cleanup)
        self.assertIs(result, True)
        self.assertEqual((captured["host"], captured["port"]), ("api.telegram.org", 443))
        self.assertIsInstance(captured["context"], ssl.SSLContext)
        self.assertTrue(captured["context"].check_hostname)
        self.assertEqual(captured["context"].verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(captured["timeout"], 0)
        self.assertLessEqual(captured["timeout"], 5)
        method, path, body, headers = connection.request_args
        self.assertEqual(method, "POST")
        self.assertEqual(path, "/bot123456:abcdefghijklmnopqrstuvwxyz_ABC-123/sendMessage")
        self.assertNotIn("?", path)
        self.assertNotIn("@", path)
        self.assertEqual(headers, {"Content-Type": "application/json"})
        payload = json.loads(body)
        self.assertEqual(set(payload), {"chat_id", "text"})
        self.assertEqual(payload["chat_id"], "-1001234567890")
        self.assertNotIn("consent", payload["text"].lower())
        self.assertEqual(response.read_size, 4097)
        self.assertTrue(connection.closed)
        self.assertTrue(connection.connected)
        self.assertTrue(connection.sock.timeouts)
        self.assertEqual(connection.sock.timeouts, sorted(connection.sock.timeouts, reverse=True))

    def test_status_json_shape_and_size_fail_closed(self) -> None:
        for status, body in (
            (500, b'{"ok":true}'),
            (302, b'{"ok":true}'),
            (200, b'{"ok":false}'),
            (200, b"[]"),
            (200, b"not-json"),
            (200, b'\xff'),
            (200, b'{"ok":false,"ok":true}'),
            (200, b"x" * 4097),
        ):
            with self.subTest(status=status, size=len(body)):
                temporary, result, _response, connection, _captured = self._send(
                    status=status,
                    body=body,
                )
                temporary.cleanup()
                self.assertIs(result, False)
                self.assertTrue(connection.closed)

    def test_credentials_are_closed_and_never_sent_when_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            for token, chat_id in (
                ("123:short", "1"),
                ("123456:abcdefghijklmnopqrstuvwxyz_ABC-123\n", "1"),
                ("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", "0"),
                ("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", "+1"),
            ):
                with self.subTest(token=token, chat_id=chat_id):
                    token_path.write_text(token, encoding="ascii")
                    calls = []
                    result = send_telegram(
                        self._snapshot(),
                        TelegramConfig(token_file=token_path, chat_id=chat_id),
                        connection_factory=lambda *args, **kwargs: calls.append((args, kwargs)),
                    )
                    self.assertIs(result, False)
                    self.assertEqual(calls, [])

    def test_secret_file_is_bounded_regular_and_no_follow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            token_path = root / "token"
            token_path.write_bytes(b"1" * 222)
            calls = []
            self.assertFalse(
                send_telegram(
                    self._snapshot(),
                    TelegramConfig(token_path, "1"),
                    connection_factory=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
            )
            self.assertEqual(calls, [])
            target = root / "target"
            target.write_text("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", encoding="ascii")
            link = root / "link"
            link.symlink_to(target)
            self.assertFalse(
                send_telegram(
                    self._snapshot(),
                    TelegramConfig(link, "1"),
                    connection_factory=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
            )
            self.assertEqual(calls, [])

    def test_fifo_secret_fails_without_blocking_or_network(self) -> None:
        if not hasattr(os, "mkfifo") or not hasattr(signal, "setitimer"):
            self.skipTest("POSIX FIFO boundary is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "token-fifo"
            os.mkfifo(fifo)
            calls = []
            alarm_fired = False

            def timeout_handler(_signum, _frame):
                nonlocal alarm_fired
                alarm_fired = True
                raise TimeoutError("FIFO open blocked")

            previous = signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, 1.0)
            try:
                result = send_telegram(
                    self._snapshot(),
                    TelegramConfig(fifo, "1"),
                    connection_factory=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous)
            self.assertFalse(result)
            self.assertFalse(alarm_fired)
            self.assertEqual(calls, [])

    def test_deadline_exhaustion_and_transport_exception_are_constant_false(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            token_path.write_text("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", encoding="ascii")
            response = _Response(200, b'{"ok":true}')
            connection = _Connection(response)
            with self.assertNoLogs(level="DEBUG"):
                result = send_telegram(
                    self._snapshot(),
                    TelegramConfig(token_path, "1"),
                    connection_factory=lambda *args, **kwargs: connection,
                    monotonic=iter((10.0, 10.1, 15.1)).__next__,
                )
            self.assertFalse(result)
            self.assertIsNone(connection.request_args)
            private = "TOKEN PRIVATE PAYLOAD"
            with self.assertNoLogs(level="DEBUG"):
                result = send_telegram(
                    self._snapshot(),
                    TelegramConfig(token_path, "1"),
                    connection_factory=Mock(side_effect=RuntimeError(private)),
                )
            self.assertFalse(result)

    def test_deadline_is_rechecked_before_write_headers_and_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            token_path = Path(directory) / "token"
            token_path.write_text("123456:abcdefghijklmnopqrstuvwxyz_ABC-123", encoding="ascii")
            phases = (
                ((10.0, 10.1, 15.1), False, False),
                ((10.0, 10.1, 10.2, 15.1), True, False),
                ((10.0, 10.1, 10.2, 10.3, 15.1), True, False),
            )
            for clock, request_expected, read_expected in phases:
                with self.subTest(clock=clock):
                    response = _Response(200, b'{"ok":true}')
                    connection = _Connection(response)
                    result = send_telegram(
                        self._snapshot(),
                        TelegramConfig(token_path, "1"),
                        connection_factory=lambda *args, **kwargs: connection,
                        monotonic=iter(clock).__next__,
                    )
                    self.assertFalse(result)
                    self.assertEqual(connection.request_args is not None, request_expected)
                    self.assertEqual(response.read_size is not None, read_expected)
