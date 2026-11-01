# DEV07-RST — результаты проверок завершённого восстановления

2026-11-01, D-360. Ограниченный локальный срез [RST-001–006](dev07-restore-terminal-checks.md): **6 серверных тестов PASS за 27.658с и 3 браузерные группы PASS**. Независимое ревью кода, тестов и фактических свидетельств положительное. Полные D07/DEV-07 не объявляются завершёнными. DEV-07 около 98%, этап 8 около 20%.

## Что подтверждено

| Сценарий | Фактическое доказательство |
|---|---|
| RST-001 | Настоящие held stage/editor GET/Check доступны своему actor, current/history/pins неизменны. Браузер проходит историю, просмотр, prepare и явную подтверждённую подстановку через существующие формы |
| RST-002 | Явная отмена освобождает pins; editor GET/state/Check и новый Save отказывают без кандидата/нового proof/публикации. Отдельно повторены исходная отмена и исходный stage_restore: durable результат released, без новой domain/version-audit записи |
| RST-003 | Отдельный проверенный Save сохраняет отредактированный текст с source provenance и consume. Точный повтор старого Save возвращает прежний результат; новый operationId отказан. Editor GET/state/Check не возвращают consumed candidate; исходный stage_restore возвращает terminal consumed |
| RST-004 | Настоящий owner current commit штатно invalidates stage с CURRENT_CHANGED, освобождает только его pins и сохраняет отдельный owner draft с его basis/pin. Проверено сервером, не отдельной браузерной группой |
| RST-005 | После отзыва main_text выбранный источник недоступен, stage остаётся held с прежними pins до штатной invalidation. Точное восстановление прежних прав до invalidation возвращает доступ на прежней source/base; последующий current commit делает stage invalidated. Старый Save с уже запрещённым полем получает точный 403/FIELDS_FORBIDDEN, read/state/Check — 409/BASE_UNAVAILABLE. Проверено сервером |
| RST-006 | Второй employee имеет те же intro/main права на ту же Page и рабочую собственную подготовку. Он и owner не читают/не применяют чужой stage и получают 403 на его отмену. Свои held-подготовки обоих доступны и проверяются; чужие status/pins/current сохраняются. Подтверждены сервер и браузер |

Браузерные группы RST-UI-001/002/003 проверяют реальные клики, ввод и формы через Chromium/Nginx. Exact replay и отрицательные прямые запросы выполняются также через Playwright BrowserContext.request с действующими cookies/CSRF; это HTTP-проверка ответа через настоящий Nginx, не отдельная визуальная приёмка каждой replay-страницы. Сравниваются actual PG domainHash, проекция durable receipts и VERSION audit count; допустимые denial-аудит и session touch не смешиваются с domain mutation.

## Воспроизводимость

Сервер и финальный browser используют один снимок: run `e1e5ad80-d819-4ecd-9e0d-0373a81d69e3`, manifest `71f78a961e082f896c5c1e8301df6cb522132f307e019b2732f63d08dfd8948f`, 229 файлов. В сравнении с финальным TP2 нет изменённых прежних файлов приложения; добавлен только `page_editor/test_restore_terminal_http.py`. Host/frozen SHA совпадают: `work/dev07-selected-20261101/source-checks.json`.

Финальный Python SHA `2998c4b46a4e6b2bf271acf83bd157b5e8db610932b0c0b12955bf7b7c8a70d7`; fixture `713b5b4be3a6369ac6d394cacdc40914b1bafb432b8cf0f44f240d7f09a8cd5b`; probe `de95a13e9351fa31f031e309249eaf020efdde872507d0c375e5e47a881010de`; host `2da0f98a4222b1871f65337efa4ae53d5f5a4ffd0906a372848efb8b8b4c4c31`. Три native SHA зафиксированы в `http-freeze.json`.

Использованы прежние approved Python/Django/PostgreSQL и Playwright 1.64.1, нормальный runtime094333… и тестовый runtime782f53…; тестовая overlay не меняет product URLConf/settings. Прежние read-only/private-network/loopback/caps сохранены, новые программы/ресурсы/схема не добавлялись. Framework имеет прежний явно обозначенный body-reader seam и не доказывает socket buffering/deadline/max.

## История проверок и ревью

До запуска независимое ревью потребовало положительный own-stage контроль второго сотрудника и точное 403-ожидание old DTO после отзыва поля. RST-QA001: fixture domainHash первоначально не включал возвращаемую проекцию receipts; исправлено до первого native run, теперь та же ordered receipt_rows используется в ответе и digest. Продуктовые правила не менялись.

Первый native run **FAIL**, RST-UI-001 PASS, RST-UI-002 PlaywrightError, без page errors/внешних запросов. Статически найден неоднозначный CSRF-селектор: logout и editor имеют отдельные поля. Два селектора ограничены `[data-editor-page]`, остальные проверки сохранены. После независимого ревью изменённых условий новый полный run **3/3 PASS**. Исходный FAIL не переименован и не засчитан как полный успех; отфильтрованный первый отчёт не раскрывает точный исходный текст PlaywrightError.

Ранние launcher-отказы также сохранены отдельно: pwsh не имеет нужного .NET Framework ACL API; Windows PowerShell сначала отказал в запуске .ps1 по process policy. Успешный запуск выполнен Windows PowerShell 5.1 с разрешением только для дочернего процесса; политики/настройки Windows не изменялись. Эти launcher failures не считаются исполненными тестами.

## Очистка и оставшаяся область

Финальный host-report подтверждает cleanup=true: users/pages/versions/drafts/stages/pins=0, сохранён один исходный system Route. Постоянные ledgers сохранены: 643 version identity tombstones, 172 media identity tombstones, 334 operation receipts, 785 append-only audit events. Host stderr=0. Синтетические credentials и результаты находятся в ignored work/, в Git не добавляются. Push не выполнялся, старый сайт/VPS не затронуты.

Два PNG 1280/390 просмотрены. Общая адаптивность не закрыта: full-page PNG при viewport390 имеет ширину406, как в TP1/TP2. Скриншоты сняты с доступной собственной held-подготовкой; они не доказывают новое terminal-specific UI.

Открытый D07-018: обычный GET собственного завершённого stage_read пока показывает общий отказ409 без отдельного пояснения причины; editor generic409 безопасен, но не подменяет это требование интерфейса. Gone после физического удаления stage, полная generation/session/identity/RAM/MAX/media/legacy/browser/resource матрица и production/public renderer остаются отдельно. Все D07/AC не закрываются суммой девяти групп. Следующий конкретный шаг — понятное отображение завершённой/устаревшей подготовки без выдачи её кандидата, затем оставшаяся матрица DEV-07. Этап 9 не начинается.

Свидетельства: ignored `work/dev07-selected-20261101/` — before-8308632d…/manifest.json, framework-first.txt, cohort-final.json, source-checks.json, native-first/host-report.json, native-fixed-csrf/host-report.json, http-freeze.json, stop-final.txt. Окончательный final-checks.json подтверждает active=false, отсутствие работающих foundation/browser контейнеров и 229 host/frozen SHA без расхождений; тома сохранены.
