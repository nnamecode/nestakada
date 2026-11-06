# REF-05M — простое изменение URL новой страницы

Дата: 2026-11-06.
Основание: D-023, D-243/D-244, D-590, D-601, D-627 и поручение владельца «Продолжай».
Статус: приёмочный план записан до кода.

## Граница

Инкремент добавляет отдельную owner-only команду изменения точного PRIMARY URL только для страницы, созданной новой системой (`is_legacy=False`). Перенесённый legacy PRIMARY не изменяется. Старый PRIMARY становится бессрочным `REDIRECT` на ту же Page; существующий read projection всегда вычисляет destination через актуальный PRIMARY, поэтому повторные смены не образуют цепочек.

Удаление страницы/redirect, изменение URL детей, HTML build/fallback, публичный renderer, schema/migrations и удаление legacy-кода вне инкремента. REF-Q004 закрыт.

## Приёмочные сценарии

- **URLC-001 — права и сессия.** GET/POST доступны только `nesadmin` с актуальными generation/editor-session и CSRF; сотрудник/анонимный/прямой запрос не меняют маршруты.
- **URLC-002 — защита legacy.** PRIMARY с `is_legacy=True` отклоняется до формы и при POST. Alias/redirect legacy-флаги не дают разрешения менять защищённый PRIMARY.
- **URLC-003 — точное подтверждение.** Форма явно показывает страницу и старый URL, принимает один новый URL. Token связывает actor, generation, page, operation, locked PostgreSQL `xmin` страницы и exact PRIMARY (id/xmin/target/kind/page/legacy). Подмена page/token/operation отклоняется.
- **URLC-004 — проверка нового адреса.** Новый URL не нормализуется и проходит существующие `exact_target`, `new_target`, scanner/private namespace validators и byte/length limits. Совпадение с PRIMARY/ALIAS/REDIRECT/SYSTEM любой страницы отклоняется; адрес действующего redirect занят.
- **URLC-005 — одна локальная transaction.** Успех изменяет target существующего PRIMARY, создаёт один non-legacy REDIRECT со старым exact target на ту же Page и один `TREE_URL_CHANGE` audit. Page/name/kind/parent/position/publication, revisions/Stable/drafts/media и остальные Route неизменны.
- **URLC-006 — повторные смены без цепочек.** После A→B→C запросы A и B дают redirect сразу на C через актуальный PRIMARY. Дочерние PRIMARY/alias не меняются; циклы не создаются.
- **URLC-007 — публикация не подменяется.** Redirect сохраняется и для hidden Page; destination остаётся текущим PRIMARY, а конечный URL сохраняет обычное published/hidden поведение. URL-команда не меняет `is_published`.
- **URLC-008 — stale/ABA/concurrency/no-op.** PRIMARY/page `xmin` отклоняет изменение и ABA после GET, второй concurrent submit и старое подтверждение. Новый URL, равный текущему, отклоняется. Изменение несвязанной страницы не инвалидирует форму.
- **URLC-009 — отсутствие ledger и rollback.** Новые `OperationReceipt`/`IdentityReservation` не создаются. Ошибка route/audit/DB откатывает PRIMARY и REDIRECT. Если commit произошёл, но HTTP вернул 503, точный повтор конфликтует без второго redirect/audit; форма сохраняет только operation/token/new target и CSRF.
- **URLC-010 — совместимость и границы.** Rename/reorder/move/create/publish/hide и legacy receipt replay не меняются. Нет сетевого TRUST/intent/head, фоновой задачи, удаления route или автоматического изменения навигации/дочерних URL.

## Проверки

1. Focused command/HTTP/fault/concurrency/read tests URLC-001–010.
2. Полный `content` и соседний `media_library + page_versions` regression.
3. `makemigrations --check --dry-run`, `git diff --check`, read-only main DB/login.
4. Независимое review завершённого инкремента.
5. Штатный Stop foundation-test; production/VPS/старый сайт не затрагиваются.
