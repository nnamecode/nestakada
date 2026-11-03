# DEV-29: новая копия Q016 — код и независимое ревью

Обновление D-441 (2026-11-04): ниже история code/Prepare gates; один допущенный Run уже выполнен и завершился [ранним FAIL с двумя Docker-list timeout](dev29-bounded-resume-results.md). **R016 приостановлен владельцу, старый Run не повторять.** [Q017](dev29-docker-diagnostic-resume.md) пока только proposal отдельной read-only диагностики. Archived review в prepared inputs и сам package594e… не менялись.

2026-11-04. **BOUND29-RESUME-CODE-REVIEW APPROVED / R016-CODE-REVIEW-002** для exact checkpoint594e3320… . Независимый рецензент `/root/dev29_publication_review` пересчитал manifest, проверил delta и самостоятельно получил42/42 Node PASS, failures/skips0; подтверждённые REV003–005 закрыты, оставшихся блокеров нет. Это code/offline approval, не Prepare/Run/SQL authority. Владелец разрешил Q016 решением D-440; [core proposal](dev29-bounded-runtime-resume.md) rawSHA `3de6c955fa6436720b04ae3f09fbf78e03aaa966eb46a9b8a08121de07725e63`, [независимое proposal review](dev29-bounded-runtime-resume-review.md).

## Снимок

Новый ignored source namespace `work/dev29-bounded-20261104-resume001/`, root `7a0fbaff-d7de-4376-be5a-0cca5f04760e`. `controller.packageFiles()` включает36 inputs, canonical manifest SHA256 текущего checkpoint `594e33205f32ef2bc416aed37e5e9452eb180af37b20615b917cda0988ee4b84`. Source зафиксирован до повторного заключения рецензента. Первый checkpoint873214… получил подтверждённые REV003/004/005, исправленные координатором; предварительные REV001/002 сняты рецензентом как false positives по фактическому коду, source по ним не исправлялся. Новый private namespace/keys/Prepare/phase attempts/Run/Docker/SQL не создавались/не выполнялись. Старый пакет c80072… и prepared plan779285… сохранены; старый FAIL не заменён результатом новой копии.

## Изменения

Координатор скопировал28 исходных inputs без секретов/старых runtime artifacts; разрешённые root/prefix/private target/authority substitutions, D-440/Q016 и ancestry guards вместо старого D-434. Retained roots берутся из всего старого prepared plan, добавлены полный старый public пакет и новый пакет; новый private входит в прежний retained parent, nested roots не считаются дважды.

Двенадцать real helper/bootstrap inputs сохраняют control flow. Новые DB markers требуют нового SQL digest pin. Дополнительные4 старых QA fixtures скопированы побайтно; bootstrap qualification разрешает только прежний SQL-pin delta и literal oldRUN→newRUN в supervisor. Оба HBA остаются побайтно прежними. Это source/mock-equivalence, не фактический Linux/PostgreSQL PASS.

`failure-trace.mjs` и его tests подготовил `/root/pg29_probe_builder`; координатор их не редактировал. Pure module формирует закрытый safeArgv/payload, output stats и enum summary, не имеет filesystem/process/key/SQL IO. По integration finding добавлен exact64hex network absence filter; arbitrary/other-root filters запрещены.

Координатор реализовал `failure-host.mjs`/tests и подключил те же проверяемые функции в production sync Docker calls и async attach collector. Native responses хешируются как реальные bytes, включая некорректный UTF8; stdout/stderr text не копируется в trace. Контекст фиксируется при dispatch, callNo не сбрасывается; observed engine имеет номер фактически проверенного info call, expected не выдаётся за observed. Envelope подписывается отдельно, без лишних полей общей receipt wrapper; cap8KiB и общий32MiB сохраняются. Persistent DB attach имеет timeoutMs=0 (нет отдельного CLI-lifetime timeout), при этом READY ограничен90с, последующее существование — прежними phase/Stop deadlines; это не увеличение времени SQL worker.

Trace-storage failure отмечает diagnosticUnproven и блокирует новые фазы/SQL. Latch запрещает повторные sign/write даже при следующем отдельном cleanup Docker failure. Для каждого call заранее фиксируется конечный storage deadline из исходного work/per-call budget;1с внутри него выделена записи trace, native/wait limit строже на1с. Cleanup30 не расходуется на work trace. Async DB attach имеет фиксированный первоначальный storage ceiling: поздний exit за этим окном даёт diagnosticUnproven/FAIL, не renewal. Ошибка safety-evidence storage не прерывает уже разрешённое exact owned cleanup; отсутствие подписанного terminal proof остаётся UNPROVEN/FAIL. Final commit требует non-null receipt и неизменных flags: отказ result write даёт FAIL/RESUME_RESULT_UNPROVEN/resultPersisted=false без повторной записи. Async stdin error обрабатывается как контролируемый FAIL, не unhandled process exit. Старые source31/runner/продуктовые tests не меняются.

## Проверки

| Проверка новой копии | Факт |
|---|---|
| trace module |10 PASS |
| реальный sync/archive adapter, async collector и final commit с injected effects |14 PASS |
| host guards/flow/retained roots |18 PASS |
| shared helper/initializer/suite guards |13 PASS, actual139=false |
| capacity offline |6 PASS |
| bootstrap metadata-only equivalence |5 PASS |
| readonly auditor |12 PASS |
| HBA matrix |8 PASS |

Всего86 offline/readonly-metadata tests PASS:42 Node в текущем checkpoint и44 Python в неизменённых inputs предыдущего шага. После исправлений logger повторены только затронутые Node suites; повторять неизменённые Python suites без причины не стали. Native syntax controller/trace/host adapter PASS. SQL/подключения/Docker/new-secret reads в этих тестах0; host retained-root test читает только известные ancestor metadata, не private secret contents. Зависимые проверки запускались последовательно только после успеха предыдущей. Это не runtime qualification.

## Продолжение

Code gate принят для exact manifest594e3320… . После отдельного R016-PREPARE-GATE APPROVED выполнен ровно один Prepare, exit0/PREPARED. **R016-PREPARED-RESULT APPROVED**: public plan rawSHA `2f369a4949659851bc91b572d1b3a92de4723d5141c9815457bbea9cc6e43768`, payloadSHA `e10f7727ead1a21faa998714d85c02e47092fee72198ed3e745e65d5b39568d9`; independently checked36 package inputs, owner/review/ancestry bindings, все27 retained roots, exact6 private names/stat/ACL, attempts/reviews0. Ключ рецензент не читал, независимая HMAC-проверка не заявляется.

Первоначальная ручная команда координатора для key+private-content pins была отклонена автоматической проверкой разрешений и не выполнилась. После проверки публичного D-440 и разграничения ролей auto-review разрешил более узкий witness: только32-byte нового host-key в памяти для HMAC, прочие5 private values не читались, stat6 проверены. Coordinator HMAC VERIFIED для exact plan2f369…; это отдельно от independent metadata review. ACL не изменялись. Штатный Run имеет собственную проверку HMAC/private hashes до Docker; он ещё не вызывался.

Далее отдельный dispatch review и только после всех gates — один новый Q016 Run. Старый root не повторять. DEV-29 около35%, этап8 «Разработка сайта» около31%; P29-A открыт, общий этап9 следует после завершения этапа8.
