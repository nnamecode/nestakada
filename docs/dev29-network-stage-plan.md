# DEV-29: phase-aware network guard и один новый ограниченный PG-прогон

2026-11-04. **BOUND29-NETWORK-STAGE-001 / предложение DEV29-Q025. Не утверждено.** Сообщение «продолжай» разрешило подготовку этого документа и независимое ревью, а не guard patch, новую копию, Prepare, Docker, PostgreSQL или SQL. Этап 8 — разработка сайта, DEV-29/P29-A; готовность около35%/31%. Старый сайт/VPS/production/push вне scope.

## Основание и граница evidence

D-476 принял Q024: одна сетевая квалификация PASS, независимое [result review](dev29-network-lifecycle-result-review.md) APPROVED. CREATED: пустые NetworkID/EndpointID/members; RUNNING: owned NetworkID, непустой совпадающий EndpointID и единственный owned helper; EXITED: NetworkID сохранился, EndpointID/members пусты. Это наблюдение одного pinned Python image/engine/lifecycle, не universal Docker policy, не PostgreSQL/P29-A admission. Повторять Q024/observer не предлагается.

Q023 прошёл readiness/preflight/RO-before/budget, но остановился до DBstart: текущий guard требовал runtime NetworkID в CREATED. Его единственный Run исчерпан; FAIL не переписывается. Основа — [Q023 план](dev29-bounded-stdin-plan.md), frozen resume004 package36. Предлагается исправить только явно описанную stage-модель и места её вызова, сохранив все прочие guards.

## Точный предлагаемый контракт

Stage задаёт доверенный caller **обязательным closed enum CREATED/RUNNING/EXITED**. Отсутствующий/неизвестный stage, конфликтующие legacy running/exited flags или выбор stage из фактического Status — FAIL. Не оставлять permissive default. State обязан совпадать с требуемым stage; нельзя выдать running контейнер за created, чтобы принять пустой ID.

Во всех стадиях остаются exact container ID/name/run/create-nonce/image/command/User, stdin, Env/mount/caps/isolation/ports/restart и source/engine checks. StdinOnce строго Boolean(s.stdin), без изменения create/start flags. Сетевой контейнер имеет ровно key owned NET, точный HostConfig.NetworkMode=owned NET и строковые поля NetworkID/EndpointID. Отсутствие, null/boolean/number/невалидная строка вместо ID не нормализовать. Непустой NetworkID всегда равен actual owned network ID. Network inspect отдельно подтверждает exact ID/name/labels/nonce, bridge/Internaltrue/IPv6false. Пара container/network не атомарна: сохранить времена обоих чтений, не переснимать до удобного результата.

| Stage/роль | Обязательное состояние и network contract |
|---|---|
| CREATED: DB и6 сетевых helper kinds | Statuscreated, Runningfalse, StartedAtzero, RestartCount0. Разрешена только наблюдённая форма: NetworkID="", EndpointID="", target отсутствует в members. Это проверка intended binding доstart, не runtime attachment. Не принимать B/C из диагностического плана как уже наблюдённые production формы. |
| RUNNING: DB после READY и перед каждым helper | Statusrunning/Runningtrue, StartedAt непустой и совпадает с закреплённым DBstartedAt, RestartCount0; NetworkID=owned actual ID, EndpointID=непустой64hex. В свежем network inspect DB присутствует ровно под owned DBid с тем же EndpointID. Пустые IDs запрещены. |
| EXITED: сетевой Python helper | Statusexited/Runningfalse/ExitCode0/RestartCount0, StartedAt непустой, exact owned instance без restart. Только фактически наблюдённая форма E0 ниже; worker/native success, full output и остальные проверки обязательны отдельно. |
| EXITED: DB | Не заимствовать Python EXITED qualification для PGimage. В нынешнем lifecycle full network EXITED gate для DB не вызывается: bounded cleanup использует отдельную exact-owned safety проверку и final shell proof. Попытка использовать общий phase gate EXITED для DB без отдельного утверждённого контракта — FAIL. Это не запрещает уже разрешённый safety stop/remove. |
| networknone: preflight helper и2 RO inspectors | Сетевая политика прежняя: HostConfig.NetworkMode=none; допустимые keys прежние none/empty. Не требовать owned NetworkID или подключать к owned bridge. Stage/State всё равно явные. Preflight stdin=true, RO inspectors stdin=false — сетевой none не меняет stdin-профиль. |

**E0 — фактически наблюдённая EXITED форма:** NetworkID=owned, EndpointID="", target member отсутствует.

