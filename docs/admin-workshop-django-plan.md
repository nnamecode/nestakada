# Перенос дизайна «Мастерская» в Django-админку

Дата: 2026-11-16. Статус: **IMPLEMENTED; FINAL REPEAT REVIEW APPROVED 0/0/0; ADMW-008 NUMERIC VISUAL EVIDENCE OPEN**.

История: первый plan review вернул P1/P2/P3=0/4/0; замечания были
устранены, repeat review подтвердил APPROVED 0/0/0. После реализации первый
final diff review вернул 0/3/1: runtime-проверка logo transport, перенос строк
навигации, полнота ADMW-005 и статус документа исправляются без расширения
функциональной области. Repeat final review подтвердил APPROVED 0/0/0;
результаты записаны в `docs/admin-workshop-django-results.md`.

## Основание

Владелец поручил перенести утверждённый дизайн «Мастерская» из
`docs/design/admin-workshop.html` в действующую локальную Django-админку.
Сверка выявила разрыв: ADMIN-03/04 утвердили прототип, но server templates
используют отдельный упрощённый синий `app/accounts/assets/manage.css`.
Функции, права, маршруты и данные уже существуют и не переписываются.

## Ограниченная область

1. Один общий server-rendered shell в `accounts/base.html`: оригинальный логотип
   из approved prototype, название «Панель администрирования сайта», оранжевая
   палитра `#f4ac40`, тёмно-коричневые акценты, верхняя навигация и рабочая
   область в стиле «Мастерская».
2. Существующие ссылки остаются прежними: страницы/разделы, заявки,
   сотрудники и права, медиа, шапка, подвал, аудит, HTML-резерв и выход.
   Недоступные роли по-прежнему не получают owner links.
3. Реальный экран дерева получает визуальную компоновку утверждённого дерева;
   существующая branch/navigation semantics сохраняется. Постоянный новый
   запрос всех страниц в общий shell не добавляется.
4. Dashboard, формы, таблицы, карточки, сообщения, версии, редактор, медиа,
   заявки и shared editor получают общие workshop tokens/styles. Их POST/GET,
   поля, подтверждения, ограничения и тексты не меняются.
5. Sole logo authority — literal `var brandLogo="data:image/png;base64,..."` in
   approved `docs/design/admin-workshop.html`. Strict decode must yield PNG
   signature, 212×126, exactly 30,190 bytes and SHA-256
   `39feb78ac1cc832b5819e886311e8424472412cc00bd2dcfd880f308f8f319f5`.
   Bytes copy unchanged to exact `app/accounts/assets/brand-logo.png`; target
   must be a regular one-link file with literal size/hash.
6. `scripts/local-foundation.ps1` source snapshot/manifest admits exactly
   `accounts/assets/brand-logo.png`; general `.png` admission remains forbidden.
7. Exact `/manage/assets/brand-logo.png` is the sole new static asset URL for
   anonymous login. Middleware gets one literal exception; unknown/sibling
   `/manage/assets/*` stay gated/404. Business URLs do not change.
8. Responsive widths: 320, 736 и 1024px; без root horizontal overflow.
   Широкие реальные таблицы сохраняют локальный horizontal scroll.

## Не входит

- новые функции, dashboard counters, категории, фильтры или действия;
- новый persistent sidebar query/context processor, SPA, UI framework;
- модели, миграции, зависимости, API, worker, cache или external fonts/icons;
- изменение auth, permissions, CSRF, sessions, audit semantics или URLs;
- изменение публичного сайта, live/VPS/deploy/push;
- Playwright и wildcard/direct broad test runs.
- prototype inline JS/event handlers/data URLs; existing CSP is not weakened.

## Файлы реализации

- `app/accounts/templates/accounts/base.html`;
- `app/accounts/templates/accounts/dashboard.html` и минимальные class hooks в
  существующих templates только там, где semantic CSS недостаточно;
- `app/accounts/assets/manage.css`;
- exact `app/accounts/assets/brand-logo.png`, accounts URL/view and one literal
  anonymous middleware exception;
- `app/accounts/test_admin_workshop.py` plus named suite `admin-workshop`;
- exact-path PNG admission in `scripts/local-foundation.ps1`;
- документы результата.

## Приёмочные сценарии

