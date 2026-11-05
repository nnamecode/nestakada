# DEV29-Q026: source/offline freeze и code review

**Последний итог D-496: BOUND29-RESUME-CODE-REVIEW APPROVED** — exact package42 2489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e. Независимый /root/q025_reviewer закрыл CODE001/002/003, подтвердил hashes/checkpoint,5changed/37unchanged и собственные syntax4/AC25/host33 PASS. Новых findings нет. Это только code/offline approval; реальные rehearsal/readiness/Prepare/native результаты не предодобрены. Ниже сохранена история прежнего freeze и исправлений.

2026-11-04. **Первый CODE REVIEW: CHANGES REQUIRED (D-495); approval пока нет.** Исполнитель /root/q025_builder, независимый reviewer /root/q025_reviewer. Владелец разрешил Q026 D-493 по exact proposal a8752b727613d8cea522affb37f90b8e716beb3ef3dd41a3fe57bd6f1b0c5c76. До независимого code approval actual rehearsal/Prepare/readiness/native не выполнять.

## Frozen пакет

- Public work/dev29-bounded-20261104-resume006/, baseline Q025package38 cd803389…bf81, checkpoint38 byteMATCH. Source31fingerprint прежний1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e.
- Package42 SHA2564deedde9b661b13ad31dacb081152a838dc30c2393a35b9547b08b3dd3788d0d.
- package-manifest.json raw6d60cd2ecf7100ddba691b2c90ac4d26319b7c77d6945b6248ab3fb6def41fee.
- delta-proof.json rawbd9ae0fae05ab4bf56edadaf2e958a34070f7797be12f14926ff4c0967c7065b.
- test-summary.json raw9d23d15da639f470750de9b69573650037405b2a9bc09410cfd12b1f497e43f9.
- real-host/review-handoff.json raw887552c9d586ac0e23de5c2f6982c844820d29fcbf43ec91b39051cdbf7815ea.

Retained35roots/75610389bytes, public733582bytes с checkpoint. Это metadata snapshot, не runtime budget/original-allocation proof. Старые run/private/keys/opinions не копировались. Q025 late history immutable.

## Проверки

Syntax17Node+12Python=29PASS, новые review-contract AC19PASS, прежние111PASS, итого130различных тестов/skip0. Синтетические INIT/PAYLOAD/C/T полныеtypedinputs проходят тотже facts validator/projector, что runtime; ранние selfassertion placeholders заменены доfreeze. Publisher race/cancel/clock/storage/NOAUTHORITY checks исполнены черезобщийinjected helper, не толькостатическаяпроверкатекста. Старые worker/SQL/stage/caps/runner/source31 ограничения сохранены, дельта/pins предстоятнезависимому review.

Одна TypeError patchscript (сменаconstpath) произошла после успешной записи одногофайла; оставшиесяфайлы дописаны отдельнымscript, append не повторялся, target syntax/AC PASS. История сохранена вtestsummary. Actual Rehearsal/Readiness/Prepare/private/Docker/SQL/native0.

## Маршрут и следующие gates

Actual independent reviewer читает bounded summary текущихфактов, принимает собственный verdict, пишет только ownwxsource в fixedoutbox и вызывает fixedPublishReview. Templates не содержатготовогоAPPROVED. Opinion неacceptedadmission: толькоRunner проверяетmonotonicdeadline/CLOSED/source иacceptedproof передследующимдействием.

NOAUTHORITY recorder однойжизнью измеряет6gate end-to-end≤80с/каждый/≤490ссreport; Publisher отдаётack+nextsummary, чтобыroot не копировалJSON/не добавлялпересылкувtimedwindow. Rehearsalнеиспользуетruntimekeys/private/liveadmissions. После квалификации иindependentreview одинPrepare, затем отдельныйnonnative sharedauth/ACL/privateIO readiness≤10с/128KiB/once иindependentreviews доoneRun. Никаких новыхnativeпроверок приunknown/failure, runtime120с/TTL/caps неувеличиваются. CODEreview неpreapproveбудущиефакты. Старыйсайт/VPS/корпус не трогать.

## Первое независимое ревью

