# TEST-10A — write-once evidence writer plan

Статус D-1054/D-1055, 2026-11-14: plan/policy independently `APPROVED`, P1=0, P2=0, P3=0; implementation начата и приостановлена владельцу по anti-loop после второго equivalent fail-closed schema mismatch в PS5 StaticTest. Partial writer сохранён, но code stage не принят. Prepare, Foundation, Docker, browser, HTTP, fixture/stand execution и Q003 не разрешены.

## Minimal scope

Добавляются только `acceptance/test10a-evidence-policy.json` и `scripts/test10-evidence-writer.ps1`. Нового сервиса, daemon, database, scheduler, dependency, model, endpoint или product setting нет. Writer работает только в фиксированном ignored root `work/test10/runs/<runId>/evidence`; CLI принимает лишь `StaticTest` либо `WriteManifest` и exact lowercase-hex `RunId`. Произвольные path/body/case/browser flags запрещены.

`WriteManifest` не создаёт run/evidence directories и не запускает preflight. Он требует заранее существующие ordinary/no-reparse `work`, `test10`, `runs`, `<runId>`, `private` и `evidence`, затем читает только fixed `private/manifest-input.json`. До первого write каталог `evidence` обязан быть полностью пуст: exact enumeration `0` файлов и `0` дочерних каталогов. Любой policy basename, `.new`, unknown file/directory или enumeration ambiguity → `BLOCKED` без изменения байтов. Fixture summary до manifest остаётся только в fixed private input/receipt и может быть сохранён отдельным будущим write-once шагом после manifest. Missing/reparse/drift/неполный chain → `BLOCKED` до записи.

## Closed input and manifest

`private/manifest-input.json` — ordinary file, максимум 1 MiB, schema `test10a-manifest-input-v1`, exact properties only:

- `runId`, UTC `createdAt` exact `yyyy-MM-ddTHH:mm:ss.fffZ` (ParseExact/invariant, без нормализации), nonempty `os`, 64-hex `sourceSha256`, pinned `appImage`, 64-hex `fixtureHash`;
- `browser`: exact properties `family=chrome`, absolute canonical `binaryPath`, 64-hex `binarySha256`, numeric `major`, four-part numeric `fullVersion` whose first part equals `major`;
- exact approved `acceptanceCaseIds` and `runScenarioIds` from D-1052;
- exact current file SHA-256 for bindings, payload registry, observer registry and evidence policy;
- `cleanupReceipt`: schema `test10a-cleanup-receipt-v1`, same `runId`, exact `composeProject`, database `{name,oid,owner}`, nonempty exact containers `[{name,id,imageSha256,labelsSha256}]`, network `{name,id,labelsSha256}`, private files `[{relativePath,sha256}]`, `evidenceRootExcluded=true`. Names/IDs/hashes are data to be independently bound later; writer validates shape/uniqueness and never enumerates or deletes resources;
- `previous1=not_run`, `previous2=not_run`.

Password, cookie, session, token, raw response/header/body, contact, personal data and unknown properties are rejected. Writer reconstructs output schema `test10a-chrome-run-v1` in fixed property order; it never copies unknown input properties.

## Write protocol

1. Require exact-empty `evidence` root before opening input; reject every existing file/directory, including all policy basenames, `.new` and unknown names.
2. Recheck full ordinary/no-reparse chain and input size/hash-bound registries immediately before writing.
3. Encode one-line canonical UTF-8 JSON without BOM/trailing newline using a local bounded serializer, not `ConvertTo-Json`. Object properties use the exact documented order; arrays preserve approved order. Strings follow RFC 8259 with `"`, `\\`, `\b`, `\f`, `\n`, `\r`, `\t`; other U+0000–001F become lowercase `\u00xx`; `/` and non-ASCII scalar values remain unescaped UTF-8; lone surrogates are rejected. Booleans are lowercase, null is `null`, integers are invariant base-10 without leading zero; floating/decimal/exponent values are forbidden. Input timestamp bytes are emitted unchanged after exact ParseExact validation.
4. Open `manifest.json.new` with `FileMode.CreateNew`, write all bytes, call `FileStream.Flush(true)`, close, reread bytes and require exact SHA-256/length.
5. Move `.new` to `manifest.json` without overwrite, reread final bytes and require the same SHA-256/length.
6. Build fixed schema `test10a-hash-summary-v1` containing only `runId`, `manifestFile=manifest.json`, `manifestBytes`, `manifestSha256`. Persist it by the same create-new/`Flush(true)`/readback/move protocol as `manifest.sha256.json`.
7. Return only safe status/hash/byte counts. Existing or stale file, partial write, readback mismatch or move ambiguity is `BLOCKED`; writer never deletes or repairs artifacts automatically.

Manifest success with missing hash summary is still `BLOCKED` and may not be retried in the same run root. This is deliberate fail-closed retention, not rollback.

Golden serializer vector is independent of the manifest builder. Exact 90 UTF-8 bytes are `{"ascii":"a/b","control":"line\nquote\"slash\\","integer":42,"unicode":"Эстакада"}` with SHA-256 `cbd5619165f9dce4242e7991344932eca8879a94f4bfae7efd4fb8e904abc110`. StaticTest compares literal expected bytes, length and SHA; it also covers null/booleans, U+0000/U+001F, slash, quote, backslash, non-ASCII, integer0/-1, rejected lone surrogate/float and timestamp exact/malformed variants.

