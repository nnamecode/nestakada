# DEV-08A: безопасное чтение публичной страницы

Дата: 2026-11-09
Основание: D-235, D-691 и устранение устаревшего статуса UX-07.

## Цель

Начать продуктовый DEV-08 с одного небольшого слоя: по точному `Route.target` получить опубликованную страницу и её текущую проверенную редакцию. Пока не переносить 92 страницы, дизайн-медиа, формы, SEO, галерею или HTML fallback.

## Приёмочные сценарии

- `PREAD-001`: PRIMARY опубликованной страницы возвращает её current revision и проверенный payload.
- `PREAD-002`: ALIAS опубликованной страницы возвращает тот же current payload без копии данных.
- `PREAD-003`: REDIRECT возвращает точный PRIMARY той же страницы; цепочки и внешний адрес не создаются.
- `PREAD-004`: неизвестный, SYSTEM и непригодный route не раскрывают данные.
- `PREAD-005`: unpublished page закрыта; published child под unpublished ancestor также закрыт без изменения его флага.
- `PREAD-006`: отсутствующий current, чужая revision, повреждённый payload/hash или некорректная schema дают закрытый отказ, а не частичную страницу.
- `PREAD-007`: чтение не пишет в Page/Route/PageRevision/PageContentState/AuditEvent и не создаёт session/cookie.
- `PREAD-008`: запрос остаётся ORM/parameter-bound; ввод не становится SQL, Django template или JavaScript.

## Не входит

HTML/CSS-шаблон, Header/Footer composition, media URLs, navigation tree, robots/sitemap, формы, заявки, аналитика и production. Следующий DEV-08B использует этот DTO для публичного шаблона после PASS и review DEV-08A.

## Статус D-693

Реализован только `content.public_read`: exact ORM lookup, PRIMARY/ALIAS verified DTO, REDIRECT напрямую к PRIMARY той же страницы, публикация всех предков, current/page/schema/payload hash integrity и закрытые `PublicNotFound`/`PublicUnavailable`. Добавлены 6 focused tests и точный `public-read` selector существующего test harness; новых зависимостей, таблиц, миграций и фоновых процессов нет.

Focused6/6 PASS за0.321с. Существующий content/security regression231/231 PASS за176.012с. Первый ошибочный вызов через runtime app остановился до тестов на ожидаемом запрете `CREATE DATABASE`; повтор выполнен изменённым штатным unit-профилем, третьей попытки не было. Independent review запущен; до `APPROVED` DEV-08A не завершён.

## Итог D-694

Первый review нашёл будущий open redirect: повреждённый stored PRIMARY мог попасть в HTTP location без read-time проверки. Добавлена одна закрытая проверка назначения через `exact_target`; повреждение даёт `PublicUnavailable`. Тесты дополнены raw invalid PRIMARY, глубоким скрытым предком, отдельными повреждениями revision schema, payload schema и payload shape.

После исправления focused9/9 PASS за0.425с, content/security234/234 PASS за176.899с, Django check PASS, migrations no changes, diff clean. Repeat independent review — `APPROVED`, P1/P2/P3 нет. Стенд остановлен с сохранением томов. DEV-08A завершён; следующий отдельный этап DEV-08B ещё не начат.
