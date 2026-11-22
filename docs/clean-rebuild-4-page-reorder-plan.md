# REBUILD-4 — bounded owner Page children reorder slice

Дата: 2026-11-21. ID: `RB4-SLICE-004E-PAGE-REORDER`. Статус: **D-1833 sole substage run stopped pre-PG at exact `SERVER_SERIAL_RNG`/`RandomNumberGenerator.Fill(serial)` boundary; cleanup/post-audit clean, product0 and exact196 undetermined; independent terminal review `ACCEPTED_FAIL`, coordinator0/1/0; TLS branch owner-paused with no subdivision/retry/probe/guessed fix absent a new explicit owner decision**.

## Purpose and boundary

Это ближайший незаблокированный bounded этап после закрытого Page Create. Он добавляет только owner-only изменение порядка полного набора direct children одного exact parent либо root. Команда меняет только `Page.position` этих siblings и `SiteSettings.structure_generation`.

Parent, name, kind, publication, every Route/URL, current+previous content, grants, media usages, gallery composition и все Page других sibling groups остаются неизменными. Reorder не создаёт, не удаляет, не перемещает между parents, не rename-ит и не publish-ит Page. Page Move runtime остаётся owner-paused; URL/delete/B002/browser/live/deploy/push закрыты.

Срез переиспользует existing `Page`, `SiteSettings.structure_generation`, staff-session lock, `Action.PAGE_REORDERED`, private/no-store ingress и public navigation projection. New model/migration/dependency/receipt/xmin token/tree snapshot/workflow/cache/generic structural framework/JavaScript нет.

## Command and structural contract

Одна pages-owned команда:

```text
reorder_children(
  actor_id,
  session_generation,
  base_structure_generation,
  parent_id,                 # canonical UUID or None for root
  ordered_child_ids,         # complete exact tuple, 0..512 canonical UUIDs
) -> ReorderResult(structure_generation, parent_id, count)
```

До transaction валидируются типы: canonical UUID objects, positive non-bool base, tuple/list length<=512, UUID-only unique children. Invalid shape, включая duplicate requested UUID, даёт fixed `INVALID_PAGE_REORDER` без query. В transaction lock order остаётся `User -> SiteSettings -> one affected Page set by UUID -> audit`. Active OWNER проверяется до SiteSettings/Page access; EMPLOYEE получает `FORBIDDEN`. Затем блокируется singleton SiteSettings и exact base сравнивается с current generation.

После SiteSettings lock выполняется bounded discovery snapshot: exact non-root parent row и at most513 actual direct children как `(id,parent_id,position)`. Unknown parent даёт `PARENT_NOT_FOUND`; child count513 или неоднозначность — `REORDER_UNAVAILABLE`. Из snapshot строится один deduplicated affected UUID set `{parent if non-root} ∪ children`; весь set приобретается одним `select_for_update().order_by("id")`. После lock команда точно повторяет parent-existence и direct-child `(id,parent_id,position)` projection и требует полного равенства discovery snapshot. Structural commands сериализованы SiteSettings lock, но эта post-lock revalidation дополнительно закрывает membership/parent/position drift и доказывает common stable-order discipline. Только затем requested tuple сравнивается с actual child UUID set и count. Missing/extra/foreign child даёт `CHILD_SET_CONFLICT`; duplicate уже был закрыт prevalidation400. GET использует тот же SiteSettings → bounded discovery → one UUID-ordered affected lock → exact revalidation rule для coherent form snapshot.

Actual visible order определяется existing `(position, UUID)`. Если requested order совпадает и positions уже exact contiguous `0..N-1`, команда возвращает `NO_CHANGE`, writes/generation/audit0. Совпадающий order с gaps является реальной нормализацией. Empty group всегда `NO_CHANGE`; one-child group commits only when its position is not0.

Current non-deferrable unique `(parent, position)` не ослабляется, включая root `nulls_distinct=False`. Для любого real change с `N>=1`:

