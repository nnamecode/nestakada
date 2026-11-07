# REF-07A: удаление изолированного TRUST-контура

Дата: 2026-11-06
Основание: D-660, явный ответ владельца «Продолжай» на `REF-Q004`.
Граница: только R7-I001 из `docs/ref7-dead-code-inventory.md`; БД, migrations и R7-I002/R7-I003 не меняются.

## Приёмочные сценарии

- `R7A-001`: удалены все tracked-файлы `trust/**`, `environment/trust/**`, `tools/dev29/**`, именованные TRUST tools/tests и `scripts/local-trust.ps1`; резервная копия исходников внутри репозитория не создаётся, восстановление остаётся в Git.
- `R7A-002`: вне документации и исторических migrations нет runtime/config/CI ссылок на `trust_service`, `trust-db`, TRUST environment или удалённые entry points.
- `R7A-003`: foundation compose/config не требует TRUST service, network, volume, secret или environment variable; обычный foundation config проходит проверку.
- `R7A-004`: Django system check и migration drift check проходят без TRUST source/settings.
- `R7A-005`: затронутые security/session/content/page-version regressions проходят на PostgreSQL; ORM, parameterized SQL, scanner filter, CSRF, роли и throttling не ослаблены.
- `R7A-006`: backup/restore scripts и их pinned foundation dependencies не ссылаются на удалённый контур; текущие backup generations не меняются.
- `R7A-007`: Git diff содержит только согласованные удаления и документы REF-07A; секреты, дампы, логи и оригиналы фотографий не добавлены.
- `R7A-008`: независимое ревью не имеет открытых P1/P2; production, VPS и старый сайт не затронуты.

## Выполнение

1. Удалить точный список 91 tracked-файла из R7-I001.
2. Выполнить статические проверки ссылок и diff.
3. Запустить foundation/Django checks и релевантные PostgreSQL regressions точными путями без wildcard.
4. Остановить стенд с сохранением volumes и подтвердить отсутствие остаточных TRUST containers/resources.
5. Передать точный diff независимому рецензенту.

`AuthSession`, `AuthResourceState`, `OperationReceipt`, `IdentityReservation`, `RestoreStage`, `VersionBasePin`, `shared_content`, migrations и данные не входят в REF-07A.
