from __future__ import annotations

import os
import subprocess
import sys

from django.test import RequestFactory, SimpleTestCase, override_settings

from config.local_cutover_identity import (
    reject_restore_write_escape,
    target_identity_view,
    validate_identity_environment,
)


SHA_A = "a" * 64
SHA_B = "b" * 64
ENV = {
    "ESTAKADA_R7C_ROLE": "old",
    "ESTAKADA_R7C_GENERATION_SHA256": SHA_A,
    "ESTAKADA_R7C_STORAGE_BINDING_SHA256": SHA_B,
}


class LocalCutoverIdentityTests(SimpleTestCase):
    databases: set[str] = set()

    def setUp(self) -> None:
        self.factory = RequestFactory()

    @override_settings(
        R7C_ROLE="old",
        R7C_GENERATION_SHA256=SHA_A,
        R7C_STORAGE_BINDING_SHA256=SHA_B,
    )
    def test_exact_get_and_head_are_empty_and_safe(self) -> None:
        for method in ("get", "head"):
            request = getattr(self.factory, method)(
                "/__r7c_target_identity__", HTTP_HOST="r7c-probe.invalid"
            )
            response = target_identity_view(request)
            self.assertEqual(response.status_code, 204)
            self.assertEqual(response.content, b"")
            self.assertEqual(response["X-Estakada-R7C-Role"], "old")
            self.assertEqual(response["X-Estakada-R7C-Generation"], SHA_A)
            self.assertEqual(response["X-Estakada-R7C-Storage-Binding"], SHA_B)
            self.assertEqual(response["Cache-Control"], "no-store")
            self.assertNotIn("Set-Cookie", response)

    @override_settings(
        R7C_ROLE="old",
        R7C_GENERATION_SHA256=SHA_A,
        R7C_STORAGE_BINDING_SHA256=SHA_B,
    )
    def test_wrong_host_and_method_are_constant_denials(self) -> None:
        wrong_host = target_identity_view(
            self.factory.get("/__r7c_target_identity__", HTTP_HOST="localhost")
        )
        wrong_method = target_identity_view(
            self.factory.post(
                "/__r7c_target_identity__", HTTP_HOST="r7c-probe.invalid"
            )
        )
        self.assertEqual((wrong_host.status_code, wrong_host.content), (400, b""))
        self.assertEqual((wrong_method.status_code, wrong_method.content), (405, b""))

    @override_settings(
        R7C_ROLE="old",
        R7C_GENERATION_SHA256=SHA_A,
        R7C_STORAGE_BINDING_SHA256=SHA_B,
    )
    @override_settings(ROOT_URLCONF="config.urls_local_cutover")
    def test_local_urlconf_contains_marker(self) -> None:
        from django.urls import resolve

        self.assertIs(resolve("/__r7c_target_identity__").func, target_identity_view)

    @override_settings(ROOT_URLCONF="config.urls")
    def test_base_urlconf_does_not_name_marker(self) -> None:
        from config.urls import urlpatterns

        self.assertNotIn("r7c-target-identity", {pattern.name for pattern in urlpatterns})

    def test_environment_contract_rejects_write_escape_and_malformed_identity(self) -> None:
        for value in ("", "0", "1"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                reject_restore_write_escape({"ESTAKADA_RESTORE_VERIFY_WRITE": value})
        self.assertEqual(validate_identity_environment(ENV), ("old", SHA_A, SHA_B))
        with self.assertRaises(RuntimeError):
            validate_identity_environment({**ENV, "ESTAKADA_R7C_ROLE": "foreign"})

    def test_settings_import_rejects_any_write_escape_presence(self) -> None:
        for value in ("", "0", "1"):
            environment = dict(os.environ)
            environment["ESTAKADA_RESTORE_VERIFY_WRITE"] = value
            result = subprocess.run(
                [sys.executable, "-B", "-c", "import config.settings.local_cutover"],
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            with self.subTest(value=value):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("forbidden", result.stderr)