| ID | Проверка | Ожидаемый результат |
|---|---|---|
| ADMW-001 | Anonymous GET login | Workshop shell/brand shown; no owner navigation; password input has no value |
| ADMW-002 | Owner dashboard | Exact existing owner links present once; authenticated identity and logout retained |
| ADMW-003 | Employee dashboard | Owner-only links absent server-side; assigned pages remain accessible |
| ADMW-004 | Pages/tree | Existing branch, ancestry, commands and exact URLs unchanged; workshop hierarchy styling |
| ADMW-005 | Editor/versions/shared/media/requests/audit | Existing screens inherit coherent shell; their forms/routes/scripts remain unchanged |
| ADMW-006 | Logo | Anonymous+owner GET/HEAD exact asset; image/png, pinned SHA/size, HEAD empty/same Content-Length, POST405, private/no-store, Vary Cookie, nosniff; siblings denied |
| ADMW-007 | Security | CSRF/session/private headers and auth gates unchanged; no external requests or inline executable JS added |
| ADMW-008 | Responsive | 320/736/1024 root overflow0; nav wraps; wide tables scroll only in their wrappers |
| ADMW-009 | Regression | Exact named auth/workshop tests PASS through `scripts/test-editor.ps1`; no wildcard/Playwright |
| ADMW-010 | Scope | models0, migrations0, dependencies0, business actions0, public/live changes0 |

## Logo transport contract

- anonymous and authenticated GET/HEAD only; POST=405;
- exact `image/png`; GET body SHA/size pinned; HEAD body empty with same
  `Content-Length`;
- `Cache-Control: private, no-store`, `Vary: Cookie`, `X-Content-Type-Options:
  nosniff`; existing CSP/security headers unchanged;
- exact literal middleware exception; sibling/unknown asset denial tested;
- host preflight pins authority data URL, target path, signature, dimensions,
  size/hash and frozen source snapshot inclusion.

## Exact named suite

`scripts/test-editor.ps1 -Suite admin-workshop` maps only:

1. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_001_anonymous_login_shell_and_no_password_value`
2. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_002_logo_transport_and_exact_bytes`
3. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_003_owner_navigation_and_dashboard_contract`
4. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_004_employee_navigation_and_editor_contract`
5. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_005_representative_screen_and_form_hook_inventory`
6. `accounts.test_admin_workshop.AdminWorkshopTests.test_admw_006_css_scope_and_source_manifest_admission`

## Literal compatibility inventory

| URL / route | Template | Frozen contract |
|---|---|---|
| `/manage/login/`, `accounts:login` | `accounts/login.html` | action/method/CSRF/username/password; password no value |
| `/manage/`, `accounts:dashboard` | `accounts/dashboard.html` | identity, assigned pages, requests/tree/reserve links |
| `/manage/pages/`, `accounts:page-tree` | `accounts/tree.html` | ancestry query and structure/publication/url/delete route names |
| `/manage/pages/<uuid>/edit/`, `page_editor:editor` | `page_editor/editor.html` | `data-editor-*`, CSRF, bridge module, editor CSS |
| `/manage/pages/<uuid>/versions/`, `page_versions:history` | history template | version actions/form names/CSRF |
| `/manage/shared/header/edit/`, `shared_content:editor` | shared editor | existing assets/forms/data hooks |
| `/manage/media/`, `media_library:catalog` | media catalog | upload/search/actions/multipart/CSRF |
| `/manage/requests/`, `service_requests:list` | requests list | list/detail/settings links |
| `/manage/audit/`, `accounts:audit-events` | audit events | filters/table/cursor links |
| employees and HTML reserve routes | existing accounts templates | existing actions/fields/CSRF |

ADMW-005 asserts resolution/methods and critical action, field, CSRF, script and
`data-*` hooks, plus server-side absence of owner links for employee. Prototype
behavior is not copied into the product.

## Visual/CUA evidence (no Playwright)

After named tests and final review, use visible local browser/CUA with fresh dev:
anonymous login; owner dashboard/tree; employee dashboard/assigned editor; owner
audit wide table. At 320, 736 and 1024 CSS pixels record per state:

- `document.documentElement.scrollWidth <= clientWidth`;
- `document.body.scrollWidth <= clientWidth`;
- navigation wrap/visibility and screenshot.

For tree/audit at320 also record wrapper `scrollWidth > clientWidth`, successful
horizontal scroll and unchanged root width. Store numeric table and screenshot
references in results. If available CUA cannot expose numeric DOM geometry,
ADMW-008 remains open; screenshots alone cannot claim PASS. No new browser
dependency or Playwright may be introduced.

## Последовательность

1. Repeat independent plan review; remediate findings.
2. Strictly decode exact approved logo, add exact source admission; RED tests.
3. Implement asset admission, shell/template hooks and CSS in one bounded slice.
4. Run only named focused suite, system/migration/diff checks through approved
   wrappers where applicable.
5. Independent final diff review.
6. Recreate local dev source snapshot, verify exact CUA matrix and widths;
   no deployment.
