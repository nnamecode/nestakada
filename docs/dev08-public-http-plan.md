# DEV-08B: минимальный публичный HTTP/HTML

Дата: 2026-11-09
Основание: D-694 и возобновление DEV-08B-Q001 владельцем.

## Цель

Подключить готовый read-only resolver DEV-08A к последнему публичному маршруту Django и одному безопасному серверному шаблону. Не строить сейчас полный публичный layout или новую платформу представлений.

## Приёмочные сценарии

- `HTTP-001`: точный PRIMARY, включая сохранённую query-строку, возвращает `200` и выводит name/title/h1/intro/main из проверенной current revision.
- `HTTP-002`: ALIAS возвращает тот же проверенный HTML без копии данных и без изменения URL.
- `HTTP-003`: REDIRECT возвращает постоянный internal redirect точно на PRIMARY той же страницы; цепочка и внешний адрес не создаются.
- `HTTP-004`: неизвестный, SYSTEM, unpublished и скрытый предком адрес возвращают обычный закрытый `404`, не раскрывая причину или данные.
- `HTTP-005`: отсутствующий/чужой/damaged current, schema/hash или непригодный сохранённый rich HTML возвращают постоянный закрытый `503` без внутренней диагностики.
- `HTTP-006`: публичная view принимает только `GET`/`HEAD`; `HEAD` не содержит body, а иные методы не изменяют состояние.
- `HTTP-007`: успешный, redirect, `404`, `503` и `405` не пишут Page/Route/PageRevision/PageContentState/AuditEvent, не создают session/cookie и используют безопасную cache policy.
- `HTTP-008`: сохранённые строки остаются данными: Django template markers не исполняются, опасный HTML/JavaScript fail closed, ORM остаётся parameter-bound.

## Минимальная реализация

- catch-all располагается последним после всех `/manage/` routes;
- request target берётся как точный `request.get_full_path()`;
- view переводит только доменные `PublicNotFound`/`PublicUnavailable` в `404`/`503`;
- rich HTML перед доверенным выводом обязан совпасть с результатом закрытого allowlist-cleaner;
- шаблон получает только DTO-поля, не имя шаблона и не исполняемый source.

## Не входит

Shared Header/Footer, навигация, media URLs, layout/embedded images, price UI, SEO/canonical/robots/sitemap, ETag/304, формы и заявки, аналитика, HTML fallback, production/VPS и перенос реальных страниц. Эти части требуют отдельных маленьких этапов после PASS и independent review DEV-08B.

## Статус D-697

Реализованы final catch-all вне `/manage`, exact `request.get_full_path()`, закрытые404/503, direct301, GET/HEAD/405, один template и fixed CSS. Перед trusted rich-HTML render сохранённые intro/main обязаны без изменений пройти closed allowlist-cleaner; template markers остаются данными.

Focused HTTP8/8 PASS за0.260с; content/security guard242/242 PASS за199.192с; Django check PASS, migrations no changes, diff clean. Первый guard выявил, что первоначальный catch-all менял неизвестный employee `/manage/password/` с404 на405; regex исключил весь `/manage`, повторный guard PASS. Первый новый regression ошибочно ожидал anonymous404 вместо штатного middleware401 и был исправлен как test expectation. Independent review запущен; до `APPROVED` DEV-08B не завершён.

## Статус D-698

Independent review приостановлен владельцу на `DEV-08B-Q002`, implementation/checks не отбрасываются. Reviewer полностью просмотрел план, product code, реальный `app/content/public.css`, template, tests, routes, suite и D-696/D-697; явных P1/P2 в просмотренном scope не нашёл. Первая ошибка — запрос отсутствующего `app/content/assets/public.css`; вторая — отсутствующего `app/estakada/settings.py`. Третьей попытки нет. Для завершения review использовать только подтверждённый `app/estakada/settings/base.py` и проверить оставшийся middleware/routing context.

## Итог D-699

Finish-review нашёл P1: `SessionPayloadMiddleware` до view загружал session для любого public path, поэтому cookie создавал ненужную DB-зависимость и мог обойти закрытый503 при отказе БД. Middleware ограничен exact `/manage` и `/manage/...`; public page/CSS с cookie и падающим session backend доказывают `load()` calls0, response cookie0, а resolver `DatabaseError` по-прежнему даёт503.

После remediation focused8/8 PASS за0.496с, guard242/242 PASS за202.069с, Django check PASS, migrations no changes, diff clean. Repeat independent review — `APPROVED`, новых P1/P2/P3 нет. Foundation stopped, volumes retained. DEV-08B завершён; следующий отдельный DEV-08C navigation ещё не начат.
