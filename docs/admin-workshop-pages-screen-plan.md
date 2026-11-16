# Перенос утверждённых экранов «Страницы» и «Редактирование»

Дата: 2026-11-16. Статус: **IMPLEMENTED; OWNER DISPLAY REFINEMENT D-1197 APPLIED LOCALLY; NUMERIC WIDTH CAPTURE OPEN**.

Уточнение D-1197: по прямому решению владельца строки общего реестра показывают
только название страницы и действие «Редактировать». Категория и exact URL в
строке не дублируются, поскольку доступны внутри редактора. Категорийный фильтр,
поиск по названию/URL, projection и данные редактора сохраняются без изменений.

Уточнение D-1198: по скриншоту владельца desktop-строки реестра уплотнены:
вертикальный padding уменьшен до 8 px, кнопка «Редактировать» — до 34 px с
компактным внутренним отступом. На ширине до 560 px общий touch-target 44 px и
полноширинная мобильная кнопка сохраняются.

Уточнение D-1199: владелец подтвердил основное назначение админки — при открытии
каждой страницы сразу должен быть виден уже импортированный или ранее созданный
текст этой страницы. Диагностика локальных 112 страниц: 59 имеют оба текстовых
поля, 47 имеют только `main_text`, 6 имеют пустые обычные текстовые поля. В
текущем UI пустой `intro_text` выводится раньше заполненного `main_text` и у 47
страниц визуально скрывает реальный текст ниже первого экрана. Первый bounded
срез меняет только presentation order: `main_text` перед `intro_text`, без
изменения payload, save protocol, прав или публичного вывода. Отдельные профили
главной/контактов и каталоги не подменяются обычным HTML; две legacy-empty
страницы требуют отдельного утверждённого содержания, потому что старый main
column был пуст и ранее созданного page-specific текста в проекте нет.

## Причина исправления

Утверждённый `docs/design/admin-workshop.html` содержит связанные экраны:
primary nav «Разделы / Страницы / Логи», левую «Структуру сайта», реестр
страниц с категорией и URL, поиск, фильтр, 12 строк на страницу и явное
действие «Редактировать», а после выбора страницы — workspace редактора с
breadcrumb, вкладками «Содержимое / Версии», компактными сведениями о странице,
панелью форматирования, областью текста и действиями проверки/сохранения.
D-1183 ошибочно перенёс только общий shell: реестр был заменён двухколоночной
сеткой названий, а рабочий редактор остался в технической линейной разметке.
Владелец отклонил обе подмены скриншотами утверждённого макета.

## Ограниченная реализация

1. Новый pure read helper `accounts.page_projection.workshop_pages(user)`
   является единственным общим источником реестра/sidebar/metadata для
   `accounts.dashboard` и `page_editor.editor_page.editor`. Это не context
   processor: он вызывается только этими двумя GET endpoints.
2. Helper использует существующие `Page`, nullable direct `parent` и exact
   primary `Route` через bounded `select_related('parent')` + filtered
   `Prefetch`/subquery; записей и денормализации нет. Owner queryset содержит
   все Page, employee queryset — distinct assigned Page only.
3. Category identity отделена от label. Owner token — literal `root` либо
   `parent:<canonical UUID>`. Root label — «Основные страницы»; parent label —
   escaped direct parent name. Если parent name совпадает с root label или два
   доступных parent имеют одинаковое имя, UI добавляет стабильный понятный
   суффикс «(раздел 1)», «(раздел 2)» в порядке name/UUID, не меняя token.
   Employee видит имя parent только если сам parent входит в его assigned set;
   иначе все такие children получают один neutral token `other` и label
   «Другой раздел», без parent UUID/name leakage.
4. Допустимы только single-value keys `q`, `category`, `p`. `q`: Unicode string,
   outer whitespace stripped, длина после strip ≤200, Cc rejected; empty means
   no search; matching is Django `icontains` over page name or displayed exact
   primary URL. `category`: ASCII `root`, `other` or `parent:<lowercase UUID>`,
   max43 and must belong to available projection. `p`: ASCII canonical decimal
   `1..9999`, no leading zero. Unknown/multi-value/control/invalid/unknown token,
   out-of-range nonempty page → generic400.
5. Helper materializes stable role queryset ordered by normalized display
   category/name/UUID with a 513th sentinel. More than512 accessible rows fails
   closed with generic503; no partial totals/filtering/sidebar. For ≤512 rows,
   category labels/tokens, filters, total, search result and 12-row pagination
   all derive from that same in-memory projection. Empty result is valid only
   on `p=1`. Prev/next preserve canonical percent-encoded nonempty `q` and
   category exactly once.
6. Sidebar строится только из того же разрешённого bounded набора. Названия и
   строки реестра ведут exact `page_editor:editor`; legacy `page-access` href
   отсутствует.
7. Header показывает утверждённую primary nav «Разделы / Страницы / Логи».
   Реальные дополнительные owner destinations сохраняются без JS в compact
   native details «Ещё»: Медиа, Заявки, Сотрудники, Шапка, Подвал, HTML-резерв.
   Для employee owner-only «Разделы/Логи/Ещё» отсутствуют; остаются «Страницы»
   и отдельная существующая разрешённая ссылка «Заявки».
8. «Создать страницу» не показывается и не включается: existing backend требует
   `DEV29_LOCAL_CREATE_ENABLED=True` вместе с `ENVIRONMENT=test`. Снятие этого
   production/dev guard не входит и требует отдельного решения владельца.
9. Responsive: sidebar 190px на wide, stacked above registry below800px;
   no root horizontal overflow; list rows remain readable at320px.
