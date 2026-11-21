# REBUILD-4 — bounded owner Page move slice

Дата: 2026-11-20. ID: `RB4-SLICE-004C-PAGE-MOVE`. Статус: **D-1779 source implemented and independently APPROVED P0/P1/P2=0/0/0; PostgreSQL runtime not yet authorized**.

## Purpose and boundary

Это ближайший bounded этап после закрытого Page Rename. Он добавляет только owner-only перенос одной существующей `Page` в другого родителя или в корень с exact местом среди siblings. Команда меняет только `Page.parent_id` переносимой Page и `Page.position` затронутых source/destination sibling groups.

Имя, kind, publication, Route/URL самой Page и всех descendants, current+previous content, H1/SEO, grants, media usages, gallery composition и SiteSettings values кроме `structure_generation` не меняются. Move не создаёт, не удаляет, не rename-ит и не publish-ит Page, не меняет URL и не реализует bulk reorder. Отдельные create/reorder/URL/delete stages, B002, browser, live/deploy/push остаются закрыты.

Срез переиспользует existing `Page`, `SiteSettings.structure_generation`, `staff_session` lock, `Action.PAGE_MOVED`, private/no-store ingress и public navigation projection. New model/migration/dependency/receipt/xmin token/tree snapshot/workflow/cache/generic structural framework/JavaScript нет.

## Command and structural contract

Одна pages-owned команда:

```text
move_page(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  destination_parent_id,
  before_page_id,
) -> MoveResult(structure_generation, parent_id, position)
```

`destination_parent_id=null` означает root, `before_page_id=null` — конец destination siblings. До transaction команда требует exact positive non-bool integer base и UUID-compatible non-bool identities; malformed input не читает DB. Target не может быть destination parent или `before_page_id`.

Одна outer `transaction.atomic()` использует lock order `User -> SiteSettings -> Page rows by UUID -> audit`. Active OWNER проверяется до structural reads. Employee получает `FORBIDDEN` без SiteSettings/Page/audit access. Singleton SiteSettings сериализует все clean-rebuild structural commands; exact base mismatch даёт `STALE_STRUCTURE`, mutation/audit0.

После SiteSettings lock команда выполняет bounded discovery без write: читает target, destination ancestry до root и полные direct sibling ID sets old parent/destination parent, затем строит один deduplicated affected-ID set. В одном `select_for_update(...).order_by("id")` она блокирует весь этот set в UUID order. После получения всех Page locks команда заново читает actual destination ancestry и полные old/new sibling ID sets и exact-сравнивает IDs и relations с discovery snapshot. Missing/extra/reparented membership, изменившаяся ancestry или любой не покрытый affected row дают fail closed до write. Итеративный Page locking и lock expansion после ordered acquisition запрещены.

Единый affected set содержит:

1. target Page;
2. destination parent и его exact ancestry до root;
3. полные direct sibling sets old parent и destination parent.

Missing target даёт `PAGE_NOT_FOUND`. Missing destination/before, before из чужой sibling group, destination=self/descendant, repeated ancestor/corrupt ancestry или placement drift fail closed до write. Server cycle check использует actual locked destination-to-root chain, а не только GET options. `NO_CHANGE` допустим только когда parent и effective order уже совпадают с запросом **и** current positions этой group уже exact contiguous `0..N-1`; writes/audit0. Если effective order совпал, но positions имеют gaps, команда выполняет обычную успешную атомарную нормализацию, generation+1 и один audit.

Успех строит exact final lists из locked rows: target удаляется из source, вставляется immediately before exact destination child или в конец, а затронутые group positions становятся contiguous `0..N-1`. Same-parent move обрабатывает одну group ровно один раз.