1. `base = max(max_current_position, N-1) + 1`;
2. существующая PostgreSQL/Django authority закреплена literal `_PAGE_POSITION_MAX = 2_147_483_647`; до первой записи вычисляется `highest = base + N - 1` и требуется `highest <= _PAGE_POSITION_MAX`;
3. все locked children в stable UUID order получают unique temporary `base..base+N-1`;
4. requested order получает final exact `0..N-1`.

Ни один child не меняет parent. Недостаточный headroom даёт `REORDER_UNAVAILABLE` до write; boundary покрывает `N=1` и `N=512` для root/non-root. Любой collision/DB/audit fault откатывает positions, generation и event одной outer transaction. Schema/constraint changes запрещены.

Один safe `PAGE_REORDERED` event получает detail `{generation,count}`. Existing audit contract требует PAGE target UUID и не допускает null. Поэтому target выбирается детерминированно из affected children: первый child в requested order, чей ordinal отличается от actual order; при normalization-only — первый child actual order. Successful command всегда имеет `N>=1`, поэтому target существует. Это не дополнительный caller input и не identity/replay mechanism.

Повтор после success видит stale base и возвращает conflict; отдельный receipt/operation UUID не создаётся. Concurrent reorder или любая другая structural command с одним base имеют не более одного winner.

## Fixed private HTTP and no-JavaScript form

Один fixed endpoint `GET|POST /manage/pages/reorder/`.

- existing private ingress cap/content boundary применяется до bounded body read. На POST Django `CsrfViewMiddleware` может разобрать уже ограниченную urlencoded form для проверки token до вызова view. Затем `staff_session_required` и OWNER role check выполняются до application field parsing и до SiteSettings/Page/command reads. Для unauthorized request гарантируется structural-query0, но не заявляется body-read0;
- GET принимает exact single query key `parent=root|<canonical UUID>`. В short transaction он блокирует SiteSettings, exact non-root parent и at most512 direct children; snapshot сортируется `(position,UUID)`. Unknown parent даёт404, malformed query400, missing/ambiguous settings or cap513 gives constant503;
- owner page list получает literal link для root; owner editor получает literal `Упорядочить дочерние страницы` для exact Page. Employee DOM не содержит оба control;
- template показывает current siblings и по одной обычной submit-кнопке `вверх/вниз`. JavaScript, drag-and-drop и generic tree widget отсутствуют. Disabled boundary buttons не отправляются;
- POST принимает только `application/x-www-form-urlencoded`, files0, canonical positive `base_structure_generation`, exact `parent`, repeated `child_id` carriers in current form order (1..512 unique canonical UUIDs) и ровно один scalar `move`. Literal move value имеет одну из двух полных форм `<canonical-uuid>|up` или `<canonical-uuid>|down`: ровно один `|`, total length39 или41, canonical UUID before separator, exact lowercase direction after it. Optional CSRF token допускается ровно один. Duplicate scalar/unknown keys, malformed/duplicate child IDs, malformed move, target outside list, boundary move, wrong type, multipart/file or body cap return fixed400 `INVALID_PAGE_REORDER_INPUT` before command;
- HTTP adapter swaps only the requested adjacent pair in the submitted exact list and passes the complete result to `reorder_children`. Caller reordering/tampering cannot escape the exact-set command proof; stale membership/order is conflict;
- closed command/HTTP mapping: `INVALID_PAGE_REORDER` (shape/duplicate requested UUID) →400; `PARENT_NOT_FOUND` →404; `STALE_STRUCTURE|NO_CHANGE|CHILD_SET_CONFLICT` → private409 fixed conflict; `REORDER_UNAVAILABLE` (cap513, corrupt/revalidation drift, headroom) and DB/audit/unexpected fault → constant503. Success302 returns to the same canonical reorder GET for parent;
- anonymous/stale session use existing bare-login contract; EMPLOYEE GET/POST403 before Page/SiteSettings query; missing/invalid CSRF framework403; valid-CSRF unsupported method405 with `Allow: GET, POST`;
- endpoint enters existing private/no-store and 4 MiB ingress boundary with own fixed `INVALID_PAGE_REORDER_INPUT`. Conflict/error HTML never reflects submitted UUID list or Page names.

