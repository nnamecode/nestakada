# R7C-SELECTOR-001 — минимальный local selector и observed-target proof

Статус: source-only design approved 23 ноября 2026 года. Первое independent architecture/data/concurrency/destructive/no-bloat review: `CHANGES_REQUIRED P0=0/P1=3/P2=1`; исправлены actual DB/media binding, разделение rehearsal/local scopes и bootstrap, mandatory pre-CAS journal, fresh pre-CAS/post-start revalidation. Repeat review: `APPROVED P0=0/P1=0/P2=0`. Реализация, Docker/runtime, topology change, migration freeze, transfer, external copy, rehearsal, cutover, rollback и live этим документом не разрешены.

Основание: `R7C-INV-001` доказал, что оба ingress/app остановлены, observed target = `NONE`, а durable selector/CAS и exact old rollback authority отсутствуют. Этот документ закрывает только архитектурную форму будущего selector primitive; old/new targets и fresh generation он не назначает.

## 1. Решение и граница атомарности

Primitive имеет два взаимоисключающих scope с разными exact resource identities:

- rehearsal: run-scoped disposable volume `r7c-rehearsal-<run-id>-selector` и disposable ingress без current/local/live route;
- future Q003: fixed project volume `r7c-local-selector` и заранее инвентаризированный durable local ingress.

Ни volume, ни ingress одного scope не может использоваться другим. Rehearsal обязан доказать exact pre/post digest durable local volume и current local ingress unchanged. Ingress монтирует только selector volume своего scope read-only. Единственный durable authority внутри scope — canonical regular file `/selector/selectors/active.conf`; selector writer получает этот volume read-write только в stopped-by-default one-shot container с `network_mode: none`, без DB/media/source/secrets mounts.

`active.conf` имеет одну closed canonical форму, создаваемую только renderer-ом из tuple:

- schema `estakada.r7c-selector-v1`;
- scope `rehearsal:<run-id>|local`;
- role `old|new`;
- полный generation SHA-256;
- один literal Docker DNS alias `r7c-old-app|r7c-new-app`;
- один связанный с role literal media root `/srv/media-old|/srv/media-new`;
- один связанный с role literal static root `/srv/source-old|new/modules/pages/static`;
- fixed upstream port `8000`;
- никаких произвольных directives, paths, variables или extra bytes.

Файл включается в fixed reviewed Nginx config только в `http` context и определяет единственный upstream `r7c_active` плюс fixed `$r7c_media_root`/`$r7c_static_root`. Canonical renderer связывает role, alias, source/static и media roots: `old` не может назвать new aliases/roots и наоборот. Generation metadata является CAS/recovery authority, но не считается observed proof. Ingress монтирует оба exact role source/static и media roots read-only; один CAS поэтому выбирает coherent app+DB authority и соответствующие public bytes.

Атомарность заявляется только для durable `active.conf` replacement в пределах одного Linux volume filesystem: exact expected state `ABSENT|PRESENT(sha256, canonical tuple)` → temp regular file → full write/reopen/hash → file `fsync` → fd-relative `os.replace` → parent-directory `fsync` → read-back exact digest. Exclusive host lock сериализует project wrappers. Scope mismatch отказывает до write. Host/Docker-admin mutation вне wrapper находится вне local guarantee и при следующей проверке даёт mismatch/UNKNOWN.

Config render/validation, ingress stop, durable selector CAS, ingress start и observed-target verification — пять отдельных фаз. Ни одна комбинация этих фаз не называется атомарной. Nginx `HUP`/reload не используется: selector меняется только при доказанно остановленном exact ingress.

### 1.1 Fail-closed bootstrap из текущего `ABSENT/NONE`

Каждый scope до switch обязан отдельной операцией создать доказанный old baseline: direct old target/storage proof → candidate old config `nginx -t` → обязательный PREPARED journal → exact scope ingress stopped/absent → CAS `ABSENT→old` → start exact scope ingress → observed-old proof → confirmed bootstrap receipt.

