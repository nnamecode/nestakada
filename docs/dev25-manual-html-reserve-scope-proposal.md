# DEV-25 — ручной HTML-резерв: ограниченное предложение области

Дата: 2026-11-12. Статус: `DEV25-Q001` утверждён владельцем в D-867; final repeat scope review D-870 `APPROVED`, P1/P2/P3=0. Продуктовый код не начат. Готовится короткий implementation plan; после его review требуется отдельное разрешение реализации.

Основание: D-592, `docs/simplification-refactoring-plan.md`, REF-AC-017–021 и REF-AC-032. DEV-25 создаёт проверенный резерв вручную; выдача резерва Nginx и автоматический возврат к Django остаются отдельными DEV-26/27. Документ не разрешает изменение живого сайта, VPS или production.

## 1. Вывод о рентабельности

DEV-25 целесообразен только в узкой форме. Публичный Django-рендерер, маршруты, галерея, shared blocks, медиа и SEO уже существуют, поэтому второй движок сайта не нужен. Текущий инвентарь даёт разумный верхний ориентир: 115 строк route map, 316 строк media evidence и около 59 MB исходных медиа. Ручной запуск снимает scheduler/ночной job/уведомления о расписании; два самодостаточных поколения остаются небольшими для обычного диска.

Если при реализации потребуется очередь, worker, новая модель состояния, отдельная template system, TRUST/head-controller или универсальный crawler, работа останавливается: это выход за утверждаемую рентабельную границу.

## 2. Входит в DEV-25

1. Только владелец `nesadmin` запускает один синхронный build через POST+CSRF в существующей админке. Сотрудник получает 403, anonymous — штатный login/отказ. Повторный пароль не нужен.
2. Один неблокирующий межпроцессный lock запрещает параллельную сборку. Очереди ожидания, фонового worker и scheduler нет.
3. Builder вызывает существующий публичный Django-рендерер внутренними точными GET-запросами. Отдельные шаблоны и повторная реализация правил страниц не создаются.
4. Manifest хранит точные request-target, включая query string. В обязательный набор входят:
   - каждый bounded non-SYSTEM `Route.target`, включая query: опубликованные PRIMARY/ALIAS сохраняются с ожидаемым `200`, hidden PRIMARY/ALIAS — как существующий blank `200`, REDIRECT — с ожидаемыми status и exact `Location`;
   - закрытый генерируемый allowlist галереи: корень, точный `?page=1` redirect, `?page=2`, допустимые `?album=<slug>` и `?page=2&album=<slug>` в единственном каноническом порядке; несуществующий `?page=1&album=<slug>` остаётся unknown/404 и не включается;
   - только известные route/generated targets; произвольные unknown/404 не перечисляются и не превращаются в резервные страницы;
   - только реально упомянутые локальные static/shared/public-media ресурсы.
5. HTML и ресурсы копируются в закрытый staging внутри заранее подготовленного доверенного reserve root. Набор самодостаточен и не зависит от последующего наличия исходного media-файла.
6. Перед активацией проверяются полнота ожидаемых request-target, отсутствие закрытых URL/данных, допустимые ссылки и методы, наличие и digest ресурсов, базовая структура HTML, manifest и числовые пределы.
7. Успешная сборка имеет одну authoritative activation point, которая переводит прежний `current` в единственный `previous`, а новый набор — в `current`. Любой отказ до неё не меняет действующие поколения; после неё generation UUID считается успешно активированным даже при потере HTTP-ответа или ошибке success-audit и не пересобирается вслепую. Старые staging безопасно удаляются только внутри проверенного reserve root. Точный atomic primitive фиксируется в implementation plan.
8. Существующий `AssetUsage.Kind.RETAINED_HTML` привязывает source assets к UUID поколения до activation, поэтому crash может оставить только безопасное переудержание, но не active current/previous без защиты. Bounded reconciliation удаляет лишь доказанно orphan usage/generation и никогда не удаляет current/previous. Это переиспользует существующую защиту media cleanup и не требует новой модели или миграции; точный filesystem/PostgreSQL protocol и fault matrix фиксируются в implementation plan.
9. После публикации контента резерв автоматически не пересобирается. Админка вычисляет `stale`, дату и возраст из manifest и live source stamp. Stamp — bounded digest всех дескрипторов, влияющих на байты набора: exact routes/status/location, publication/tree/current revisions and payloads, shared Header/Footer, media descriptors и сохранённые file digests, SEO/trusted public configuration и локальные static bytes. Физические media bytes сверяются с сохранёнными digest. Ошибка текущей попытки показывается непосредственным owner-ответом и существующим audit event; если интерфейсу нужен устойчивый последний результат, он читает один bounded latest audit event. Новая state table не создаётся.
10. Аудит получает только фиксированные коды начала/успеха/ошибки/занятости без HTML, URL query с пользовательскими данными, содержимого страниц, filesystem paths, cookies и секретов.

