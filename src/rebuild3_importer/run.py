from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from rebuild3_importer.coordinator import ImportCoordinator, SafeResult
from rebuild3_importer.freeze import (
    FreezePackage,
    build_public_manifest,
    freeze_package_digest,
)
from rebuild3_importer.manifest import ManifestLimits
from rebuild3_importer.runtime_source import SourceEndpoint, open_source_bound
from rebuild3_importer.runtime_target import (
    ConcreteRunOps,
    MediaTransfer,
    TargetEndpoint,
)
from rebuild3_importer.source import SourceReader, VerifiedLedgerEvidence


class EntrypointError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True, repr=False)
class RunConfig:
    """Closed in-memory authority for one reviewed importer run."""

    source: SourceEndpoint
    target: TargetEndpoint
    package: FreezePackage
    limits: ManifestLimits
    expected_package_digest: str
    source_media_root: Path
    target_rebuild_root: Path
    result_root: Path


def _validate_config(value: object) -> RunConfig:
    if (
        not isinstance(value, RunConfig)
        or not isinstance(value.source, SourceEndpoint)
        or not isinstance(value.target, TargetEndpoint)
        or not isinstance(value.package, FreezePackage)
        or not isinstance(value.limits, ManifestLimits)
        or not all(
            isinstance(path, Path)
            for path in (
                value.source_media_root,
                value.target_rebuild_root,
                value.result_root,
            )
        )
    ):
        raise EntrypointError("entrypoint-config")
    try:
        actual_digest = freeze_package_digest(value.package)
    except Exception:
        raise EntrypointError("entrypoint-package") from None
    if actual_digest != value.expected_package_digest:
        raise EntrypointError("entrypoint-package")
    return value


def run(
    config: RunConfig,
    bind_ledger: Callable[[str], VerifiedLedgerEvidence],
) -> SafeResult:
    """Run the single fixed source-to-disposable-target composition once."""

    config = _validate_config(config)
    if not callable(bind_ledger):
        raise EntrypointError("entrypoint-ledger-binder")

    media = None
    opened = None
    handed_to_coordinator = False
    try:
        media = MediaTransfer(
            config.source_media_root,
            config.target_rebuild_root,
            config.limits.trusted_svg_sha256,
        )
        opened = open_source_bound(config.source, bind_ledger)
        frozen = build_public_manifest(
            opened.executor,
            opened.session,
            config.package,
            config.limits,
            config.expected_package_digest,
        )
        source = SourceReader(
            opened.executor,
            opened.session,
            opened.ledger,
            frozen.page_resolver,
        )
        ops = ConcreteRunOps(
            config.target,
            opened.lifecycle,
            media,
            config.result_root,
        )
        coordinator = ImportCoordinator(ops, source)
        handed_to_coordinator = True
        result = coordinator.run(frozen.manifest)
    except BaseException:
        cleanup_error = False
        if opened is not None and not handed_to_coordinator:
            try:
                opened.lifecycle.close()
            except BaseException:
                cleanup_error = True
        if media is not None:
            try:
                media.close()
            except BaseException:
                cleanup_error = True
        if cleanup_error:
            raise EntrypointError("entrypoint-cleanup-ambiguous") from None
        raise

    try:
        media.close()
    except BaseException:
        raise EntrypointError("entrypoint-cleanup-ambiguous") from None
    return result