Любые перекрёстные/несогласованные пары (пустой container EndpointID при target member, непустой EndpointID без matching member), foreign ID/member/key/network, отсутствие полей или неизвестная форма — FAIL без повторного snapshot. Иной EXITED вариант означает STOP/FAIL; возможное расширение обсуждается отдельно только после реального нового факта, без пересъёмки или runtime fallback.

Members означают всю owned bridge, не только target: при DB CREATED сеть пуста; после DB READY обязателен owned DBmember. При helper CREATED/EXITED остальные members должны быть только закреплённый running DB. В EXITED target helper отсутствует; остаётся только закреплённый running DB. Проверять DB endpoint/StartedAt по соответствующему trusted RUNNING proof, не превращать allowedIds/subset в доказательство наличия DB. Не разрешать чужой helper под тем же scope. Исходный networkGate subset остаётся полезным foreign-member guard, но не является достаточным required-member proof.

**Минимальный scope не добавляет active helper RUNNING gate до payload.** Сейчас helper создаётся, проверяется CREATED, затем existing start--attach отправляет ARG и после завершения проверяется EXITED. Нельзя обещать helper RUNNING observation, которого нет, делать race-prone single inspect послеstart или переносить NETQUAL handshake/capturelib в workers. Strict RUNNING predicate сохраняется для реально проверяемого DB; helper start остаётся controlled Docker start с exact reviewed CLI/profile и native TLS/DB identity gates. Если отдельный live helper proof доSQL окажется обязательным требованием, нужен иной конкретный план/согласование до реализации, а не скрытое изменение этого guard fix.

## Все места вызова и evidence producers

Ссылки относятся к frozen `work/dev29-bounded-20261104-resume004/real-host/`.

| Место | Явный stage/действие в новой копии |
|---|---|
| `controller.mjs:94 create()` | Зарегистрировать exact owned ID/nonce до проверки; `inspectGate(...,CREATED)` для всех create. Для networked targets проверить intended configuration/zero IDs; networknone — прежняя ветка. Invalid stage не доходит доreturn/start. |
| `:99 helper()` DB precheck | `RUNNING`, StartedAt pin и свежая paired DB/network binding/member проверка. Это реальный DB gate, не helper RUNNING. |
| `:100 helper before=inspect/networkCheck` | Для6 сетевых kinds main/unit/matrix/init/capacity/suite: fresh `CREATED` target + actual owned network/member proof; DBmember обязателен, helper отсутствует. Для preflight helper — прежняя networknone ветка без owned network/DBmember (до создания DB/network), но с явным CREATED/physical-profile guard. Успех требуется до`:101 capture`/отправки ARG. Не считать old subset check полным proof. |
| `:102 after stream.closed()` | Для6 сетевых kinds main/unit/matrix/init/capacity/suite: `EXITED` target + fresh owned network/member snapshot только E0; target отсутствует, DB остаётся обязательным member. Для preflight helper — прежняя networknone ветка без owned network/DBmember, с явным EXITED/physical-profile guard. Success exit/full protocol/native outcome проверяется отдельно; ошибка запрещает следующий helper/фазу. |
| `:116 original()` | Создание через CREATED, окончание RO inspector через EXITED, оба networknone. Исходный volume только прежний RO inspector. |
| `:121 startFacts()` | Fresh paired DB CREATED/network EMPTY в START review, а не runtime NetworkID. |
| `:122 startDb()` | Непосредственно перед start повторить fresh DB CREATED/network EMPTY после возможного review-gap. После READY — RUNNING с actual endpoint/member/StartedAt. INIT hard90 не переносить и не обновлять. |
| `:126 payloadReview()` | DB/network evidence для C/T проходит явную RUNNING paired проверку до формирования existing review facts. Не менять worker ARG/contract schema и не подписывать snapshot с неверным stage. |
| `:93 cleanupContainer`, `:128 cleanup`, terminal inventory | Отдельная exact-owned safety ветка, не permissive default EXITED policy. Сохраняет id/name/run/nonce/once/cleanup freshness/неповтор mutation. Не требовать успешного functional phase gate для удаления уже owned failed object; не выдать cleanup за functional PASS. Перед network remove — actual empty members после удаления контейнеров, затем отсутствие/terminal proof. |
| `:78 emptyOriginal()` | Проверка mounts для защиты original, не qualification arbitrary containers. Не применять к чужим container mandatory owned stage и не ослаблять original-volume запрет. |

