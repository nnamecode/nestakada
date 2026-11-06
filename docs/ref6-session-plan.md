# REF-06A — стандартные Django sessions и отзыв generation

Дата: 2026-11-06.
Основание: D-600, D-601, D-634, REF-AC-031 и поручение владельца «Продолжай».
Статус: приёмочный контракт записан до кода.

## Граница

Переключить действующий вход, закрытые страницы и editor-session check с двойного реестра `django_session + AuthSession` на одну стандартную серверную Django session. В session хранятся только user identity Django, `UserProfile.generation`, время выдачи и последнее активное обращение. Сохраняются idle 30 минут, absolute 12 часов, owner identity `nesadmin`, две роли, CSRF/private headers, password hashing и `LoginThrottle`.

`AuthSession`, `AuthResourceState`, старые настройки, миграции и legacy-тесты физически не удаляются в этом инкременте: удаление остаётся REF-Q004. Логи, HTML-резерв, заявки и backup не входят.

## Приёмочные сценарии

- **SESS-001 — один runtime session store.** Успешный вход создаёт одну Django `Session` с exact user/generation/issued/last-seen и не создаёт `AuthSession`; logout удаляет Django session.
- **SESS-002 — строгая session identity.** Отсутствующие, malformed, чужие user/generation/timestamps, inactive user, неизвестная роль и owner не `nesadmin` получают закрытый 401 без traceback/секретов.
- **SESS-003 — сроки.** Активный закрытый запрос продлевает idle до 30 минут, но не absolute 12 часов; passive `/manage/session/` не продлевает. Clock rollback закрывает session.
- **SESS-004 — generation revoke.** Reset password, disable/enable, изменение или отзыв PageGrant атомарно увеличивают generation. Все прежние sessions теряют доступ на следующем закрытом запросе; новая session видит только актуальные права.
- **SESS-005 — recovery.** Owner recovery и trusted invalidate-all увеличивают generation и отзывают все прежние sessions без обхода через оставшиеся Django rows.
- **SESS-006 — editor checks.** Все page/shared editor команды проверяют ту же Django session, актуальные user/profile/generation/active/role и сроки; удалённая, устаревшая или malformed session отклоняется до записи.
- **SESS-007 — concurrency.** Два активных запроса сериализованно сохраняют монотонный last-seen; более ранний запрос не может затереть более позднее время или продлить absolute limit.
- **SESS-008 — отказ и аудит.** DB/audit failure не создаёт частично вошедшую session; password/session payload не попадают в HTML/audit. Permission denial пишет один bounded event без старых lower-bound counters.
- **SESS-009 — throttle неизменен.** Порог 5/10 минут, блок 15 минут, per-IP source validation, dummy hash и concurrency пятой ошибки продолжают работать; session cap/`AuthResourceState(kind=sessions)` больше не участвуют во входе.
- **SESS-010 — переходность.** Основной runtime не читает и не пишет `AuthSession`; таблица и historical data сохраняются до REF-Q004. Новых зависимостей, API, CAPTCHA, 2FA и email confirmation нет.

## Проверки

Focused accounts/session/editor tests на PostgreSQL; реальные revoke и concurrent touch; затем `accounts`, связанные content/page_versions/page_editor/shared_content наборы, migration/diff checks, независимое review, read-only main DB/login и Stop.
