# DEV-29: контроллер изолированных PostgreSQL-проверок

Обновление D-439 (2026-11-04): описанный ниже package/Prepare сохранён, но его единственный Run уже завершился **FAIL/PREFLIGHT/HOST_DOCKER до create/SQL**. [Фактический результат и независимое ревью](dev29-bounded-runtime-results.md); [предложение нового root run DEV29-Q016](dev29-bounded-runtime-resume.md). Старый Run не повторять; нижняя точка продолжения относится к состоянию до этой попытки. Архив code-review в prepared inputs не менялся.

2026-11-04. BOUND29-REAL-HOST-001, действующее разрешение Q014/D-434. **BOUND29-REAL-CODE-REVIEW APPROVED** для текущего frozen source package. Независимый рецензент `/root/dev29_publication_review` подтвердил exact manifest, закрыл REV001–012 и самостоятельно получил 17/17 offline host PASS; оставшихся P0/P1 нет. Разрешена фиксация code gate и отдельно проверяемый Prepare. **Runtime INIT/C/T NOT_ADMITTED/NOT_RUN.** Это не доказательство фактического PostgreSQL/SQL, сохранности оригинального тома, real1000 или actual139.

Основания: [согласованный Q014](dev29-bounded-sandbox-proposal.md), [принятый inert QA Q015](dev29-bounded-qa-result-review.md), [ограниченное ревью real helpers](dev29-bounded-real-code-review.md). Старые source31, runner, QA-пакеты и сохранённый корпус не изменяются. Старый сайт/VPS/production/push вне работы.

## Пакет и фактические проверки

Ignored пакет: `work/dev29-bounded-20261103/real-host/`. `controller.packageFiles()` включает 28 файлов: десять новых host/audit inputs, двенадцать ранее проверенных real helper inputs и шесть фиксированных зависимостей из прежних пакетов. Canonical manifest SHA256 текущего checkpoint, независимо пересчитанный рецензентом: `c80072e83a98c25b6606b0c3ea332987b65d2f46e1f27526d12d74391048c6b9`. Source зафиксирован. Старый checkpoint `4ed709…` не одобрен после исправлений REV009/010; одобрение `a53d8a…` отозвано после REV011/012; `3bd273…` имел открытый REV012. Старое approval не переносилось на новый код.

- Node: синтаксис controller/flow/spec PASS; 17 автономных host tests PASS у координатора и независимого рецензента, failures/skips0.
- Python: auditor 12/12, HBA matrix 8/8 PASS; AST всех пяти host Python-файлов PASS. Тесты используют synthetic injected IO: фактические подключения/SQL/чтения секретов — 0.
- Прежние 24 offline real-helper tests остаются отдельным ранее проверенным результатом; в этом checkpoint повторно не запускались.
- Source31 fingerprint подтверждён: `1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`.
- До Prepare оба новых namespace отсутствовали. После отдельного PREPARE-GATE APPROVED выполнен ровно один штатный Prepare: exit0/PREPARED, пакет c80072…; созданы новый public plan и шесть private inputs с унаследованной owner/SYSTEM ACL, без изменения ACL. Run/phase admissions/attempts/Docker/PostgreSQL не выполнялись; свежая Docker inventory не заявляется.

Prepared plan raw SHA256: `779285dfa6e644257ebb52157751ce7842661a736f2480fbb15c3812ce82256c`, createdUTC `2026-11-03T21:37:05.460Z` (4 ноября по Москве). Координатор отдельно подтвердил HMAC, scope/package binding, метаданные шести private files и пустые attempts/reviews. Секретные значения не выводились. **PREPARED-RESULT APPROVED**: независимый рецензент проверил exact public envelope/scope/run/manifest и proposal/review-copy/owner-copy hashes, шесть private имён и stat metadata без extras, унаследованную owner/SYSTEM-only ACL без изменения правил, пустые attempts/reviews и отсутствие admission/attempt/complete/result/run.lock. Независимая HMAC-проверка не заявляется: рецензент ключ не читал и отдельно учитывает witness координатора. Это только приёмка Prepare, не runtime approval.

## Замечания первого независимого ревью

