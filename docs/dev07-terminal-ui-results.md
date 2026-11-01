# DEV07-RUI — сообщения собственного завершённого восстановления

2026-11-01, D-361, [контракт RUI-001–006](dev07-terminal-ui-checks.md), D07-018. **Выполнено в ограниченной локальной области:** 20 серверных тестов PASS за 59.663с — 6 новых RUI, 6 прежних RST и 8 прежних versions HTTP; **3 браузерные группы PASS** через Chromium/Nginx с первого запуска. Независимое ревью кода, QA и фактических результатов положительное. DEV-07 около 98%, этап 8 около 20%.

## Изменение

Собственная подготовка после отмены сообщает, что она отменена; после применения — что уже применена; после утраты совместимости — что нужно подготовить восстановление заново из истории. Экран409 не выдаёт исторический текст и не повторяет действие. Действующая собственная подготовка открывается как прежде. Чужой stage при тех же правах на ту же Page, отсутствующий UUID и отказ текущего доступа сохраняют общий отказ без причины чужого состояния.

Единственная продуктовая правка — stage_read в app/page_versions/views.py, SHA `d063e2475a583c02a54128fd34b0e2b3b17385b66c5f8017b202c8c1a4a2542b`. Перехватывается только точный `ValidationError.messages == ['VERSIONS_STAGE_STALE']`. После свежего E.enter читается только status строки, отфильтрованной по Page/actor/UUID. Закрытый whitelist released/consumed/invalidated/held использует фиксированные сообщения и прежний error.html/HTTP409. Missing/foreign/unknown остаются общим отказом; прочие ValidationError проходят прежнюю обработку. Нет нового DTO/маршрута/receipt, чтения candidate через fallback, автоматического rebase/cleanup/TTL/terminate_stage.

## Серверные доказательства

| Область | Что действительно проверено |
|---|---|
| RUI-001/002/003 | Настоящие released/consumed/invalidated, точные видимые тексты409/no-store, повторные GET без candidate/result и без изменения domain/receipt/pins/VERSION audit |
| RUI-004 | Grant-stale held получает пояснение, сохраняя status/pins. Точное восстановление прежних прав до semantic invalidation возвращает прежний положительный held path |
| RUI-005 | SamePage/samegrants другой employee и owner имеют собственные работающие held stages, но не получают статус/кандидат чужого. Missing/отзыв прав/завершённая сессия закрыты; текущие session отказы не нормализованы в terminal-сообщения |
| RUI-006 | Actual execute_wrapper запрещает исторический payload SELECT в terminal GET. Положительный контроль намеренно вызывает детектор настоящим ORM SELECT, предотвращая чтение payload; затем terminal GET не вызывает детектор. Отдельный injected MEDIA_UNAVAILABLE после настоящего get_stage/preflight сохраняет старое сообщение несовместимости, не маскируется новым |

Проверяются реальные PostgreSQL/сессии/CSRF/engine/child и широкие before/after snapshots. Существующий framework body-reader seam не доказывает socket transport. Инъекция MEDIA_UNAVAILABLE — контроль границы обработки ошибки, не новая проверка настоящего недоступного файла.

## Браузер и очистка

RUI-001 выполняет native prepare/cancel и дважды открывает настоящий stage_read409 с видимым сообщением released; samePage/samegrants другой employee получает общий отказ. RUI-002 выполняет edited selected-stage Save, открывает consumed409 без повторного применения, а owner не получает причину чужого состояния. RUI-003 создаёт свой held stage, выполняет настоящий competing current Save другим actor, затем дважды видит сообщение invalidated. Во всех случаях проверены no-store, отсутствие candidate/result/editor initial state, receipt-inclusive domainHash и VERSION audit invariants. Это новые проверки видимой DOM-отрисовки, не только чтение response.text через API.

Actual host-report: status PASS/failed=null/stderrBytes=0; собственные users/pages/versions/drafts/stages/pins очищены до0, сохранён один system Route. Постоянные 660 version identity tombstones, 172 media identity tombstones, 343 operation receipts и 800 append-only audit events сохранены. Old fixture не менялась; runtime/no-store/CSP/inline/storage/external/page-error controls прошли в пределах assertions.

Два PNG лично просмотрены: terminal-1280.png 1280x900 и terminal-390.png 390x844. Текст нового экрана читается, candidate/кнопок применения нет; это не закрытие адаптивности всей админки с прежним editor overflow.

## Снимок и инструменты

Один app source: run `3e015682-c22b-461c-bb7e-ffda09e3b57d`, manifest `96551e0705171bad80c36b336d57ab324650528121106f655be5cdc4cf6a2796`, 230 файлов. С предыдущего RST изменён только page_versions/views.py, добавлен page_editor/test_terminal_ui_http.py; host/frozen SHA совпадают (source-checks.json). Python QA SHA `56ebfb491fce9e02529b4d123de470f3440c9e75f41e4768b1b1844e95096b7e`.

Native повторно использует неизменную RST fixture `713b5b4be3a6369ac6d394cacdc40914b1bafb432b8cf0f44f240d7f09a8cd5b` с receipt-inclusive domainHash. Новый probe `40a984e43563c3907eca9283183c916e1f769dab147d08ac38decb14b9854783`, host `68d3688a45fdb4db130ae107fe738b0bdfee43d41de34b3f88644c0d79baf415`; node --check обоих PASS, независимое code-ревью до запуска положительное. Прежние approved runtime094333…/test782f…/Playwright1.64.1, loopback/private networks/read-only source/caps сохранены. Новых зависимостей/ресурсов/миграций/настроек Windows нет.

## Ограничения

Generic409 editor selected-source JSON не менялся. UI для gone после физического удаления stage, полные read-vs-cancel/grants/session гонки, late-session/current-basis матрица, MAX/media/legacy/browser/resource и общая адаптивность остаются отдельно. Сообщение held описывает отказ текущего запроса, не постоянный запрет: восстановление прежних прав может снова разрешить held до штатной invalidation. Никакой линейризуемости всех read-races этим набором не заявляется.

Свидетельства в ignored work/dev07-terminal-ui-20261101/: before-f049…/manifest.json, cohort-first.json, framework-first.txt, source-checks.json, http-freeze.json, native-first/host-report.json и screenshots, stop-final.txt. Final-checks.json подтверждает active=false, отсутствие foundation/browser контейнеров,230 host/frozen SHA без расхождений; тома сохранены. Git push не выполнялся. Старый сайт/VPS не затронуты. Полный DEV-07/этап8 не завершён, этап9 не начинается.
