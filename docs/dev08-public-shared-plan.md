# DEV-08D: безопасные Header/Footer на публичной странице

Дата: 2026-11-09
Основание: D-066, завершённые DEV-08C / D-702 и DEV07-SH-PUB / D-356.

## Цель

Подключить к реальной публичной странице уже реализованный `shared_content.public.render_shared`, не создавая второй reader, storage, lifecycle, HTML cache или фоновый процесс. Реальный host передаёт renderer только проверенную текущую страницу и навигацию DEV-08A/C; после финальной повторной проверки из того же снимка собирается body.

## Приёмочные сценарии

- `PSH-001`: опубликованная PRIMARY/ALIAS-страница показывает ровно один current Header и один current Footer; header получает точные PRIMARY-ссылки DEV-08C, а draft/history/stage не публикуются.
- `PSH-002`: host stamp однозначно включает используемые `PublicPage`, payload и navigation. Изменение страницы, меню или shared current между capture и recheck даёт согласованный новый ответ после не более одной повторной попытки либо закрытый `503`, но не смешанный HTML.
- `PSH-003`: отсутствующий, несовместимый или повреждённый current Header/Footer, payload/hash/schema, AssetUsage/READY media либо private bytes даёт обезличенный `503 no-store`; содержимое повреждения и private path не выдаются.
- `PSH-004`: Header/Footer проходят существующий закрытый parser/hydration; сохранённый Django/Python/JavaScript template source не исполняется. Page rich HTML сохраняет DEV-08B equality guard и также не исполняется как шаблон.
- `PSH-005`: production URLConf выдаёт только существующие verified shared media и два фиксированных versioned shared asset. Неизвестные UUID, filename/digest, private/history/draft-only media и недопустимые методы закрыты готовыми response-функциями.
- `PSH-006`: GET/HEAD/If-None-Match используют готовый составной ETag, учитывающий страницу, меню, Header/Footer, media и trusted assets; старый ETag не скрывает повреждение. Ответ имеет строгий self-only CSP.
- `PSH-007`: неизвестный public target остаётся `404`, REDIRECT остаётся прямым `301` и оба пути не читают shared blocks. Ошибка shared/database/storage на существующей странице становится `503`.
- `PSH-008`: anonymous GET/HEAD/304/media/static не создают session/cookie и не пишут Page/Route/PageRevision/PageContentState/shared/audit. `/manage` сохраняет приоритет и прежние права.

## Минимальная реализация

- маленький host-adapter в `content`, который повторно получает существующие `PublicPage` + `public_navigation()` и строит typed `HostContext`/`NavItem`;
- существующий `render_shared` и существующие `html_response`, `media_response`, `static_response` без копирования их проверок;
- существующий публичный template оборачивает body в уже проверенные `header_html`/`footer_html` и подключает versioned `public-shared.css/js`;
- три точных production routes: shared media, shared CSS и shared JS перед последним catch-all.

## Не входит

Новый кэш готового HTML, новые таблицы/зависимости/background jobs, изменение editor/shared lifecycle, перенос реальных материалов, новый дизайн Header/Footer, SEO/price/forms/fallback/production deployment.

## Рентабельность

Новый renderer или упрощённая копия существующего отклонены: они дублировали бы уже проверенные integrity/media/race/security правила. DEV-08D ограничен адаптером и routing/composition, необходимыми для запуска публичной страницы.

## Статус D-703

Сценарии `PSH-001–008` записаны до продуктового кода. Подтверждено, что `shared_content.public.render_shared` уже закрывает current Header/Footer, schema/hash, READY media, bounded retry и составной ETag; `shared_content.public_views` уже закрывает HTTP static/media. Реализация начата только как production host-adapter и подключение этих готовых функций.

## Итог D-704

DEV-08D завершён. Добавлены typed `PublicSharedHost`, композиция существующего safe renderer, три точных resource route и typed `NavItem.current` для `aria-current` без второго меню. Header/Footer, Page body и navigation берутся из одного финально перепроверенного снимка; неизвестный target и direct redirect обходят shared renderer. Ошибки current/schema/hash/media/storage закрываются `503 no-store`; HTML/template source не исполняется.

Проверки: `public-shared-page` 3/3 PASS за 23.041с; `public-http` 8/8 PASS; `public-nav` 5/5 PASS; существующий `shared-public` 10/10 PASS за 115.881с; общий guard 250/250 PASS за 223.027с. Django check PASS, migrations no changes, diff-check clean. Первые focused-запуски выявили только три разные ошибки тестовой оснастки (коллизия helper-name, ошибочное требование порядка HTML-атрибутов, защищённый QuerySet в имитации current); каждая была локализована и изменена до следующего запуска, одинаковая ошибка не повторялась дважды.

Independent review: `APPROVED`, P1/P2/P3 нет. Reviewer подтвердил coherent final capture, закрытые safe-render границы, backward-compatible `NavItem.current`, exact resource routes/session bypass и отсутствие нового storage/lifecycle/cache/schema/background слоя. Production/VPS/старый сайт не затронуты.
