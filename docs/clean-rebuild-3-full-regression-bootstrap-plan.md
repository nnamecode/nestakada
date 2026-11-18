# RB3 full synthetic regression bootstrap plan

Status: completed by D-1498; run6 PASS168/168 and independently ACCEPTED. The bootstrap remains a synthetic-test boundary, not authorization for DB/capture/import/rebuild runtime.

## Purpose and boundary

This plan fixes only the synthetic regression harness proven incomplete by run2/run3. It does not change production importer code, package readers, Django settings, images, dependencies, databases, media, zero-ledger instances or rebuild state.

The existing `app-editor:candidate-d330` image supplies pinned Python dependencies, not application source. The current host `app` is therefore mounted read-only at its normal `/app` path. Current importer code, zero-ledger module and evidence docs remain narrow read-only mounts under `/review`. Import precedence is exactly `/review/src:/app`.

No persistent bootstrap script is added. One inline Python preamble runs in the same process as `unittest` and exists only for that invocation.

## Synthetic Django bootstrap

The container receives a second tmpfs at `/run/secrets`, owned by UID/GID 10001 and mode0700. The inline preamble:

1. creates exactly `/run/secrets/database-password` and `/run/secrets/django-secret` with `O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC`, mode0600 and fixed ASCII synthetic values of at least 32 bytes; each value is written exactly and closed once, then the named entry is reopened no-follow and `fstat` must prove regular file, UID/GID10001, mode0600 and exact byte size before settings import; any existing entry or mismatch fails closed;
2. sets only the isolated test environment: `DJANGO_SETTINGS_MODULE=estakada.settings.local_http`, `ESTAKADA_LOCAL_ENV=test`, `ESTAKADA_DB_NAME=estakada_foundation_unit`, `ESTAKADA_DB_USER=app_migrator`, and the two exact credential-file variables;
3. calls `django.setup()` before importing the regression modules;
4. loads exactly these 12 test modules with `unittest.defaultTestLoader`: `rebuild3_importer.tests.test_content`, `test_coordinator`, `test_freeze_authority`, `test_freeze`, `test_manifest`, `test_media_authority`, `test_payload_transform`, `test_run`, `test_runtime_source`, `test_runtime_target`, `test_source`, `test_zero_ledger_authority`; the fully qualified `rebuild3_importer.tests.` prefix applies to every abbreviated name; `suite.countTestCases()` must equal166 before execution, and process exit is nonzero unless the complete suite succeeds.

The database endpoint remains the settings default `db:5432`, but `--network none` makes it unreachable. The tested literal package readers only read SHA-pinned files beside their modules; no writer/apply function is invoked. A missing bootstrap prerequisite must fail before the suite, not weaken settings.

## Container boundary

- existing image only; pull/build/install forbidden;
- `--network none`, root filesystem read-only, UID/GID10001, all capabilities dropped and `no-new-privileges`;
- `/tmp` and `/run/secrets` are the only writable tmpfs mounts;
- interpreter is invoked as `python3 -B`; `PYTHONDONTWRITEBYTECODE=1` is also explicit in the container environment;
- host `app` read-only to `/app`;
- host `src/rebuild3_importer` read-only to `/review/src/rebuild3_importer`;
- host `src/rebuild3_zero_ledger.py` read-only to `/review/src/rebuild3_zero_ledger.py`;
- host `docs` read-only to `/review/docs`;
- no project, database, Docker volume or host-secret writes;
- no retry or second run under the same permission.

## Acceptance scenarios

- `RB3-RUN4-BOOT-001`: import resolution selects current `/review/src/rebuild3_importer`, current zero-ledger module and host `/app/content`; no module is loaded from an unintended image copy.
- `RB3-RUN4-BOOT-002`: media authority resolves exactly `/review/docs/analytics-media-evidence.csv` and keeps its pinned digest/count checks.
- `RB3-RUN4-BOOT-003`: both synthetic credential files are created only in `/run/secrets` tmpfs with writable exclusive no-follow/close-on-exec creation and mode0600; exact write+single close is followed by no-follow reopen and regular/UID/GID/mode/size proof before settings import; existing entries or mismatch cause fail-closed startup.
- `RB3-RUN4-BOOT-004`: Django uses only the isolated `test` profile and completes `django.setup()` without a database connection.
- `RB3-RUN4-BOOT-005`: network is none and no tested path invokes a real database, subprocess, package install, image build or persistent write.
- `RB3-RUN4-BOOT-006`: the exact 12 named modules are loaded once; execution is refused unless the suite contains exactly166 cases, and success requires every case to pass with any load error producing nonzero exit.
- `RB3-RUN4-BOOT-007`: production importer, package readers, Django settings and dependencies remain byte-for-byte unchanged by the bootstrap stage.
- `RB3-RUN4-BOOT-008`: run4 remains separately owner-authorized after independent plan review; this plan and review do not authorize execution.

## Bloat control

The light option is one reviewed inline preamble and existing mounts. A new settings module, launcher file, image, dependency, pure-reader subsystem, database service or test framework is explicitly out of scope. If inline bootstrap cannot satisfy the acceptance scenarios, stop and return to the owner rather than adding infrastructure.

## D-1493 successor-count amendment

The authorized run4 correctly used the reviewed exact166 guard. D-1491 then added exactly one new test method, `test_empty_legacy_main_uses_only_exact_page_name_for_target_h1`, inside the same approved 12-module set. A future run5 must therefore keep the same module list and bootstrap boundary but require `suite.countTestCases() == 167` before execution. No other discovery or scope change is permitted.

## D-1496 second successor-count amendment

The authorized run5 correctly used the reviewed exact167 guard. D-1495 adds exactly one further discoverable focused method for home media coverage. The same 12-module future run6 suite must therefore refuse execution unless `suite.countTestCases() == 168`. Historical run4 exact166 and run5 exact167 remain correct; no module or bootstrap boundary changes.