Текущий non-deferrable unique `(parent, position)` не ослабляется, включая root благодаря `nulls_distinct=False`. Здесь `S` — размер source group до move, включая target (`S>=1`), `D` — размер destination group до move (`D>=0`), а при same-parent `N=S=D` обозначает единственную group. После locks и до первой записи команда вычисляет staging base строго выше всех current **и final** positions и проверяет base/highest temporary value против верхней границы `PositiveIntegerField`; при нехватке headroom возвращает typed unavailable с writes0.

- same-parent: `base = max(max_current_position, N-1) + 1`; все `N` rows одной group переводятся в уникальные `base..base+N-1`, после чего получают final contiguous `0..N-1`;
- cross-parent: `base = max(max_affected_current_position, S-2, D) + 1`, то есть строго выше final source `0..S-2` и final destination `0..D`. `S-1` остающихся source rows получают `base..base+S-2`, все `D` destination rows — `base..base+D-1` (ranges могут совпадать, пока parents различны), а target получает отдельный `special = base + max(S-1, D)`, не занятый ни в source, ни в destination. Только после полного staging target меняет parent, сохраняя свободный `special`; затем source и destination получают exact final contiguous ranges независимо от порядка final row updates.

Каждая row staged ровно один раз до finalization; никакой target parent switch со значением из destination temporary range не допускается. Unexpected collision/DB fault откатывает всю outer transaction; partial final tree невозможен. Schema/constraint changes запрещены.

Затем `SiteSettings.structure_generation` увеличивается ровно на 1 и пишется один safe `PAGE_MOVED`, target PAGE UUID, detail только `{"generation": new_structure_generation}`. Audit/DB fault откатывает parent, все positions, generation и event. Concurrent structural commands на одном base имеют не более одного winner; global structure generation intentionally invalidates any older structural form, including an unrelated branch.

## Fixed private HTTP and coherent form

Один fixed owner-only no-JavaScript endpoint:

- `GET /manage/pages/<uuid>/move/` после immediate OWNER check в short transaction блокирует SiteSettings, читает at most513 Page rows в stable UUID order и требует count<=512. Полный graph в памяти обязан иметь existing/null parents, no self/cycle. Form snapshot содержит exact `base_structure_generation` и один required `<select name="placement">`; target и его descendants не предлагаются как parents. Locks освобождаются до render;
- placement value имеет только closed canonical form `root|end`, `root|<before UUID>`, `<parent UUID>|end` или `<parent UUID>|<before UUID>`. Любой UUID wire token должен буквально совпадать с canonical lowercase hyphenated `str(UUID(token))`; альтернативный регистр, braces, hex-only и иная textual normalization отвергаются. Для каждой legal parent group enumeration сначала удаляет target из child list, затем создаёт ровно `N+1` slots: before каждого оставшегося child и end. Поэтому same-parent никогда не выдаёт `before_page_id=target`. Form без JS показывает one option per legal insertion slot, всего не более `2*Page count+1`; labels имен всегда autoescaped;
- `POST` принимает только `application/x-www-form-urlencoded`, files0, exact single `base_structure_generation` и `placement` плюс optional single CSRF token. Base — canonical positive ASCII decimal; placement — exact closed grammar и bounded length. Duplicate/unknown keys, malformed UUID/sentinel, wrong type, multipart/file, body cap дают fixed400 before command;
- success302 возвращает в existing editor target Page. Stale generation, no-change, self/descendant, unknown/foreign destination/before дают private409 fixed conflict with exactly one reload link to move form; target Page missing404; missing settings, corrupt/oversize graph, ambiguous DB or unexpected command/audit fault give constant503;
- employee GET/POST —403 до structural query/command; anonymous/stale session используют existing exact bare-login contract; missing/invalid CSRF — framework403; valid-CSRF unsupported method —405 with `Allow: GET, POST`;
- endpoint входит в private/no-store и 4 MiB ingress boundary с own fixed `INVALID_PAGE_MOVE_INPUT`. Error/conflict не отражает placement или Page names.

Existing editor получает только одну owner-link `Переместить страницу`; employee DOM её не содержит. API, modal, drag-and-drop, JavaScript и generic form/tree builder не добавляются.