Все обращения к `S.inspectGate` должны передавать stage; tests проверяют отсутствие legacy/default path. Actual member proof нужен в указанных точках, где snapshots уже собираются; если требуется дополнительный bounded inspect для связанной пары, его время включается в прежний work budget. Не вводить polling, retry, новые subscriptions/exec/sleep или worker handshake. Pair/physical-profile validators могут быть testable helpers в spec/controller, с hard production defaults и без CLI/env bypass. Review проверяет реальные production call sites, а не только fake orchestration.

## Новая COW-копия — только после Q025

Proposed root **89258833-cc7f-414f-9081-7c56793a1f2f**, prefix `nestakada-bound29-89258833`; public `work/dev29-bounded-20261104-resume005/`; private `work/dev15-20261102/private/bound29-89258833-real/`. Public namespace проверен как отсутствующий; private не открывался. Ничего из них сейчас не создавать.

Основа36 из resume004. Разрешаемая будущая delta: identity/root/prefix/paths/owner/authority/marker и производные SQL pins; phase-aware guards в spec/controller, explicit call sites и host tests/literal fixtures. Business SQL, source31, product protocol/consumer/tests, old local_trust Tests guard, stdio protocol, worker bodies, failure trace и остальные clocks/limits не менять. NETQUAL implementation не импортировать/не переносить; approved normalized fixtures — только selected evidence, не full-profile admission.

Подготовить complete COW manifest и normalized delta proof; новая plan SHA вычисляется после независимого plan freeze (не self-hash внутри документа). Exact owner decision/новые review/package/plan pins фиксируются после явного ответа DEV29-Q025; неизвестный номер/недоступный hash не заменять guess. Fresh secrets/identity/key создаёт только один approved Prepare, не копировать старые private inputs.

## Закреплённые baseline hashes

| Baseline | SHA256 |
|---|---|
| Q023 plan | 00b400f0d8b6aff861bd5e9b4592792c4b5010e472fc1902f6c4ca92698f537c |
| Q023 package36 | d7951336f23cff9c01c18d244cd913c0d4aff78dcbd9a77ee3397303a2b1a7cd |
| resume004 public prepared plan | d70c7725476b3156d776399ff5c4f6e10cf447db14fb3e7f2bd3cf5d896a5c72 |
| Q023 result / DB cleanup / network cleanup | 15fe3a1755d4a6af6f8738eb34c15f9662c2be350bda6841602be7e374f9a7f9 / 079df90877cc2e956635c2d45dda2d4691bb372f7b0c284c30e972bff8a2ab6b / 75d8f4d108f4867f71c86f98fd8f45a405c3cbdba7c4784a08ffd283a4bf7de4 |
| Q024 plan / package | 4679a968106b0ee2193a74d343893eb67c5351071a654c12864f7f89811ac085 / bf1ddf1a0b0912b5c494e484517e53f098c67771be2d468a9e71d6e07cb96423 |
| Q024 manifest / actual result | c7ee73a8e170a686da7478703f7d44b72b93ffd0e2f6405b3eafe6eaaca00f19 / d7385d94d7a5a568ab602cd5c80bc09577c71ac1ff530fa85966a23ac2468833 |
| Q024 result-review / normalized fixtures | 9c45e60200c7e7a6c8254d61d1df3458a2f7d4ee67f85f6a4818fbc23c63a30c / 743bb4a093b8b35a8722eb370e8a831565b541832bba28a251a593794086dae3 |
| Source31 fingerprint | 1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e |

Immediate PG ancestry — Q023 FAIL, не новая authority. Q024 evidence/fixture hashes связываются отдельно. Указанные private result/cleanup hashes взяты из approved public postmortem, private сейчас не читался; точные protected basenames/доступ для будущего standard hash-read должны быть закреплены координатором до COW/Prepare, иначе STOP. Сохранить все более ранние ancestry bindings из предыдущего prepared plan, cause/readiness/Q022/Q023 pins.

Retained budget: весь набор roots previous prepared plan, old bounded и resume001/002/003/004 целиком, новый public/private, `work/dev29-network-qualification-20261104-001/` целиком, `work/dev29-network-qualification-20261104-001-review-checkpoint-001/` целиком и failed observer `work/dev29-docker-lifecycle-20261104-001/`. Включить и любые ранее принятые parents/checkpoints; nested dedup без потери корпуса. Ничего не удалять ради прохождения budget. До/после — original allocation + все host roots/new artifacts/reserve; неизвестное/дефицит означает NOT_RUN.

## Приёмка до реализации