Writer filesystem access is dependency-injected through a closed adapter containing only: enumerate exact root, inspect ordinary/no-reparse chain, read fixed input/registry bytes, open fixed `.new` with `CreateNew`, `Flush(true)`, readback, and move fixed `.new` to absent final. Production adapter exposes no delete, replace, overwrite, recursive operation or process launch. Fault tests use an injected in-memory/temporary adapter and assert call traces contain no delete/replace/overwrite.

Static AST validation starts at `WriteManifest` and follows every reachable local function. Every `CommandAst` must resolve case-sensitively to a function declared in the same script and present in the reviewed production-call allowlist, with one no-bloat exception: exact literal module-qualified `Microsoft.PowerShell.Utility\ConvertFrom-Json` parses the already size-bounded UTF-8 input. No unqualified/other cmdlet, alias, bare executable name, other module-qualified command, dynamic command name, dot-source, call operator or scriptblock invocation is allowed in that graph. The parser result is still checked for exact property sets/types/duplicate-key-safe behavior; canonical output never uses `ConvertTo-Json`. Static golden tests prove the literal qualified command is present and reject unqualified/shadowed/parser alternatives. Test-only entry/functions, including exact-root cleanup, are separately named `StaticTest-*` and excluded from the production allowlist/call graph.

Every reachable static/constructor call is checked against exact type/member pairs: `IO.Path::{GetFullPath,Combine,GetDirectoryName,GetFileName}`, `IO.File::{Open,ReadAllBytes,Move,GetAttributes}`, `IO.Directory::GetFileSystemEntries`, `Text.UTF8Encoding::new`, `Security.Cryptography.SHA256::Create`, `BitConverter::ToString`, `DateTimeOffset::ParseExact`, `String::{Equals,IsNullOrWhiteSpace,Concat}`, `Regex::{IsMatch,Matches}` and closed collection constructors used by validation. `IO.File::GetAttributes` is the only filesystem identity probe: every root/input/output ancestor through the fixed run root is checked and must have neither `FileAttributes.ReparsePoint` nor an unexpected `FileAttributes.Directory` state; missing/error is `BLOCKED`. These two enum flags are data, not additional callable members. Instance calls are allowed only on variables whose provenance is one of those exact constructors/factories, with exact members: `FileStream::{Write,Flush,Dispose}`, `UTF8Encoding::{GetBytes,GetString}`, `SHA256::{ComputeHash,Dispose}`, regex match/group reads and closed collection `{Add,Contains}`; unknown/dynamic provenance or member is rejected. All `Diagnostics.Process`, `ProcessStartInfo`, `Management.Automation` invocation APIs, reflection/delegate activation and every unlisted type/member fail validation. Thus `docker`, `cmd`, `curl`, `Start-Process`, `Invoke-Expression`, `[Diagnostics.Process]::Start` and equivalent launch paths are rejected without relying on a blacklist alone. AST golden tests require `GetAttributes` in the allowlist and reject a substituted `FileInfo`, cmdlet or omitted ancestor probe.

## Offline acceptance scenarios

- `T10W-001`: PS5-compatible StaticTest verifies the independent canonical golden corpus, then writes a valid synthetic manifest into a unique temporary ordinary directory; both files have no BOM/newline, JSON schemas and readback hashes match, `Flush(true)` path is instrumented as reached.
- `T10W-002`: second write to the same root, every policy basename/`.new`, unknown file and unknown child directory returns `BLOCKED` without changing any existing byte; exact-empty inventory is mandatory.
- `T10W-003`: invalid RunId, extra/missing input field, wrong exact9 order, registry hash drift, wrong browser family/version, secret-like key and cleanup receipt mismatch are rejected before artifact creation.
- `T10W-004`: file/directory reparse point in every available chain position is rejected; unsupported platforms may report a bounded skipped reparse subcase but not PASS it silently.
- `T10W-005`: injected short write/readback mismatch/move failure leaves retained evidence and does not overwrite, delete or retry; equivalent second error stops under the project anti-loop rule.
- `T10W-006`: AST/closed-adapter checks prove fixed CLI modes/root/basenames, `CreateNew`, `Flush(true)`, readback SHA, no delete/replace/overwrite/recursive/process primitives, no Docker/browser/HTTP and no arbitrary output parameter.

StaticTest may use only a unique OS temporary directory created by the test. Cleanup is outside the production writer/adapter and occurs only after whole-tree lstat/no-reparse, exact containment and exact-owned inventory equality; mismatch retains the directory and returns `BLOCKED`. The one test-only delete is a single direct exact-root operation after those checks. StaticTest reports `dockerCalled=false`, `browserCalled=false`, `httpCalled=false`. Regression suites remain closed until a later approved runtime stage and, if needed, run only through named `scripts/test-editor.ps1` suites.

## Gates

Сначала independent plan/policy review P1/P2/P3=0. Затем реализация writer + PS5 offline scenarios и отдельный code review. Даже approved writer не открывает Q003: все 40 bindings и 6 observers D-1052 остаются unbound; actual stand/fixture/browser execution требует будущих reviewed implementations и отдельного owner gate.