/root/q025_reviewer подтвердил package42 hash; собственные syntax4, AC19/19 и host33/33 PASS, skip0. Три подтверждённых замечания:

1. REVIEW26-CODE-001 P1, review-contract:13–20/controller:130–133: authoritative state не включает отмену и drift во время ожидания/валидации/proof write/consume. Проверка времени и наличия CLOSED/result не заменяет verify/cancel; при отказе первого finalGate consume также должен попытаться закрыть gate. Нужен единый fail-close и отрицательные сценарии всех границ, без admission после отмены.
2. REVIEW26-CODE-002 P1, review-facts:3–9/controller:174–176: для START не проверяются original-before/retained budget/fresh preflight; для helpers не читаются и не сверяются actual rawFile, before/after и cleanup linked proofs. Подпись envelope и объявленные hex-хеши не доказывают существование/содержимое файлов. Нужны реальные безопасные mappings и missing/tampered negatives через рабочий путь и синтетические fixtures. Historical START уже подтверждён как реальные старые факты и pinned historical profile, это сохраняется.
3. REVIEW26-CODE-003 P2, controller:187: заявленные размеры1024/65536 относятся к data, фактические payload1263/65776 и envelope1354/65867. Нужны измеренные сериализованные byte bounds и отдельный обязательный schema rejection наряду с HMAC tamper negative.

Ошибок инструментов у рецензента не было. Actual rehearsal/Readiness/Prepare/Docker/SQL/native не запускались, исходники он не менял. Исполнителю разрешены ровно3исправления после review-checkpoint; остальные guards/лимиты/source31/SQL/worker не расширять. После нового freeze обязателен повторный независимый review.

## Второй freeze: исправление трёх замечаний

CODE001: authoritative отмена/дрейф/verify включены в окно и единый fail-close, в том числе при первом отказе consume. CODE002: общий resolver читает реальные raw/input/before/after/cleanup и обязательные START engine/original/budget/preflight; live/historical/synthetic используют тот же путь. CODE003: payload действительно1024/65536 сериализованных байт, envelope измеряется отдельно, auth/schema-negative раздельны.

Затронутые syntax4/static PASS → AC25/25 PASS → host33/stage10 PASS. С неизменёнными68 тестами общий distinct136 PASS, skip0; повторные запуски не суммируются. Старые52 publicfiles сохранены в review-checkpoint-001, manifest6350739aff03e0d9dd12da55a272f77c348f8561e0586ec520c0790bdae9b2a9. Из42inputs изменены5, остальные37 byte-identical. Ошибок инструментов в этом исправлении не было.

- Package42 SHA2562489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e.
- Manifest23cf584e4cef3b85c618a5504a52bdd97a303ee3dfbd492e7d1ed9bdfe3844e7.
- Deltaa05ab3fc603a79c9fc8826ba755f218130354d9798ebf7ef8b7f03de81a3b953.
- Test-summaryb16815f9785156778ec1664e81d4176bb6a7154b5d118ea949be440ad64ce140.
- Handoff1dfa0f18c3bccbbd44994462a8ed4526c72a2f639b302d58800cd28e534681b5.

Retained35roots/76069765bytes/public1192958bytes, metadata88430bb5b2851d78dedeb710d9364e3b680c7910bf835c2190f75e4a11d6aba0. Runtime budget ещё NOT_PROVEN. Пакет на повторном независимом ревью; actual historical resolver/Rehearsal/Readiness/Prepare/private/native ещё не выполнялись.

## Готовность измеряемой передачи

Readonly historical START до rehearsal attempt отдельным frozen API не экспортирован; новый обходной путь не создавался. Он будет впервые исполнен внутри разрешённой единственной NOAUTHORITY квалификации. Exact handoff raw1dfa0f18c3bccbbd44994462a8ed4526c72a2f639b302d58800cd28e534681b5: reviewer сам читает START, принимает hypothetical verdict, пишет свой wxsource и вызывает Publisher, затем сам обрабатывает ack/nextSummary доT. Root только заранее готовит команды и наблюдает; JSON за reviewer не копирует. При отказе qualification — NOT_RUN, без повтора.
