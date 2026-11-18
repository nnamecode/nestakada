from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Protocol

from rebuild3_importer.errors import CoordinatorError
from rebuild3_importer.manifest import PublicManifest
from rebuild3_importer.source import PrivateSourceRows, SourcePreflight, SourceReader, VerifiedLedgerEvidence


SHA256 = re.compile(r"^[0-9a-f]{64}$")
RESULT_SCHEMA = "estakada.rebuild-result"
RESULT_VERSION = 1


@dataclass(frozen=True, slots=True)
class TargetNames:
    run_id: uuid.UUID
    database: str
    media_key: str
    owner_role: str
    importer_role: str


@dataclass(frozen=True, slots=True)
class ProjectionCounts:
    site_settings: int
    pages: int
    routes: int
    current: int
    previous: int
    staff: int
    grants: int
    assets: int
    files: int
    usages: int
    albums: int
    photos: int


@dataclass(frozen=True, slots=True)
class PreTargetProof:
    counts: ProjectionCounts
    source_media_digest: str


@dataclass(frozen=True, slots=True)
class ReadbackProof:
    schema: str
    version: int
    counts: ProjectionCounts
    manifest_digest: str
    database_digest: str
    source_media_digest: str
    target_media_digest: str
    ledger_identity: uuid.UUID
    ledger_generation: int
    ledger_digest: str
    constraints_ok: bool
    counts_ok: bool
    usages_ok: bool


@dataclass(frozen=True, slots=True)
class CleanupProof:
    names_exact: bool
    media_contained: bool
    media_non_link: bool
    owners_exact: bool
    roles_exact: bool
    connections_zero: bool
    pointers_absent: bool

    def allows_cleanup(self) -> bool:
        return all(value is True for value in (
            self.names_exact,
            self.media_contained,
            self.media_non_link,
            self.owners_exact,
            self.roles_exact,
            self.connections_zero,
            self.pointers_absent,
        ))


@dataclass(frozen=True, slots=True)
class SafeResult:
    schema: str
    version: int
    phase: str
    run_id: uuid.UUID
    database: str
    media_key: str
    manifest_digest: str
    ledger_identity: uuid.UUID
    ledger_generation: int
    ledger_digest: str
    counts: ProjectionCounts
    database_digest: str | None
    source_media_digest: str
    target_media_digest: str | None
    error_code: str | None


class RunOps(Protocol):
    def validate_pre_target(self, manifest: PublicManifest, source: SourcePreflight) -> PreTargetProof: ...
    def create_empty_target(self, names: TargetNames) -> None:
        """Acquire the empty pair; success means exact ownership."""
        ...
    def target_acquisition_status(self, names: TargetNames) -> str:
        """After create failure return exact ACQUIRED/ABSENT/AMBIGUOUS."""
        ...
    def record_created(self, result: SafeResult) -> None: ...
    def prepare_target(self, names: TargetNames) -> None: ...
    def begin_import(self, names: TargetNames) -> None: ...
    def import_public(self, manifest: PublicManifest) -> None: ...
    def import_private(self, rows: PrivateSourceRows) -> None: ...
    def apply_zero_request_ledger(self, evidence: VerifiedLedgerEvidence) -> None: ...
    def copy_and_verify_files(self, manifest: PublicManifest, names: TargetNames) -> None: ...
    def verify_before_commit(self, manifest: PublicManifest, rows: PrivateSourceRows) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def readback(self, manifest: PublicManifest, names: TargetNames) -> ReadbackProof: ...
    def close_source_identity(self) -> None:
        """Close RRRO, set exact source role NOLOGIN, revoke literal grants and remove its secret."""
        ...
    def close_identities(self, names: TargetNames) -> None: ...
    def record_sealed(self, result: SafeResult) -> None: ...
    def seal_status(self, result: SafeResult) -> str:
        """Return exact durable EXACT/ABSENT/AMBIGUOUS status; Q003 uses the same authority."""
        ...
    def record_failed(self, result: SafeResult) -> None: ...
    def cleanup_proof(self, names: TargetNames) -> CleanupProof: ...
    def cleanup_exact_pair(self, names: TargetNames) -> None: ...


def target_names(run_id: uuid.UUID) -> TargetNames:
    if not isinstance(run_id, uuid.UUID) or run_id.version != 4 or run_id.variant != uuid.RFC_4122:
        raise CoordinatorError("run-id")
    compact = run_id.hex
    return TargetNames(
        run_id=run_id,
        database=f"estakada_rebuild_{compact}",
        media_key=f"{run_id}/media",
        owner_role=f"estakada_rb3_owner_{compact}",
        importer_role=f"estakada_rb3_importer_{compact}",
    )


