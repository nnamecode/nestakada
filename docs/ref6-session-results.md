# REF-06A — результат стандартных Django sessions

Дата: 2026-11-06. Решение: D-637. Приёмочный контракт: SESS-001–010 из `docs/ref6-session-plan.md`.

## Результат

Runtime входа, закрытых HTTP-страниц и editor-команд переключён с двойного `django_session + AuthSession` на одну стандартную server-side Django session. В ней хранятся только стандартная Django identity, текущий `UserProfile.generation`, время выдачи и последнее активное обращение.

Сохранены idle 30 минут, absolute 12 часов, passive session check без продления, немедленный revoke через generation после password/active/PageGrant/recovery, роли owner/employee, owner identity `nesadmin`, CSRF, private/no-store, password hashing и `LoginThrottle`.

Строгая проверка требует словарь и точные типы user/backend/hash/generation/timestamps, constant-time сверяет auth hash, проверяет active/profile/role/owner и порядок `issued <= last_seen <= now`. Malformed, foreign, stale, clock-rollback и revoked session удаляется и получает закрытый 401 без traceback или записи. Editor использует тот же validator.

`AuthSession`, `AuthResourceState`, старые миграции и historical rows не удалялись: это legacy до отдельного REF-Q004. Новых зависимостей, API, CAPTCHA, 2FA или email confirmation нет.

## Проверки

- `accounts + page_versions.test_http + page_versions.test_simple_commands`: 66/66 PASS за 54.946 с.
- Затронутые `page_editor` HTTP/UI-наборы: 87/87 PASS за 306.686 с.
- `content.test_creation + shared_content.test_simple_commands`: 21/21 PASS за 29.067 с.
- `makemigrations --check --dry-run`: `No changes detected`.
- `git diff --check`: PASS.
- Login smoke: HTTP 200, `Cache-Control: private, no-store`.
- Независимое повторное ревью после закрытия P1 malformed payload: `APPROVED`, новых замечаний нет.

Read-only основная локальная test-БД не изменилась: pages 6, revisions 22, states 6, Stable 0, drafts 1, stages consumed/held 3/0, owner pins 1, receipts 396, identities 765, legacy AuthSession 3, Django Session 3.

Широкие legacy shared reservation/public/cancel наборы не включались: они требуют отдельный `RC_TEST_STATE_ROOT_REQUIRED` и не относятся к заменённому session runtime. Проверены связанные простые shared-команды. Production, VPS и старый сайт не затрагивались.

## Следующая точка

Текущий этап — REF-06/REF-6. Следующий ограниченный инкремент следует выбрать отдельно и до кода записать его приёмочные сценарии. Полный объём раздела логов по D-037/D-038 пока не утверждён. Удаление legacy-кода и таблиц по REF-Q004 остаётся закрытым.
