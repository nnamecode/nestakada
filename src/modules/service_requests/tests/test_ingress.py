from __future__ import annotations

import hashlib
from unittest.mock import Mock

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from modules.accounts.middleware import PrivateIngressMiddleware


_CONSENT = "Synthetic consent"
_PRIVACY = "Synthetic privacy"
_CONFIGURED = {
    "SERVICE_REQUESTS_ENABLED": True,
    "SERVICE_REQUEST_FORM_VERSION": "v1",
    "SERVICE_REQUEST_CONSENT_VERSION": "v1",
    "SERVICE_REQUEST_CONSENT_TEXT": _CONSENT,
    "SERVICE_REQUEST_CONSENT_SHA256": hashlib.sha256(_CONSENT.encode()).hexdigest(),
    "SERVICE_REQUEST_PRIVACY_TEXT": _PRIVACY,
    "SERVICE_REQUEST_PRIVACY_SHA256": hashlib.sha256(_PRIVACY.encode()).hexdigest(),
    "SERVICE_REQUEST_TELEGRAM_TOKEN_FILE": "/run/secrets/telegram-token",
    "SERVICE_REQUEST_TELEGRAM_CHAT_ID": "-1001234567890",
    "SERVICE_REQUEST_LEDGER_ROOT": "/srv/estakada/private/request-ledger",
    "SERVICE_REQUEST_INDEPENDENT_ADAPTER": "external-v1",
}


class ServiceRequestIngressTests(SimpleTestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def _request(self, *, body: bytes = b"x", client_ip: str | None = "192.0.2.1"):
        request = self.factory.post(
            "/request/submit/",
            data=body,
            content_type="application/x-www-form-urlencoded",
        )
        if client_ip is not None:
            request.META["HTTP_X_ESTAKADA_CLIENT_IP"] = client_ip
        return request

    @override_settings(**_CONFIGURED)
    def test_valid_exact_ipv4_and_ipv6_reach_downstream(self) -> None:
        for client_ip in ("192.0.2.1", "2001:db8::1"):
            with self.subTest(client_ip=client_ip):
                downstream = Mock(return_value=HttpResponse("OK"))
                response = PrivateIngressMiddleware(downstream)(self._request(client_ip=client_ip))
                self.assertEqual((response.status_code, response.content), (200, b"OK"))
                downstream.assert_called_once()

    @override_settings(**_CONFIGURED)
    def test_invalid_or_noncanonical_length_rejects_before_downstream(self) -> None:
        for value in (None, "", "0", "00", "+1", "8193", " 1", "9" * 5000):
            with self.subTest(value=value):
                request = self._request()
                if value is None:
                    request.META.pop("CONTENT_LENGTH", None)
                else:
                    request.META["CONTENT_LENGTH"] = value
                downstream = Mock(return_value=HttpResponse("LEAK"))
                response = PrivateIngressMiddleware(downstream)(request)
                self.assertEqual(
                    (response.status_code, response.content, response["Cache-Control"]),
                    (400, b"INVALID_REQUEST_INPUT", "private, no-store"),
                )
                downstream.assert_not_called()

    @override_settings(**_CONFIGURED)
    def test_missing_spoofed_list_or_malformed_identity_rejects(self) -> None:
        cases = (
            ({}, None),
            ({}, "192.0.2.1,198.51.100.2"),
            ({}, "192.0.2.1:443"),
            ({}, "2001:0db8::1"),
            ({}, "fe80::1%eth0"),
            ({"HTTP_FORWARDED": "for=192.0.2.1"}, "192.0.2.1"),
            ({"HTTP_X_FORWARDED_FOR": "192.0.2.1"}, "192.0.2.1"),
            ({"HTTP_X_REAL_IP": "192.0.2.1"}, "192.0.2.1"),
        )
        for extra, client_ip in cases:
            with self.subTest(extra=extra, client_ip=client_ip):
                request = self._request(client_ip=client_ip)
                request.META.update(extra)
                downstream = Mock(return_value=HttpResponse("LEAK"))
                response = PrivateIngressMiddleware(downstream)(request)
                self.assertEqual(
                    (response.status_code, response.content, response["Cache-Control"]),
                    (400, b"INVALID_INGRESS", "private, no-store"),
                )
                downstream.assert_not_called()

    @override_settings(SERVICE_REQUESTS_ENABLED=False)
    def test_default_off_does_not_create_an_intake_middleware_surface(self) -> None:
        downstream = Mock(return_value=HttpResponse("CATCH_ALL"))
        request = self._request(client_ip=None)
        request.META.pop("CONTENT_LENGTH", None)
        response = PrivateIngressMiddleware(downstream)(request)
        self.assertEqual(response.content, b"CATCH_ALL")
        downstream.assert_called_once()

    @override_settings(SERVICE_REQUESTS_ENABLED=True)
    def test_enabled_but_invalid_configuration_has_no_partial_post_surface(self) -> None:
        downstream = Mock(return_value=HttpResponse("CATCH_ALL", status=404))
        request = self._request(client_ip=None)
        request.META.pop("CONTENT_LENGTH", None)
        response = PrivateIngressMiddleware(downstream)(request)
        self.assertEqual((response.status_code, response.content), (404, b"CATCH_ALL"))
        downstream.assert_called_once()
    @override_settings(**(_CONFIGURED | {"SERVICE_REQUEST_CONSENT_TEXT": "\ud800"}))
    def test_malformed_unicode_configuration_leaves_exact_post_closed(self) -> None:
        downstream = Mock(return_value=HttpResponse("CATCH_ALL", status=404))
        request = self._request(client_ip=None)
        request.META.pop("CONTENT_LENGTH", None)
        response = PrivateIngressMiddleware(downstream)(request)
        self.assertEqual((response.status_code, response.content), (404, b"CATCH_ALL"))
        downstream.assert_called_once()
