# REF-07B: удаление legacy `AuthSession`

Дата: 2026-11-06
Основание: D-663 и явный ответ владельца «Продолжай» на `REF-07B-Q001`.
Граница: только модель/таблица `accounts.AuthSession`, её runtime-нулевые тестовые ссылки и новая миграция. `django_session`, `AuthResourceState`, `LoginThrottle` и R7-I003 не меняются.

## Приёмочные сценарии

- **ASDROP-001 — точные данные до удаления.** Перед миграцией read-only запрос подтверждает exact count legacy `AuthSession`, Django `Session` и основные контрольные counts; никакие строки не удаляются вручную.
- **ASDROP-002 — восстановимая точка.** До миграции создаётся новое проверенное поколение local PostgreSQL+media backup; isolated restore-check его current generation проходит. Backup не попадает в Git.
- **ASDROP-003 — узкая schema migration.** Новая migration после `accounts.0003` содержит только `DeleteModel(AuthSession)`; historical migrations не редактируются, посторонних schema changes нет.
- **ASDROP-004 — одна session-система.** Модель удалена из `accounts.models`, runtime/tests больше её не импортируют; стандартная DB-backed Django `Session` и generation/issued/last-seen остаются единственным session store.
- **ASDROP-005 — безопасность неизменна.** Login/logout, idle/absolute expiry, password/active/PageGrant revoke, malformed-session fail-closed, CSRF, роли, throttle и private headers проходят прежние проверки.
- **ASDROP-006 — миграции.** Forward migration удаляет только таблицу `accounts_authsession`; migration plan и drift clean. На отдельной синтетической test DB проверяется reverse schema recreation и повторный forward; исторические три строки восстанавливаются только из ASDROP-002 backup, что явно документируется.
- **ASDROP-007 — стабильность.** Accounts, affected shared/content/page-version/editor и полный штатный PostgreSQL test suite проходят; основной контрольный набор данных кроме legacy AuthSession не меняется.
- **ASDROP-008 — завершение.** Static refs0, diff/secret checks PASS, foundation stopped с volumes, independent review без P1/P2. Production/VPS/старый сайт и orphan TRUST volume не затрагиваются.

## Порядок

1. Снять read-only counts и fresh pre-migration backup; восстановить current изолированно.
2. Добавить `accounts/migrations/0004_delete_authsession.py`, удалить модель и заменить legacy-only test assertions.
3. На новом source snapshot выполнить migration checks, focused и полный regression-набор.
4. Проверить synthetic reverse→forward без заявления о возврате удалённых строк.
5. Остановить стенд, подтвердить сохранность pre-migration backup и передать diff независимому рецензенту.

Удаление трёх исторических строк является ожидаемым и разрешённым результатом REF-07B. Оно не разлогинивает действующие Django sessions, поскольку runtime не читает `AuthSession` после REF-06A.
