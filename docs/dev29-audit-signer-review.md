# P29-A: независимое ревью signer и observation producer

Актуализация Q008/D-419 перед первым Observe: после CAPS-REVIEW-001/BIND-REVIEW-001 APPROVED fixed RUN стал50a66937-6be2-4d76-bf50-9849f3601986; producer принимает эквивалентные CAP_* перед exact whitelist, flow/signature protocol/ownerD417 unchanged. Current authorize SHA6b3e990d… и preflight90ef0e16… зафиксированы в [Q008 code gates](dev29-q008-runtime-review.md) и q008-runtime-code.json. Исторические003 SHA ниже относятся к первоначальной подготовке. Последний exact snapshot проверяется отдельно до Observe; runtime admission от этого текста не создаётся.

2026-11-03, DEV29-Q007/D-417. **AUDIT-SIGNER-REVIEW-003 APPROVED** только для offline audit-only preparation. Реальные Observe/IssueAudit/Audit не выполнялись и данным ревью не создаются. Явное разрешение владельца на read-only Audit уже записано D-417; повторное согласование того же объёма после запуска engine не требуется.

## Закрытые замечания

| ID | Приоритет | Замечание | Закрытие |
|---|---|---|---|
| AUDSIG-REV-001 | P1 | Unsigned observation/approval не доказывали фактический preflight | CLOSED в002: отдельный HMAC observation receipt связывает producer/review/owner/plan/sanitized facts/context/engine/DB ID; signer проверяет подпись и повторяет inspect predicates |
| AUDSIG-REV-002 | P1 | Admission не сохранял долговечную связь с владельцем/review/observation | CLOSED в002: отдельный once-written signed authorization receipt до admission, hashes decision/signer/reviews/observation/approval/Verify/payload/raw admission/input files |
| AUDSIG-REV-003 | P2 | Workflow race между первым check и записью | CLOSED в002: exclusive audit-signing.lock, повтор forbidden/input hashes перед ключом и записью, once receipt/admission, частичные артефакты сохраняются |
| AUDSIG-REV-004 | P1 | Тестировались только валидаторы, не IssueAudit orchestration | CLOSED в002: actual injectable issueAuditFlow и VM188, gates/Verify/lock/rechecks/key/auth/receipt/admission, early failure без ключа, race/retry/partial/safe errors |
| AUDSIG-REV-005 | P1 | Не тестировалась actual Observe цепочка, читающая реальный ключ | CLOSED в003: exported observeFlow и VM329 импортируют фактический код; exact6 read-only команд, owner/review/Verify/timeout/JSON/topology/writes/key/repeat проверены без реальных вызовов |
| AUDSIG-REV-006 | P2 | Полные Docker objects могли сохранить лишние данные | CLOSED в003: sanitizeFacts сохраняет только выбранный evidence DTO; Env/proxy/registry/TLS extras/host mount Source исключены, private canary не попадает в persisted facts/receipt basis |

## Факт независимой проверки

Рецензент read-only перечитал все7 новых audit*.mjs и подтвердил syntax/inert imports, synthetic preflight21, authorize21, production preflight VM329 и issue VM188 PASS. Старые package9 и candidate31 не менялись; source/контракт controller Audit сохранены. Никакого Docker/SQL/Observe/IssueAudit/Verify/настоящего ключа рецензент не использовал, файлы не редактировал. Обрезанный вывод одной объединённой проверки был разделён на меньшие вызовы; ошибка кода или повтор эквивалентной ошибки не возникали.

Точные SHA всех7 файлов сохранены append-only в ignored `work/dev29-publication-20261103/pg-check/audit-prepared-source.json`. Основные runtime-модули:

- audit-authorize.mjs: `c0f789d7cd77b73397afb4dc1845e18e73d94a9ba9e20753663b72203b28459a`;
- audit-preflight.mjs: `fa4389a89452684d2aa8ba00f459ca4d46be0c26ab9d82ce8b36c03c04f6f807`;
- audit-issue-flow.mjs: `b25cd90a2ff14c768502e20aeae4e1561f17b8945952bbcb9af8539fa390d804`.

Перед реальным Observe/IssueAudit оператор сверяет все7 SHA и raw SHA этого review; append-only observation/approval/auth receipt/admission пока отсутствуют. Код не устанавливает программы/ресурсы/сети/права и не выдаёт разрешение Run. Частичные receipts/locks при ошибке не стираются для повторной попытки.

## Текущий внешний блокер

Docker engine недоступен; единственный diagnostic info вернул отсутствие pipe. Ни Observe, ни signer с реальным ключом, ни Audit/SQL не запускались. Разрешённая задача продолжается после того, как владелец запустит Desktop или отдельно явно поручит его запуск. Старый сайт/VPS не затронуты. DEV-29 около35%, этап8 около31%.