## 3. Закрытая граница набора

В HTML-резерв не входят:

- `/manage/`, login, история, preview, черновики, ручные и Stable-версии как отдельные URL;
- POST/PUT/PATCH/DELETE, readiness, admin actions, API и внутренние diagnostics;
- заявки, их содержимое и любые персональные данные;
- sitemap при неизвестной свежести резерва; DEV-26 должен возвращать для него честный отказ, а не устаревший индекс;
- работающая форма заявки. Даже если обычный сайт позже включит приём, trusted internal reserve render context, который невозможно задать через path/query/header/cookie, принудительно исключает intent, CSRF token и рабочий action и показывает только заранее согласованный безопасный disabled fallback без ложного сообщения об успехе;
- внешние scripts/fonts/trackers/iframes и получение ресурсов из сети во время build;
- robots как механизм переключения сайта, SQL dump, media backup и замена обычных DEV-22/23 копий.

## 4. Числовые пределы предложения

Начальные hard caps, которые implementation plan обязан подтвердить тестами и сверить с фактическим инвентарём:

- не более 512 точных response targets;
- не более 1024 локальных resource files;
- не более 4 MiB одного HTML-ответа;
- не более 2 MiB manifest;
- не более 512 MiB одного полного поколения.

Builder использует `cap + 1` там, где это возможно, и отказывает целиком при превышении. Пределы не должны молча отбрасывать URL или ресурсы. Два поколения дают верхнюю границу около 1 GiB плюс один ограниченный staging; фактический набор ожидается существенно меньше.

## 5. Безопасность и устойчивость, которые не сокращаются

- Серверная проверка owner/employee/anonymous, POST-only и CSRF; скрытая кнопка не считается контролем доступа.
- Только allowlisted host, path и query keys. Fetchable/embedded resources и form actions обязаны быть same-origin: внешние scripts/styles/fonts/images/iframes, scheme-relative URL, userinfo и любая сеть во время build запрещены. Обычные navigation links и SEO metadata от trusted renderer проверяются отдельной закрытой схемой/host policy, сохраняются как данные и никогда не загружаются builder. Traversal, encoded separator и управляющие символы отклоняются во всех файловых отображениях.
- Никакого shell command из URL, динамического SQL и записи по пути из request/HTML. Имена файлов выводятся из digest/закрытого отображения manifest.
- Reserve root задаётся закрытой настройкой, проверяется по resolved path, типу, владельцу/правам и не может быть workspace root, media root, static root или `/`/диск.
- Staging создаётся как новый каталог; существующий набор не перезаписывается на месте. Symlink/reparse point и выход из root запрещены.
- Полный source stamp из пункта 2.9 снимается до и после bounded capture. Изменение любой включённой зависимости до authoritative activation point делает попытку неуспешной, а current/previous остаются прежними.
- Ответы публичного рендерера проверяются до записи; redirect loops, 4xx/5xx, неожиданный content type, missing resource и private marker проваливают весь build.
- Ошибка диска, БД, renderer, validation или manifest до authoritative activation point наблюдаема владельцу и в безопасном аудите, но не публикует частичный набор. Сбой ответа/audit после этой точки не отменяет уже активированное поколение.
- Проверки REF-AC-017–019/021 выполняются в DEV-25. REF-AC-032 проверяется для current/previous usage. Nginx-матрица REF-AC-020 относится к DEV-26/27.

