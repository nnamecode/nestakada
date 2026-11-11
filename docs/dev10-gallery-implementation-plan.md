# DEV-10 — минимальный план галереи и альбомов

Статус: завершено локально D-819 от 2026-11-10. `DEV10-IMP-001–008` и G10-AT-001–015 закрыты; final independent code review `APPROVED`, P1=0/P2=0/P3=0. Persistent/production apply и публикация не выполнялись и не разрешены.

## 1. Утверждённый результат

- `/gallery-of-works/` — HTTP 200, 17 карточек в порядке `MAP-114, MAP-113, MAP-112, MAP-111, MAP-109, MAP-106, MAP-102, MAP-099, MAP-096, MAP-092, MAP-086, MAP-081, MAP-076, MAP-070, MAP-061, MAP-056, MAP-036`.
- `/gallery-of-works/?page=2` — прямой HTTP 200 без редиректа, семь карточек `MAP-086, MAP-081, MAP-076, MAP-070, MAP-061, MAP-056, MAP-036` и ссылка на полный каталог.
- `/gallery-of-works/?page=1` — HTTP 302 с одним относительным `Location: /gallery-of-works/`; после перехода обычный корень. Не выдавать 301 за неизвестный исторический факт.
- Семнадцать точных прежних URL `MAP-036/056/061/070/076/081/086/092/096/099/102/106/109/111/112/113/114` — самостоятельные HTTP 200 страницы утверждённого D-805 вида.
- Общие данные содержат 214 оригиналов с точными исходными байтами/SHA-256; по альбомам соответственно `7,12,8,10,8,7,25,14,15,11,21,9,13,32,9,9,4` в порядке MAP выше по возрастанию.
- Карточка без JavaScript ведёт на самостоятельный URL. При JavaScript она открывает server-rendered выбранный альбом в модальном viewer каталога. API, background fetch и выполнение хранимого JavaScript отсутствуют.

## 2. Зафиксированные authority

| Файл | Байты | SHA-256 | Назначение |
|---|---:|---|---|
| `docs/analytics-route-map.csv` | 121766 | `c1d542d0761ffbdb9fc58c9227fc94144515ab18c3155952a93dc6fb4d1bbad8` | 17 точных URL, H1, source snapshots |
| `docs/media-inventory.csv` | 189296 | `2be3bf2b24ca589c9eaf88a040ee80ed098417667e5c04db89ca669332155ad0` | 214 source URL/path/bytes/SHA |
| `work/gallery-of-works.html` | 51884 | `5e9e5bbbdfdcae7a85a2575be441f209a3d32fb91b65169f2202c4c055bebc3d` | утверждённый порядок/названия/счётчики/композиция каталога |
| `work/site-audit/gallery.html` | 71885 | `89dea67b4dc41ff1520a9db31d38ca8d11c12a39f9c2c7c942ef94c0ca8cc974` | прежний корень и album associations |
| `work/site-audit/gallery-page-2.html` | 51390 | `6e4bd964bb6f769ecb23250a907ba56ef6b4fc1a9c44907e9d99f2e845535d46` | точный прежний page=2 subset/order |

Host-проверка читает только эти exact regular files и 17 source snapshots, уже названных route map; realpath обязан оставаться внутри workspace. Она требует точные SHA authority, 17 уникальных MAP/URL, 214 уникальных gallery-original, точные per-album order/count и совпадение каждого локального файла с bytes/SHA. В JSON не помещаются сами фотографии, абсолютные пользовательские пути или секреты.

До чтения действуют численные пределы: route map `128 KiB`, media inventory `256 KiB`, approved root `64 KiB`, old root `128 KiB`, old page2 `64 KiB`, каждый source snapshot `64 KiB`, все 17 snapshots вместе `512 KiB`, итоговый JSON `512 KiB`. Ровно 17 source rows и 214 photo rows; UTF-8 source URL не более 2048 bytes, относительный local path не более 1024 bytes, H1/title 255 characters, alt 300 characters, album source text 4096 UTF-8 bytes. Один original не более `1 MiB`, сумма original bytes не более `48 MiB`; хэширование потоковое. Для каждого предела selfcheck проверяет exact cap и cap+1 до parser/package output.

