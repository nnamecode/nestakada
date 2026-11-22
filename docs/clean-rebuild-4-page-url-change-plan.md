# REBUILD-4 — Page URL Change

Дата: 2026-11-21. ID: `RB4-SLICE-004G-PAGE-URL-CHANGE`. Статус: **plan и source independently APPROVED 0/0/0; PostgreSQL/runtime 0**.

Initial review `0/2/2` подтвердил два блокера качества: обычный retention AuditEvent нельзя использовать как вечную origin-authority; каждый URL change добавляет Route и обязан сохранять Page Delete ceiling512. D-1846 утверждает remediation ниже: один durable boolean, bounded Route composition и закрытые HTTP branches. Audit остаётся журналом, не identity table.

## Граница

Срез добавляет только owner-only смену PRIMARY path существующей Page, созданной командой clean rebuild `create_page`. Импортированные legacy Page защищены. Старый PRIMARY в той же transaction становится прямым `REDIRECT` этой же Page; существующие redirects продолжают разрешаться через единственный актуальный PRIMARY и не образуют цепочку.

Не меняются Page name/kind/parent/position/publication, descendants, aliases, content current/previous, grants, media usages и SiteSettings кроме `structure_generation`. Единственное schema change — `Page.primary_url_mutable BooleanField(default=False)` и обычная `AddField` migration: migration backfill существующих rows в false выполняется Django schema operation, custom `RunPython` отсутствует, постоянный PostgreSQL DEFAULT не предполагается. Importer raw `INSERT_PAGE_SQL` явно включает колонку и literal SQL `FALSE`; `TARGET_READBACK_QUERIES["pages"]`, expected target rows/canonical digest и target invariant требуют false для каждой imported Page. Model/migration fitness доказывает exact non-null Boolean, Python default false и parity. `create_page` явно создаёт true; `_create_replay` требует locked marker exactly true, иначе `PAGE_ID_CONFLICT`. Новых tables, dependencies, receipts, route registry, generic structural framework, JavaScript, public renderer, B002 или live/deploy нет.

## Authority и команда

Единственная authority смены URL — locked `Page.primary_url_mutable is True`. Значение false закрывает GET/POST/command как `LEGACY_URL_PROTECTED`. Audit cardinality, retention и actor не участвуют. Delete→recreate того же UUID через `create_page` создаёт новую Page с true независимо от старых retained audit rows. URL change добавляет обычный `PAGE_URL_CHANGED`, но не меняет marker.

```text
change_primary_url(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  new_path,
) -> UrlChangeResult(structure_generation, primary_path, redirect_path)
```

Ввод проверяется до transaction: canonical Page UUID, positive non-bool integer base и exact NFC path длиной 1..2048. Один pages-owned `validate_new_public_path(value, *, error_code)` становится sole write boundary для `create_page` и URL change. Path начинается одним `/`, не содержит scheme/host/query/fragment/backslash/whitespace/control, malformed percent escape, decoded `.`/`..`, literal или percent-decoded `/manage` namespace, включая encoded slash variants. Никакого trim/normalization. Action-specific error mapping сохраняется: create → `INVALID_PAGE_CREATE`, URL change → `INVALID_PAGE_URL`.

Transaction lock order: existing active staff User → singleton SiteSettings → exact Page → bounded Route этой Page в UUID order. OWNER проверяется до structural rows. Route query materializes `[:513]`: count>512 → `URL_CHANGE_UNAVAILABLE`; count=512 не имеет headroom и тоже отказывает до write; count≤511 допускает дальнейшую проверку. Locked composition требует ровно один PRIMARY; каждый mode/outcome входит в closed enums, каждый Route проходит `clean()`, normal outcome совпадает с Page.kind, wash alias сохраняет единственное model exception, каждый REDIRECT target отличается от current PRIMARY. Global target unique уже DB-enforced. Damaged composition → `URL_CHANGE_UNAVAILABLE`/write0. Затем проверяются current base и `primary_url_mutable is True`. Новый path, совпадающий с current PRIMARY, даёт `NO_CHANGE`; любой existing PRIMARY/ALIAS/REDIRECT с этим target — `PATH_OCCUPIED`.

Успех:

1. меняет target существующего PRIMARY на `new_path`;
2. создаёт один Route той же Page: old target, mode `REDIRECT`, outcome = Page.kind;
3. увеличивает `SiteSettings.structure_generation` ровно на 1;
4. пишет один `PAGE_URL_CHANGED`, target Page UUID, detail только `generation`;
5. возвращает new generation/new PRIMARY/old redirect.

