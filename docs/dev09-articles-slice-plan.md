# DEV-09B: первый ограниченный пакет переноса статей

Дата: 2026-11-09. Статус: план до кода, требуется независимое ревью.

## Цель и граница

Подготовить первый реальный, проверяемый пакет данных DEV-09 только для непрерывной ready-ветки:

- `MAP-001` `/` — скрытый структурный корень `home`;
- `MAP-006` `/articles/` — скрытый дочерний каталог `articles_catalog`;
- `MAP-031` `/articles/zamena-masla-v-dvigatele` — скрытая дочерняя статья `article` с тремя исходными абзацами.

Этот срез не пишет в PostgreSQL и не создаёт Django-команду импорта. Результат — один versioned JSON-пакет и один host-only read-only валидатор. Отдельный применитель в БД допускается только следующим срезом после ревью этого пакета.

## Почему именно эта ветка

Все три строки входят в доказанный DEV-09A ready-subset и образуют полную цепочку предков. Ветка услуг пока не подходит: её точный предок `MAP-002 /services/` заблокирован отсутствующим утверждённым каталогом. Создание временного неправильного корня потребовало бы последующего переноса дерева и не принимается.

## Формат пакета

Фиксированный файл `app/content/dev09b_articles_slice.json` содержит:

- `schema = dev09-articles-slice-v1`, точные SHA-256 MAP/RTE и идентификаторы `MAP-001`, `MAP-006`, `MAP-031`;
- для каждой страницы — заранее заданный UUID, `map_id`, точный URL, kind, parent UUID или `null`, nonnegative position, name, H1, исходный title, пустое description, `is_published=false`;
- `content_state=deferred` для главной и каталога: это только необходимые скрытые предки, не заявление о полном переносе их содержимого;
- `content_state=source_text_complete_media_deferred` и ровно три plain-text абзаца для статьи;
- source snapshot path/SHA для каждой строки, без абсолютных путей и без содержимого медиа.

Позиции фиксированы утверждённым будущим деревом, а не порядком появления в этом частичном пакете: `MAP-001` — root position `0`; `MAP-006` — position `4` среди детей главной по порядку основной навигации макета (services, actions, gallery, reviews, articles, contacts); `MAP-031` — position `0` среди детей каталога по порядку карточек `work/articles.html`. Уникальность проверяется только для пары `(parent_uuid, position)`, как в существующей модели; одинаковый `0` на разных уровнях корректен. Пропуски зарезервированы для ещё не перенесённых siblings и не заполняются временными страницами.

Абзацы хранятся как обычные строки, а не доверенный HTML. Поэтому пакет не переносит script/style/event attributes, Django/Python/JavaScript или произвольную разметку. Будущий применитель обязан экранировать текст и построить разрешённые `<p>` сам; этот срез применитель не создаёт.

## Валидатор

`tools/dev09-articles-slice.mjs` использует только встроенные `fs/path/crypto` существующего Node и принимает только `--check` или `--selfcheck`.

- До любого чтения для фиксированных MAP, RTE, package и трёх snapshots проверяет lexical repo containment, `lstat` regular-file, отсутствие symlink/junction/reparse и realpath containment; realpath обязан совпасть с ожидаемым lexical target. Произвольных входных путей нет. Source path из пакета сначала обязан exact-match allowlist и MAP/RTE, и только затем допускается к filesystem-проверкам.
- Повторно проверяет SHA входных MAP/RTE из D-729 и SHA каждого source snapshot.
- Требует exact set/order трёх MAP, exact ready review state и one-to-one совпадение MAP↔RTE.
- Проверяет закрытую JSON-схему, UUID, parent chain без цикла, unique URL/ID и unique `(parent_uuid, position)`, exact positions, kinds и `is_published=false`.
- Для `MAP-031` только после проверки полного snapshot SHA нормализует CRLF/CR в LF и читает фиксированные строки 248–259 из `source_main_locator=:248`. После удаления только внешних tabs/spaces строки обязаны иметь узкую exact grammar: открывающий `<div class="col-lg-9 col-md-8">`; whitespace-only; `<div class="pagetitle">`; `<i ></i>`; один `<h1>TEXT</h1>`; `</div>`; ровно три последовательных single-line `<p>TEXT</p>`; две whitespace-only строки; закрывающий `</div>`. Внутри H1/P запрещены `<`, `>`, CR/LF и любые entities кроме единственного поддержанного `&ndash;`, который декодируется в Unicode `–`; остальной текст, включая внутренние пробелы и дефисы, не нормализуется. Неизвестная entity, лишняя/пропавшая строка, wrapper/tag, второй locator или malformed UTF-8 закрывают проверку. Полученные H1 и три строки сравниваются exact Unicode с пакетом. Negative fixtures selfcheck покрывают duplicate locator, nested/active tag, unknown entity, malformed wrapper/line count и paragraph mismatch.
- Для `MAP-001/006` не притворяется, что содержимое перенесено: проверяет только metadata/source identity и `content_state=deferred`.
- Выводит bounded JSON без HTML excerpts, пользовательских данных и абсолютных путей. Ошибки снаружи — только постоянный код.
- Не использует сеть, subprocess, npm, Django, БД; ничего не пишет и не импортирует.

## Приёмочные сценарии

- `MIGA-001`: `--check` проходит только при exact package schema и exact трёх MAP/RTE/source hashes.
- `MIGA-002`: пакет содержит ровно цепочку `MAP-001 → MAP-006 → MAP-031`; UUID/URL и `(parent_uuid, position)` уникальны, exact positions `0/4/0`, цикл/чужой parent запрещены.
- `MIGA-003`: все страницы скрыты; отсутствие `is_published=false` закрывает проверку.
- `MIGA-004`: главная и каталог явно `deferred` и не получают выдуманный текст или медиа.
- `MIGA-005`: статья содержит исходные H1/title и ровно три plain-text абзаца; изменение, потеря или добавление абзаца закрывает проверку.
- `MIGA-006`: HTML источника не становится доверенным payload; активная/неожиданная разметка в article boundary закрывает проверку.
- `MIGA-007`: повреждение MAP, RTE, snapshot либо package schema/exact values/source comparisons закрывает весь результат без частичного ready. Самохэш пакета и несуществующий внешний package-SHA не используются.
- `MIGA-008`: invalid CLI и внутренние ошибки не печатают source text, absolute paths или stack trace.
- `MIGA-009`: `--selfcheck` проверяет positive/negative grammar/schema/path fixtures в памяти, включая escape/symlink/realpath rejection через fake filesystem boundary, и не читает/не пишет рабочие данные.
- `MIGA-010`: проверка доказывает только готовность пакета; БД, публикация, MEDIA-06, READY-04/MIG-01/ANA-Q041 и остальные 112 MAP остаются вне результата.

## Явно не входит

Универсальный scraper/ETL, автоматический обход сайта, очередь, ledger/state machine, rollback-платформа, запись в БД, management UI/API, публикация, медиа, SEO-сборка, каталог карточек, остальные статьи и обход внешних blockers.
