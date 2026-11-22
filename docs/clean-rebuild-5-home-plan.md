# REBUILD-5 — HOME v4 для нового `src/`

Дата: 2026-11-22. ID: `RB5-SLICE-002-HOME`. Статус: **функциональный runtime подтверждён; D-1855 checkpoint владельцем визуально отклонён в D-1856, HOME не завершён; исправление перенесено на следующую смену, оригиналы gallery works остаются отдельным media gate**.

## Результат

Точный URL `/` получает утверждённую адаптивную v4-композицию поверх завершённого public shell. Используется только новый `src/`; старый `app/` остаётся authority для уже принятого HOME package, но не импортируется runtime-кодом.

В первой поставке присутствуют hero, восемь преимуществ, три сравнительные карточки, пять шагов, восемь услуг, шесть групп цен до восьми строк, фотополоса, шесть работ и локальный блок «ОТЗЫВЫ» со ссылкой `/reviews`. Контакты, social marks, form и map присутствуют только как утверждённая визуальная композиция; активные form/PII, iframe, Яндекс/YouTube/analytics widgets, external scripts и автоматические внешние запросы отсутствуют до существующих LEGAL/CONTACT gates.

## Минимальная архитектура

1. Новых моделей, миграций, таблиц, page-builder, API, cache, queue, worker или второго version store нет.
2. В существующий home payload `estakada.page-content/v1` добавляется одно закрытое поле `home_profile`. Предыдущий пустой HOME может иметь `home_profile=null`; для non-home поле запрещено.
3. Import transform переносит уже утверждённый `home-profile-v1` в target DTO, заменяя legacy `image_id` на точный target `asset_id`. Код не читает `app/` или package во время HTTP-запроса.
4. Existing `lead`, `process_steps` и optional `about` остаются owner-editable current+previous полями. Профиль хранит защищённую структуру/порядок/identity/media; отдельный structured editor в этот slice не добавляется.
5. Public projector проверяет current hash/schema/kind/routes/generation, exact current AssetUsage, READY CONTENT/GALLERY_ORIGINAL assets и exact MAIN/LEGACY_PUBLIC file metadata. Nginx расширяет тот же строгий canonical UUID allowlist только на `legacy-public` для побайтно неизменных галерей; preview/private/nested/query остаются404. Projector возвращает frozen DTO без model/file-root/hash/private данных в template context. Физические bytes читает только Nginx.
6. Bound price source меняет только сумму/from и visibility по stable Page/row UUID. Missing source использует сохранённый fallback; новый объект с тем же URL/именем не подхватывается. Service/work labels, targets и images остаются owner-versioned profile facts.
7. Capture страницы, source rows, media usages/files и structure/settings поколения повторно сверяется до рендера; drift даёт constant503/no-store без partial HTML.
8. Один fixed local JS допускается только для price tabs; без JS все группы остаются видимы. Fetch/XHR/WebSocket/storage/cookie/eval/innerHTML/inline script запрещены.

## Acceptance до кода

| ID | Обязательный результат |
|---|---|
| `RB5-HOME-001` | Legacy empty previous HOME остаётся valid; profile на non-home, unknown/missing keys, неправильные counts/UUID/internal URL/asset mapping отклоняются |
| `RB5-HOME-002` | Transform даёт exact 8 advantages, 3 comparisons, 5 steps, 8 services, 6 price groups≤8, photo strip, 6 works, local reviews и exact21 target assets |
| `RB5-HOME-003` | GET/HEAD `/` рендерит только coherent published current HOME; hidden→blank, redirect/unknown сохраняют shell contract, malformed/drift→503 без partial body |
| `RB5-HOME-004` | Exact current usages/READY MAIN files дают только allowlisted media URLs/metadata; missing/duplicate/wrong-purpose/state/kind/usage дают503; Python file read0 |
| `RB5-HOME-005` | Bound price amount/from и visibility проецируются по exact IDs; missing source использует explicit fallback; URL/name reuse0; projector writes0 |
| `RB5-HOME-006` | HTML сохраняет утверждённый порядок и exact internal links; visual-only contact/social/form/map не собирают данные и не загружают внешние ресурсы; active PII/form/iframe/QR/Yandex/YouTube/external scripts/auto-requests0 |
| `RB5-HOME-007` | 320/390/768/1024/1440 CSS не создаёт fixed-width overflow; keyboard/focus semantic; no-JS показывает все цены |
| `RB5-HOME-008` | Existing public shell exact12 и affected content/import/editor tests остаются зелёными; Django check/migration diff/diff-check чистые |

## Порядок

1. Tests-first target profile validation + import transform.
2. Public media/home projector и coherence tests.
3. HOME template/scoped CSS/fixed local JS и HTTP acceptance.
4. Static review/remediation и локальный Docker/browser-preview выполнены; визуальное завершение фиксируется только после повторной приёмки владельца. Чтение gallery originals остаётся отдельным media gate.

## Результат проверки

- Старый authority test в корректном `estakada.settings.local_http` registry: 1/1 PASS без БД и сети.
- Source cohort: первый запуск 28/29, единственный отказ оказался ложным test oracle; после test-only исправления HOME confirmation 3/3 PASS.
- Последующий `nginx -t` PASS; PostgreSQL остановлен `exit=0`, временный confirmation container удалён после `exit=0`.
- Первый локальный Docker/browser-preview после CSS MIME и mobile H1 remediation дал технические PASS, но владелец отклонил визуальный результат как не соответствующий утверждённому макету; ложная отметка завершения отозвана.
- D-1854 перенёс сохранённую HOMEV4-композицию в новый `src/`: full-bleed hero, proof8, comparison3, process5, services8, настоящий tabbed price UI, photo strip, works6 и локальные reviews; шапка снова показывает exact6 меню. Повторная проверка: desktop/mobile horizontal overflow0, console errors0. Визуальное принятие владельцем ещё не заявлено.
- D-1855 устранил оставшуюся подмену макета: DOM и CSS перенесены буквально из утверждённого D-146 reference. Добавлены локальные SVG social marks и favicon, исправлен повтор адреса. Chrome 1440×900/390×844: overflow0, console0; Django check0, JS/diff clean. Новый HOME3 run остановлен тестовой инфраструктурой preview role/search_path, временная test DB удалена; третьего эквивалентного повтора нет, D-1853 HOME3/3 сохраняется.
- D-1856: владелец повторно отклонил визуальный результат. D-1855 остаётся только сохранённым техническим checkpoint, visual acceptance отсутствует; следующий рабочий шаг — точное сравнение с утверждённым authority и исправление, а не переход к другим public families.
- Первый Chrome diagnostic содержал внедрённые локальным антивирусом обращения к его endpoint; в чистой проверке endpoint заблокирован до загрузки страницы. Сам сайт внешних ресурсов/запросов не создаёт. Live/deploy и production не затронуты.

Этот план заменяет прежнюю восьмишаговую процессную разбивку только для нового `src/`: функциональные и security/data требования DEV-12 сохраняются, а старые package/writer/framework слои не копируются.
