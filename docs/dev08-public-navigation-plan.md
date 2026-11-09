# DEV-08C: read-only публичная навигация

Дата: 2026-11-09
Основание: D-032 и завершённый DEV-08B / D-699.

## Цель

Добавить к существующему публичному шаблону простую навигацию по реально доступным опубликованным страницам. Не менять старую административную проекцию `content.reads.public_tree()`: она поднимает опубликованного ребёнка через скрытого предка и потому не соответствует публичной доступности DEV-08A.

## Приёмочные сценарии

- `NAV-001`: опубликованные страницы с опубликованными предками и валидным PRIMARY входят в навигацию в порядке `position,id`; имя и точный URL возвращаются как данные.
- `NAV-002`: unpublished page и всё её поддерево исключаются, даже если у ребёнка собственный `is_published=True`.
- `NAV-003`: ALIAS, REDIRECT и SYSTEM не создают дополнительные пункты; пункт всегда ведёт на PRIMARY той же страницы.
- `NAV-004`: видимая опубликованная страница без PRIMARY или с повреждённым stored PRIMARY закрывает проекцию как `PublicUnavailable`, а не создаёт битую/внешнюю ссылку.
- `NAV-005`: cycle/disconnected/corrupt tree закрывается как `PublicUnavailable`; обход ограничен числом фактически прочитанных страниц.
- `NAV-006`: текущая страница, в том числе открытая через ALIAS, помечается `aria-current="page"`; имена и URL экранируются шаблоном.
- `NAV-007`: чтение навигации не пишет Page/Route/PageRevision/PageContentState/AuditEvent, не создаёт session/cookie и не использует пользовательский HTML/JS/template source.
- `NAV-008`: отказ БД или повреждение навигации даёт существующий обезличенный `503`; неизвестная запрошенная страница по-прежнему даёт `404` до построения навигации.

## Минимальная реализация

- один frozen DTO `PublicNavigationItem` и одна read-only функция рядом с DEV-08A resolver;
- один проход по Page и PRIMARY Route, без рекурсивных SQL-запросов и без кэша;
- существующий публичный шаблон получает плоский pre-order список безопасных ссылок;
- существующие `public_tree`, админка, модели и schema не меняются.

## Не входит

Shared Header/Footer, выпадающие меню и сложная визуальная иерархия, media, price, SEO/ETag, forms, fallback, production и перенос реальных страниц.

## Статус D-701

Реализованы frozen `PublicNavigationItem`, две read-only выборки Page+PRIMARY, bounded pre-order с полным cycle/disconnected контролем, исключение hidden subtree и fail-closed invalid/missing PRIMARY. Existing `public_tree` не менялся. Template выводит escaped exact links и `aria-current` для current Page, включая ALIAS request.

Focused NAV5/5 PASS за0.383с; content/security guard247/247 PASS за202.867с; Django check PASS, migrations no changes, diff clean. Новых schema/dependencies/cache/background process нет. Independent review запущен; до `APPROVED` DEV-08C не завершён.

## Итог D-702

Independent review — `APPROVED`, P1/P2/P3 нет. Подтверждены стабильный sibling/pre-order, hidden subtree closure, exact PRIMARY validation, cycle/disconnected/missing-primary503, escaped links, alias current marker, no-write/session и отсутствие лишней архитектуры. Возможная concurrent change даёт только краткий in-flight старый снимок или503 и не раскрывает hidden subtree; общий lock/cache признан непропорциональным текущему read-only масштабу.

DEV-08C завершён, foundation stopped. Следующий отдельный этап DEV-08D — reuse существующих safe Header/Footer; не начат.
