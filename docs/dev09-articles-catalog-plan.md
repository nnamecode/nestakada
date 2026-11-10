# DEV-09D: полный ready-каталог статей тем же проверенным контрактом

Дата: 2026-11-09. Статус: план до кода, требуется независимое ревью.

## Цель и граница

Расширить уже проверенный DEV-09B/DEV-09C пакет с одной статьи до всех 18 ready-статей каталога, не создавая новый импортный слой. Итоговый пакет содержит ровно 20 скрытых страниц: существующие структурные `MAP-001 /` и `MAP-006 /articles/`, затем 18 article-детей в позициях `0..17` по порядку карточек утверждённого `work/articles.html`.

Все 18 MAP-строк имеют один `review_state=design_basis_present_verify_migration_before_launch`, один `target_template=article_plain_hero_all_text_below` и один locator `//div[contains(@class,"col-lg-9")]:248`. Фактическая read-only проверка pinned snapshots уточнила CSV facts: 14 статей содержат только plain paragraphs; `MAP-065`, `MAP-071`, `MAP-093` содержат также ровно один обычный `<ul>` с соответственно 4, 6 и 6 plain `<li>`; единственный paragraph `MAP-103` разделён тремя `<br />` на четыре plain-text segment. Иных body tags, tables, links, images и iframes нет. Поэтому универсальный HTML parser и отдельные пакеты не нужны; достаточно двух закрытых block types и code-owned hard break внутри paragraph.

Точный article subset и позиции:

| position | map_id | URL |
|---:|---|---|
| 0 | MAP-031 | `/articles/zamena-masla-v-dvigatele` |
| 1 | MAP-037 | `/articles/zamena-texnicheskix-zhidkostej` |
| 2 | MAP-043 | `/articles/zamena-filtrov-avtomobilya` |
| 3 | MAP-048 | `/articles/kompyuternaya-diagnostika-avtomobilya` |
| 4 | MAP-053 | `/articles/remen-grm` |
| 5 | MAP-057 | `/articles/remont-akpp` |
| 6 | MAP-065 | `/articles/remont-dvigatelya-avtomobilya` |
| 7 | MAP-071 | `/articles/remont-i-diagnostika-avtoelektriki` |
| 8 | MAP-072 | `/articles/remont-mkpp` |
| 9 | MAP-077 | `/articles/polirovka-far` |
| 10 | MAP-082 | `/articles/regulirovka-razval-sxozhdeniya-koles` |
| 11 | MAP-087 | `/articles/kachestvennyie-uslugi-shinomontazha` |
| 12 | MAP-093 | `/articles/sistema-oxlazhdeniya-dvigatelya` |
| 13 | MAP-100 | `/articles/ochistka-kondiczionera` |
| 14 | MAP-103 | `/articles/kuzovnoj-remont-avtomobilya` |
| 15 | MAP-105 | `/articles/povrezhdenie-lakokrasochnogo-pokryitiya` |
| 16 | MAP-108 | `/articles/pokraska-bampera` |
| 17 | MAP-110 | `/articles/kompleksnaya-shumoizolyacziya` |

## Минимальные изменения

- Существующий `app/content/dev09b_articles_slice.json` остаётся единственным versioned package. Поскольку payload честно меняется с `paragraphs` на ordered `blocks`, schema повышается до `dev09-articles-slice-v2`; v1 не маскирует новую форму. Историческое имя файла не переименовывается, чтобы не добавлять новый snapshot/manifest allowlist и не оставлять старый мёртвый пакет.
- В пакет добавляются 17 точных article-записей с фиксированными canonical UUID, URL, parent UUID `MAP-006`, position `1..17`, source path/SHA/title/H1 и ordered blocks. Разрешены только exact objects `{"type":"paragraph","segments":["…"]}` и `{"type":"unordered_list","items":["…"]}`; deferred pages имеют `blocks=[]`. Paragraph обычно имеет один segment, а только MAP-103 — четыре; package никогда не хранит `<br>`. Все страницы остаются `is_published=false`, `content_state=source_text_complete_media_deferred`, description empty; tags/attributes/entities исходника не хранятся как trusted payload.
- Existing host-only validator получает закрытый EXPECTED/SOURCES список всех 20 страниц и exact block shape для каждого article. Общая grammar не становится HTML parser: после pinned SHA и единственного exact locator проверяются фиксированный wrapper/H1, затем только ожидаемая последовательность single-line `<p>…</p>`; для трёх exact MAP IDs — одного `<ul>` с ожидаемыми 4/6/6 single-line `<li>TEXT</li>`; для MAP-103 — ровно три literal `<br />` без attributes, дающие четыре segments; затем две пустые строки и closing div. Missing/extra/reordered block/item/break или любой иной tag/attribute закрывает проверку.
- Named entities декодируются не общим HTML decoder, а exact allowlist: `&ndash;→–`, `&mdash;→—`, `&laquo;→«`, `&raquo;→»`, `&nbsp;→U+00A0`. Любая другая named/numeric entity или сырой `&`, `<`, `>`, CR/LF в text закрывает проверку. Title/H1 дополнительно подтверждены без entities.
- Existing UNIT-only writer получает тот же закрытый EXPECTED/block-shape список. Он строит HTML сам: только `<p>`, code-owned `<br>`, `<ul><li>`; каждый text-node segment/item проходит `html.escape(..., quote=False)` (кавычки не являются атрибутами), U+00A0 канонизируется только в code-owned `&nbsp;`, а итог обязан удовлетворять existing `restricted_clean(output) == output`. Package не может передать tag/attribute/raw HTML. Package SHA меняется на проверенный SHA расширенного файла; лимит 64 KiB, nofollow/regular/realpath/LF/UTF-8/duplicate/schema guards сохраняются.
- Create/replay остаются одной транзакцией и теми же Page/PRIMARY Route/revision/state/draft/pin/metadata/audit contracts. Возвращаемый count вычисляется из точного пакета, а не фиксируется числом `3`.
- Focused tests расширяются на 20 aggregate, порядок/позиции, разные paragraph counts, exact three list shapes, MAP-103 three-break shape, entity decoding, safe re-escaping/sanitizer equality, exact replay, real concurrency и late rollback. Existing negative security boundaries не удаляются и не ослабляются.