def _safe_result(
    phase: str,
    names: TargetNames,
    manifest: PublicManifest,
    ledger: VerifiedLedgerEvidence,
    pre_target: PreTargetProof,
    readback: ReadbackProof | None = None,
    error_code: str | None = None,
) -> SafeResult:
    if phase not in ("CREATED", "SEALED", "FAILED"):
        raise CoordinatorError("result-phase")
    return SafeResult(
        RESULT_SCHEMA,
        RESULT_VERSION,
        phase,
        names.run_id,
        names.database,
        names.media_key,
        manifest.digest,
        ledger.identity,
        ledger.generation,
        ledger.digest,
        pre_target.counts,
        None if readback is None else readback.database_digest,
        pre_target.source_media_digest,
        None if readback is None else readback.target_media_digest,
        error_code,
    )


def _valid_counts(value: object) -> bool:
    if not isinstance(value, ProjectionCounts):
        return False
    items = (
        value.site_settings,
        value.pages,
        value.routes,
        value.current,
        value.previous,
        value.staff,
        value.grants,
        value.assets,
        value.files,
        value.usages,
        value.albums,
        value.photos,
    )
    return (
        value.site_settings == 1
        and all(type(item) is int and item >= 0 for item in items)
    )


def _valid_pre_target(value: object, source: SourcePreflight) -> bool:
    return (
        isinstance(value, PreTargetProof)
        and _valid_counts(value.counts)
        and value.counts.staff == source.staff_count
        and value.counts.grants == source.grant_count
        and value.counts.current == source.current_count
        and value.counts.previous == source.previous_count
        and isinstance(value.source_media_digest, str)
        and SHA256.fullmatch(value.source_media_digest) is not None
    )


def _valid_readback(
    proof: object,
    manifest: PublicManifest,
    ledger: VerifiedLedgerEvidence,
    pre_target: PreTargetProof,
) -> bool:
    if not isinstance(proof, ReadbackProof):
        return False
    digests = (
        proof.manifest_digest,
        proof.database_digest,
        proof.source_media_digest,
        proof.target_media_digest,
        proof.ledger_digest,
    )
    return (
        proof.schema == RESULT_SCHEMA
        and type(proof.version) is int
        and proof.version == RESULT_VERSION
        and all(isinstance(value, str) and SHA256.fullmatch(value) is not None for value in digests)
        and _valid_counts(proof.counts)
        and proof.counts == pre_target.counts
        and proof.manifest_digest == manifest.digest == proof.database_digest
        and proof.source_media_digest == pre_target.source_media_digest == proof.target_media_digest
        and proof.ledger_identity == ledger.identity
        and type(proof.ledger_generation) is int
        and proof.ledger_generation == ledger.generation
        and proof.ledger_digest == ledger.digest
        and proof.constraints_ok is True
        and proof.counts_ok is True
        and proof.usages_ok is True
    )