Rehearsal bootstrap затрагивает только disposable resources и в `finally` возвращает durable local selector/current ingress к exact неизменному pre-run state. Durable local bootstrap требует отдельного runtime/topology owner gate, не является Q003 cutover и не выбирает new; он только переводит future current selector из `ABSENT/NONE` в independently observed old. Q003 запрещён, пока durable local bootstrap receipt не confirmed и active selector не exact old.

Unknown/malformed/nonempty scope вместо ожидаемого `ABSENT` блокирует bootstrap без cleanup/guess. Bootstrap использует тот же обязательный journal, phase/revalidation/recovery contract, что switch.

## 2. Target identity, actual storage binding и mutation fence

Old и new target находятся в разных exact internal web/DB networks. Ingress присоединён только к двум web networks; app — к своему web+DB; DB не имеет host binding. В каждой web network alias `r7c-old-app` или `r7c-new-app` разрешается ровно в один заранее инвентаризированный app container. Duplicate/missing/foreign membership блокирует действие.

Каждый app container имеет matching immutable image digest, config digest и labels:

- `estakada.r7c.role=old|new`;
- `estakada.r7c.generation.sha256=<64hex>`;
- safe DB/media identity tokens из readiness packet.

Labels/environment/marker не являются actual-storage proof, потому что их назначает wrapper. Для каждого old/new target отдельный stopped-by-default verifier в уже pinned image:

1. Docker inspect связывает app с exact DB endpoint/network/credential mount token и exact media mount ID/token из readiness packet.
2. Verifier подключается через фактический target DB network с read-only role/options и использует generation-v5 projection для exact DB identity, applied migrations, semantic schema/release, table counts/content hashes.
3. Тот же verifier монтирует фактический target media root read-only и повторно считает exact closed media inventory/count/bytes/SHA без вывода paths или contents.
4. Полученный `storageBindingSha256` — canonical hash DB+media projection — обязан совпасть с exact old rollback authority либо fresh `SEALED` generation readiness packet.
5. App inspect обязан указывать ровно на те же DB network/credential token/media mount identity, которые проверил verifier.

Verifier выводит только safe counts/digests/result, не имеет external network и удаляется после run. Wrong DB, wrong media mount, stale generation, source drift или incomplete projection блокируют selector mutation. Actual-storage proof повторяется перед CAS и после ingress start; прошлый receipt сам по себе не переиспользуется.

Cutover settings обязательны для обоих targets и fail closed без exact generation и `storageBindingSha256` environment. Они:

- включают `default_transaction_read_only=on` для application DB connection;
- не содержат scheduler/cleanup worker;
- оставляют request intake default-off;
- публикуют только local identity endpoint, описанный ниже;
- не меняют schema, DB или media.

Fixed cutover Nginx config допускает публичные `GET|HEAD`, а admin/editor/upload/request POST и любой иной mutating method завершает до upstream. Mutation fence доказывается одновременно container/config bitmap, negative HTTP checks, read-only DB connection setting и неизменными actual DB/media fingerprints. Privileged Docker/DB administration остаётся технически доступным вне application bitmap; любое out-of-band действие запрещено rollback window и обнаруженный fingerprint drift немедленно прекращает zero-divergence claim. Selector primitive никогда не открывает writes; отдельное будущее owner decision должно закончить zero-divergence rollback claim до любого открытия authoritative writes.

## 3. Independent observed-target marker

Ожидаемое значение из selector нельзя выдавать за observation. Поэтому каждый target через local-cutover-only Django URLconf отвечает на exact endpoint `/__r7c_target_identity__` только при fixed probe host `r7c-probe.invalid`:

- status `204`;
- response header `X-Estakada-R7C-Generation: <64hex>` из обязательного target environment;
- response header `X-Estakada-R7C-Role: old|new`;
- response header `X-Estakada-R7C-Storage-Binding: <64hex>` из обязательного target environment;
- `Cache-Control: no-store`;
- body, cookies и DB/media reads отсутствуют.

Base/public URLconf endpoint не содержит. Fixed Nginx config не синтезирует и не переписывает эти response headers, очищает одноимённые client request headers и proxy cache не использует. Ingress имеет только loopback host binding; production/live route отсутствует.

