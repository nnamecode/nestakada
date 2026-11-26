from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest


LABELS = (
    "modules.accounts.tests.test_http_auth",
    "modules.pages.tests.test_http_list",
    "modules.pages.tests.test_http_editor",
    "modules.pages.tests.test_commands",
    "modules.pages.tests.test_grants",
    "modules.pages.tests.test_http_grants",
    "modules.pages.tests.test_staff_lifecycle",
    "modules.pages.tests.test_http_staff",
    "modules.pages.tests.test_publication",
    "modules.pages.tests.test_http_publication",
    "modules.pages.tests.test_public_read",
    "modules.pages.tests.test_legacy_plain_projection",
    "modules.pages.tests.test_site_settings",
    "modules.pages.tests.test_site_settings_commands",
    "modules.pages.tests.test_http_site_settings",
    "modules.pages.tests.test_rename",
    "modules.pages.tests.test_http_rename",
    "modules.pages.tests.test_create",
    "modules.pages.tests.test_http_create",
    "modules.pages.tests.test_reorder",
    "modules.pages.tests.test_http_reorder",
    "modules.pages.tests.test_delete",
    "modules.pages.tests.test_http_delete",
    "modules.pages.tests.test_move",
    "modules.pages.tests.test_http_move",
    "modules.pages.tests.test_url_change",
    "modules.pages.tests.test_http_url_change",
    "modules.pages.tests.test_contract",
    "modules.audit.tests.test_http",
    "modules.audit.tests.test_retention",
    "fitness.test_rebuild3_schema.Rebuild3SchemaSourceTests.test_page_url_authority_field_matches_ordinary_add_field_migration",
    "rebuild3_importer.tests.test_runtime_target.TargetProjectionTests.test_literal_projection_verifies_before_single_commit",
    "rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_exact_committed_projection_returns_closed_proof_once",
    "rebuild3_importer.tests.test_runtime_target.TargetCommittedReadbackTests.test_any_row_or_count_drift_fails_closed",
    "rebuild3_importer.tests.test_runtime_target.TargetMigrationRunnerTests.test_exact_leaves_generated_alias_and_cleanup",
)


class Core19Failure(RuntimeError):
    pass


class BoundedSink(io.TextIOBase):
    def __init__(self, limit: int = 1_048_576) -> None:
        self.limit = limit
        self.written = 0

    def write(self, value: str) -> int:
        size = len(value.encode("utf-8", errors="replace"))
        self.written += size
        if self.written > self.limit:
            raise Core19Failure("CORE19_OUTPUT_CAP")
        return len(value)


def fail(code: str) -> None:
    raise Core19Failure(code)


def label_index(test_id: str) -> int | None:
    matches = tuple(
        index for index, label in enumerate(LABELS, start=1)
        if test_id == label or test_id.startswith(label + ".")
    )
    return matches[0] if len(matches) == 1 else None


def iter_test_cases(suite):
    for item in suite:
        if hasattr(item, "__iter__"):
            yield from iter_test_cases(item)
        else:
            yield item


def build_method_aliases(suite) -> dict[str, str]:
    grouped = {index: [] for index in range(1, len(LABELS) + 1)}
    seen = set()
    for test in iter_test_cases(suite):
        test_id = test.id()
        index = label_index(test_id)
        if index is None or test_id in seen:
            fail("CORE19_METHOD_ALIAS_DISCOVERY_INVALID")
        seen.add(test_id)
        grouped[index].append(test_id)
    if len(seen) != 250 or any(not values for values in grouped.values()):
        fail("CORE19_METHOD_ALIAS_DISCOVERY_INVALID")
    aliases = {}
    for index, test_ids in grouped.items():
        for method, test_id in enumerate(sorted(test_ids), start=1):
            aliases[test_id] = f"L{index:02d}M{method:03d}"
    return aliases


def result_test_id(test) -> str | None:
    parent = getattr(test, "test_case", None)
    candidate = parent if parent is not None else test
    try:
        return candidate.id()
    except BaseException:
        return None


def result_aliases(entries, aliases: dict[str, str]) -> str:
    matched = set()
    for entry in entries:
        test = entry[0] if isinstance(entry, tuple) else entry
        test_id = result_test_id(test)
        if test_id is None:
            return "UNMAPPED"
        alias = aliases.get(test_id)
        if alias is None:
            return "UNMAPPED"
        matched.add(alias)
    if matched:
        return "_".join(sorted(matched))
    return "NONE"


