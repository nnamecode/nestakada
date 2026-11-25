from __future__ import annotations

import ast
from pathlib import Path

from django.test import SimpleTestCase


class ServiceRequestStaticPrivacyTests(SimpleTestCase):
    def test_production_modules_have_no_logging_or_print_sink(self) -> None:
        root = Path(__file__).resolve().parents[1]
        files = tuple(
            path for path in root.glob("*.py")
            if path.name not in {"__init__.py", "apps.py"}
        )
        self.assertTrue(files)
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                with self.subTest(path=path.name, line=getattr(node, "lineno", 0)):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        names = {alias.name.split(".", 1)[0] for alias in node.names}
                        self.assertNotIn("logging", names)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        self.assertNotEqual(node.func.id, "print")

    def test_audit_detail_literals_never_name_personal_or_transport_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        forbidden = {
            "name", "phone", "vehicle", "comment", "consent", "token",
            "chat_id", "payload", "response",
        }
        seen = 0
        for path in root.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "append_event"
                ):
                    continue
                seen += 1
                detail = next((item.value for item in node.keywords if item.arg == "detail"), None)
                if detail is None:
                    continue
                self.assertIsInstance(detail, ast.Dict)
                keys = {
                    key.value for key in detail.keys
                    if isinstance(key, ast.Constant) and isinstance(key.value, str)
                }
                self.assertTrue(keys.isdisjoint(forbidden), (path.name, keys & forbidden))
        self.assertGreaterEqual(seen, 4)
