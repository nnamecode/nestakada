# DEV-29: итоговое независимое ревью residual Run8

2026-11-03. **REG29-ACTUAL-RESULT-REVIEW-001 APPROVED** для bounded service evidence Run8, не полного P29-A. Рецензент файлы не менял, SQL/start/retry/mutations не выполнял.

Verify/runtimeAdmitted=false, HMAC admission/provenance/baseline/before/live/final/payload/result-receipt и closed schemas PASS. Signed result receipt closed4, scope/run/plan/exact raw result SHA совпали. Все8 case/result/probe/send/output/after/send/output связаны; probe source exact new residual/probe.py, witnesses exact parent unit-witness.py. Mandatory after byte-equal baseline, rollback/cleanup true, flush/mainWrites false; policy exact HIDDEN/LIVE_NO_SET.

- RG001: по10 отказов admission до SQL, реальные Operation0.
- RG002: reader401/wrong epoch/revoked/exact prepare replay подтверждены.
- RG003: accounting/count1000 injections явно true, real1000=false; raw rows Operation2/AdmissionPolicy1/RecoveryReceipt0.
- RG004: lease revision/stale reject/fence+activate replay/old revoked/new writer; raw rows Operation1/AdmissionPolicy2/RecoveryReceipt2.

Limitations exact: capacity/native/fullRegression false, fixtureResourceFacts true; injections только RG003. Lifecycle run.lock→COMPLETE exact, failure terminals и старые PG/1000 artifacts отсутствуют; при cleanup оставалось462270ms admission. Все baseline/after: UNIT7journal=0/migrations3/sequence4true/marker/schema; MAIN b42ec332…/closed archives16387,32563/preservation равны принятой точке. Source31/protected/package19/full older ancestry/prior-five неизменны.

| Case | Probe / witness, ms | Peak probe / witness, bytes |
|---|---|---|
|001-HIDDEN|7669 /4548|52199424 /46297088|
|001-LIVE|7165 /4229|50319360 /46059520|
|002-HIDDEN|7920 /4869|50450432 /46505984|
|002-LIVE|8343 /4495|49774592 /46813184|
|003-HIDDEN|12351 /4382|50704384 /46059520|
|003-LIVE|11164 /4533|50311168 /45764608|
|004-HIDDEN|8693 /4681|50421760 /46084096|
|004-LIVE|8902 /4798|49975296 /46809088|

OOM/oomKill0, helpers<256MiB/90с. Signed budgets341514648/342314307/342458659<2GiB. Physical WAL/dead pages не заявляются неизменными.

| Артефакт | Raw SHA256, кроме canonical plan |
|---|---|
|Plan canonical|90114402d2f4a58407b0776370ffe102cacfe1643ae2770652284d7d91c78e2e|
|Admission|521e0ebea56a51a48645c234b42f3ba1b420378dfa0ce81127d73f227d5f1030|
|Payload review receipt|e901d669790c48d16819907afa13e602da3aff8c42272b75d0cdc2c48a7f787f|
|Residual result|7ee99cf9a5cc20cd9f36b5f95caf3716878eed07ffff01db08327e7ea6cbc825|
|Signed result receipt|783ca7799dc8b433203ca1a7c3ecefbe2bffb7aaa4f74e268425b7231fb83fef|
|Final budget|2d455cd94820fe521fe113021fd77566b006bac844747501535588b5604c578f|
|29-input archive manifest|e84bb244d4223aa7a2a500dd3f31984c0ef3737f46fede74dba9c263188abb7d|

Все29 archived/current input hashes при review совпали, secret-like inputs отсутствуют. Cleanup closed/bound result/finalbudget:0containers/0networks/0helpers/volume retained/permit{}/source verification. Подтверждены Stop/RO After artifacts/current Verify; повторный Docker inventory рецензент не выполнял.

Общий result fullP29A/fullRegression/appAdmission/edgeAdmission=false. Настоящие1000/1001, full139 runner/migration, native exclusion/restart/crash/concurrency/HTTP остаются NOT_RUN. Прежние5 групп не повторялись, защита runner/корпус не изменены. Старый сайт/VPS/production не затронуты. Следующий участок — конкретный безопасный вариант получения остаточных свидетельств, требующий отдельного согласования новых ресурсов/полномочий.
