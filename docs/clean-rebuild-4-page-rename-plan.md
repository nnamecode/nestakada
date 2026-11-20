# REBUILD-4 — bounded owner Page rename slice

Дата: 2026-11-20. ID: `RB4-SLICE-004B-PAGE-RENAME`. Статус: **source complete D-1746; plan and final source review APPROVED0/0/0, exact10/diff-check PASS; Docker/runtime0 pending separate reviewed run plan and explicit owner permission**.

## Purpose and boundary

Это ближайший минимальный незаблокированный инкремент `RB4-SLICE-004` после завершённой публикации и SiteSettings. Он добавляет только owner-only переименование уже существующей Page. Команда меняет ровно `Page.name`; H1, SEO, kind, parent, position, publication, Route/URL, current/previous content, grants, usages и SiteSettings values не меняются.

Срез не создаёт, не перемещает, не сортирует и не удаляет Page, не меняет URL, navigation или public renderer, не добавляет preview/upload/media bytes, B002, JavaScript, live/deploy или push. Он переиспользует существующие `Page`, `SiteSettings.structure_generation`, staff-session lock и `AuditEvent`. Новых model/migration/dependency/receipt/workflow/status/tree-version/generic structural-command framework/form builder нет.

## Command and validation contract

Одна pages-owned команда:

```text
rename_page(
  actor_id,
  session_generation,
  page_id,
  base_structure_generation,
  name,
) -> RenameResult(structure_generation, name)
```

До transaction команда требует exact positive non-bool integer base, UUID-compatible Page identity и exact string name. Новый name обязан быть NFC, иметь длину `1..500`, не иметь leading/trailing whitespace, C0/DEL control characters и не состоять только из whitespace. Команда не исправляет, не trim-ит и не нормализует ввод. Нарушение даёт `INVALID_PAGE_NAME` без DB/audit write. Эти правила являются closed write boundary для нового действия; существующие импортированные имена read-time не переписываются.

Одна outer `transaction.atomic()` блокирует active staff User существующим `lock_staff_session`, немедленно проверяет OWNER и только затем блокирует exact singleton SiteSettings → target Page. Employee получает `FORBIDDEN` без обращения к SiteSettings/Page/audit. После locks проверяются exact base generation и no-change. Missing settings fail closed; unknown Page даёт `PAGE_NOT_FOUND`; stale base — `STALE_STRUCTURE`; exact current name — `NO_CHANGE`. Stale/no-change не увеличивают generation и не создают audit.

Успех:

1. меняет только locked `Page.name` через `update_fields=("name",)`;
2. увеличивает `SiteSettings.structure_generation` ровно на 1;
3. добавляет ровно один `PAGE_RENAMED`, target PAGE UUID, detail только с новым structure `generation`;
4. возвращает exact new generation и name.

Audit/DB fault откатывает Page name, generation и event вместе. Команда не читает и не блокирует Route, PageContent, PageGrant, Asset/Usage или sibling rows: они не участвуют в rename-инварианте. Конкурентные structural commands сериализуются SiteSettings lock; на одном base максимум один победитель.

## Fixed private HTTP

Один fixed owner-only no-JavaScript endpoint:

- `GET /manage/pages/<uuid>/rename/` показывает escaped current Page name и одну форму с exact hidden `base_structure_generation` и text `name` (`maxlength=500`, required). После немедленной OWNER check короткая transaction блокирует и читает `SiteSettings → Page` в том же порядке, что команда, поэтому name+generation принадлежат одному structural state; locks освобождаются до render. Employee получает403 без structural query, anonymous/stale session идёт через существующий login contract, unknown Page404, missing/ambiguous DB503;
- `POST` принимает только `application/x-www-form-urlencoded`, без files, с exact keys `base_structure_generation`, `name` и optional single CSRF token. Оба значения должны быть single; base — canonical positive ASCII decimal без sign/leading zero; name проходит тот же closed validator команды. Любой malformed/duplicate/unknown input даёт `INVALID_PAGE_RENAME_INPUT`/400 до command;
- success302 направляет в существующий editor этой Page; stale/no-change возвращает private409 с reload только rename form; unknown Page404, employee403, stale owner session302 login, unexpected DB/audit failure constant503;
- endpoint входит в существующий private/no-store и 4 MiB pre-body ingress boundary. Значение name безопасно HTML-экранируется; private error body не отражает введённое имя.

