# DEV-29: независимое ревью focused PostgreSQL-пакета

2026-11-03. **FOCUSED-CODE-REVIEW APPROVED**, итог FOCUSED-CODE-REVIEW-002. Основание — Q009/D-421 и [план](dev29-focused-postgres-plan.md). Документ фиксируется до конца этого прогона; фактические payload/measurement/result review записываются отдельно.

Первое FOCUSED-CODE-REVIEW-001 потребовало исправлений; повторное FOCUSED-CODE-REVIEW-002 независимо подтвердило их и приняло весь пакет. Рецензент не менял исходники и не выполнял Prepare/Docker/SQL/чтение реальных ключей. Это approval кода, не свидетельство runtime PASS.

| Замечание | Статус и результат |
|---|---|
| FSTOR-REV-001–003 | CLOSED: закрытая схема бюджета, точные DB/network/mounts/caps, привязка plan/image/volume/source/producer/review и проверки свежести. Storage offline44 PASS. |
| FOC-REV-001 | CLOSED: actual createController проверен через injected fs/crypto/spawn/time по всей цепочке Prepare/Baseline/Authorize/Run001/Continue. Проверены drift, wrong DB/role/OID/marker/schema/session/nonempty, mounts, partial output/timeout/cleanup/preservation/expiry, locks/retry; PG002/007 и старый Run исключены. 2170 offline checks PASS. |
| FOC-REV-002 | CLOSED по FOCUSED-GATE-SIGNERS-REVIEW-001 APPROVED: отдельные закрытые Payload/Measurement issuers; позднее чтение ключа, проверка HMAC входов, повторная сверка public SHA/phase, однократная запись wx, Docker/SQL отсутствуют. Независимые syntax/inert import/58 actual-flow synthetic checks PASS, реальных ключей/записей/SQL/Docker0. |
| FOC-REV-003 | CLOSED: plan/checkpoint фиксируют SHA прежних package9/audit7, audit-prepared-source, operator ledger, presence transfer-lock и полное содержимое трёх прежних runs. Non-cleanup Verify пересчитывает manifest; cleanup сохраняет узкие безопасные проверки. |
| FSTOR-VS-REV-001–003 | CLOSED: VerifyStart выполняет полный focused Verify до Docker и после HMAC; inventory учитывает labels и точные имена независимо от labels. Повторно сверяет public bytes, том, образы и отсутствие ресурсов перед START_VERIFIED. Actual injected-flow negatives включены в storage59 PASS. |

Независимые проверки: syntax9 modules/tests и inert imports PASS; core/flow91, actual controller2170, storage59, actual issuers58 PASS. Реальные Docker/SQL/key/FS writes0. Замечаний P0–P3 не осталось. Scope/TTL15мин/remaining200с/soft20с/caps/forced rollback/mandatory after-witness проверены; fullP29A/fullRegression/APP/EDGE остаются false.

Следующий допуск: immutable Prepare/Verify, подписанный Before/VerifyStart и read-only сверка, DB-only restore/Baseline/Authorize, отдельное actual payload/provenance review перед Run001. Продолжение003–006 — только после actual measurement/budget review и закрытого подписанного gate. Старый сайт и VPS не затронуты.