Observed proof состоит из независимой связки:

1. Docker inspect доказывает exact ingress ID/image/config/network membership и ровно один target container для каждого role alias.
2. Fresh actual-storage verifier доказывает exact DB/media projection и `storageBindingSha256` через фактические network/mounts; readiness packet generation/storage authority совпадает.
3. Exact target container label generation/role, configured storage binding и inspect connection/mount identities совпадают с verifier.
4. Bounded one-shot probe на exact internal web network обращается напрямую к target marker и получает matching generation/role/storage binding.
5. После ingress start host loopback probe обращается через ingress к тому же marker и получает matching generation/role/storage binding.
6. Through-ingress marker обязан совпасть с direct target marker, fresh storage verifier и canonical selector tuple; затем обычный public canary подтверждает actual HTTP serving. Ожидаемое wrapper value само по себе ни один шаг не закрывает.

Probe использует уже pinned Python/app image, `--rm`, exact internal web network, read-only rootfs, no secrets/mounts, bounded timeout и no external route. Он не становится compose service, daemon или scheduler. Endpoint и probe не являются production health API.

## 4. Exact phases будущего wrapper

Один wrapper удерживает exclusive host lock от preflight до cleanup/postcondition. Retry-in-place отсутствует.

### 4.1 Prepare, без изменения active selector

1. Проверить closed readiness packet, exact old/new identities, continuous mutation fence и temp resources zero.
2. Снять pre-run `active.conf` state через one-shot read-only verifier: `ABSENT` либо exact canonical `PRESENT`; symlink, nonregular, hardlink, extra selector entry, malformed bytes или digest mismatch → UNKNOWN/stop.
3. Renderer создаёт run-scoped candidate bytes; writer публикует только run-scoped staging candidate после reopen/hash/fsync. Active selector не меняется.
4. Pinned ingress image выполняет `nginx -t` с exact fixed base config и exact candidate bytes, mounted read-only. Candidate hash после validation обязан совпасть.
5. Fresh actual-storage verifiers и direct probes доказывают old и new DB/media bindings, markers и readiness при закрытых mutations.
6. До первого stop/CAS mandatory journal атомарно фиксирует `PREPARED`: schema/scope/run ID, exact ingress ID, old/new target IDs, storage-binding hashes, expected current selector state/digest, candidate digest и closed mutation bitmap. File+parent fsync и read-back обязательны; journal failure даёт mutation0.

### 4.2 Commit selector

1. Identity-check exact scope/ingress container ID/config/image; остановить только его и атомарно записать journal phase `INGRESS_STOPPED`.
2. Доказать `State.Running=false`, отсутствие loopback listener и неизменный pre-run selector digest. Stop failure или unknown оставляет writes closed и запрещает CAS.
3. Непосредственно перед CAS заново проверить exact old/new container IDs, labels, alias cardinality, network membership, app connection/mount identities, fresh actual-storage bindings, direct markers/readiness и mutation bitmap. Любой mismatch даёт selector mutation0.
4. One-shot selector writer выполняет ровно один exact CAS expected old/ABSENT digest → candidate digest. Он не запускает/останавливает containers и не имеет network. После read-back journal атомарно переходит в `SELECTOR_COMMITTED`.
5. Read-only verifier повторно доказывает canonical candidate digest и scope.
6. Запустить exact ingress container без recreate; identity mismatch запрещает start. После exact running identity journal переходит в `INGRESS_STARTED`.
7. До through-ingress marker повторно проверить exact target/alias/network identities и fresh actual DB/media storage binding. Post-CAS mismatch идёт только в rollback/unknown matrix.
8. Доказать through-ingress marker и public canary. Только после этого journal переходит в `OBSERVED_OLD|OBSERVED_NEW`, а selector state считается known old/new.

### 4.3 Failure и rollback