Существующий editor получает только одну owner-ссылку «Переименовать страницу». Employee DOM этой ссылки не содержит. List bulk action, modal, search, API, JavaScript и generic form helper не добавляются.

Exact HTTP outcomes:

Если строка явно не говорит иначе, session, CSRF и wire считаются валидными, чтобы проверять именно заявленный downstream outcome. Employee POST, stale-session POST и любой unsupported unsafe method передают valid CSRF token; отдельная CSRF-строка проверяет missing/invalid token до view.

| Condition | Result |
|---|---|
| valid owner GET | `200`, one fixed form with coherent name+generation |
| successful owner POST | `302`, exact Location existing editor for that Page |
| malformed wire or ingress body cap | `400 INVALID_PAGE_RENAME_INPUT`, command0 |
| employee GET/POST | `403 FORBIDDEN`, structural command/query0 |
| unknown Page | `404 PAGE_NOT_FOUND` |
| stale generation or no-change | `409`, fixed conflict marker and only one reload link to this rename form |
| missing settings, ambiguous DB or unexpected command/audit fault | `503 PRIVATE_DATA_UNAVAILABLE` |
| stale session | existing exact login redirect after logout |
| missing/invalid CSRF on POST | framework `403`, command0 |
| valid-CSRF unsupported method, включая PUT | `405`, `Allow: GET, POST`, command0 |

Все перечисленные private responses, включая redirect/error, получают `Cache-Control: private, no-store`; введённое name не отражается ни в одном error/conflict response. Exact `/rename/` regex расширяет существующий ingress allowlist и возвращает собственный body-cap marker, не общий editor marker.

## Acceptance before code

| ID | Scenario | Required result |
|---|---|---|
| `RB4-REN-001` | anonymous/EMPLOYEE GET+POST и employee editor/direct command | Existing authentication/403 before structural query or mutation; employee DOM has no rename control; settings/page/audit access0 |
| `RB4-REN-002` | OWNER renames on current base | Only Page.name changes; structure generation +1; one safe `PAGE_RENAMED`; exact returned result |
| `RB4-REN-003` | rename preservation | H1/SEO/kind/parent/position/publication/routes/current+previous/grants/usages and all SiteSettings values except structure generation remain byte/value-identical |
| `RB4-REN-004` | empty, whitespace-only, leading/trailing whitespace, non-NFC, control, 501 chars, non-string | Closed invalid-name failure; mutation/generation/audit0; no normalization |
| `RB4-REN-005` | stale base, same name, missing settings/Page | Exact stale/no-change/not-found/unavailable outcome; mutation/audit0 |
| `RB4-REN-006` | two structural commands on one base; GET concurrent with rename | Commands: at most one winner and stale loser writes0. GET returns only complete old `(name,generation)` or complete new pair; mixed pair forbidden |
| `RB4-REN-007` | injected Page/settings/audit DB fault | Name, generation and audit roll back together |
| `RB4-REN-008` | GET/POST wire, CSRF, duplicate/unknown keys, wrong content type, files, noncanonical base, >4 MiB, unsupported method | Exact outcome table: tokenless/invalid-CSRF POST → framework403; valid-CSRF PUT → `405 Allow: GET, POST`; employee/stale-session POST use valid CSRF; closed body/command boundary and no reflected private input |
| `RB4-REN-009` | PostgreSQL lock/DAG/static inspection | User → SiteSettings → Page → audit; pages imports only existing accounts/audit authorities; reverse import0 |
| `RB4-REN-010` | static scope inspection | model/migration/dependency/receipt/framework/JS/public renderer/Page Route/public URL/public navigation/B002/media changes0; exactly one literal private management route and one owner-only editor link are in scope |

Focused discovery target: exact10 test methods, domain/command6 plus HTTP4; subtests cover the closed matrices. Runtime, exact count and regression cohort require a separate reviewed run plan and fresh explicit owner permission after source review.

## No-bloat stop line

Если реализация потребует новой schema, универсального lifecycle service, operation receipt, tree snapshot, cached navigation, JS widget или изменения content/URL/media contracts, остановиться до кода и вынести это в отдельный архитектурный срез. Rename не должен становиться скрытым способом изменить H1, SEO или URL.