## 3. Хранение и импорт без новой медиасистемы

1. Один закрытый `dev10_gallery.json` хранит только bounded metadata: IDs, exact routes, titles/H1/text, positions, source URL, относительный подтверждённый local path, bytes, SHA-256, alt и album order. Схема, максимальные размеры и exact key set фиксированы; неизвестные/дублированные поля отклоняются.
2. Каждый album остаётся обычным `Page.Kind.ALBUM` с собственной current revision `page-content-v1`. Его 4–32 фотографий представлены существующими `embedded_images` и image layout nodes; произвольный HTML/шаблон/JS не хранится.
3. Root остаётся одним `Page.Kind.GALLERY`; `?page=2` — exact alias того же Page. Редактируемые копии альбомов/фотографий для root/page2/modal не создаются.
4. Файлы проходят существующие `Asset(is_legacy=True) → LEGACY_PUBLIC → mark_ready` правила D-024. DEV-10 не создаёт второй uploader/import service: bounded content writer принимает только exact набор уже существующих READY assets, у которых source URL, source SHA, единственный LEGACY_PUBLIC file SHA/bytes и manifest совпали с package.
5. После UNIT guard/package validation, но до DB content/auth transaction, DB-free bounded preflight всех 214 files вызывает существующий storage manifest по exact package key/SHA/bytes и фиксирует evidence digest. Missing/replaced/unreadable blob или несовпадающие bytes/SHA прекращают операцию. Внутри транзакции после identity SQL/блокировок все 214 Asset/AssetFile descriptors читаются `select_for_update`: READY, `is_legacy=True`, source URL/SHA, file ID/kind/key/SHA/bytes и digest обязаны совпасть с package и outside evidence. Descriptor drift даёт полный rollback.
6. Hidden UNIT-only writer одной DB-транзакцией создаёт полный штатный aggregate 18 pages: 18 PRIMARY routes плюс один page2 ALIAS, 18 initial revisions/states/owner drafts/metadata/base pins/audit events, 36 revision+draft identity reservations и ровно 642 media usages — 214 `ordinary_version`, 214 `current_page`, 214 `draft`. Root не имеет media slots. Writer использует существующие `engine.new_revision`, usage sync и aggregate invariants, не обходит lifecycle ради упрощённого счётчика.
7. Exact replay исчерпывающе сверяет все эти rows/fields/usages/events/reservations и отсутствие grants, restore stages, operation receipts, revision protections и иных gallery children. All-absent создаётся атомарно, all-exact даёт writes0; mixed/extras/collision/exception/concurrent contender дают constant validation error и полное before/after equality. Persistent/production apply не запускается.

UNIT entrypoint default-off: только `ENVIRONMENT=test`, явный `DEV10_GALLERY_APPLY_ENABLED=True`, PostgreSQL DB `estakada_foundation_unit`, user `app_migrator`. Wrong/missing env/flag/engine/DB/user прекращает работу до package read, первого SQL и mutation. После outside filesystem preflight actual first SQL — существующая identity/authenticity check; затем единый порядок locks `content → auth`, как в принятом DEV-09 writer. Negative tests фиксируют SQL0/writes0 для disabled boundary и правильный first-SQL/lock order для enabled boundary.

Это отделяет неизбежную физическую запись файлов существующим медиасервисом от атомарного подключения галереи. Сбой подготовки файла не публикует и не связывает частичную галерею; отдельная очередь, journal и rollback-platform не добавляются.

## 4. Публичная проекция

Добавляется один bounded gallery DTO/projection в существующем `content` public layer, а не новый runtime service.

