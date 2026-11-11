# DEV-12 — ограниченное предложение по сборке главной

Статус: `DEV12-Q001` утверждён владельцем в D-834 от 2026-11-11. Первое independent scope review вернуло P1=0/P2=2/P3=1; после D-835 repeat review подтвердило закрытие P2 и dependency P3, а последнее wording P3 по RSP-AC-10 исправлено в D-836. Ожидается final confirmation. Это ещё не implementation plan и не разрешение product code. Основание: D-077, D-117–D-146, D-222–D-235, D-268, D-300, REQ-009/012/016/030 и завершённые DEV-08/10/11.

## 1. Рентабельная граница

Не создавать универсальный page-builder, новую модель блоков, вторую систему версий, API, cache, queue, worker, scheduler или свободно исполняемый HTML/JavaScript. Существующие `Page(kind=home)` и current `PageRevision` остаются источником H1/title/description/indexing и ограниченных текстов владельца. Сотруднику главная недоступна по REQ-016.

Утверждённая v4-композиция реализуется отдельным code-owned шаблоном и закрытой схемой профиля с числовыми лимитами. Код владеет только типами, лимитами, защищённым порядком, allowlist полей и проверками; он не содержит вторую конкретную копию подписей, сумм и URL. Конкретный профиль главной хранится внутри существующего versioned payload `PageRevision` страницы `kind=home` как ограниченное home-only расширение схемы, без новой модели или таблицы. Профиль содержит только заранее известные типы: hero, преимущества, сравнение, пять шагов, восемь услуг, шесть ценовых категорий максимум по восемь строк, фотополосу, шесть работ и локальный сокращённый блок отзывов. Произвольные template names, HTML, CSS, JavaScript, URL или запросы из редактора не исполняются.

Это сознательно уже общего конструктора, но не одноразовый статический HTML: responsive template/CSS переиспользуют существующий public/shared host, SEO, media и navigation; данные имеют typed projection и fail-closed проверки.

## 2. Источники и поведение

- Hero/H1/SEO: current verified home revision. Два безопасных rich-text поля остаются owner-only; структурные подписи и порядок — защищённая композиция.
- Услуги: exact восемь принятых карточек и старые URL. Только внутренние exact targets; внешние и query targets запрещены.
- Профиль и fallback: concrete stable source/row IDs, подписи, суммы, URL и fallback находятся в том же current home revision payload. Только владелец сохраняет разрешённые поля через обычные concurrency/version/Stable правила. Fallback становится новым только после явного успешного owner save; рендер никогда автоматически не записывает последнее увиденное значение в revision.
- Цены: шесть принятых категорий, до восьми строк. Closed mapping использует сохранённые stable Page/price-row IDs. Доступный опубликованный источник только проецирует актуальную цену при чтении; скрытый существующий источник применяет D-256. Удаление источника не мутирует revision по D-300: показывается последний явно сохранённый владельцем fallback до следующей ручной правки. Совпавший позже URL не наследует связь.
- Работы: шесть утверждённых DEV-10 альбомов и побайтно неизменные gallery files. Карточка использует exact album ID/target, без копирования фотографий в новую подсистему.
- Медиа главной: только READY Asset/AssetFile и exact `current_page` slots существующей media lifecycle; общий bounded capture, физическая проверка и recapture. Новая таблица файлов не нужна.
- JavaScript: один фиксированный локальный asset только для мобильного меню и price tabs; без fetch/XHR/storage/eval/dynamic import/HTML insertion. Без JS все категории и ссылки остаются доступны серверно либо через понятный fallback.

## 3. Что намеренно не входит в первый DEV-12 slice

- Весь v4-блок `es-service-contact` (заявка, контакты и карта) отсутствует в DEV-12, а не заменяется выдуманным CTA. Он относится к DEV-13/CONTACT-01/LEGAL-01/DEV-30 и требует отдельных разрешений; form controls, POST и сбор персональных данных отсутствуют.
- Блок отзывов в DEV-12 имеет ровно локальный сокращённый вариант: заголовок `ОТЗЫВЫ` и обычная внутренняя ссылка `/reviews` с утверждённой подписью `ОТКРЫТЬ ВСЕ ВИДЕО-ОТЗЫВЫ`. Текст о загрузке с Яндекс Карт, iframe Яндекса, YouTube previews/embeds, Метрика и любые внешние запросы отсутствуют до DEV-30 после LEGAL-01/COOKIE-Q001.
- Telegram/MAX/Instagram/QR и AutoRepair real profile — только после подтверждения CONTACT-01. Неподтверждённые кнопки не показываются.
- INFOGRAPHICS-01 относится к внутренним страницам услуг и не блокирует главную; отдельные схемы не изобретаются.
- Автоматическая публикация, persistent migration apply, live site, VPS, HTML fallback и ночное расписание не входят.

## 4. Предлагаемые приёмочные границы

| ID | Проверка |
|---|---|
| H12-AT-001 | `/` использует exact published home/current verified revision и утверждённый порядок секций; hidden/damaged/mismatch закрываются без partial HTML. |
| H12-AT-002 | 320/390/768/1024/1440 не имеют горизонтального overflow, обрезанного текста или наложений; no-JS сохраняет содержимое и переходы. |
| H12-AT-003 | Восемь услуг имеют exact labels/targets; неизвестный, внешний, query или дублирующий target закрывает projection. |
| H12-AT-004 | Шесть price groups и максимум восемь строк проходят exact ID mapping; published source update проецируется без записи, hidden source следует D-256, deleted source использует последний явно owner-saved fallback по D-300, reused URL не захватывает связь. |
| H12-AT-005 | Шесть gallery cards используют DEV-10 IDs/targets/files и существующий contextual media boundary; фото не перекодируются и не копируются. |
| H12-AT-006 | Media slots/files имеют отдельные cap+1 queries, exact READY variant, physical verify и coherent recapture; corrupt/missing/cap overflow дают 503/no-store без UUID/partial body. |
| H12-AT-007 | Concrete profile и fallback находятся в `PageRevision`; owner может менять только разрешённые home fields с обычными versions/Stable/concurrency, восстановление возвращает их согласованно; employee/direct request не меняет главную или protected composition. |
| H12-AT-008 | Рендер содержит ровно локальные `ОТЗЫВЫ` + ссылку `/reviews`; `es-service-contact`, form controls/POST/data collection, external iframe/script/request, unconfirmed social/QR и real AutoRepair profile отсутствуют. |
| H12-AT-009 | Fixed JS работает только как enhancement; CSP local-only, GET/HEAD asset, POST405, нет network/storage/eval/dynamic HTML. |
| H12-AT-010 | Рендер и удаление source никогда не мутируют home revision/profile; удалённый собственный URL остаётся 404, homepage использует последний explicit owner-saved fallback, а его изменение требует нового owner save. |

## 5. Предлагаемый порядок после ответа владельца

1. Утвердить либо изменить `DEV12-Q001`.
2. Провести независимое scope review и закрыть findings.
3. Составить минимальный implementation plan с точными package/media authorities и тестовыми caps.
4. Провести independent plan review.
5. Получить отдельное разрешение product implementation.

`DEV12-Q001`: утвердить ли эту минимальную границу — собрать локально утверждённую главную без рабочей формы, сторонних embeds и неподтверждённых контактов, используя existing Page/version/media/public layers и закрытый bounded profile вместо универсального конструктора блоков?
