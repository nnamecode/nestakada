# TEST-08 base MVP — независимое ревью плана

Дата: 2026-11-15. Verdict: **APPROVED**, P1/P2/P3=`0/0/0`.

Рецензент read-only подтвердил:

- admission соответствует выбранному владельцем варианту 1 и не возвращает DEV-26/27, intake/ПД, SMTP/Telegram, analytics/widgets или внешние production gates;
- фактическая матрица равна 17 `text_only` + 20 `partial_http` + 103 `assertions_waiting_driver` = 140;
- stage9 evidence только переиспользуется, а TEST-08 не подменяет TEST-09/10 или launch;
- существующий Playwright harness честно не считается e2e сайта без общего fixture/bindings и не предлагается к запуску;
- будущий fixture ограничен test environment, отдельной test DB, synthetic identities, default-off integrations, existing packages, manifest/cleanup и запретом новых production endpoint/model/migration/dependency/runner/content format;
- exact10 групп ограничивают base-MVP scope, а точные scenarios/evidence IDs должны быть записаны в execution plan до запуска;
- wildcard, прямой широкий `manage.py test`, Playwright, production import и внешняя сеть запрещены;
- PARTIAL/BLOCKED не агрегируются в PASS, правило остановки после второй эквивалентной ошибки сохранено;
- план не разрешает fixture implementation или execution.

Docker, Foundation, тесты, Playwright, сеть и live не запускались; рецензент файлы не изменял. Следующий допустимый этап — отдельный минимальный план изолированного TEST-08 fixture, затем его независимое ревью и явное разрешение владельца до реализации.
