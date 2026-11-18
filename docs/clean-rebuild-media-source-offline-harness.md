# REBUILD-1 media source offline orchestration harness

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-SOURCE-OFFLINE-HARNESS-001`.

Статус: **FROZEN D-1405; owner chose defer-to-migration-freeze; no new diagnostics or runs**.

## Решение владельца и цель

После четырёх pre-media orchestration incidents владелец выбрал option1: один bounded offline harness вместо новых Docker runtime attempts. Harness должен выявлять PowerShell/Docker-inspect normalization и cleanup state-machine regressions до owner-gated runtime.

## Минимальная архитектура

Добавляется ровно один focused PowerShell test-файл `tools/test-rebuild-media-source-offline.ps1`. Новая production module/library/dependency/service/image/config/manifest отсутствует. `tools/rebuild-dbpre.ps1` не получает test mode и не dot-source test code.

Harness:

1. читает только bytes текущего `tools/rebuild-dbpre.ps1`, проверяет regular/non-reparse file и bounded size;
2. PowerShell AST parser обязан дать errors0;
3. находит exact unique function definitions `Test-ExactVerifierIdentity` и `Test-ExactVerifierCleanupIdentity`, а также exact relevant catch block/function `Invoke-MediaVerifier`; missing/duplicate definitions fail;
4. создаёт isolated in-memory ScriptBlock только из exact extracted reviewed function text плюс минимальные literal globals и fail-closed in-memory fakes/spies для `Invoke-Docker`, `Assert-ExactPrivateAcl`, `Assert-DbOnlyScope`, `Assert-ExactCidFile`, `Get-Command`, `Invoke-BoundedProcess`, `Test-Path` и `Remove-Item`; production function text/state algorithm вручную не копируется;
5. fake Docker возвращает только synthetic inspect JSON/objects и synthetic bounded ps results. Spies записывают bounded call intent только в память и fail на любом неожиданном command/argument/order; fake `Remove-Item` ничего не удаляет, а записывает exact requested literal path. External process, Docker API/named pipe, filesystem mutation, network, DB, verifier, media и repo writes0;
6. harness печатает только one bounded aggregate PASS envelope либо constant FAIL code plus one exact allowlisted non-sensitive case identifier; fake IDs/names are fixed non-sensitive test values. Raw exception/source/inspect/path/ID output0.

Harness не является общим mocking framework. Он не тестирует PostgreSQL/SQL/media hashing, не обещает Docker daemon compatibility и не разрешает новый runtime. Его граница — deterministic host orchestration semantics, уже вызвавшие RUN001–004.

## Acceptance scenarios

- `RB1-MSRC-OFF-AC-001`: runner regular/non-reparse/bounded, AST errors0, required function definitions unique; no external invocation tokens in harness except static source checks.
- `AC-002`: full start predicate принимает exact synthetic config с Docker `CapAdd=null`; отклоняет nonempty CapAdd и drift каждого reviewed security field, включая full ID/name/label/image, network/root/log/user/resources/caps/security/entrypoint/full argv/mount/tmpfs.
- `AC-003`: narrow cleanup predicate принимает exact ID/name/label/image despite unrelated start-config drift; отклоняет mismatch каждого из четырёх identity fields and inspect count≠1.
- `AC-004`: behavioral in-memory execution exact extracted production `Invoke-MediaVerifier` proves: valid parsed cid + known pre-start full-config failure uses narrow identity, exact removal/absence, repeated cid validation/delete and original phase rethrow; invalid cid never auto-removes; post-start ambiguity reaches `UNKNOWN_ISOLATED` before narrow cleanup. AST-only pattern matching is not accepted for these behavioral claims.
- `AC-005`: full64-sensitive `docker ps` calls use `--no-trunc`; clean zero-result array remains real empty array under StrictMode; nullable CapAdd normalization remains true-empty.
- `AC-006`: output contains only contract/status/case counts/elapsed, constant failure code and on FAIL one exact allowlisted non-sensitive case identifier; source/function/inspect raw text, paths, IDs and exception details0.
- `AC-007`: harness self-check proves every boundary call was intercepted by the explicit fake allowlist, unexpected calls0, and it did not resolve/invoke `docker.exe`, start process, access environment secrets, or write/delete files. One run, retry0.
- `AC-008`: no-bloat — exactly one new test file; one separately recorded production correction is allowed only because source-backed review proved missing `MemorySwap=128m` inspect equality for an already-created resource limit. Other production changes0; no Pester/module/dependency/mock framework/snapshot/golden file.

## Gate sequence

1. independent architecture/acceptance review;
2. owner-selected contract being approved permits implementation of the one offline file only under D-1363 microstage flow;
3. static/parser review of implementation;
4. one offline harness execution only after code review approval; because it has Docker/DB/media/process0, this is not a runtime gate;
5. result review; any future Docker media-source run remains separately owner-gated and is not automatically restored by harness PASS.

При обнаружении, что source-backed state-machine checks требуют production refactor/module или duplicate implementation, work stops for owner choice rather than expanding scope.
