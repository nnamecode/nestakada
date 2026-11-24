# R7-CUTOVER-PLAN-001 — local cutover и rollback до REBUILD-Q003

Статус: source-only plan approved 23 ноября 2026 года. Первое independent architecture/data/destructive/concurrency review: `CHANGES_REQUIRED P0=0/P1=3/P2=0`; исправлены exact generation binding, mutation fence и selector/reload atomicity claim. Repeat review: `APPROVED P0=0/P1=0/P2=0`. Документ не разрешает Docker/runtime, чтение media, migration freeze, transfer, изменение current pointer/Nginx, local cutover, rollback, external copy, production/live или destructive cleanup. `R7-LOCAL-001` закрыт `PASS`, но сам по себе не делает проект готовым к `REBUILD-Q003`.

## 1. Цель и честная граница

Нужно заранее определить один проверяемый путь локального выбора нового runtime и возврата на старый без преобразования или удаления старых DB/media. До фактического Q003 выполняется отдельный isolated rehearsal, который использует реальные Docker/Nginx primitives, но не меняет текущий local target.

План не заменяет:

- fresh coherent migration freeze и exact `SEALED` DB+media pair по `TRANSFER-AC-001..014`;
- полную REBUILD-7 acceptance;
- verified restore-check из фактической encrypted external copy по `BACKUP-AC-010`;
- отдельное разрешение владельца `REBUILD-Q003`;
- production deploy, DNS/TLS, FirstVDS, live traffic или `REBUILD-Q004`.

## 2. Состояние допуска

| Gate | Текущее evidence | Статус для Q003 |
|---|---|---|
| Локальный backup/restore нового runtime | `R7-LOCAL-001`: generation-v5, `R7L-AC-001..007 PASS`, final review `0/0/0` | Закрыт только локально |
| Fresh migration candidate | Реальный import/transfer остаётся B002-blocked; exact fresh `SEALED` pair из текущего freeze отсутствует | BLOCKED |
| Old rollback authority | `R7C-INV-001` зафиксировал topology/bitmap, но current durable selector отсутствует и exact old rollback target не назначен | OPEN/BLOCKED |
| Full local acceptance | Public exact115/responsive закрыты; оставшиеся runtime/concurrency/quality branches должны быть закрыты либо явно superseded reviewed evidence | OPEN |
| External restore | Restore из фактической encrypted external copy не выполнялся | BLOCKED |
| Rollback rehearsal | Изолированное реальное switch→new→rollback→old не выполнялось | OPEN |
| `REBUILD-Q003` | Отдельного разрешения local cutover нет | CLOSED |

Любой `BLOCKED|OPEN|UNKNOWN` запрещает запрос Q003. Boolean «готово» без ссылок на exact evidence не допускается.

## 3. Authority и неизменяемые правила

1. **Новый кандидат:** только exact fresh `SEALED` pair из одного coherent freeze. Matching manifest/ledger/read-back обязательны. Один generation ID/digest связывает seal, local+encrypted external copies, external restore-check, rehearsal, readiness packet и Q003 cutover. Если старые writers после seal снова открывались, candidate и packet stale; нужен новый freeze/run и новый evidence chain.
2. **Старый rollback target:** exact runtime image/config-name inventory, DB identity и media root фиксируются до rehearsal/cutover. На всё rollback window они сохраняются без migration, rewrite, cleanup или reuse.
3. **Current selector:** до реализации read-only topology inventory обязан назвать durable selector generation/config digest, CAS precondition/token, отдельно observed serving target и независимый fail-closed ingress primitive. Atomicity допускается заявлять только для durable file/pointer CAS. Config validation, ingress stop/start и observed-target verification — отдельные неатомарные фазы. Новый routing/controller service запрещён.
4. **Один координатор:** project-owned wrapper держит exclusive host lock до конца cleanup и пишет safe receipt только после exact postconditions.
5. **Нет общего DB/filesystem ACID claim:** безопасность обеспечивают sealed immutable pair, fail-closed selector CAS и сохранённый old target.
6. **Request intake:** остаётся default-off. Cutover/rehearsal не может включить request POST, Telegram, scheduler или cleanup.
7. **Никаких удалений:** old runtime/DB/media, backup generation, manifests и rollback evidence не удаляются. `REBUILD-Q004` отдельно.
8. **Mutation fence:** с начала coherent freeze и на всё rollback-capable local window old и new target не принимают admin/editor/upload/request/scheduler/cleanup mutations. Writes открываются только отдельным будущим решением, когда rollback без переноса данных больше не заявляется либо утверждён отдельный data-divergence/reconciliation contract. Failure/unknown всегда оставляет оба write bitmap closed.

