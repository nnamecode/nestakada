import uuid
from unittest import TestCase

from rebuild3_importer.coordinator import (
    CleanupProof,
    ImportCoordinator,
    PreTargetProof,
    ProjectionCounts,
    ReadbackProof,
    RESULT_SCHEMA,
    RESULT_VERSION,
    SafeResult,
    target_names,
)
from rebuild3_importer.errors import CoordinatorError
from rebuild3_importer.manifest import PublicManifest
from rebuild3_importer.source import PrivateSourceRows, SourcePreflight, VerifiedLedgerEvidence


RUN_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
DIGEST = "a" * 64
MEDIA_DIGEST = "b" * 64
SNAPSHOT = "10:20:"
MANIFEST = PublicManifest(SNAPSHOT, DIGEST, {}, {})
LEDGER = VerifiedLedgerEvidence(uuid.uuid4(), 3, DIGEST, 0, SNAPSHOT)
PRIVATE = PrivateSourceRows((), (), ())
COUNTS = ProjectionCounts(1, 2, 2, 2, 0, 0, 0, 3, 3, 2, 1, 1)
PREFLIGHT = SourcePreflight(LEDGER, 0, 0, 2, 0)


class FakeSource:
    def __init__(self, fail=None):
        self.fail = fail
        self.closed = False
        self.calls = []

    def preflight(self, snapshot_id):
        self.calls.append("preflight")
        if self.fail == "preflight":
            raise ValueError("private-value")
        return PREFLIGHT

    def read_private(self):
        self.calls.append("read_private")
        if self.fail == "read_private":
            raise ValueError("private-value")
        return PRIVATE

    def close(self):
        self.calls.append("close")
        if self.fail == "close":
            raise RuntimeError("private-value")
        self.closed = True


class FakeOps:
    def __init__(
        self, fail=None, cleanup=True, seal_status="AMBIGUOUS", counts=COUNTS,
        acquisition_status="ABSENT",
    ):
        self.fail = fail
        self.cleanup = cleanup
        self._seal_status = seal_status
        self.counts = counts
        self._acquisition_status = acquisition_status
        self.calls = []
        self.results = []

    def hit(self, name):
        self.calls.append(name)
        if self.fail == name:
            raise RuntimeError("secret/private/path")

    def validate_pre_target(self, manifest, source):
        self.hit("validate")
        return PreTargetProof(self.counts, MEDIA_DIGEST)
    def create_empty_target(self, names): self.hit("create")
    def target_acquisition_status(self, names):
        self.calls.append("acquisition_status")
        return self._acquisition_status
    def record_created(self, result): self.hit("created"); self.results.append(result)
    def prepare_target(self, names): self.hit("prepare")
    def begin_import(self, names): self.hit("begin")
    def import_public(self, manifest): self.hit("public")
    def import_private(self, rows): self.hit("private")
    def apply_zero_request_ledger(self, evidence): self.hit("ledger")
    def copy_and_verify_files(self, manifest, names): self.hit("files")
    def verify_before_commit(self, manifest, rows): self.hit("verify")
    def commit(self): self.hit("commit")
    def rollback(self): self.hit("rollback")
    def readback(self, manifest, names):
        self.hit("readback")
        return ReadbackProof(
            RESULT_SCHEMA, RESULT_VERSION, self.counts, DIGEST, DIGEST,
            MEDIA_DIGEST, MEDIA_DIGEST, LEDGER.identity, LEDGER.generation,
            DIGEST, True, True, True,
        )
    def close_source_identity(self): self.hit("close_source_identity")
    def close_identities(self, names): self.hit("close_identities")
    def record_sealed(self, result): self.hit("sealed"); self.results.append(result)
    def seal_status(self, result): self.hit("seal_status"); return self._seal_status
    def record_failed(self, result): self.hit("failed"); self.results.append(result)
    def cleanup_proof(self, names):
        self.hit("cleanup_proof")
        return CleanupProof(*(self.cleanup,) * 7)
    def cleanup_exact_pair(self, names): self.hit("cleanup")