## Что не входит

Persistent local/production apply, management command, HTTP endpoint, publication, automatic scheduling, ETL/ledger/rollback framework, второй package format, новые модели/миграции/зависимости/worker/cache, catalog-card payload, media и обработка 34 blocker routes не входят. Старый сайт, VPS и production DB не затрагиваются.

## Приёмочные сценарии до кода

- `MIGD-001`: MAP/RTE дают ровно 18 ready article rows; exact IDs/URLs и позиции `0..17` совпадают с утверждённым каталогом, parent у всех — MAP-006.
- `MIGD-002`: каждый из 18 pinned source snapshots имеет exact SHA, единственный locator, expected title/H1 и exact closed block shape: 14 ordinary paragraph-only; MAP-065 `p,p,p,ul(4),p`; MAP-071 `p,p,ul(6),p`; MAP-093 `p,p,p,ul(6)`; MAP-103 `p(4 segments/3 br)`. Любое отклонение fail-closed.
- `MIGD-003`: canonical schema-v2 package содержит ровно 20 уникальных page UUID/URL и `(parent_id, position)`, две deferred structural pages и 18 unpublished source-text articles; payload допускает только typed paragraph segments/unordered-list items, произвольного HTML/JS/template payload нет; package v1 и незакрытые/лишние keys отвергаются.
- `MIGD-004`: validator selfcheck покрывает variable paragraph count, missing/extra/reordered paragraph/list/item/br, duplicate locator, active/nested/attributed tag, весь exact five-entity decode map, unknown/numeric entity, raw ampersand, malformed wrapper/facts и full package/content mismatch через production helpers.
- `MIGD-005`: default-off writer при exact UNIT DB/role атомарно создаёт ровно 20 hidden aggregate с legacy PRIMARY routes, initial revision/state/draft/pin/metadata и code-owned escaped p/br/ul/li main_text; malicious strings экранируются во всех segments/items, `restricted_clean(output)==output`, published count равен нулю. MAP-108 whitespace-only U+00A0 paragraph сохраняется exact как исходный контент и не считается пустой строкой.
- `MIGD-006`: полное exact replay всех 20 aggregate не создаёт новых строк; missing/mixed/changed/extra page-related state закрывается до частичной записи.
- `MIGD-007`: ошибка на поздней статье откатывает все созданные в транзакции страницы, маршруты, версии, reservations, metadata и audit events.
- `MIGD-008`: ENV/default-off/settings guard остаётся до package/DB; actual `current_database/current_user` остаётся первым SQL transaction до content/auth locks и mutation. Persistent/local/production запуск невозможен.
- `MIGD-009`: replay/preflight проверяют UUID collisions и полный aggregate/audit tuple для всех 20 страниц, включая обе стороны owner-draft pin cohort и отсутствие extra migration events.
- `MIGD-010`: два реальных одновременных вызова writer дают ровно один create и один exact replay, итог — ровно 20 aggregates и 20 migration audit events без partial/duplicate state.
- `MIGD-011`: focused DEV-09 и полный content/security guard проходят; Django check, makemigrations `--check --dry-run`, фактические package LF/SHA/size `<=64KiB` и diff-check проходят без повышения cap.
- `MIGD-012`: HTTP/CLI/management endpoint, публикация, scheduler, network и write-действия host validator отсутствуют. Package schema v2 является только закрытой формой данных, не DB schema; новых model/migration/dependency/ETL/cache/worker/state-machine слоёв нет, повторно используются доказанные DEV-09B/DEV-09C contracts.

После реализации обязательны independent code review и остановка test foundation. До `APPROVED` DEV-09D не считается завершённым.