| ID | Приоритет | Исправление, принятое повторным независимым ревью |
|---|---|---|
| BOUND29-HOST-REV-001 | P1 | START включает точный INIT template и закрытое правило получения actual OID/system ID; материализация проверяется побайтно по canonical JSON. C/T payload templates проверяются независимо до fresh once admission, затем разрешены только заранее названные подстановки. |
| BOUND29-HOST-REV-002 | P1 | Закрытый review artifact с независимым reviewer, run/package/source/result/status; архив содержимого, проверка до key read и повторная проверка при принятии подписанного ответа. Пустой/посторонний/self approval отклоняется тестами. |
| BOUND29-HOST-REV-003 | P1 | Engine ID, полные inspect, exact cleanup/absence queries и raw responses, отдельное network evidence и финальные raw inventories связываются подписанными receipts. |
| BOUND29-HOST-REV-004 | P1 | Plan фиксирует SHA256, размер, regular type и nlink всех новых private inputs, включая host-key; до key read и каждого dispatch проверяется отсутствие drift. Содержимое секретов не выводится. |
| BOUND29-HOST-REV-005 | P1 | Signed helper evidence связывает full ID/nonce/input/raw/inspect/cleanup; parsed results и итоговый evidence ledger ссылаются на SHA квитанций. DB-ready/final-stream и original raw также связаны с подписями. |
| BOUND29-HOST-REV-006 | P0 | Оба original RO inspector требуют `volume-nocopy`; gate проверяет HostConfig.Mounts/NoCopy до start. Missing/false NoCopy отвергается негативным тестом. |
| BOUND29-HOST-REV-007 | P1 | Review C/T template перенесено до once admission; stricter remaining C850/T490 секунд при прежнем TTL≤900, без renewal/retry. Резерв: worker620/260 + два audit90 +50 секунд. Каждый audit имеет общий host deadline90 с ограничением subprocess timeout оставшимся временем. |
| BOUND29-HOST-REV-008 | P1 | UNIT и MAIN witnesses выполняются последовательно в отдельных try, каждый не более одного раза даже при ошибке первого. Ошибка worker не пропускает эти попытки; ошибка/expiry/cancel/drift даёт UNPROVEN, а не заявление сохранности. |
| BOUND29-HOST-REV-009 | P1 | Свежий engine gate перед mutations/dispatch/cleanup и после inventories; несовпадение exact ID/local npipe/Linux означает FAIL, а не подпись пустого inventory нового daemon со старым ID. Добавлены негативы смены engine перед create/cleanup/terminal. |
| BOUND29-HOST-REV-010 | P1 | Terminal stage идёт после original-after: bounded cleanup только новых owned IDs, которые ещё не обрабатывались, затем fresh engine/raw global containers+networks inventory. Уже обработанные DB/network/cleanup не повторяются; оставшаяся неопределённость даёт UNPROVEN. Негатив orphan после инспектора запрещает cleanupProved. |
| BOUND29-HOST-REV-011 | P1 | CLOSED: единый host deadline C620/T260/audit90 начинается до engine/create и включает post-inspect/cleanup. Последние30 секунд отведены cleanup заранее; рабочий срок C590/T230/audit60 строже разрешённых максимумов. Captures и subprocess timeouts ограничены оставшимся рабочим сроком. |
| BOUND29-HOST-REV-012 | P1 | CLOSED: cleanupMutation передаёт one-shot mark callback в rawDocker; rawDocker проверяет deadline/timeout, затем вызывает callback непосредственно перед spawnSync. Engine/pre-dispatch expiry оставляет actual-attempt=false; dispatch/spawn failure ставит true и запрещает retry. Закрытый cleanup interval использует ранее выданный deadline, не renewal. |

Дополнительная узкая проверка `/root/pg29_probe_builder` не нашла прямого FAIL C → T или общего PASS без cleanup/original proof; подтвердила пробелы review/payload и after-failure evidence. После FAIL T схема/миграции/пустота UNIT сравниваются с baseline; изменённая схема не получает preservation PASS. Реальный adapter ещё не квалифицирован автономными fake-IO тестами как выполненный Docker/PostgreSQL-процесс.

## Точка продолжения

Code gate пройден для exact c80072…; один Prepare принят независимым PREPARED-RESULT APPROVED. Далее — отдельный runtime/preflight review, свежий local preflight, original RO-before и start/payload/result gates Q014, последовательные INIT → C → T и обязательный Stop/RO-after/terminal inventory. Новый ответ владельца для уже разрешённого Q014 не требуется; технические gates остаются обязательными. DEV-29 около35%, этап8 «Разработка сайта» около31%; P29-A открыт. Следующий общий этап после завершения этапа8 — этап9 «Unit-тесты».
