import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from rebuild3_importer.freeze import FreezePackage, freeze_package_digest
from rebuild3_importer.manifest import ManifestLimits
from rebuild3_importer.run import EntrypointError, RunConfig, run
from rebuild3_importer.runtime_source import SourceEndpoint
from rebuild3_importer.runtime_target import TargetEndpoint
from rebuild3_importer.source import SourceSession, VerifiedLedgerEvidence


PACKAGE = FreezePackage(
    pages=(), routes=(), source_shared=(), source_media=(), site_settings={},
    assets=(), files=(), usages=(), gallery_albums=(), gallery_photos=(),
    media_bindings=(), usage_bindings=(),
)
LIMITS = ManifestLimits(0, 0, 0, 0, 0, 0, 0, 1, 0, 0, frozenset())
DIGEST = freeze_package_digest(PACKAGE)
EVIDENCE = VerifiedLedgerEvidence(
    uuid.UUID("00000000-0000-4000-8000-000000000001"),
    1,
    "1" * 64,
    0,
    "10:20:",
)


def BINDER(_snapshot_id):
    return EVIDENCE


def config(*, digest=DIGEST):
    return RunConfig(
        SourceEndpoint(
            "source.example.test", 5432, Path("C:/authority/source-ca.pem"),
            "foundation_admin", Path("C:/authority/source-admin.secret"),
            Path("C:/authority/source-reader.secret"),
            "2026-11-18T12:10:00.000000Z",
        ),
        TargetEndpoint(
            "target.example.test", 5432, Path("C:/authority/target-ca.pem"),
            "foundation_admin", Path("C:/authority/target-admin.secret"),
            Path("C:/authority/secrets"), "2026-11-18T12:10:00.000000Z",
        ),
        PACKAGE,
        LIMITS,
        digest,
        Path("C:/authority/source-media"),
        Path("D:/rebuild-target"),
        Path("C:/authority/results"),
    )


class EntrypointTests(TestCase):
    def dependencies(self):
        media = Mock()
        lifecycle = Mock()
        opened = SimpleNamespace(
            executor=object(),
            session=SourceSession(10, 20, "10:20:"),
            ledger=object(),
            lifecycle=lifecycle,
        )
        frozen = SimpleNamespace(manifest=object(), page_resolver=object())
        source = object()
        ops = object()
        result = object()
        return media, lifecycle, opened, frozen, source, ops, result

    def test_exact_in_memory_package_is_wired_once(self):
        media, lifecycle, opened, frozen, source, ops, result = self.dependencies()
        with (
            patch("rebuild3_importer.run.MediaTransfer", return_value=media) as transfer,
            patch("rebuild3_importer.run.open_source_bound", return_value=opened) as source_open,
            patch("rebuild3_importer.run.build_public_manifest", return_value=frozen) as freeze,
            patch("rebuild3_importer.run.SourceReader", return_value=source) as reader,
            patch("rebuild3_importer.run.ConcreteRunOps", return_value=ops) as run_ops,
            patch("rebuild3_importer.run.ImportCoordinator") as coordinator_type,
        ):
            coordinator_type.return_value.run.return_value = result
            self.assertIs(run(config(), BINDER), result)

        transfer.assert_called_once_with(
            Path("C:/authority/source-media"), Path("D:/rebuild-target"), frozenset(),
        )
        source_open.assert_called_once_with(config().source, BINDER)
        freeze.assert_called_once_with(
            opened.executor, opened.session, PACKAGE, LIMITS, DIGEST,
        )
        reader.assert_called_once_with(
            opened.executor, opened.session, opened.ledger, frozen.page_resolver,
        )
        run_ops.assert_called_once_with(config().target, lifecycle, media, config().result_root)
        coordinator_type.assert_called_once_with(ops, source)
        coordinator_type.return_value.run.assert_called_once_with(frozen.manifest)
        media.close.assert_called_once_with()
        lifecycle.close.assert_not_called()

    def test_freeze_failure_closes_unhanded_source_and_media(self):
        media, lifecycle, opened, _frozen, _source, _ops, _result = self.dependencies()
        with (
            patch("rebuild3_importer.run.MediaTransfer", return_value=media),
            patch("rebuild3_importer.run.open_source_bound", return_value=opened),
            patch("rebuild3_importer.run.build_public_manifest", side_effect=RuntimeError("freeze")),
        ):
            with self.assertRaisesRegex(RuntimeError, "freeze"):
                run(config(), BINDER)
        lifecycle.close.assert_called_once_with()
        media.close.assert_called_once_with()

    def test_coordinator_failure_is_not_retried_by_entrypoint(self):
        media, lifecycle, opened, frozen, source, ops, _result = self.dependencies()
        with (
            patch("rebuild3_importer.run.MediaTransfer", return_value=media),
            patch("rebuild3_importer.run.open_source_bound", return_value=opened),
            patch("rebuild3_importer.run.build_public_manifest", return_value=frozen),
            patch("rebuild3_importer.run.SourceReader", return_value=source),
            patch("rebuild3_importer.run.ConcreteRunOps", return_value=ops),
            patch("rebuild3_importer.run.ImportCoordinator") as coordinator_type,
        ):
            coordinator_type.return_value.run.side_effect = RuntimeError("coordinator")
            with self.assertRaisesRegex(RuntimeError, "coordinator"):
                run(config(), BINDER)
        lifecycle.close.assert_not_called()
        media.close.assert_called_once_with()

    def test_invalid_authority_fails_before_components(self):
        with patch("rebuild3_importer.run.MediaTransfer") as transfer:
            with self.assertRaisesRegex(EntrypointError, "entrypoint-package"):
                run(config(digest="0" * 64), BINDER)
        transfer.assert_not_called()

    def test_cleanup_ambiguity_is_fail_closed(self):
        media, lifecycle, opened, _frozen, _source, _ops, _result = self.dependencies()
        lifecycle.close.side_effect = RuntimeError("close")
        with (
            patch("rebuild3_importer.run.MediaTransfer", return_value=media),
            patch("rebuild3_importer.run.open_source_bound", return_value=opened),
            patch("rebuild3_importer.run.build_public_manifest", side_effect=RuntimeError("freeze")),
        ):
            with self.assertRaisesRegex(
                EntrypointError, "entrypoint-cleanup-ambiguous",
            ):
                run(config(), BINDER)
        media.close.assert_called_once_with()

    def test_non_callable_binder_fails_before_components(self):
        with patch("rebuild3_importer.run.MediaTransfer") as transfer:
            with self.assertRaisesRegex(
                EntrypointError,
                "entrypoint-ledger-binder",
            ):
                run(config(), EVIDENCE)
        transfer.assert_not_called()

    def test_binder_base_exception_closes_media_without_retry(self):
        media = Mock()

        def interrupt(_endpoint, _binder):
            raise KeyboardInterrupt()

        with (
            patch("rebuild3_importer.run.MediaTransfer", return_value=media),
            patch("rebuild3_importer.run.open_source_bound", side_effect=interrupt),
        ):
            with self.assertRaises(KeyboardInterrupt):
                run(config(), BINDER)
        media.close.assert_called_once_with()