## Navigation and URL result

Move никогда не изменяет `Route` ни target URL. Existing read-only public projection после commit видит new parent/order по `structure_generation`. Published descendants при hidden ancestors по-прежнему поднимаются к nearest published ancestor/root. Fixed Header exact-six не меняется; move влияет только на appropriate automatic section/catalog navigation blocks.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-MOV-001` | anonymous/stale/EMPLOYEE GET+POST, employee editor and direct command | Existing bare-login/403 before tree query or mutation; employee DOM has no move control; SiteSettings/Page/audit access0 |
| `RB4-MOV-002` | OWNER moves Page between two parents before exact child and to end/root | Target parent and exact position change; source/destination become contiguous; structure generation +1; one safe `PAGE_MOVED`; exact result DTO |
| `RB4-MOV-003` | same-parent placement, exact current placement and same order with gapped positions | Real local move updates one group once; exact contiguous no-op returns fixed conflict with writes/generation/audit0; same order with gaps atomically normalizes and commits generation+1/audit1 |
| `RB4-MOV-004` | self, descendant, unknown parent, foreign/unknown before, corrupt ancestry | Closed conflict/unavailable result before write; server uses actual locked ancestry; cycle and partial tree forbidden |
| `RB4-MOV-005` | preservation snapshot | Name/kind/publication, all Route targets/modes/outcomes including descendants, content/current+previous, grants, usages, gallery and all unrelated Page rows remain value-identical |
| `RB4-MOV-006` | two structural commands on one base and unrelated-branch structural commit | At most one winner; every older global structure form becomes stale; loser writes/audit0 |
| `RB4-MOV-007` | same/cross-parent collision-sensitive order, including `S=1,D=0`, `S=1,D=1`, contiguous destination where old formula gave `base==D`, root `parent=NULL`, and source/destination temporary-value overlap at parent switch | Staging is strictly above all old/final ranges and distinct target `special` never violates unique constraint; final groups exact contiguous; insufficient headroom/fault rolls back without partial order |
| `RB4-MOV-008` | injected target/sibling/settings/audit DB fault | Parent, every position, generation and audit roll back together |
| `RB4-MOV-009` | GET concurrent with move; same-parent slot enumeration; 512/513 rows; missing parent/cycle | GET returns one complete old or new `(generation, placements)` snapshot; mixed form forbidden; target is removed before `N+1` slots and is never its own before; 512 accepted, 513/corrupt graph fixed503 |
| `RB4-MOV-010` | wire, canonical/noncanonical UUIDs, duplicate/unknown keys, placement grammar, wrong content type/files, >4 MiB, CSRF, PUT | Only lowercase hyphenated UUID text is accepted; exact fixed400/framework403/405 table; command0 and private input/name reflection0 |
| `RB4-MOV-011` | published/hidden tree before and after move | Existing public navigation immediately reflects committed parent/order and hidden-ancestor promotion; all exact URLs and Header exact-six unchanged |
| `RB4-MOV-012` | DAG/static scope inspection | Discovery→one deduplicated Page set→single UUID-ordered lock→exact revalidation; lock order User→SiteSettings→Page UUID order→audit; models/migrations/dependencies/receipts/xmin tokens/cache/JS/API/public renderer/media/B002 changes0; one literal route/link only |

Focused source target: exact12 test methods, proposed command/domain8 plus HTTP4, with subtests for closed matrices. Exact count, PostgreSQL concurrency/constraint evidence and accepted regression cohort require a separate reviewed run plan and fresh explicit owner permission only after source review.

## No-bloat and stop line

Если correct move требует schema/constraint change, OperationReceipt/IdentityReservation, per-row xmin form token, generic tree service, editable navigation model, cache, recursive SQL framework, JavaScript drag-and-drop или URL rewrite, остановиться до кода и вынести новый architectural decision. Этот срез не должен превращаться в bulk reorder/create/URL/delete subsystem.