## 4. Пакеты работы

### `R7C-INV-001` — read-only topology inventory

Отдельный runtime/media-read gate обязателен до выполнения. Inventory без секретов фиксирует:

- exact container/project/service names, IDs, immutable image digests, networks и running/stopped bitmap;
- current local ingress selector и его canonical config digest;
- old/new DB names/owners и media roots только как safe tokens/digests, без credentials/absolute paths в отчёте;
- host bindings/ports и отсутствие production/live target;
- closed write-path bitmap: admin/editor/upload/request POST/scheduler/cleanup;
- exact rollback target и доказательство, что он не совпадает с disposable/staging target.

Inventory ничего не стартует, не останавливает и не переключает. Unknown selector/topology блокирует дальнейший пакет.

### `R7C-FREEZE-001` — exact generation chain до rehearsal

Каждое runtime/external действие требует своего отдельного разрешения. Один непрерывный evidence chain:

1. Закрывает old mutations, ждёт writer inventory zero и фиксирует exact old write bitmap.
2. Создаёт один fresh coherent transfer run и exact `SEALED` generation ID/digest.
3. Не открывая old writers, создаёт local и encrypted external immutable copies **этого же** generation/digest и проверяет read-back.
4. Выполняет full restore-check из external copy именно этого generation/digest.
5. Передаёт тот же generation/digest в rehearsal и readiness packet.

Если old writers открылись, generation/restore/rehearsal evidence сразу stale; Q003 packet не выпускается. Q003 wrapper не создаёт другой candidate и не выполняет external copy скрыто. Если владелец не продолжает cutover, old writers можно открыть только с явной фиксацией invalidation; следующий цикл начинается с нового freeze.

### `R7C-REHEARSAL-001` — isolated local switch/rollback rehearsal

Требует отдельного bounded Docker/PostgreSQL/Nginx разрешения. Rehearsal использует disposable ingress selector/network namespace, который не является current local target и не имеет production/live route.

Порядок:

1. Проверить exact inventory digest, exclusive lock, temp-resource zero и pre-run bitmap.
2. Доказать old rollback target readable/healthy в isolated path без mutation.
3. Доказать new candidate exact `SEALED`, generation/digest совпадает с local+external copies и external restore receipt; old writers после seal не открывались. Stale/unsealed/mismatched candidate отказывает до switch.
4. Поднять old и new targets только с mutation paths closed, без host public port; durable selector disposable ingress сначала указывает на old и имеет exact generation token.
5. Выполнить реальные readiness/HTTP observations old; подготовить new config и проверить его до commit; identity-check и остановить disposable ingress; atomic CAS только durable selector old-generation→new-generation; стартовать ingress и отдельно доказать observed serving target=new.
6. На new доказать exact115, private denial, request POST absent, cookie/cache/canonical rules и отсутствие outbound attempts.
7. Ввести один reviewed failure после new selection; оставить оба write bitmap closed; identity-check и остановить ingress; atomic CAS только durable selector new-generation→old-generation; стартовать ingress и отдельно доказать observed serving target=old, readiness/HTTP без DB/media transform.
8. Повторно выбрать new только если контракт rehearsal явно требует positive final state; иначе selector остаётся old. Current local selector никогда не меняется.
9. В `finally` удалить только exact disposable ingress/config staging после containment/no-link checks, вернуть exact pre-run bitmap, снять lock и записать safe receipt.

Failure/unknown selector state не угадывается: disposable ingress остаётся stopped/closed, оба write bitmap closed, current target неизменен, evidence требует owner inspection. Retry-in-place отсутствует.