class CoordinatorTests(TestCase):
    def test_success_has_fixed_order_and_safe_seal(self):
        ops, source = FakeOps(), FakeSource()
        result = ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
        self.assertEqual(result.phase, "SEALED")
        self.assertEqual(ops.calls, [
            "validate", "create", "created", "prepare", "begin", "public", "private",
            "ledger", "files", "verify", "commit", "readback", "close_source_identity",
            "close_identities", "sealed",
        ])
        self.assertEqual(source.calls, ["preflight", "read_private", "close"])
        self.assertTrue(source.closed)
        self.assertIsNone(result.error_code)
        created, sealed = ops.results
        self.assertEqual((created.phase, sealed.phase), ("CREATED", "SEALED"))
        self.assertIsNone(created.database_digest)
        self.assertIsNone(created.target_media_digest)
        self.assertEqual(sealed.database_digest, DIGEST)
        self.assertEqual(sealed.target_media_digest, MEDIA_DIGEST)
        for saved in (created, sealed):
            self.assertEqual((saved.schema, saved.version), (RESULT_SCHEMA, RESULT_VERSION))
            self.assertEqual(saved.ledger_identity, LEDGER.identity)
            self.assertEqual(saved.ledger_generation, LEDGER.generation)
            self.assertEqual(saved.counts, COUNTS)

    def test_failed_result_has_closed_field_matrix(self):
        ops = FakeOps(fail="files")
        with self.assertRaises(CoordinatorError):
            ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        created, failed = ops.results
        self.assertEqual((created.phase, failed.phase), ("CREATED", "FAILED"))
        self.assertIsNone(failed.database_digest)
        self.assertIsNone(failed.target_media_digest)
        self.assertIsNotNone(failed.error_code)
        self.assertEqual((failed.schema, failed.version), (RESULT_SCHEMA, RESULT_VERSION))
        self.assertEqual(failed.ledger_identity, LEDGER.identity)
        self.assertEqual(failed.counts, COUNTS)

    def test_names_are_generated_only_from_fresh_uuid4(self):
        names = target_names(RUN_ID)
        self.assertEqual(names.database, f"estakada_rebuild_{RUN_ID.hex}")
        self.assertEqual(names.media_key, f"{RUN_ID}/media")
        for bad in (uuid.UUID(int=0), uuid.uuid1()):
            with self.assertRaisesRegex(CoordinatorError, "run-id"):
                target_names(bad)

    def test_every_precommit_failure_rolls_back_and_cleans_exact_pair(self):
        for point in ("prepare", "begin", "public", "private", "ledger", "files", "verify", "commit"):
            ops, source = FakeOps(fail=point), FakeSource()
            with self.assertRaises(CoordinatorError) as caught:
                ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
            self.assertNotIn("secret", str(caught.exception))
            self.assertTrue(source.closed)
            if point != "prepare":
                self.assertIn("rollback", ops.calls)
            self.assertIn("failed", ops.calls)
            self.assertIn("cleanup", ops.calls)
            self.assertNotIn("sealed", ops.calls)

    def test_pre_target_failure_creates_nothing_and_reads_no_private_rows(self):
        ops, source = FakeOps(fail="validate"), FakeSource()
        with self.assertRaises(CoordinatorError):
            ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
        self.assertNotIn("create", ops.calls)
        self.assertNotIn("read_private", source.calls)
        self.assertEqual(ops.results, [])

    def test_every_source_count_drift_blocks_before_target_creation(self):
        for field in ("staff", "grants", "current", "previous"):
            values = {name: getattr(COUNTS, name) for name in COUNTS.__slots__}
            values[field] += 1
            ops = FakeOps(counts=ProjectionCounts(**values))
            with self.subTest(field=field), self.assertRaisesRegex(CoordinatorError, "pretarget-failed"):
                ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
            self.assertNotIn("create", ops.calls)

    def test_invalid_projection_counts_block_before_target_creation(self):
        cases = (
            ProjectionCounts(0, 2, 2, 2, 0, 0, 0, 3, 3, 2, 1, 1),
            ProjectionCounts(1, True, 2, 2, 0, 0, 0, 3, 3, 2, 1, 1),
            ProjectionCounts(1, -1, 2, 2, 0, 0, 0, 3, 3, 2, 1, 1),
        )
        for counts in cases:
            ops = FakeOps(counts=counts)
            with self.subTest(counts=counts), self.assertRaisesRegex(CoordinatorError, "pretarget-failed"):
                ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
            self.assertNotIn("create", ops.calls)

    def test_atomic_create_collision_never_touches_foreign_pair(self):
        ops, source = FakeOps(fail="create"), FakeSource()
        with self.assertRaisesRegex(CoordinatorError, "create-failed"):
            ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
        self.assertTrue(source.closed)
        for forbidden in ("created", "close_identities", "failed", "cleanup_proof", "cleanup"):
            self.assertNotIn(forbidden, ops.calls)

    def test_create_failure_uses_exact_acquisition_status_without_guessing(self):
        acquired = FakeOps(fail="create", acquisition_status="ACQUIRED")
        with self.assertRaisesRegex(CoordinatorError, "create-failed"):
            ImportCoordinator(acquired, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertIn("close_identities", acquired.calls)
        self.assertIn("cleanup_proof", acquired.calls)
        self.assertIn("cleanup", acquired.calls)
        self.assertNotIn("failed", acquired.calls)

        ambiguous = FakeOps(fail="create", acquisition_status="AMBIGUOUS")
        with self.assertRaisesRegex(CoordinatorError, "create-failed"):
            ImportCoordinator(ambiguous, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertNotIn("close_identities", ambiguous.calls)
        self.assertNotIn("cleanup_proof", ambiguous.calls)
        self.assertNotIn("cleanup", ambiguous.calls)

    def test_created_write_ambiguity_isolates_acquired_pair(self):
        ops = FakeOps(fail="created")
        with self.assertRaisesRegex(CoordinatorError, "create-failed"):
            ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertIn("close_identities", ops.calls)
        self.assertNotIn("failed", ops.calls)
        self.assertNotIn("cleanup_proof", ops.calls)

    def test_postcommit_or_readback_failure_is_unsealed_and_cleanup_only_with_proof(self):
        for cleanup in (True, False):
            ops, source = FakeOps(fail="readback", cleanup=cleanup), FakeSource()
            with self.assertRaises(CoordinatorError):
                ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
            self.assertIn("failed", ops.calls)
            self.assertEqual("cleanup" in ops.calls, cleanup)
            self.assertNotIn("sealed", ops.calls)

    def test_seal_write_ambiguity_isolated_without_failed_overwrite_or_cleanup(self):
        ops, source = FakeOps(fail="sealed", seal_status="AMBIGUOUS"), FakeSource()
        with self.assertRaisesRegex(CoordinatorError, "seal-ambiguous"):
            ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
        self.assertIn("seal_status", ops.calls)
        self.assertNotIn("failed", ops.calls)
        self.assertNotIn("cleanup_proof", ops.calls)
        self.assertNotIn("cleanup", ops.calls)

    def test_seal_lost_response_converges_only_from_exact_durable_status(self):
        exact = FakeOps(fail="sealed", seal_status="EXACT")
        result = ImportCoordinator(exact, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertEqual(result.phase, "SEALED")
        self.assertNotIn("failed", exact.calls)

        absent = FakeOps(fail="sealed", seal_status="ABSENT")
        with self.assertRaisesRegex(CoordinatorError, "seal-absent"):
            ImportCoordinator(absent, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertIn("failed", absent.calls)
        self.assertIn("cleanup", absent.calls)

    def test_identity_close_ambiguity_blocks_seal_and_cleanup_without_retry(self):
        for point in ("close_source_identity", "close_identities"):
            ops, source = FakeOps(fail=point), FakeSource()
            with self.assertRaisesRegex(CoordinatorError, "close-identities-failed"):
                ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
            self.assertEqual(ops.calls.count(point), 1)
            self.assertNotIn("sealed", ops.calls)
            self.assertNotIn("cleanup_proof", ops.calls)
            self.assertNotIn("cleanup", ops.calls)

        ops, source = FakeOps(), FakeSource(fail="close")
        with self.assertRaisesRegex(CoordinatorError, "close-identities-failed"):
            ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
        self.assertEqual(source.calls.count("close"), 1)
        self.assertIn("close_source_identity", ops.calls)
        self.assertIn("close_identities", ops.calls)
        self.assertNotIn("failed", ops.calls)
        self.assertNotIn("cleanup_proof", ops.calls)

    def test_failed_result_or_cleanup_ambiguity_never_guesses(self):
        for point in ("failed", "cleanup_proof", "cleanup"):
            ops, source = FakeOps(fail=point), FakeSource(fail="read_private")
            with self.assertRaises(CoordinatorError):
                ImportCoordinator(ops, source, run_id=RUN_ID).run(MANIFEST)
            self.assertNotIn("sealed", ops.calls)

    def test_rollback_ambiguity_isolates_without_failed_or_cleanup(self):
        class RollbackFaultOps(FakeOps):
            def rollback(self):
                self.calls.append("rollback")
                raise RuntimeError("unknown rollback outcome")

        ops = RollbackFaultOps(fail="files")
        with self.assertRaises(CoordinatorError):
            ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertNotIn("failed", ops.calls)
        self.assertNotIn("cleanup_proof", ops.calls)
        self.assertNotIn("cleanup", ops.calls)

    def test_readback_mismatch_blocks_seal(self):
        class DriftOps(FakeOps):
            def readback(self, manifest, names):
                self.hit("readback")
                return ReadbackProof(
                    RESULT_SCHEMA, RESULT_VERSION, COUNTS, DIGEST, "c" * 64,
                    MEDIA_DIGEST, MEDIA_DIGEST, LEDGER.identity, LEDGER.generation,
                    DIGEST, True, True, True,
                )

        ops = DriftOps()
        with self.assertRaisesRegex(CoordinatorError, "readback-mismatch"):
            ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        self.assertNotIn("sealed", ops.calls)
        self.assertIn("cleanup", ops.calls)

    def test_readback_identity_generation_and_source_media_drift_block_seal(self):
        variants = (
            {"source_media_digest": "c" * 64, "target_media_digest": "c" * 64},
            {"ledger_identity": uuid.uuid4()},
            {"ledger_generation": LEDGER.generation + 1},
            {"schema": "other"},
            {"version": 2},
        )
        for changes in variants:
            class DriftOps(FakeOps):
                def readback(self, manifest, names):
                    self.hit("readback")
                    values = {
                        "schema": RESULT_SCHEMA, "version": RESULT_VERSION,
                        "counts": COUNTS, "manifest_digest": DIGEST,
                        "database_digest": DIGEST,
                        "source_media_digest": MEDIA_DIGEST,
                        "target_media_digest": MEDIA_DIGEST,
                        "ledger_identity": LEDGER.identity,
                        "ledger_generation": LEDGER.generation,
                        "ledger_digest": DIGEST, "constraints_ok": True,
                        "counts_ok": True, "usages_ok": True,
                    }
                    values.update(changes)
                    return ReadbackProof(**values)

            ops = DriftOps()
            with self.subTest(changes=changes), self.assertRaisesRegex(CoordinatorError, "readback-mismatch"):
                ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
            self.assertNotIn("sealed", ops.calls)

    def test_coordinator_is_one_shot(self):
        coordinator = ImportCoordinator(FakeOps(), FakeSource(), run_id=RUN_ID)
        coordinator.run(MANIFEST)
        with self.assertRaisesRegex(CoordinatorError, "run-reuse"):
            coordinator.run(MANIFEST)

    def test_invalid_run_id_closes_source_lifecycle_without_target_actions(self):
        for invalid in (uuid.UUID(int=0), "", 0, False):
            ops, source = FakeOps(), FakeSource()
            coordinator = ImportCoordinator(ops, source, run_id=invalid)
            with self.assertRaisesRegex(CoordinatorError, "run-id"):
                coordinator.run(MANIFEST)
            self.assertEqual(source.calls, ["close"])
            self.assertEqual(ops.calls, ["close_source_identity"])

    def test_safe_results_contain_no_private_payload(self):
        ops = FakeOps()
        ImportCoordinator(ops, FakeSource(), run_id=RUN_ID).run(MANIFEST)
        for result in ops.results:
            self.assertIsInstance(result, SafeResult)
            self.assertEqual((result.schema, result.version), (RESULT_SCHEMA, RESULT_VERSION))
            self.assertEqual(result.ledger_identity, LEDGER.identity)
            self.assertEqual(result.counts, COUNTS)
            rendered = repr(result).lower()
            for forbidden in ("username", "password", "phone", "source_key", "secret/private/path"):
                self.assertNotIn(forbidden, rendered)