- Failure до CAS: active selector exact old, ingress можно вернуть только при matching mandatory journal и том же old digest; fresh old storage/target proof и observed-old обязательны.
- Failure после CAS, но до observed-new success: stop exact ingress; только если mandatory journal exact, phase допускает recovery, active digest exact candidate и stored old canonical bytes/digest exact, выполнить один CAS new→old, start exact ingress и fresh storage+observed-old proof.
- Если digest, ingress identity, alias membership или marker unknown/mixed/mismatched: ingress остаётся stopped, оба targets mutation-closed, active bytes и evidence сохраняются; owner inspection, без угадывания и второго CAS.
- Missing/malformed/incomplete/mismatched journal всегда разрешает только exact ingress stop при matching identity, closed writes и owner inspection; automatic start/CAS/rollback запрещены.
- Failure observed-old rollback не вызывает третью попытку и не открывает writes.
- Success receipt пишется только после exact selector read-back, ingress identity, fresh actual-storage binding, observed target, canary и unchanged mutation bitmap; journal получает final `CONFIRMED|ROLLED_BACK|UNKNOWN` до receipt.

## 5. Crash recovery table

| Durable active selector | Ingress | Observed marker | Recovery |
|---|---|---|---|
| exact old | stopped | unavailable | только при valid journal phase: full fresh old target/storage revalidation, start exact ingress, observed-old; иначе owner inspection |
| exact old | running exact | exact old | known old только при matching journal/fresh storage binding; иначе stop/inspect |
| exact new | stopped | unavailable | только valid journal разрешает один exact-token rollback new→old; missing/incomplete journal → owner inspection |
| exact new | running exact | exact new | known new только при matching journal/operation/receipt, fresh storage binding и post-switch gates; иначе stop/inspect |
| exact old/new | running | opposite или mixed | stop exact ingress; writes closed; no success |
| missing/malformed/foreign/mismatched | любой | любой | stop exact ingress; writes closed; preserve evidence; owner inspection |
| selector exact, ingress ID recreated/foreign | любой | любой | не signal/start/stop foreign container; writes closed; owner inspection |

Mandatory journal не является вторым selector authority: selector bytes определяют durable target, journal только разрешает или запрещает bounded recovery. Он создаётся `PREPARED` до stop/CAS и имеет closed phases `PREPARED→INGRESS_STOPPED→SELECTOR_COMMITTED→INGRESS_STARTED→OBSERVED_OLD|OBSERVED_NEW→CONFIRMED|ROLLED_BACK`, с `UNKNOWN` из любой неоднозначной boundary. Каждая transition требует exact previous journal digest, atomic file replacement, file+parent fsync и read-back. Journal содержит exact scope, ingress ID, old/new target/storage/selector digests и mutation bitmap, но не paths, secrets, DB/media payloads или generic transition graph. Missing/incomplete/mismatched/UNKNOWN journal блокирует normal bootstrap/cutover; automatic start/CAS/rollback запрещены.

Normal transition graph не ослабляется recovery shortcut. Единственное отдельное pre-CAS recovery разрешение принимает exact previous journal digest, exact non-ABSENT expected selector digest и observed role, заново сверяет current selector с journal authority и только затем фиксирует `OBSERVED_OLD|OBSERVED_NEW→ROLLED_BACK`. Terminal receipt дополнительно требует: `CONFIRMED` selector exact candidate, `ROLLED_BACK` selector exact non-ABSENT expected.

Следующая операция в том же scope разрешена только после terminal receipt и побайтно связанной с ним safe external receipt. Coordinator проверяет exact receipt/journal digests и scope, после чего one-shot network-none writer удаляет сначала terminal receipt, затем terminal journal с parent fsync; crash между unlink оставляет terminal journal и требует ту же external authority для завершения. Active selector не удаляется. External receipt append-only именуется exact `runId-receiptSha256.json`, поэтому bootstrap, new switch и later old switch одного rehearsal scope не перезаписывают evidence.

## 6. Storage, cleanup и safe evidence