## 6. Не входит

- nightly/cron/systemd timer, авто-build после каждого сохранения, очередь, retry worker и delivery notifications;
- отдельный микросервис, API, cache, новая DB model/migration или универсальная state machine;
- HTTP crawler, headless browser и Playwright;
- TRUST/head, health-voting, ручной флаг «сайт сломан» и отдельный controller переключения;
- больше одного previous, архив HTML-поколений, diff, zip/download и редактирование manifest;
- Nginx fallback, изменение конфигурации VPS и проверка аварийной выдачи — это DEV-26/27 после отдельного согласования;
- live/persistent apply, реальные секреты, публикация и изменение старого сайта.

## 7. Минимальные приёмочные границы

- `DEV25-AT-001`: owner POST создаёт полный проверенный current; employee/anonymous запрещены; второй параллельный POST получает bounded busy без второй сборки.
- `DEV25-AT-002`: manifest exact-set сверяет каждый bounded non-SYSTEM Route и allowlisted gallery target вместе с query, status и redirect `Location`; неизвестные 404, включая `?page=1&album=<slug>`, отсутствуют, а ресурсы полны.
- `DEV25-AT-003`: missing URL/resource, private marker, redirect loop, лимит, renderer/DB/disk fault и изменение полного source stamp до authoritative activation point оставляют current/previous byte-identical.
- `DEV25-AT-004`: второй успешный build через одну activation point даёт новый current и один previous; потеря ответа/audit после неё определяется по тому же generation UUID как успех. Изменение page revision, route/status/location/publication/tree, shared, media descriptor/digest, SEO/public configuration или static bytes без build показывает stale.
- `DEV25-AT-005`: набор не содержит manage/history/preview/PII/token/cookie/external fetch. При включённом обычном intake trusted internal reserve context всё равно исключает intent/CSRF/action и показывает disabled fallback; anonymous HTTP не может включить reserve-mode.
- `DEV25-AT-006`: referenced assets current/previous защищены существующим `retained_html`; pre-activation crash может только переудержать orphan. Bounded reconciliation удаляет доказанный orphan, никогда current/previous; после безопасной ротации более не используемый asset освобождается.
- `DEV25-AT-007`: traversal/symlink/reparse/oversize и подменённый manifest fail closed; external embedded/fetchable URL запрещён, а допустимая navigation/SEO ссылка не загружается; audit и owner error не раскрывают содержимое или секреты.
- `DEV25-AT-008`: обычные PostgreSQL+media backup/restore остаются независимыми; HTML-резерв не выдаётся за backup данных.

## 8. Предлагаемый порядок после утверждения

1. Независимое scope review этого документа.
2. Короткий implementation plan с точной картой request-target, filesystem/DB activation protocol и fault matrix.
3. Независимое plan review.
4. Отдельное разрешение владельца на реализацию.
5. Tests-first малыми срезами: pure manifest/policy → bounded capture → staging/resources/validation → current/previous+retained usage → owner UI/status/audit → combined fault/security regression → independent code review.

## 9. Вопрос владельцу

`DEV25-Q001`: **утверждён D-867.** Ограниченный DEV-25: ручной owner-only синхронный build существующим renderer, exact request-target manifest с gallery query, самодостаточные HTML/static/media, один current+previous, вычисляемый stale и existing `retained_html`, без scheduler/worker/new model/TRUST/Nginx. DEV-26/27 остаются отдельными этапами.