- Root/page2 читают только известные direct album children с PRIMARY routes и current revisions; скрытый album пропускается и не раскрывается. Порядок опубликованных карточек берётся из утверждённой gallery position, не из имени или URL; неизвестный/лишний child не принимается за альбом.
- Обложка — первая фотография той же current album revision. Root и album не получают отдельные копии asset usage.
- Для modal принимаются только canonical query forms `?album=<exact-segment>` и `?page=2&album=<exact-segment>`; во втором случае album обязан входить в seven-item page2 subset. Порядок параметров фиксирован генератором ссылок.
- Unknown, duplicate, empty, reordered or extra query key, album outside page2 subset и query на direct album URL дают 404 без DB-derived diagnostics.
- `?page=1` обрабатывается до обычного resolver как единственное exact temporary redirect; POST и другие методы сохраняют общий 405 boundary.
- Один read transaction строит root/children/revisions/usages/media DTO. Missing/duplicate PRIMARY у опубликованного album, unknown/extra child, wrong kind/parent, corrupt revision/layout/usage/file, cap overflow или snapshot race дают 503 без частичного HTML.
- Root без modal открывает 17 cover files; page2 — 7; modal добавляет выбранный album, максимум 49/39 unique files. Существующие жёсткие caps 64 slots/files не увеличиваются и проверяются до media open.
- Direct album использует существующий body/media boundary, новый album template branch добавляет approved viewer markup. Общий Header/Footer, breadcrumbs и autoescape сохраняются.

## 5. Viewer и доступность

Один fixed local `public-gallery.js` без зависимостей и inline-script работает только с server-rendered `data-*`/DOM текущего viewer. Он не принимает HTML, URL файла или selector из хранимого контента и не вызывает `fetch`, XHR, storage, eval либо dynamic import.

- открытие карточки с JS переводит только на canonical server-rendered modal URL; без JS href остаётся direct album URL;
- стрелки, thumbnails и Left/Right выбирают уже отрисованное изображение; счётчик имеет `01 / NN`;
- dialog имеет label, явную кнопку закрытия, видимый focus, Escape/backdrop close и возврат focus на карточку;
- CSS сохраняет пропорции изображения (`object-fit: contain`), не обрезает/не преобразует оригинал и не создаёт горизонтальный overflow страницы на mobile;
- CSP остаётся `script-src 'self'`; никаких внешних библиотек или новых npm/pip зависимостей.

## 6. Приёмочные сценарии до кода

| ID | Сценарий и ожидаемый результат | Связь |
|---|---|---|
| G10-AT-001 | Host preflight на fixed authority даёт exact17/exact214, per-album counts/order, total bytes и SHA; modified/missing/extra/duplicate path, URL, MAP, image или changed authority SHA закрывается до package output | REQ-008, AC-MIG-003/009 |
| G10-AT-002 | Package validator принимает только exact schema и зафиксированные 128/256/64/128/64/64/512/512 KiB, 1 MiB/file, 48 MiB total, row/string/path caps; exact-cap проходит, cap+1, traversal, symlink escape, control/surrogate, absolute path и unknown key отклоняются constant error до output | D-024, REQ-025 |
| G10-AT-003 | DB-free outside preflight подтверждает physical manifest 214 blobs по package descriptors; locked DB recapture подтверждает exact READY legacy descriptors. Hidden writer создаёт exact18 pages/19 routes/18 revisions+states+drafts+metadata+pins+events/36 reservations/642 usages; exact replay writes0; missing/replaced blob, descriptor drift, mixed/extra/collision/exception/concurrency дают полное before/after equality | AC-008, AC-MIG-003 |
| G10-AT-004 | Root published fixture отвечает 200 и содержит exact17 cards в D-218 order/count; каждая no-JS href — точный direct album URL и cover — первая фотография того же album | REQ-008/009, AC-008/009 |
| G10-AT-005 | Exact `?page=2` отвечает direct200, не имеет Location, содержит exact seven MAP-086…036 в порядке старого page2 и ссылку на root | D-245, AC-008 |
| G10-AT-006 | Exact `?page=1` GET/HEAD отвечает 302 с единственным relative Location root; root затем200. `page=01`, repeats/extras/reordered forms не наследуют это правило | D-805, AC-MIG-003 |
| G10-AT-007 | Все 17 direct album URLs отвечают200 с exact H1/text/photo count/order, breadcrumbs и `Все работы`; first/last navigation does not lose/duplicate photo | D-246, AC-008/009 |
| G10-AT-008 | Root modal URL для каждого album и page2 modal URL для каждого of seven отвечают200 с exact selected album; root+selected unique files ≤49, page2+selected ≤39, чужой page2 album404 | D-218/D-245 |
| G10-AT-009 | Unknown/empty/duplicate/reordered/extra query and query on direct album URL return404; no query value reaches file path, template name, SQL fragment or raw HTML | REQ-008, security boundary |
| G10-AT-010 | Hidden album gives existing blank behavior at its direct route, is omitted from catalog and is not leaked by modal; unknown/extra child or malformed revision/hash/usage/file/kind/parent/route and 65-slot synthetic case gives catalog503 before media open | REQ-003/008/025 |
| G10-AT-011 | Concurrent child revision/usage change cannot mix generations in one response; result is one coherent old/new snapshot or503, never mixed photo IDs/hashes | AC-MIG-003/009 |
| G10-AT-012 | Every served gallery media URL retains contextual page/slot authorization, exact registered LEGACY_PUBLIC bytes/SHA and no access through another page/slot | D-024, REQ-025 |
| G10-AT-013 | Static HTML/CSS/JS checks prove semantic cards/dialog/buttons/counter/thumbnails, escaped text, local script, no inline/eval/fetch/storage; pure viewer state tests cover arrows/bounds/Escape/focus contract without Playwright | REQ-009, AC-009 |
| G10-AT-014 | GET/HEAD parity, POST405, public no session cookie, no-cache/no-store boundaries, CSP/nosniff and existing normal404/503/redirect regressions remain intact | DEV-08, security boundary |
| G10-AT-015 | Existing focused public/media/content tests plus full relevant regression, Django check, no migrations, manifest/diff checks pass; foundation stopped. No live/persistent apply/publication | pipeline stage 8/10 |

