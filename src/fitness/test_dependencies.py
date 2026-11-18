from __future__ import annotations

import ast
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = SOURCE_ROOT / "modules"
EXPECTED_MODULES = frozenset({"audit", "accounts", "media", "pages", "gallery"})
FORBIDDEN_PACKAGES = frozenset({"kernel", "common", "base", "utils"})
ALLOWED_EDGES = {
    "audit": frozenset(),
    "accounts": frozenset({"audit"}),
    "media": frozenset({"audit"}),
    "pages": frozenset({"accounts", "media", "audit"}),
    "gallery": frozenset({"pages", "media", "audit"}),
}


def _package_parts(path: Path) -> list[str]:
    relative = path.relative_to(SOURCE_ROOT)
    parts = list(relative.with_suffix("").parts)
    return parts[:-1] if parts[-1] != "__init__" else parts[:-1]


def _imports(source: str, *, package: list[str], filename: str) -> list[tuple[str, tuple[str, ...]]]:
    tree = ast.parse(source, filename=filename)
    imports: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((alias.name, tuple()) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package) - (node.level - 1)
                if keep < 0:
                    imports.append(("<invalid-relative>", tuple()))
                    continue
                prefix = package[:keep]
                module = ".".join(prefix + ((node.module or "").split(".") if node.module else []))
            else:
                module = node.module or ""
            imports.append((module, tuple(alias.name for alias in node.names)))
    return imports


def _path_imports(path: Path) -> list[tuple[str, tuple[str, ...]]]:
    return _imports(
        path.read_text(encoding="utf-8"),
        package=_package_parts(path),
        filename=str(path),
    )


def _cross_module_violation(owner: str, module: str, names: tuple[str, ...]) -> str | None:
    if module == "<invalid-relative>":
        return "invalid relative import"
    if module == "app" or module.startswith("app."):
        return f"legacy import: {module}"
    if module == "config" or module.startswith("config."):
        return f"module imports config: {module}"
    parts = module.split(".") if module else []
    if parts == ["modules"]:
        dependencies = names
        for dependency in dependencies:
            if dependency == owner:
                continue
            if dependency not in ALLOWED_EDGES[owner]:
                return f"forbidden edge: {owner}->{dependency}"
            return f"private package import: modules.{dependency}"
        return None
    if len(parts) < 2 or parts[0] != "modules" or parts[1] == owner:
        return None
    dependency = parts[1]
    if dependency not in ALLOWED_EDGES[owner]:
        return f"forbidden edge: {owner}->{dependency}"
    if len(parts) == 2:
        if names != ("api",):
            return f"private cross-module import: {module} {names}"
    elif len(parts) != 3 or parts[2] != "api":
        return f"private cross-module import: {module}"
    return None


class DependencyFitnessTests(unittest.TestCase):
    def test_exact_real_module_set_without_placeholders(self) -> None:
        actual = {
            path.name
            for path in MODULE_ROOT.iterdir()
            if path.is_dir() and (path / "__init__.py").is_file()
        }
        self.assertEqual(actual, EXPECTED_MODULES)
        self.assertFalse(FORBIDDEN_PACKAGES & {path.name for path in SOURCE_ROOT.iterdir()})
        self.assertFalse(FORBIDDEN_PACKAGES & actual)

    def test_no_clean_source_imports_legacy_app(self) -> None:
        for path in SOURCE_ROOT.rglob("*.py"):
            for imported, _ in _path_imports(path):
                self.assertFalse(
                    imported == "app" or imported.startswith("app."),
                    f"legacy import in {path.relative_to(SOURCE_ROOT)}: {imported}",
                )

    def test_exact_module_dag_and_public_api_only(self) -> None:
        for owner in sorted(EXPECTED_MODULES):
            for path in (MODULE_ROOT / owner).rglob("*.py"):
                for imported, names in _path_imports(path):
                    violation = _cross_module_violation(owner, imported, names)
                    self.assertIsNone(
                        violation,
                        f"{path.relative_to(SOURCE_ROOT)}: {violation}",
                    )

    def test_synthetic_reverse_private_and_relative_edges_are_rejected(self) -> None:
        fixtures = (
            ("accounts", "from modules.pages.api import x", ["modules", "accounts"], "forbidden"),
            ("pages", "from modules.accounts.models import User", ["modules", "pages"], "private"),
            ("pages", "from modules import accounts", ["modules", "pages"], "private"),
            ("accounts", "from ..pages.api import x", ["modules", "accounts"], "forbidden"),
            ("audit", "from config import settings", ["modules", "audit"], "config"),
            ("media", "from modules.pages.api import x", ["modules", "media"], "forbidden"),
            ("pages", "from modules.media.models import Asset", ["modules", "pages"], "private"),
            ("accounts", "from modules.audit.api.private import x", ["modules", "accounts"], "private"),
        )
        for owner, source, package, expected in fixtures:
            with self.subTest(source=source):
                imported, names = _imports(source, package=package, filename="fixture.py")[0]
                self.assertIn(expected, _cross_module_violation(owner, imported, names) or "")

    def test_synthetic_public_edge_is_accepted(self) -> None:
        imported, names = _imports(
            "from modules.audit.api import ActorRef",
            package=["modules", "accounts"],
            filename="fixture.py",
        )[0]
        self.assertIsNone(_cross_module_violation("accounts", imported, names))


if __name__ == "__main__":
    unittest.main()
