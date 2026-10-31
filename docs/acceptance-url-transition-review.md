# Сбои фиксации URL: подготовка и независимое ревью

2026-10-30. Продолжение этапа7 по D-301/302/303/305/308 и поручению владельца. Прежние изменения сохранены. Только тесты/оснастка/документы, без кода сайта и изменений старого сайта/VPS/их БД/файлов/ОС/настроек.

## Подготовлено

`acceptance/url-transition.spec.js`:**11сценариев**, пять границ×GET/HEAD и отдельный поздний worker. Частичные AT204/212, AC-HTML-004/012:до записи долговечного запрета, после запрета до DBcommit, после DBcommit до финализации, обновление входящих редиректов, допуск ответа. Повтор exactoperationId/confirmation не создаёт новую мутацию; удержанный pending не открывается по времени. Явная ownerсверка опирается на actualDB/transaction evidence, а не название стадии или желаемый результат. Неизвестный исход не требует придуманного автоматического отката.

После конечной сверки проверяется точный DBнабор A/B/C/targetP без дублей/чужих целей и сохранность history/receipt. Поздний worker остановлен до admission и после подтверждения не выдаёт старое разрешение. Уже допущенные ответы не смешиваются с этой пробой. [Полный контракт и пределы](acceptance-url-transition.md).

Добавлен только тестовый `url-transition-control-v1` для6fixedfault/barrieractions; сами URLмутации/ownerrecheck через control запрещены. Cap отделён от fallback/backup/HTML/log/jobs/restore. Concretecontroller/нового framework/APIпродукта нет. SAFE024-url-transition и SAFE032 — **2новые самопроверки** clientguard, не доказательство физическогоscope. [Транспорт](local-test-adapter.md).

11сценариев приложения **не исполнялись**:нет приложения/bridge/bindings/controller и физическогоARC-10. Gateprobe — будущий настоящий локальный HTMLgate с общей admissionpoint, не модель статуса/прямая выдача файла. Свидетельства source/phase/commit/head/worker ещё проверяются при независимом review конкретных привязок.

## Независимое ревью

Автор сценариев — url_transition_faults, исправлений/оснастки/интеграции — координатор. url_transition_review проверял read-only, не исправлял результат.

| ID | Приоритет | Замечание | Исправление/результат |
|---|---|---|---|
| TEST-R056 | P2 | Ярлык commitState мог подменить испытание известной pre/postcommit границы | Независимые DB page/revision/history/receipt/redirects подтверждают соответствующую границу; publicunknown не заменяет факт; независимо закрыто |
| TEST-R057 | P2 | Правильный HTTP301 и count≤1 не исключали дубли/чужие цели после финальной сверки | ExactaffectedA/B/C∨targetP DBнабор с targetPageId после recheck, history/receipt сохранены; independentlyclosed |
| TEST-R058 | P2 | Конкурентный bridgeзапрос мог отвергнуть Promise до появления обработчика | Немедленный success/rejectionhandler; после release ошибка явно выбрасывается, не превращается в pass; independentlyclosed |

После исправлений существенных замечаний в целевой частичной области нет. Это не полное TEST-07 и не прошедшие AC.

## Фактические проверки

- **80 driver-safety passed**, skipped/unexpected/flaky=0,13,021с; `test-results/acceptance/driver-url-transition-results.json`, `work/acceptance-driver-url-transition.txt`. Рецензент отдельно сверил JSON. Прежние78 не суммируются с пересекающимися80.
- Контейнерное перечисление **985 tests in 35 files**, exit0: `work/acceptance-stage7-list-url-transition.txt`. JS/PowerShell синтаксис проверен. Это сборка списка, не исполненные11сценариев сайта.
- После синхронизации **4 документные/изоляционные самопроверки passed**, skipped/unexpected/flaky=0,2,801с; `test-results/acceptance/documents-url-transition-results.json`, `work/acceptance-documents-url-transition.txt`. git diff --check без ошибок. Это оснастка/документы, не11сценариев сайта.

Матрица140AT: **24 text_only /7 partial_http /109 assertions_waiting_driver**. AT204/212 впервые получили частичные assertions; 140AC/63REQ/115MAP/RTE сохранены. Ни один полный AC не объявлен пройденным. Работа сохранена локально без commit/push.

## Остаток

Реальные kill/crash/unknowncommit, отказы/откаты независимогоhead, истечение/подмена подтверждений, смена прав/занятости/основания во время ожидания, все workers/lease/close/drain/8s bridgebudget, конкурирующая ночная сборка и новые инкарнации ещё отдельные ветви. Доказательство показания phase/rollbackVerified требует первичных DB/transaction/control свидетельств, не готового ожидаемого ответа fixture. Ошибка до release должна безопасно завершать собственную fixture/зависшие запросы; эта готовность конкретного адаптера ещё не проверена.

Этап7 продолжается, полный TEST-07/UX-07/physicalARC10 открыт. Код этапа8/production — только после отдельного согласования владельца.