UNIT boundary дополнительно проверяется в G10-AT-002/003: missing/wrong ENV/flag/engine/DB/user даёт SQL0/writes0; enabled path доказывает actual first identity SQL и lock order `content → auth` до aggregate mutation.

Полная responsive/manual browser-приёмка desktop/tablet/phone остаётся перед запуском без Playwright. Canonical/meta/sitemap закрывает DEV-11/AT-604; DEV-10 не дублирует SEO subsystem. Проверка всех реальных 214 SHA входит в preflight и позднюю launch acceptance AT-605.

## 7. Минимальные задачи реализации

| ID | Изменение | Зависит от | Проверка |
|---|---|---|---|
| DEV10-IMP-001 | Host preflight и canonical metadata package из fixed authority | D-805 | G10-AT-001/002 |
| DEV10-IMP-002 | Closed Python package loader, exact numeric caps и default-off UNIT guard | IMP-001 | G10-AT-002 |
| DEV10-IMP-003 | Physical blob preflight + locked descriptor recapture + full atomic 18-page/642-usage aggregate/replay поверх existing READY legacy assets | IMP-002, media lifecycle/version engine | G10-AT-003 |
| DEV10-IMP-004 | Bounded gallery read DTO/query parser/coherent projection в existing public layer | IMP-002 | G10-AT-004–012 |
| DEV10-IMP-005 | Root/page2/direct album/modal template branches и CSS | IMP-004 | G10-AT-004–010/013 |
| DEV10-IMP-006 | Fixed dependency-free local viewer JS and endpoint/CSP integration | IMP-005 | G10-AT-008/013/014 |
| DEV10-IMP-007 | Focused security/media/concurrency/public regression and final evidence | IMP-001–006 | G10-AT-001–015 |
| DEV10-IMP-008 | Independent code review, fixes and repeat bounded verification | IMP-007 | pipeline stage 10 |

## 8. Явно исключено

Новые models/migrations/page schema/API/cache/queue/worker/scheduler/external library; универсальный gallery builder; редактирование фотографий; хранение 214 бинарников в Git; persistent/production apply; публикация; живой сайт/VPS; DEV-11 SEO; DEV-25/26 HTML reserve; ночная автоматика. Ручной HTML reserve позже включает root, page2 и 17 direct album pages из тех же данных, но не обязан сохранять каждое modal query state.