### `R7C-Q003-READINESS` — owner packet, не действие

После успешного rehearsal формируется один safe checklist со ссылками на evidence:

- full acceptance closed;
- exact fresh sealed transfer generation ID/digest;
- verified local+encrypted external copies **того же** generation/digest;
- full restore-check именно этого generation/digest из external copy;
- old rollback target exact и immutable;
- rehearsal PASS;
- reviewed selector primitive и wrapper source digest;
- rollback window и deletion prohibition;
- current pre-cutover bitmap и writes freeze procedure.

Packet дополнительно фиксирует, что old writers не открывались от seal до выпуска packet. Любое re-open, topology/schema/tool change или несовпадение generation/digest аннулирует packet целиком.

Этот packet не переключает target. Только владелец отдельным ответом разрешает `REBUILD-Q003`.

### `R7C-CUTOVER-001` — фактический local cutover после Q003

До отдельного Q003 закрыт. После разрешения один bounded wrapper:

1. Повторно сверяет readiness packet и source digests; старое evidence не переиспользуется после topology/schema/tool change.
2. Повторно доказывает тот же readiness generation ID/digest, exact SEALED/local/external/restore receipts и непрерывно закрытые old writers. Новый candidate не создаётся; mismatch/stale packet завершает run до selector work.
3. Фиксирует exact old durable selector generation/config digest, observed serving target=old, closed bitmap и old rollback identity.
4. Запускает new target isolated с mutations closed, проходит readiness и обязательные pre-switch checks; staging config проходит syntax/identity validation до commit.
5. Identity-check и останавливает exact local ingress как независимый fail-closed primitive; доказывает отсутствие serving target. Только затем делает atomic durable selector CAS old-generation→new-generation.
6. Стартует exact ingress и отдельно доказывает observed serving target=new generation/digest. File CAS не выдаётся за atomic reload/switch; success ещё не объявляется.
7. Выполняет bounded post-switch exact115/private/request-off/outbound checks при закрытых mutations. Failure останавливает ingress и пытается exact durable CAS new→old только при matching generation token, затем стартует ingress и доказывает observed old. Любая mixed/unknown/mismatched state оставляет ingress stopped и оба write bitmap closed для owner inspection.
8. На success сохраняет old runtime/DB/media минимум семь полных суток и дольше, пока нет owner acceptance плюс успешного restore нового поколения. Оба target остаются mutation-closed на всё zero-divergence rollback window.
9. `finally` не открывает writes по прежнему bitmap. Он сохраняет mutation fence, очищает только exact staging, снимает lock после exact selector/ingress postcondition и пишет safe receipt. Old target и backup не удаляются.

Поздний owner rollback в окне допустим без переноса данных только пока mutation fence непрерывно доказан. Он использует те же stop-ingress → durable CAS → start → observed-old фазы, exact old identity, отдельное актуальное разрешение и safe receipt. Он не накатывает migrations и не преобразует old DB/media. Открытие authoritative writes требует отдельного решения и прекращает это zero-divergence rollback claim.

### Selector recovery matrix

| Durable selector | Observed serving target | Result |
|---|---|---|
| exact old generation | exact old | Known old; writes closed |
| exact new generation | exact new | Known new; writes closed; success только после post-switch gates |
| exact old | new или mixed | Stop exact ingress; writes closed; no success; owner inspection либо reviewed old recovery |
| exact new | old или mixed | Stop exact ingress; writes closed; no success; exact-token rollback attempt допустим только внутри bounded phase |
| unknown/missing/mismatched digest или target | любой/unknown | Stop exact ingress, preserve targets/evidence, writes closed, no cleanup selector evidence, owner inspection |

Observed target должен происходить из reviewed local-only evidence, связанного с actual upstream container/generation, а не из ожидаемого значения wrapper. Конкретный marker/inspection primitive выбирается после `R7C-INV-001` и проходит independent review.

## 5. Acceptance

