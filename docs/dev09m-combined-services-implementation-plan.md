# DEV-09M: acceptance и минимальный implementation plan

Дата: 2026-11-13. Статус: подготовлен после `DEV09M-Q001=1`; product code не начат. До реализации обязательны независимое ревью этого плана и отдельное разрешение владельца.

## Исправленная граница

Область — 25 точных старых URL, 24 объекта Page и 25 Route. MAP-088 и MAP-115 не являются двумя страницами: это legacy exact-200 alias `/services/drugie-uslugi/avtomojka` и primary `/services/avtomojka` одного Page вида `service_wash_legacy_alias`. Canonical старого адреса указывает на новый по D-822. Редиректа нет.

Не входят: публикация, persistent apply, grants, live/VPS, медиа, actions/reviews/contacts, gallery query states, legacy10 без утверждённого дизайна, новые модели/миграции/зависимости/API/cache/worker/scheduler/service/importer.

## Точный состав и дерево

| Группа | Page | Route | Родитель и позиции |
|---|---:|---:|---|
| MAP-010 + MAP-019–029, кузовная ветвь | 12 | 12 | MAP-010 под master MAP-002 в позиции 0; дети MAP-019–029 в позициях 0–10 |
| MAP-015/016, отдельные шиномонтаж и сход-развал | 2 | 2 | существующий MAP-014 «Другие услуги», позиции 5 и 6 по D-206/D-207/D-230 |
| MAP-032/038/083 | 3 | 3 | существующий MAP-014, утверждённые позиции 0/1/4 |
| MAP-041 | 1 | 1 | существующий MAP-011 «Плановое ТО», позиция 2 |
| MAP-058/068/069/089 | 4 | 4 | существующий MAP-012 «Ремонт», позиции 3/6/7/11 |
| MAP-073 | 1 | 1 | существующий MAP-013 «Диагностика», позиция 5 |
| MAP-115 primary + MAP-088 alias | 1 | 2 | master MAP-002, позиция 5; один Page автомойки |
| Итого | 24 | 25 | без изменения существующих Page/Route |

Identity inventory зафиксирован в `docs/dev09m-combined-services-manifest.md`. По `DEV09M-Q002=1/Q003=1` единственный canonical structured data authority до writer-кода — отдельно рассмотренный `app/content/dev09m_combined_services.json`: после D-951 package SHA256 `a59d13ef3c3b1d9d1dbde2e1b741358c751cd6f8f1b46360b85f0ba81f477677`, bytes318209, page-content SHA `ce786ef915f627af939946b93689448a019e18ca22707da58712d21bb4aeef37`, route-content SHA `cc5d3255f01e40098a90fd3a48ff8efe2d4f117026b3c55cdaef16fbe42b6433`. Он фиксирует name/h1/title/description/intro/blocks/tables/source-restored prices для24 Page и mapping25 Route; writer/tests могут только принять или отклонить эти bytes, но не строить другую projection.

Все новые Page создаются скрытыми. До preflight writer в одном порядке блокирует все существующие parent Page, их primary Route, current PageContentState/PageRevision и sibling scopes. Для каждого родителя переиспользуется полный `_exact_aggregate` contract: ровно один OwnerDraft с exact base pin/metadata/reservations/audit; запрещены только посторонние extras и RestoreStage. Для позиций 0–4 проверяется точный существующий group/tile `name+href`; для новых MAP-015/016 проверяется точное отсутствие sibling positions5/6 и canonical JSON authority, без изменения payload родителя. Writer не исправляет и не создаёт родителей неявно.

## Закрытый пакет

Один файл `app/content/dev09m_combined_services.json`, schema `dev09-combined-services-v1`, содержит ровно 24 Page и отдельный список из 25 Route. Для каждого Page фиксируются literal UUID, MAP ID, primary URL, kind, parent UUID, position, name/h1/title/description, `is_published=false`, source/artifact path+SHA256, intro и упорядоченные blocks. Для автомойки фиксируются один primary и один alias Route.

Разрешённые blocks и только их exact keys:

| type | exact keys | closed value contract |
|---|---|---|
| paragraph | `type,segments` | 1–128 segments; segment exact `text,strong`, strong bool |
| heading | `type,text` | plain non-empty text |
| unordered_list / ordered_list | `type,items` | 1–128 items; item exact `segments` и optional `children`; children разрешён только первому MAP-024 ordered item, ровно один closed unordered_list, без дальнейшего nesting |
| table | `type,caption,header,rows` | caption segments или null; header 1–16 cells; 1–128 rows |
| ordered_sections | `type,items` | только MAP-041; 1–32 section; section exact `heading,blocks`, blocks только paragraph/list, depth ровно 2 максимум |

Table cell имеет exact keys `text,strong,rowspan,colspan,scope`: text non-empty, strong bool, rowspan 1–128 и не выходит за row group, colspan 1–16, вычисленная ширина таблицы 1–16, scope только null/`row`/`col`. Иные keys/types/enums, sparse/overlap cells и третья глубина запрещены. Raw source/artifact HTML, template fragments, Django templates, Python и JavaScript не принимаются.

Source сохраняет обязательные тексты и цены D-023; artifact задаёт утверждённую компоновку. Пропущенные artifact цены MAP-038/073 восстанавливаются из pinned source. Максимумы до кода: source 43,512 bytes и artifact 24,691 bytes.