def error_aliases(result, aliases: dict[str, str]) -> str:
    categories = {
        "AttributeError": "ATTRIBUTE_ERROR",
        "BrokenBarrierError": "BROKEN_BARRIER",
        "DataError": "DATA_ERROR",
        "DatabaseError": "DATABASE_ERROR",
        "DoesNotExist": "DOES_NOT_EXIST",
        "ImproperlyConfigured": "IMPROPERLY_CONFIGURED",
        "IntegrityError": "INTEGRITY_ERROR",
        "KeyError": "KEY_ERROR",
        "MultipleObjectsReturned": "MULTIPLE_OBJECTS",
        "OperationalError": "OPERATIONAL_ERROR",
        "PermissionError": "PERMISSION_ERROR",
        "ProgrammingError": "PROGRAMMING_ERROR",
        "RuntimeError": "RUNTIME_ERROR",
        "TimeoutError": "TIMEOUT_ERROR",
        "TransactionManagementError": "TRANSACTION_ERROR",
        "TypeError": "TYPE_ERROR",
        "ValueError": "VALUE_ERROR",
    }
    recorded = getattr(result, "core19_error_types", {})
    matched = set()
    for test, _detail in result.errors:
        test_id = result_test_id(test)
        if test_id is None:
            return "UNMAPPED_OTHER"
        alias = aliases.get(test_id)
        if alias is None:
            return "UNMAPPED_OTHER"
        category = categories.get(recorded.get(test_id), "OTHER")
        matched.add(f"{alias}_{category}")
    return "_".join(sorted(matched)) if matched else "NONE"


def failure_aliases(result, aliases: dict[str, str]) -> str:
    if getattr(result, "core19_failure_locations_overflow", False):
        return "LOCATIONS_OVERFLOW"
    recorded = getattr(result, "core19_failure_lines", {})
    matched = set()
    for test, _detail in result.failures:
        test_id = result_test_id(test)
        if test_id is None:
            return "UNMAPPED_N0000"
        alias = aliases.get(test_id)
        if alias is None:
            return "UNMAPPED_N0000"
        lines = recorded.get(test_id, ())
        if not lines:
            matched.add(f"{alias}_N0000")
        else:
            for line in lines:
                matched.add(f"{alias}_N{line:04d}")
        if len(matched) > 64:
            return "LOCATIONS_OVERFLOW"
    return "_".join(sorted(matched)) if matched else "NONE"


def unexpected_failure_code(stage_code: str, exc: BaseException) -> str:
    categories = {
        "AttributeError": "ATTRIBUTE_ERROR",
        "ImproperlyConfigured": "IMPROPERLY_CONFIGURED",
        "ImportError": "IMPORT_ERROR",
        "KeyError": "KEY_ERROR",
        "ModuleNotFoundError": "MODULE_NOT_FOUND",
        "OperationalError": "OPERATIONAL_ERROR",
        "OSError": "OS_ERROR",
        "PermissionError": "PERMISSION_ERROR",
        "ProgrammingError": "PROGRAMMING_ERROR",
        "RuntimeError": "RUNTIME_ERROR",
        "SystemExit": "SYSTEM_EXIT",
        "TypeError": "TYPE_ERROR",
        "ValueError": "VALUE_ERROR",
    }
    category = categories.get(type(exc).__name__, "OTHER")
    if type(exc).__name__ == "ModuleNotFoundError":
        missing = getattr(exc, "name", None)
        exact_modules = {
            "config": "CONFIG_ROOT",
            "config.settings": "SETTINGS_PACKAGE",
            "config.settings.base": "BASE_SETTINGS",
            "config.settings.test": "TEST_SETTINGS",
            "config.settings.core19_runtime": "CORE19_SETTINGS",
            "modules": "MODULES_ROOT",
            "csp": "CSP",
            "psycopg": "PSYCOPG",
            "psycopg2": "PSYCOPG2",
            "asgiref": "ASGIREF",
            "sqlparse": "SQLPARSE",
        }
        local_apps = {
            "modules.accounts": "ACCOUNTS_APP",
            "modules.audit": "AUDIT_APP",
            "modules.gallery": "GALLERY_APP",
            "modules.media": "MEDIA_APP",
            "modules.pages": "PAGES_APP",
            "modules.service_requests": "SERVICE_REQUESTS_APP",
        }
        alias = exact_modules.get(missing)
        if alias is None and isinstance(missing, str):
            if missing == "django" or missing.startswith("django."):
                alias = "DJANGO"
            else:
                for prefix, candidate in local_apps.items():
                    if missing == prefix or missing.startswith(prefix + "."):
                        alias = candidate
                        break
        category = f"MODULE_NOT_FOUND_{alias or 'OTHER_MODULE'}"
    if not stage_code.startswith("CORE19_") or not stage_code.endswith("_FAILED"):
        return "CORE19_UNEXPECTED_CODE_INVALID"
    return f"{stage_code[:-7]}_{category}_FAILED"