Каждый scope volume имеет closed inventory: `selectors/active.conf`, bounded `staging/<run-id>.conf` текущего run, не более одного mandatory operation journal и одного final receipt. Между завершёнными операциями journal/receipt могут быть exact closed только после сохранения и проверки append-only external safe receipt; active selector остаётся единственной target authority. Никаких symlink, device, socket, FIFO, hardlink>1, unknown files или иных nested paths. Caps: selector ≤4 KiB, journal/receipt ≤16 KiB каждый, staging files ≤2 и общий volume ≤96 KiB. Rehearsal volume уничтожается только после confirmed current-local unchanged и exact disposable containment; durable local volume не удаляется до Q004.

Cleanup удаляет только exact current-run staging после known selector/ingress/observed state и containment checks. Active selector, previous canonical bytes in evidence, target containers, DB/media, sealed generation и rollback evidence не удаляются. Unknown state запрещает selector/evidence cleanup. Q004 остаётся отдельным destructive gate.

Safe receipt содержит schema/run ID, source/tool/config/image digests, old/new generation digests, pre/post selector digests, exact ingress/container IDs, phase outcomes, observed role/generation, mutation bitmap и cleanup result. Secrets, absolute host paths, credentials, row/media contents и raw logs запрещены.

## 7. Acceptance для source design и будущей реализации

- `R7CS-AC-001`: canonical selector schema closed; scope/role/alias/generation contradictions и extra bytes rejected.
- `R7CS-AC-002`: durable CAS exact old→new/old выполняется one-shot network-none writer через same-filesystem replace+file/parent fsync; stale expected digest mutation0.
- `R7CS-AC-003`: config validation, exact ingress stop, selector CAS, ingress start и observation разделены; HUP/reload и atomic-switch claim отсутствуют.
- `R7CS-AC-004`: marker происходит из actual Django target, не из selector/wrapper/Nginx expectation; direct и through-ingress proofs совпадают с fresh actual DB/media storage verifier, inspect и readiness authority.
- `R7CS-AC-005`: duplicate/missing/foreign alias/container/network/image/config/generation/storage binding blocks before selector mutation; identities/storage повторно проверяются непосредственно pre-CAS и post-start.
- `R7CS-AC-006`: обе DB/media пары сохраняются и их actual fingerprints остаются exact; оба targets mutation-closed всё zero-divergence rollback window; selector не открывает writes.
- `R7CS-AC-007`: mandatory pre-stop journal и injected failure/crash на каждой phase boundary дают exact old/new known state либо stopped ingress+closed writes+owner inspection; missing/incomplete journal запрещает automatic recovery, blind retry и третий CAS отсутствуют.
- `R7CS-AC-008`: current ingress never serves mixed/unknown target as success; observed marker and public canary required.
- `R7CS-AC-009`: receipt/cleanup closed, bounded и safe; active/old/new/data/evidence не удаляются.
- `R7CS-AC-010`: source-only package меняет только design/status docs; runtime implementation требует отдельный reviewed plan и owner gate.
- `R7CS-AC-011`: rehearsal использует только disposable volume/ingress и оставляет durable local selector/current ingress exact unchanged; каждый scope имеет отдельный fail-closed `ABSENT→old` bootstrap, durable bootstrap не считается Q003/new cutover.

## 8. No-bloat и отклонённые варианты

Не добавляются controller/service-discovery daemon, blue-green platform, generic deploy framework, retry queue, DB selector table, request-time integrity module, Nginx njs/native module, Docker socket внутри app, public health API или автоматический writer opener.

Не переиспользуется runtime-rejected DEV-26 fallback delivery path. Не используется Nginx HUP: прежний опыт также подтверждает, что selector replace, reload и serving result нельзя честно назвать одной атомарной операцией. Host bind-mounted selector отклонён из-за разных Windows/Linux rename semantics; named volume оставляет durable CAS внутри одного Linux filesystem и даёт closed one-shot writer boundary.

Tests-first source implementation plan `docs/clean-rebuild-7-selector-implementation-plan.md` прошёл repeat independent review `APPROVED P0=0/P1=0/P2=0`. Следующий gate — отдельный owner approval только на source edits `R7CSI-IMP-001..006`. Он не разрешает Docker/PostgreSQL/media read, topology apply, selector bootstrap или switch.