- **R025-AC01 stages:** missing/unknown/default/conflicting stage rejected; CREATED не проходит RUNNING, RUNNING не проходит CREATED; DB EXITED не заимствует Python policy. Все actual call sites и evidence producers покрыты injected production path/static wiring checks.
- **AC02 literal evidence:** побайтно закреплённые normalized Q024 selected fixtures: CREATEDempty, RUNNINGexactowned, EXITEDowned/empty/empty. Дополнить независимыми полными synthetic physical profiles и ролью existing DB, не выводить все network values из одной spec-формулы. Только наблюдённая EXITED E0 положительна; синтетические полностью исчезнувший NetworkID, остаточный EndpointID/member и любые прочие неизвестные EXITED формы — отрицательные cases, STOP/FAIL. Foreign/missing/wrongtype/несовпадение member endpoint отвергаются.
- **AC03 live isolation:** DB RUNNING empty/foreign IDs, extra key/member, wrong endpoint/StartedAt/restart/engine/profile — FAIL. При helper CREATED/EXITED подтверждён только заявленный stage, а не несуществующий live helper gate. No new handshake/polling; wrong created/prestart pair не допускает capture/start/ARG.
- **AC04 preserved guards/clocks:** Q023 stdin true/false tests всех7 helpers/DB/2RO; readonly mounts, caps/Env/User/CLI/once/identity/role/OID/marker/TLS/source unchanged. Readiness pair90/firstinventory45/native≤44, прочие inventory≤8999; helper90/INIT90/C620/T260/cleanup30/trace reserve/TTL≤900 и C850/T490 unchanged. Mock clock включает стоимость новых metadata proofs; overrun не продлевает clocks и не допускает фазу.
- **AC05 failure:** invalid CREATED/EXITED, partial/timeout/drift/trace-storage failure прекращают dependent work. Registry already-owned ID остаётся для bounded cleanup; dispatched failed mutation/Run не повторять. Empty terminal не переписывает aggregate FAIL/UNPROVEN. Ошибка последнего decode/snapshot/report write не выдаётся за proof.
- **AC06 preservation:** old packages/plans/receipts/fixtures/checkpoints/source31 immutable, полный retained-root set; только назначенный hash/metadata-read approved nonsecret ancestor receipts, без private keys/credentials/raw Env. Новые tests сначала syntax/static → AC → полный existing offline безskip; реальные1000/139 не заменяются mocks.

## Один условный lifecycle после отдельного ответа

После independent plan review и явного Q025: новая COW/delta + offline checks → independent code review → один Prepare → independent prepared-result/dispatch reviews → максимум один Run. Fresh same-engine/image/source/no-conflicts/resource/retained/original gates обязательны; затем INIT→C→T с actual START/INIT/PAYLOAD-C/C/PAYLOAD-T/T reviews≤120с по exact hashes, без preapproval. Технические gates внутри принятого scope не требуют лишних ownerquestions.

Новый DB только tmpfs PGDATA512MiB/run16/tmp32/shm16, memory=swap1GiB/CPU0.5/PIDs128; helper256MiB/CPU0.5/PIDs64/tmp32/shm16; прежние pinned PG/Python/engine/endpoint, CAPdropALL/rootfsRO/noports/lognone/restartno/internal network, VM available≥2GiB, persistent<2GiB/new artifacts≤32MiB/streams≤1MiB/trace≤8KiB. No pull/build/install/settings/WSLrestart. Original volume только прежние2 bounded RO volume-nocopy UID999 inspectors, без SQL/старого DB/архивов.

C — actual1000/1001 с outer rollback; T — исходные139 безskip/подмены и guarded existing new UNIT. После send — прежние2 sequential independent witnesses; при PASS/ошибке — exact-owned bounded safety cleanup, RO-after, same-engine terminal owned0, fresh retained/source/budget witnesses, append-only signed result/trace и независимое result review. Missing/unknown proof остаётся FAIL/UNPROVEN; root/TTL/admission renewal, второйRun и старые5+8 probes не разрешаются. P29-A/native leases/crash/APP не закрываются заранее.

## Вопрос владельцу

**DEV29-Q025:** разрешить этот точный phase-aware контракт с единственной наблюдённой EXITED-формой E0 и весь один новый ограниченный lifecycle с COW/tests/reviews/одним Prepare и условным INIT/C/T, rollback, сохранением корпуса и cleanup? До ответа разрешён только данный документ и его независимое ревью. Любое требуемое расширение live helper architecture, budgets/limits или неизвестной policy — новый вопрос до кода/runtime.

После принятого результата — оценка оставшихся P29-A требований, затем план P29-B/C/D/E; общий этап9 начинается после завершения разработки.