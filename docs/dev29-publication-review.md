# DEV-29: независимое ревью предложения публикации

Дата: 2026-11-03. Объект: `docs/dev29-publication-proposal.md`. Итог: **APPROVED для передачи владельцу на архитектурное согласование**. Это ревью не является утверждением архитектуры и не разрешает реализацию.

Рецензент работал только на чтение, не изменял файлы и не подменял проверкой собственное изменение.

## Ход ревью

| Проверка | Итог | Замечания и закрытие |
|---|---|---|
| DEV29-PUB-REVIEW-001 | CHANGES REQUIRED | PUB-REV-001: нужен доказанный EDGE close до APP-коммита unpublish. PUB-REV-002: сохранить D-307 normal Nginx→Django и честную границу видимости. PUB-REV-003: закрыть wire-инварианты. PUB-REV-004: разделить неизвестные фазы и CAS. PUB-REV-005: уточнить session/restart continuation. Все исправлены и закрыты в REVIEW-002. |
| DEV29-PUB-REVIEW-002 | CHANGES REQUIRED | PUB-REV-006: старый `is_published=True` после restore мог обойти более новый TRUST HIDDEN. PUB-REV-007: неоднозначен объём будущего ответа DEV29-Q004. Оба исправлены и закрыты в REVIEW-003. |
| DEV29-PUB-REVIEW-003 | CHANGES REQUIRED | PUB-REV-008: один cohort receipt не доказывал две разные фазы. PUB-REV-009: acceptance преждевременно разрешал пустой 200 во время PENDING_DENY. Оба исправлены и закрыты в REVIEW-004. |
| DEV29-PUB-REVIEW-004 | APPROVED | Отдельные immutable prepare/final cohort receipts, `mainReceipt` и COMPLETE согласованы; до доказанного HIDDEN + final cohort сохраняется 503. Новых противоречий не найдено. |

## Что независимо подтверждено

- normal-start/restore barrier сверяет свежий TRUST snapshot до допуска APP cohort и не доверяет старому Boolean после отката APP;
- локальный deny-only срез не является удалённым per-request gate и не может сам опубликовать скрытую в APP страницу;
- публикация открывает normal traffic только после TRUST final `LIVE_NO_SET` и полного final cohort receipt;
- снятие публикации требует prepare cohort receipt и реального независимо проверенного EDGE close до APP-коммита; до final HIDDEN сохраняется контактный 503;
- prepare/final receipts неизменяемы и не взаимозаменяемы, exact replay и restart сверяют phase/head/generation/fingerprint;
- сеть не ожидается под APP locks/транзакцией, роли reader/writer/recovery разделены, feature flag остаётся выключенным;
- `DEV29-Q004` просит утвердить или отклонить только архитектуру. Даже положительный ответ не разрешает код: сначала нужен отдельный точный план и разрешение владельца.

## Открытая граница

Архитектура ещё не утверждена владельцем. EDGE gate, IPC/readiness/fencing APP cohort, production, внешний TRUST, ночной HTML, URL/delete, старый сайт и VPS в этой работе не реализовывались и не проверялись.
