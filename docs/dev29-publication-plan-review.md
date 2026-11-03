# DEV-29: независимое ревью плана P29-A

Дата: 2026-11-03. Артефакт: `dev29-publication-plan.md`. Рецензент работал read-only, файлы не менял. Итог PLAN-REVIEW-002: **APPROVED для передачи владельцу на DEV29-Q005**, не разрешение реализации вместо владельца.

PLAN-REVIEW-001: CHANGES REQUIRED. Исправлены и независимо закрыты:

- PLAN-REV-001/P1: TRUST получает непрозрачный basis hash и не может проверить action внутри него. A29-001 теперь проверяет wire shape/fingerprint; предметный action/basis остаётся APP B/D.
- PLAN-REV-002/P1: prepare/report имеют разные fingerprints, первый корректный mainReceipt/mainIncarnation принимается от authenticated writer. A29-002 проверяет policy equality, формат и PHASE_CONFLICT при изменённом replay; происхождение APP proof этим не доказывается.
- PLAN-REV-003/P2: consumer проверяет UUID/shape/generation/digest/key-target, но не имеет APP Page/Route mapping. A29-005 оставляет предметную привязку P29-C.

PLAN-REVIEW-002: все три замечания CLOSED, новых противоречий с D-410/Q004, границами P29-A и A29-001–008 не найдено. APP/сеть/credentials/Boolean/MAIN/рабочий writer/permit/production остаются за пределами участка. Fixture не заменяет APP/cohort/EDGE e2e.

Одна ошибка инструмента в первом ревью: Windows glob был передан rg как буквальный путь; исправленный вызов с `-g` успешен, эквивалентного повтора ошибки не было. Runtime/БД не запускались.