После успеха exact Route count не превышает512. Route full validation проходит до сохранения. Unique target и singleton structure lock закрывают collision/concurrency. Любой validation/DB/audit fault откатывает PRIMARY, redirect, generation и audit. Retry после уже committed change видит stale base/path occupied и не пишет второй redirect/audit; специальный receipt не создаётся.

## Fixed private HTTP

- `GET /manage/pages/<uuid>/url/`: только OWNER; coherent short transaction читает SiteSettings → Page → bounded Routes, проверяет marker/composition/headroom и затем показывает escaped Page name, current PRIMARY, generation и одно поле `new_path`. Marker false получает `403 LEGACY_URL_PROTECTED`, unknown Page `404`, damaged/cap-full composition или missing settings `503`.
- `POST` exact urlencoded wire: `base_structure_generation`, `new_path`, optional single framework CSRF. Unknown/duplicate/file/multipart/JSON/noncanonical fields → `400 INVALID_PAGE_URL_INPUT` до command.
- success → `302` в существующий editor Page. Stale/no-change/path conflict → private `409` с одной reload-ссылкой на URL form; input не отражается. Unexpected fault → constant `503`.
- endpoint входит в private/no-store и 4 MiB pre-body ingress. Missing/invalid CSRF → framework403/command0; stale session → existing exact login redirect after cleanup; valid-CSRF unsupported method → `405 Allow: GET, POST`.
- Editor OWNER видит literal link «Изменить URL» только для valid created-here Page; employee и legacy Page link не получают. List action, modal, API, JS и slug helper отсутствуют.

## Acceptance before code

| ID | Сценарий | Требование |
|---|---|---|
| `RB4-URL-001` | owner меняет A→B | PRIMARY=B, REDIRECT=A той же Page, generation +1, один safe audit; прочие данные неизменны |
| `RB4-URL-002` | A→B→C | A и B остаются REDIRECT той же Page и resolver направляет оба прямо на C; chain/cycle нет |
| `RB4-URL-003` | existing/imported marker=false; create=true; delete→recreate same UUID | false form/action/command закрыты; fresh created incarnation true допускается независимо от audit retention/cardinality; mutation до authority 0 |
| `RB4-URL-004` | invalid path matrix | query/fragment/private namespace/encoded private namespace/malformed percent/traversal/backslash/control/non-NFC/cap+1 отклоняются без normalization/write |
| `RB4-URL-005` | new path занят PRIMARY/ALIAS/REDIRECT; no-op; Route count511/512/513 | occupied/no-change без write; 511→success и final512; existing512/513 fixed unavailable без write, Page Delete ceiling сохранён |
| `RB4-URL-006` | preservation | name/kind/tree/positions/publication/marker=true/children/aliases/content/grants/usages и SiteSettings scalars неизменны; Page Delete composition digest включает marker как часть всех Page fields |
| `RB4-URL-007` | stale base и concurrent structural commands | благодаря User→SiteSettings→Page→Route lock одному base соответствует максимум один winner; loser пишет 0 |
| `RB4-URL-008` | injected validation/Route save/settings save/audit fault | PRIMARY/redirect/generation/audit откатываются атомарно |
| `RB4-URL-009` | anonymous/employee/stale session, missing/invalid CSRF, wire/body cap, PUT | auth/employee query0, stale exact login redirect, framework403, exact 400/405/409/503 boundaries, private no-store, submitted path не отражается |
| `RB4-URL-010` | UI visibility и public read authority | link только OWNER+created-here; old path direct301 к current PRIMARY; hidden final path сохраняет blank200 contract |
| `RB4-URL-011` | schema/importer/DAG scope | one non-null Page bool+ordinary AddField migration; existing=false, raw importer INSERT/readback/digest=false, create/replay=true; Delete digest/preservation includes marker; pages использует existing accounts/audit/models; new table/dependency/JS/receipt/B002/public-template changes 0 |
| `RB4-URL-012` | PostgreSQL focused cohort | exact new URL domain8 + HTTP4 с marker/delete-recreate/cap/CSRF subtests; Route UNIQUE, lock order, rollback и concurrency исполняются в отдельном reviewed runtime package |

Кроме новых exact12, regression package отдельно включает существующие affected cohorts: rebuild3 target importer raw SQL/readback/digest; schema model↔migration fitness; Page Create replay marker; Page Delete composition/preservation; `makemigrations --check --dry-run` и migration drift check. Эти existing regressions не притворяются частью exact12 и должны быть посчитаны run-plan review до runtime.

## Stop line

Кроме единственного D-1846 `primary_url_mutable`, если реализация требует новый marker/table, receipt/history, generic router, redirect cleanup policy, изменения exact legacy URL, child URL rewrite, public template или storage layer, остановиться и вынести выбор владельцу. Runtime/Docker — только после source review и отдельного bounded разрешения.