## Navigation and preservation

Existing read-only public navigation observes the committed `(parent,position,UUID)` order through `structure_generation`. Published/hidden behavior and hidden-ancestor promotion do not change. Fixed Header exact-six is unaffected; reorder changes only appropriate automatic section/catalog order. Breadcrumb ancestry and every exact URL remain unchanged.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-ROR-001` | anonymous/stale/EMPLOYEE GET+POST, employee list/editor and direct command | Ingress cap then framework CSRF may parse bounded POST; existing bare-login/403 before application parsing/structural query/mutation; employee DOM controls0; SiteSettings/Page/audit access0 |
| `RB4-ROR-002` | OWNER reorders complete root and non-root sibling sets | Only exact siblings positions become requested contiguous `0..N-1`; generation+1; one `PAGE_REORDERED` with exact count and deterministic affected-child target |
| `RB4-ROR-003` | already contiguous order; same order with gaps; empty and one-child group | Exact no-op writes0; gaps normalize atomically; empty no-op; one child normalizes only from nonzero position |
| `RB4-ROR-004` | missing/extra/duplicate/foreign child, unknown parent, discovery→lock drift, child moved after GET, cap512/513 | One UUID-ordered affected lock+exact revalidation; duplicate shape400/query0; exact-set mismatch409; parent404; cap/corrupt503; partial order0 |
| `RB4-ROR-005` | preservation snapshot across other groups and affected rows | Parent/name/kind/publication, Routes/URLs, current+previous, grants, usages, gallery and unrelated Page rows remain value-identical |
| `RB4-ROR-006` | staging collision boundaries and literal `2_147_483_647` headroom for N=1/N=512 root/non-root | `highest=base+N-1` checked before writes; unique constraint remains enabled; valid boundaries succeed; insufficient headroom `REORDER_UNAVAILABLE` with writes0 |
| `RB4-ROR-007` | two reorder/other structural commands share one base; audit/row-save faults | At most one success; loser stale; fault rolls back all positions/generation/audit; deadlock/partial tree0 |
| `RB4-ROR-008` | navigation after root/non-root reorder and hidden ancestors | Automatic navigation order updates after commit; hidden promotion unchanged; Header exact-six, ancestry and URLs unchanged |
| `RB4-ROR-009` | owner GET root/non-root and no-JS adjacent controls | Coherent generation+exact ordered carriers; boundary buttons disabled; literal list/editor links only for owner; names autoescaped |
| `RB4-ROR-010` | POST literal `<UUID>|up|down` success, repeated submit, stale/exact-set drift | Exactly one separator and exact direction; adapter swaps one adjacent pair; command proves full set; success302 canonical GET; repeat/stale/set mismatch fixed409 without reflection |
| `RB4-ROR-011` | malformed query/body, duplicate/unknown keys or child IDs, noncanonical UUID, bad move length/separator/direction, target/boundary, multipart/file/body cap | Exact fixed400 `INVALID_PAGE_REORDER_INPUT`; command/structural-query0 where applicable; submitted values not reflected |
| `RB4-ROR-012` | CSRF middleware ordering, unsupported methods, session/role race and unexpected projection/command fault | Bounded form may be parsed only by framework CSRF before view; then existing bare-login/403 before structural queries; framework403/405, constant503 and private/no-store throughout |

Focused source target: exact12 test methods, proposed command/domain8 plus HTTP4, with subtests covering root/non-root, set matrices, boundary/fault/concurrency and wire matrices. PostgreSQL exact count/regression cohort require a separate reviewed run plan and fresh explicit owner permission after source review.

## Stop conditions

Если корректный reorder требует schema/constraint change, client JavaScript, arbitrary drag/drop payload, new tree snapshot/receipt/operation ledger, generic structural service, changes parent/URL/content/media, weakens full-set proof или возобновляет Page Move runtime, остановиться до кода и запросить новое решение. Этот slice не поглощает Move/URL/delete/navigation model/B002.
