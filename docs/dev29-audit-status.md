# P29-A: первый read-only Audit

2026-11-03. Основание D-417–D-419. **Q007/Q008 выполнены: read-only Audit PASS, независимое итоговое ревью APPROVED, стенд остановлен и очищен, том сохранён.** [Актуальные результаты](dev29-readonly-audit-results.md), [независимое ревью](dev29-readonly-audit-review.md). Следующий участок — отдельный конкретный план PG-проверок публикации с fixture/rollback; Run/тестовая запись пока не разрешены. Ниже — история подготовки и прежних блокеров, не текущий статус.

## Что выполнено

Один разрешённый Docker diagnostic: `docker --context desktop-linux info --format '{{.ServerVersion}}'` вернул ошибку отсутствия pipe dockerDesktopLinuxEngine. Процессы Docker Desktop/com.docker.backend не обнаружены. Автоматический запуск Desktop исключён планом; повтор Docker-команды без изменённого условия не выполнялся. Дополнительная попытка прочитать неподтверждённый стандартный путь Desktop.exe дала отсутствие файла; повторов по этому пути не было. Фактический путь установки не установлен, никаких install/repair/изменений системы не выполнялось.

Offline подготовлены signer `audit-authorize.mjs`, read-only observation producer `audit-preflight.mjs` и общая injectable `audit-issue-flow.mjs` с тестами в `work/dev29-publication-20261103/pg-check/`, отдельно от девяти frozen package-файлов. Контроллер/исторические доказательства/продукт не изменялись. Синтаксис PASS; актуальные21 signer/21 preflight synthetic checks,188 issue-flow VM и329 actual Observe-flow VM checks PASS, realKeyReads=0/dockerCalls=0/sqlCalls=0/admissionIssued=false. Это тестовые доказательства, не выпуск настоящей подписи.

Signer имеет только IssueAudit, fixed run и audit-admission destination. Он проверяет закрытый payload, D-417/точный SHA строки решения, принятые signer/code-review SHA, plan/package SHA, свежий подписанный observation receipt с полным DB ID, code/review/sanitized facts/context/engine binding и expiry до15минут. Observation producer допускает только фиксированные read-only Docker-команды и не вызывает SQL или lifecycle. Полные inspect/info дампы не сохраняются: из evidence исключены Env/proxy/registry/system metadata и host mount Source; canary-тест проверяет отсутствие этих значений в сохранённом DTO/receipt. Signer использует только фиксированную offline Verify. Перед ключом — public gates и exclusive audit-signing.lock, затем проверка observation HMAC и повтор входов/forbidden files. Отдельный signed audit-authorization-receipt связывает owner/signer/review/observation/approval/Verify/payload/raw admission; он пишется once до admission. Lock и частичные артефакты остаются для review при ошибке. Старый working permit/ключи/ACL не меняются. Никакие реальные observation/approval/admission сейчас не созданы.

Verify существующего run `1b296fa0-2cff-4dbf-bcb0-623770d7bf85` повторно PASS/runtimeAdmitted=false. Добавление отдельного signer не меняет девять ранее принятых package SHA и source31. Snapshot/runner/архивные proofs сохранены.

## Следующая точка

**Этот исходный порядок выполнен в рамках Q007/Q008.** Актуальная точка — dev29-readonly-audit-results.md, Audit не повторять. Исторические шаги ниже сохранены для provenance; все публичные входы подписанного допуска архивированы.

1. Docker Desktop уже запущен владельцем, engine Linux29.9.2 подтверждён. Existing volume/3 pinned images сохранны по metadata, containers/networks0. Получить ответ Q008 на уточнение восстановления temporary compose ресурсов, затем подготовить/проверить RO-volume inspector перед стартом; до этого ресурсы не создавать.
2. Выполнить диагностический preflight существующих DB/volume/network/images и проверить signer-review перед использованием. Если обнаружено расхождение — не создавать замену и не снимать guard.
3. Выполнить принятый read-only audit-preflight Observe: once facts/подписанный observation receipt с реальными ID/time/SHA; затем подготовить audit-payload.json и audit-signer-approval.json в exact run. Поля approval: scope=PG29-AUDIT-SIGNER-APPROVAL, runId, ownerDecisionId=D-417, ownerDecisionSha256, signerSha256, signerReviewSha256, observationSha256. Observation внутри аутентифицированного receipt имеет scope=PG29-READONLY-DOCKER-PREFLIGHT, runId, dbContainerId, observedUtc, preflightPassed=true только после actual inspect predicates. Signer повторяет predicates над raw facts и проверяет HMAC/producer SHA перед выдачей допуска.
4. Независимо сверить эти факты, затем один IssueAudit и один controller Audit в границах Q007. До этого никаких действительных admission/signature/attempt/locks не создавать.
5. Независимое result-review baseline/сохранности/cleanup/Stop. Run/fixture writes по-прежнему требуют отдельного разрешения и фактического budget report.

| RA29 | Состояние |
|---|---|
| 001 | PASS: exact latest source/package/protected SHA/Verify до и после, historical inputs архивированы |
| 002 | PASS: RO volume inspector, VerifyStart, DB-only restore по Q008, exact IDs/caps/internal network/pinned image |
| 003 | PASS: reviewed actual signed observation/payload, один audit-only IssueAudit с provenance receipt |
| 004 | PASS: единственный read-only Audit, fresh MAIN/UNIT/schema/archive catalog, никакой fixture записи |
| 005 | PASS: независимое result-review, exact own cleanup0containers/0networks/volume retained/workingpermit{} |

Текущий этап8 около31%, DEV-29 около35%. Product publication/APP/cohort/EDGE не объявляются готовыми. Старый сайт/VPS не затронуты.