def main() -> None:
    unexpected_code = "CORE19_BOOTSTRAP_FAILED"
    try:
        if os.environ.get("ESTAKADA_CORE19_SYNTHETIC_RUNTIME") != "1":
            fail("CORE19_MARKER_INVALID")
        project_root = "/project/src"
        if os.getcwd() != project_root:
            fail("CORE19_WORKDIR_INVALID")
        sys.path.insert(0, project_root)
        unexpected_code = "CORE19_DJANGO_IMPORT_FAILED"
        import django

        unexpected_code = "CORE19_DJANGO_SETUP_FAILED"
        django.setup()
        unexpected_code = "CORE19_RUNNER_IMPORT_FAILED"
        from django.core.management import call_command
        from django.db import connection
        from django.test.runner import DiscoverRunner

        unexpected_code = "CORE19_RUNNER_PREPARE_FAILED"
        if len(LABELS) != 35 or len(set(LABELS)) != 35:
            fail("CORE19_LABELS_INVALID")

        class RecordingResult(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.core19_error_types = {}
                self.core19_failure_lines = {}
                self.core19_failure_location_count = 0
                self.core19_failure_locations_overflow = False

            def _record_failure_line(self, test, err):
                test_id = result_test_id(test)
                if test_id is None:
                    return
                selected = None
                traceback = err[2]
                while traceback is not None:
                    filename = traceback.tb_frame.f_code.co_filename.replace("\\", "/")
                    if filename.startswith("/project/src/") and "/tests/" in filename:
                        selected = traceback.tb_lineno
                    traceback = traceback.tb_next
                if isinstance(selected, int) and 1 <= selected <= 9999:
                    lines = self.core19_failure_lines.setdefault(test_id, set())
                    if selected not in lines:
                        if self.core19_failure_location_count >= 64:
                            self.core19_failure_locations_overflow = True
                        else:
                            lines.add(selected)
                            self.core19_failure_location_count += 1

            def addError(self, test, err):
                self.core19_error_types[test.id()] = type(err[1]).__name__
                super().addError(test, err)

            def addFailure(self, test, err):
                self._record_failure_line(test, err)
                super().addFailure(test, err)

            def addSubTest(self, test, subtest, err):
                if err is not None and issubclass(err[0], test.failureException):
                    self._record_failure_line(subtest, err)
                super().addSubTest(test, subtest, err)

        class RecordingTextRunner(unittest.TextTestRunner):
            resultclass = RecordingResult

        class RecordingRunner(DiscoverRunner):
            test_runner = RecordingTextRunner
            recorded_result = None

            def run_suite(self, suite, **kwargs):
                result = super().run_suite(suite, **kwargs)
                self.recorded_result = result
                return result

        hidden = BoundedSink()
        with contextlib.redirect_stdout(hidden), contextlib.redirect_stderr(hidden):
            unexpected_code = "CORE19_CHECK_FAILED"
            call_command("check", verbosity=0)
            unexpected_code = "CORE19_MIGRATION_CHECK_FAILED"
            call_command("makemigrations", check=True, dry_run=True, verbosity=0)
            runner = RecordingRunner(verbosity=1, interactive=False, keepdb=False)
            unexpected_code = "CORE19_DISCOVERY_FAILED"
            suite = runner.build_suite(LABELS)
            if suite.countTestCases() != 250:
                fail("CORE19_DISCOVERY_MISMATCH")
            method_aliases = build_method_aliases(suite)
            unexpected_code = "CORE19_DATABASE_PRECHECK_FAILED"
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_database WHERE datname = %s",
                    ["estakada_core19_test"],
                )
                if cursor.fetchone() != (0,):
                    fail("CORE19_TEST_DATABASE_PREEXISTS")
            unexpected_code = "CORE19_SUITE_EXECUTION_FAILED"
            failures = runner.run_tests(LABELS)
            result = runner.recorded_result
            unexpected_code = "CORE19_DATABASE_POSTCHECK_FAILED"
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_database WHERE datname = %s",
                    ["estakada_core19_test"],
                )
                database_count = cursor.fetchone()
        if result is None:
            fail("CORE19_SUITE_RESULT_MISSING")
        if result.testsRun != 250:
            fail("CORE19_SUITE_TEST_COUNT_MISMATCH")
        if result.errors:
            fail(f"CORE19_SUITE_ERRORS_{error_aliases(result, method_aliases)}")
        if result.failures:
            fail(f"CORE19_SUITE_FAILURES_{failure_aliases(result, method_aliases)}")
        if result.skipped:
            fail(f"CORE19_SUITE_SKIPS_{result_aliases(result.skipped, method_aliases)}")
        if result.expectedFailures:
            fail(f"CORE19_SUITE_EXPECTED_FAILURES_{result_aliases(result.expectedFailures, method_aliases)}")
        if result.unexpectedSuccesses:
            fail(f"CORE19_SUITE_UNEXPECTED_SUCCESSES_{result_aliases(result.unexpectedSuccesses, method_aliases)}")
        if failures != 0:
            fail("CORE19_SUITE_RETURN_COUNT_MISMATCH")
        if database_count != (0,):
            fail("CORE19_TEST_DATABASE_REMAINS")
        print("CORE19_ADMIN_RUNTIME_OK tests=250 failures=0 errors=0 skips=0")
    except Core19Failure as exc:
        print(str(exc))
        raise SystemExit(1) from None
    except BaseException as exc:
        print(unexpected_failure_code(unexpected_code, exc))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