10. `page_editor:editor` использует тот же helper/header/sidebar/workspace.
    Helper вызывается после существующих before/require_session/after stamp
    checks; `EditorSlot`, повторная проверка identity/context, escaped
    `json_script` и текущая admission/save policy не ослабляются. Breadcrumb
    показывает «Содержимое / <direct parent или Основные страницы>», заголовок —
    имя текущей страницы; вкладка «Версии» ведёт в существующий
    `page_versions:history`.
11. В compact metadata показываются реальные read-only имя, категория, exact
    primary URL и состояние публикации. Ссылка просмотра выдаётся только при
    наличии primary URL. Изменение имени/категории/URL/публикации и удаление не
    подменяются fake form controls: соответствующие существующие owner-команды
    остаются в «Разделах» до отдельного безопасного объединения экранов.
12. Существующие `data-editor-*` hooks, escaped initial state, source/draft/
    rebase panels, media/price controls, check/save protocol и editor bundle не
    меняются. CSS только группирует фактически поддерживаемые controls в
    утверждённую светлую toolbar/editor/action композицию; новых команд нет.
13. Sidebar редактора строится из того же bounded role-aware projection, что и
    реестр; текущая страница выделена. Общая функция чтения не делает записей и
    не раскрывает owner pages сотруднику.
14. Truthful counter: «Найдено: N · Страниц: M». Для owner дополнительно
    допускается read-only `SharedBlock.objects.count()` из существующей модели,
    строго только для подписи «Общих блоков: S»; employee этот count не получает
    и shared rows/sidebar из него не строятся. Новых shared functions нет.
15. Exact code boundary: новый `app/accounts/page_projection.py`,
    `accounts/views.py`, `page_editor/editor_page.py`, templates `base.html`,
    `dashboard.html`, `editor.html`, existing `manage.css`/`editor.css` и
    `accounts/test_admin_workshop.py`. Models, migrations, bundle/bridge JS,
    URLs, commands and dependencies remain unchanged.

## Не входит

- изменение creation/publication/tree command policies;
- unread-log counter, fake count, decorative non-working controls;
- models, migrations, dependencies, JS, API, cache or background work;
- public site, live/VPS/deploy/push;
- wildcard/direct broad tests or Playwright.
- fake metadata editing, fake create/delete/publication controls или перепись
  рабочего editor bundle только ради визуального сходства.

## Приёмка

- `ADMWP-001`: owner dashboard renders primary three-item nav, sidebar,
  one-column registry rows with title and exact editor action; category/URL
  remain available in the editor and are not duplicated in registry rows.
- `ADMWP-002`: q/category/p filters return exact subsets and preserve query in
  pagination; duplicate/root-collision category labels remain distinct;
  invalid/multi-value/Cc/noncanonical/out-of-range input returns400 without data
  leakage; 513 accessible pages fail closed503 while 512 remain complete.
- `ADMWP-003`: employee sees only assigned pages/categories and no owner utility
  menu; assigned child with unassigned parent shows neutral category; existing
  Requests link remains and owner-only tree/log destinations are absent.
- `ADMWP-004`: 13+ permitted rows produce 12-row first page and exact second
  page; counts distinguish found/pages/shared blocks without fake values.
- `ADMWP-005`: existing dashboard/tree/editor routes and role gates remain;
  page creation is absent and its guard unchanged.
- `ADMWP-006`: responsive CSS contains bounded pages-workspace/sidebar/row
  contracts; no external URL/JS added.
- `ADMWP-007`: real editor GET preserves all existing security/protocol hooks
  and renders approved workspace, breadcrumb, Content/Versions tabs, real page
  metadata, selected sidebar item and exact existing history/editor links.
- `ADMWP-008`: employee editor sidebar contains only assigned pages; owner-only
  metadata commands/utilities are absent and editor field permissions remain
  unchanged.
- `ADMWP-009`: editor CSS presents existing toolbar, editor surface, statuses
  and page actions responsively without changing bundle commands or inventing
  controls; source/draft/rebase/media/price panels remain reachable.
- `ADMWP-010`: если `intro_text` пуст, а `main_text` заполнен, существующий
  основной текст является первым визуальным редактором; порядок не меняет
  значения payload и оба разрешённых поля остаются доступны.

## Exact verification map

- existing `test_admw_001_anonymous_login_shell_and_no_password_value` keeps the
  anonymous/login boundary;
- existing `test_admw_002_logo_transport_and_exact_bytes` keeps immutable logo
  transport;
- existing `test_admw_003_owner_navigation_and_dashboard_contract` proves
  ADMWP-001/002/004 using fixtures for duplicate parent names, a real parent
  named «Основные страницы», 13-row paging, query encoding, invalid inputs,
  exact512 and 513 fail-closed;
- existing `test_admw_004_employee_navigation_and_editor_contract` proves
  ADMWP-003/008 with two employees, assigned/unassigned parents and two pages;
- existing `test_admw_005_representative_screen_and_form_hook_inventory` proves
  ADMWP-005/007 on real rendered owner/employee editor GETs while asserting all
  prior `data-editor-*`, json_script, bundle, source/draft/rebase/history hooks;
- existing `test_admw_006_css_scope_and_source_manifest_admission` proves
  ADMWP-006/009 static responsive/no-external-resource contracts.

Only `scripts/test-editor.ps1 -Suite admin-workshop` and later `-Suite check`
run; no wildcard/direct broad runner or Playwright. After GREEN and independent
diff review, a fresh dev restart is inspected through visible browser/CUA for
owner Pages+Editor and employee Pages+Editor at 320/736/1024. Evidence requires
the requested viewport, screenshot, visible absence of clipped controls and a
supported numeric root-overflow reading. If the available CUA surface cannot
produce that numeric reading, the width item remains explicitly OPEN and the
same previously unsupported API call is not attempted a third time; it is not
silently accepted. No live/publication follows from this preview.