- `R7C-AC-001`: readiness packet имеет closed exact evidence set; любой open/blocked/unknown gate запрещает Q003.
- `R7C-AC-002`: topology inventory доказывает exact old/new/selector/bitmap identities без секретов и mutation.
- `R7C-AC-003`: один exact generation ID/digest связывает fresh `SEALED` pair, local+encrypted external copies, external restore receipt, rehearsal, readiness packet и Q003; reopened old writers делают всю цепочку stale.
- `R7C-AC-004`: rehearsal использует disposable non-current ingress и реально проходит old→new→old через отдельные config-validate, ingress-stop, durable-selector-CAS, ingress-start и observed-target phases.
- `R7C-AC-005`: rehearsal/cutover new target проходит readiness, exact115, private denial, request POST absent, cache/cookie/canonical и outbound0.
- `R7C-AC-006`: до final post-switch success оба targets mutation-closed; failure до durable CAS сохраняет old; post-CAS failure возвращает old только по exact token+observed-old proof; mixed/unknown оставляет ingress и оба write bitmap closed без ложного success.
- `R7C-AC-007`: source DB/media, sealed candidate, old rollback target и current selector неизменны после rehearsal; cleanup exact и bitmap restored.
- `R7C-AC-008`: Q003 cutover выполняется только после отдельного owner approval и fresh revalidation всех authorities.
- `R7C-AC-009`: old runtime/DB/media сохраняются минимум семь полных суток после cutover и до owner acceptance + successful new restore; zero-divergence late rollback требует непрерывный mutation fence всего окна; delete требует Q004.
- `R7C-AC-010`: safe receipt содержит только run/evidence IDs, digests, phases, bitmap и PASS/failure code; secrets, row/media payloads, host paths и logs отсутствуют.
- `R7C-AC-011`: external copy, production/live, DNS/TLS/VPS и destructive cleanup не подразумеваются local rehearsal или Q003.

## 6. Review focus и anti-bloat

Independent architecture/data/destructive/concurrency review до любого runtime обязан проверить exact generation binding, mutation fence, durable selector CAS versus observed target, independent ingress stop, recovery matrix, stale sealed candidate, old writer freeze, rollback window, exact cleanup и отсутствие ложного production claim.

Не добавляются controller daemon, deployment service, service discovery, generic persistent state machine, retry queue, new catalog UI или second coordinator. Допустимы один bounded wrapper, небольшой explicit phase enum внутри одного run, atomic durable file/config CAS, independent exact ingress stop/start, existing Docker/Nginx/PostgreSQL и closed JSON receipt. Конкретные selector/observed-target primitives не выбираются до `R7C-INV-001`.

Итог review: initial `P0=0/P1=3/P2=0`; все три P1 remediated. Repeat `APPROVED P0=0/P1=0/P2=0`. Runtime/data/topology не изменялись.

## 7. Следующая точка

`R7C-INV-001` выполнен 23 ноября 2026 года read-only и завершён fail-closed: оба ingress/app stopped, observed serving target `NONE`, durable selector/CAS/observed-generation primitive отсутствует, exact old rollback target не назначен, fresh `SEALED` candidate отсутствует. Safe evidence прошло repeat independent review `APPROVED P0=0/P1=0/P2=0`: `docs/clean-rebuild-7-local-cutover-inventory.md`. Контейнеры и topology не изменялись; media contents не читались.

`R7C-SELECTOR-001` source-only design закрыт repeat review `APPROVED P0=0/P1=0/P2=0`: `docs/clean-rebuild-7-selector-design.md`. Он определил раздельные disposable rehearsal/durable local scopes, fail-closed `ABSENT→old` bootstrap, Linux-volume canonical selector CAS, mandatory pre-CAS journal, fresh actual DB/media binding и direct→through-ingress target proof без HUP/daemon.

Tests-first source implementation plan `R7C-SELECTOR-IMP-PLAN-001` закрыт repeat review `APPROVED P0=0/P1=0/P2=0`. Следующий возможный пакет — отдельное owner approval только на source edits `R7CSI-IMP-001..006`; Docker/PostgreSQL/media read, topology apply, transfer, rehearsal и cutover остаются отдельными gates.