Числовые caps: source/artifact по 64 KiB; package 512 KiB; pages=24 и routes=25 exact; blocks 128/page и 2,048/package; sections 32/page; list items 128/block и 256/page; tables 4/page; rows 128/table; columns 16/table; cells 2,048/table и 4,096/package; UTF-8 text leaf 8 KiB, intro 8 KiB, суммарный plain text 64 KiB/page; rendered intro+main 128 KiB/page и 2 MiB/package; nesting depth 2. Для каждого измерения отдельный exact-cap PASS и cap+1 отказ до render/write.

## Acceptance-сценарии

- `MIGM-001`: schema, точные 24 Page/25 Route, MAP IDs, UUID, URL, родители/позиции, source/artifact SHA, page/route digests и authority aggregate совпадают с `docs/dev09m-combined-services-manifest.md`.
- `MIGM-002`: renderer выдаёт только разрешённую sanitizer-equivalent разметку; script/template/event/style/unknown tag/attribute не проходит.
- `MIGM-003`: все тексты, block order, таблицы, строки, ячейки, rowspan/colspan/scope и MAP-041 nested sections совпадают с pinned literals.
- `MIGM-004`: MAP-038/073 содержат source-authoritative цены; ни одна цена не выдумана и не потеряна.
- `MIGM-005`: существующие родители exact → создаются ровно 24 hidden Page, 24 initial versions и 25 Route в одной transaction.
- `MIGM-006`: MAP-088 и MAP-115 ведут на один Page; опубликованная изолированная fixture отдаёт оба адреса HTTP 200, одинаковое содержимое и canonical старого адреса на `/services/avtomojka`.
- `MIGM-007`: полный exact replay делает zero writes и возвращает тот же aggregate.
- `MIGM-008`: missing/changed parent, occupied sibling position, reserved URL/UUID, чужой Route или mixed partial state отказывают до записи.
- `MIGM-009`: unknown block/key, reordered/missing/extra page/route, altered text/table/hash/cap+1 отказывают до записи.
- `MIGM-010`: инъекция template/Python/JavaScript/raw HTML отказывается до render/write.
- `MIGM-011`: late failure на последнем Page, version или Route откатывает всю группу и не меняет родителей.
- `MIGM-012`: два concurrent writer дают один create и один exact replay без дублей.
- `MIGM-013`: feature flag false останавливает чтение package/write.
- `MIGM-014`: persistent apply, publication, navigation enablement, media и live отсутствуют.
- `MIGM-015`: named regression проходит только через wrapper; прямой широкий запуск не является продуктовой проверкой.

## Минимальные изменения по срезам

1. `IMP-001 — canonical data gate`: независимо рассмотреть уже подготовленный `app/content/dev09m_combined_services.json`, его package/content SHA,24 Page/25 Route, restored prices и closed grammar. Это data review, не writer/code approval.
2. `IMP-002 — tests against approved JSON`: после data APPROVED добавить `app/content/test_dev09m_combined_services.py` с MIGM-001–004 и отрицательными grammar/cap cases; JSON bytes являются source of truth. Не расширять крупный `test_dev09e_services_catalog.py`.
3. `IMP-003 — validator/renderer`: точечно расширить `app/content/dev09_migration_apply.py`; переиспользовать существующие reader, flag, sanitizer, transaction и payload helpers. Добавить только table/ordered-section closed validators.
4. `IMP-004 — atomic writer`: один `apply_combined_services()` с preflight absent/exact/mixed, row locks, Page+version+Route transaction и exact replay.
5. `IMP-005 — wrapper/foundation allowlist`: в `scripts/test-editor.ps1` добавить `content.test_dev09m_combined_services` после существующего `content.test_dev09e_services_catalog` в suite `dev09-services`; в `scripts/local-foundation.ps1` добавить package literal в оба exact path и name allowlist/manifest набора.
6. `IMP-006 — writer tests`: MIGM-005–013, включая last-route rollback и concurrency.
7. `IMP-007 — bounded regressions`: только `scripts/test-editor.ps1 -Suite dev09-services`, затем именованные `public-read`, `public-http`, `public-nav`, `check`, `migrations` при затронутой области; без wildcard и без Playwright.
8. `IMP-008 — independent code review`: проверить P1/P2/P3, исправить только findings, повторить затронутые именованные suites. Persistent apply и публикация остаются отдельным будущим gate.

Exact implementation file set: новые `app/content/dev09m_combined_services.json` и `app/content/test_dev09m_combined_services.py`; изменяемые только `app/content/dev09_migration_apply.py`, `scripts/test-editor.ps1`, `scripts/local-foundation.ps1` и stage documentation. Иные product files требуют остановки и amendment review.

Точная основная команда regression: `pwsh -File scripts/test-editor.ps1 -Suite dev09-services`. Затем отдельными wrapper-вызовами suites `public-read`, `public-http`, `public-nav`, `check`, `migrations`; wildcard и Playwright запрещены.

## Stop rules и ожидаемый результат

После первой ошибки фиксируются причина и изменившееся условие перед единственным повтором. Вторая одинаковая ошибка при эквивалентном действии немедленно переводит работу в «Приостановлено владельцу»; третьей попытки нет. Windows-поиск использует буквальный каталог и `-g`, не wildcard внутри path.

Результат DEV-09M implementation: только локально доказанный, скрытый, повторяемый exact content package. Он не включает запуск сбора заявок, изменение живого сайта или выбор новых функций.