class ImportCoordinator:
    """Fixed one-shot disposable import order; it has no resume or retry path."""

    __slots__ = ("_ops", "_source", "_run_id", "_used")

    def __init__(self, ops: RunOps, source: SourceReader, *, run_id: uuid.UUID | None = None) -> None:
        self._ops = ops
        self._source = source
        self._run_id = uuid.uuid4() if run_id is None else run_id
        self._used = False

    def run(self, manifest: PublicManifest) -> SafeResult:
        if self._used:
            raise CoordinatorError("run-reuse")
        self._used = True
        try:
            names = target_names(self._run_id)
        except Exception:
            closed = self._close_source_only()
            raise CoordinatorError("run-id" if closed else "run-id-source-close-ambiguous") from None
        ledger: VerifiedLedgerEvidence | None = None
        pre_target: PreTargetProof | None = None
        target_created = False
        created_recorded = False
        transaction_open = False
        source_map_close_attempted = False
        source_map_closed = False
        source_identity_close_attempted = False
        source_identity_closed = False
        target_identities_close_attempted = False
        target_identities_closed = False
        acquisition_ambiguous = False
        seal_ambiguous = False
        stage = "pretarget"
        try:
            if not isinstance(manifest, PublicManifest):
                raise CoordinatorError("manifest")
            if not isinstance(manifest.digest, str) or SHA256.fullmatch(manifest.digest) is None:
                raise CoordinatorError("manifest")
            source_preflight = self._source.preflight(manifest.snapshot_id)
            if not isinstance(source_preflight, SourcePreflight):
                raise CoordinatorError("source-preflight")
            ledger = source_preflight.ledger
            pre_target = self._ops.validate_pre_target(manifest, source_preflight)
            if not _valid_pre_target(pre_target, source_preflight):
                raise CoordinatorError("pretarget-proof")

            stage = "create"
            try:
                self._ops.create_empty_target(names)
            except Exception:
                try:
                    acquisition = self._ops.target_acquisition_status(names)
                except Exception:
                    acquisition = "AMBIGUOUS"
                if acquisition == "ACQUIRED":
                    target_created = True
                elif acquisition == "AMBIGUOUS":
                    acquisition_ambiguous = True
                elif acquisition != "ABSENT":
                    acquisition_ambiguous = True
                raise
            target_created = True
            seal_ambiguous = True
            self._ops.record_created(_safe_result("CREATED", names, manifest, ledger, pre_target))
            created_recorded = True
            seal_ambiguous = False

            stage = "prepare"
            self._ops.prepare_target(names)
            transaction_open = True
            self._ops.begin_import(names)

            stage = "database-import"
            self._ops.import_public(manifest)
            private_rows = self._source.read_private()
            self._ops.import_private(private_rows)
            self._ops.apply_zero_request_ledger(ledger)

            stage = "file-copy"
            self._ops.copy_and_verify_files(manifest, names)
            stage = "precommit-verify"
            self._ops.verify_before_commit(manifest, private_rows)
            self._ops.commit()
            transaction_open = False

            stage = "readback"
            proof = self._ops.readback(manifest, names)
            if not _valid_readback(proof, manifest, ledger, pre_target):
                raise CoordinatorError("readback-mismatch")

            stage = "close-identities"
            source_map_close_attempted = True
            self._source.close()
            source_map_closed = True
            source_identity_close_attempted = True
            self._ops.close_source_identity()
            source_identity_closed = True
            target_identities_close_attempted = True
            self._ops.close_identities(names)
            target_identities_closed = True
            stage = "seal"
            sealed = _safe_result("SEALED", names, manifest, ledger, pre_target, proof)
            try:
                self._ops.record_sealed(sealed)
                return sealed
            except Exception:
                stage = "seal-status"
                try:
                    status = self._ops.seal_status(sealed)
                except Exception:
                    status = "AMBIGUOUS"
                if status == "EXACT":
                    return sealed
                if status == "ABSENT":
                    stage = "seal-absent"
                    raise CoordinatorError("seal-absent")
                seal_ambiguous = True
                raise CoordinatorError("seal-ambiguous")
        except Exception as exc:
            code = (
                exc.code
                if isinstance(exc, CoordinatorError)
                and exc.code in ("manifest", "readback-mismatch", "seal-absent", "seal-ambiguous")
                else f"{stage}-failed"
            )
            self._fail(
                names,
                manifest if isinstance(manifest, PublicManifest) else None,
                ledger,
                pre_target,
                code,
                target_created=target_created,
                created_recorded=created_recorded,
                transaction_open=transaction_open,
                source_map_close_attempted=source_map_close_attempted,
                source_map_closed=source_map_closed,
                source_identity_close_attempted=source_identity_close_attempted,
                source_identity_closed=source_identity_closed,
                target_identities_close_attempted=target_identities_close_attempted,
                target_identities_closed=target_identities_closed,
                seal_ambiguous=seal_ambiguous or acquisition_ambiguous,
            )
            raise CoordinatorError(code) from None

    def _fail(
        self,
        names: TargetNames,
        manifest: PublicManifest | None,
        ledger: VerifiedLedgerEvidence | None,
        pre_target: PreTargetProof | None,
        code: str,
        *,
        target_created: bool,
        created_recorded: bool,
        transaction_open: bool,
        source_map_close_attempted: bool,
        source_map_closed: bool,
        source_identity_close_attempted: bool,
        source_identity_closed: bool,
        target_identities_close_attempted: bool,
        target_identities_closed: bool,
        seal_ambiguous: bool,
    ) -> None:
        lifecycle_ambiguous = False
        if transaction_open:
            try:
                self._ops.rollback()
            except Exception:
                code = "rollback-ambiguous"
                lifecycle_ambiguous = True
        if not source_map_close_attempted:
            try:
                self._source.close()
                source_map_closed = True
            except Exception:
                code = "source-close-ambiguous"
                lifecycle_ambiguous = True
        elif not source_map_closed:
            lifecycle_ambiguous = True
        if not source_identity_close_attempted:
            try:
                self._ops.close_source_identity()
                source_identity_closed = True
            except Exception:
                code = "source-identity-close-ambiguous"
                lifecycle_ambiguous = True
        elif not source_identity_closed:
            lifecycle_ambiguous = True
        if target_created and not target_identities_close_attempted:
            try:
                self._ops.close_identities(names)
                target_identities_closed = True
            except Exception:
                code = "identity-close-ambiguous"
                lifecycle_ambiguous = True
        elif target_created and not target_identities_closed:
            lifecycle_ambiguous = True
        if not target_created:
            return
        if seal_ambiguous or lifecycle_ambiguous:
            return
        if not created_recorded:
            try:
                proof = self._ops.cleanup_proof(names)
                if isinstance(proof, CleanupProof) and proof.allows_cleanup():
                    self._ops.cleanup_exact_pair(names)
            except Exception:
                pass
            return
        if manifest is None or ledger is None or pre_target is None:
            return
        try:
            self._ops.record_failed(_safe_result("FAILED", names, manifest, ledger, pre_target, error_code=code))
        except Exception:
            return
        try:
            proof = self._ops.cleanup_proof(names)
            if not isinstance(proof, CleanupProof) or not proof.allows_cleanup():
                return
            self._ops.cleanup_exact_pair(names)
        except Exception:
            return

    def _close_source_only(self) -> bool:
        closed = True
        try:
            self._source.close()
        except Exception:
            closed = False
        try:
            self._ops.close_source_identity()
        except Exception:
            closed = False
        return closed
