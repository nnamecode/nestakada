# DEV-05 — реальные HTTP/UI-сценарии до тестового кода

2026-10-31, D-327/D-328. Нормативные входы: dev05-versions.md, dev05-checks.md, MAN-01/02, UI-S007–013, acceptance-version-time.md. **Сценарии записаны до runner/fixture; первый реальный browser/HTTP-прогон прошёл: 15 групп PASS (VH-010/011 объединены).** Проверены actual engine/HTTP/form contract, настоящие PageRevision/State/Protection/Draft/Stage и закрытые URLs, не generic bindings. Итоговая граница и независимое ревью — [dev05-implementation.md](dev05-implementation.md).

## Граница

Проверяем закрытую историю, escaped просмотр/сравнение, manual checkpoint/metadata, Stable/снятие, удаление допустимой ordinary и restore prepare → stage → cancel. Нет generic payload-writer HTTP, прямого restore+publish, fake editor/public renderer, настоящих Header/Footer или заявлений о прохождении всех прежних e2e. Commit/rollback/конкурентность engine разработчик проверяет настоящими PostgreSQL-тестами; seed теми же engine API только готовит исходное состояние, не засчитывается за browser-save.

## Предварительные сценарии

| ID | Действия и заранее заданный oracle |
|---|---|
| VH-001 | Настоящий login owner/assigned/otheremployee; visitor без login. В исходной Page ровно10ordinary и2Stable; owner и assigned видят все12 ID/типы/метки/actual timestamps. Visitor401/чужой сотрудник403 на history/read/compare; ответы private,no-store/Vary:Cookie |
| VH-002 | В snapshot есть различимые обычный текст, безопасный буквальный HTML/JS-canary и отдельный owner draft canary. Read/compare показывают escaped данные; скрипт не выполняется. Employee history/compare/contextual image не раскрывают owner draft, его payload/refs и ID |
| VH-003 | Владелец открывает prepare manual с явно показанным current/source, вводит имя/комментарий и дату1960 с зоной, создаёт. Новая ordinary копирует current, не draft/несохранённое тело запроса; current/драфт/Page URL/tree/публикация неизменны;10ordinary+всеStable после допустимого prune |
| VH-004 | Replay той же manual operation с теми же параметрами даёт тот же result ID без второй версии/аудита. Изменение имени/даты/action при том же operation ID отклонено. Другой actor не получает прежние полномочия из receipt |
| VH-005 | Metadata manual меняется на дату2099 с явной зоной, в том числе у manual со Stable: protection/payload/actual created_at/author/sequence/source неизменны. Name200/comment1000 допустимы,201/1001 и naive date отклонены без усечки; employee прямые POST запрещены |
| VH-006 | Owner после просмотра ставит Stable конкретному допустимому снимку; current не меняется. Employee/visitor/GET/CSRF/tampered confirmation не ставят/не снимают. Следующий manual checkpoint ordinary, Stable не наследуется |
| VH-007 | Owner готовит снятие Stable; wrong password и stale точное подтверждение после разрешённого metadata-edit manual не снимают. Актуальное подтверждение+текущий пароль выполняют только нужную демоцию; current защищён, original timestamp не меняется,10ordinary-лимит применяется |
| VH-008 | Prepare delete обычной допустимой версии, отменить — состояние неизменно; prepare/confirm с актуальным composition удаляет только её. Current,Stable и owner-draft/stage base не удаляются; пропавший ID не выбирает соседнюю строку. Физические media bytes не удаляются |
| VH-009 | Replay того же delete operation даёт consumed/gone/прежний result, не удаляет другую версию. Mismatch operation/target/action запрещён. Stale confirmation после релевантной metadata/защиты/использования не принимается |
| VH-010 | Read/compare/restore prepare сами не создают историю/пины и не меняют current. Явный POST stage создаёт удержания source/base и projection по актуальным правам; current/history/Page поля неизменны. Явный cancel освобождает только свою stage, не чужие удержания |
| VH-011 | Assigned employee stage берёт только разрешённые intro/main/price, не защищённые H1/SEO/media/layout/URL/parent/publish/Stable/owner draft. Нет автоматического объединения stale базы. UI не предлагает publish от одного restore-POST |
| VH-012 | Contextual historical file читается owner и assigned employee только при реальном membership File→Asset→PageRevision; ContentType image/webp/nosniff/private,no-store и actual HTTP bytes/SHA совпадают с ФС. Чужая revision/file UUID, unreferenced Asset и private-source запрещены; owner-only media endpoint для employee остаётся закрытым |
| VH-013 | Реальные current/ordinary/Stable/draft references удерживают реальные media-файлы. Manual/prune/delete меняют только свои ledger refs; observer сверяет before/after DB+ФС и тот же source/main/preview SHA. Этот тест не имитирует будущий HTML consumer |
| VH-014 | Owner/employee/visitor прямые mutation запросы без/с forged CSRF, GET и неизвестными полями отклонены по контракту; ложного успеха/истории/Stable/current change нет. Валидный owner UI служит положительным контролем |
| VH-015 | Desktop1280/mobile390: история/просмотр/compare/manual/Stable/точные подтверждения/cancel доступны без горизонтального переполнения. Снимки только после login и без password/token значений, не записывать trace/HTTPheaders |
| VH-016 | Actual timestamps показываются в Europe/Moscow по серверному UTC instant, manual dates1960/2099 показаны отдельно. Предварительные expected значения рассчитываются независимой datetime/Intl логикой по seed actualUTC, а не копируются из DOM. Полный audit-export относится DEV17 |

Для сложных сценариев каждый вариант имеет отдельную проверку/артефакт; название VH не заменяет все отрицательные ветви. Если реальный контракт не позволяет сделать ветвь в рамках DEV05, она отмечается NOT_CHECKED с причиной и связью, а не fake PASS.

Неизвестная историческая schema не делает escaped просмотр исполняемым и не допускает restore. При этом после безопасного конкретного просмотра владелец вправе поставить Stable такому снимку: защита не требует пригодности payload к восстановлению. Если подобного реального исторического fixture нет в этом HTTP-корпусе, ветвь остаётся отдельной PG-проверкой/NOT_CHECKED, а не новым запретом приложения.

## Fixture/runner план

Только пустая обычная local_http/test foundation-БД. Seed создаёт случайные собственные actors с canary runId, две собственные Page, PageGrant, реальные исходные PageRevision/Stable/draft через подтверждённые engine API. Медиа по возможности загружается через настоящий uploads.upload и существующий worker из согласованных синтетических файлов DEV06; никаких fake READY/AssetFile insert для положительной HTTP-приёмки. Snapshot корпуса — минимальный доверенный content DTO, не пользовательский нормализатор/редактор.

Host fixture операции seed/observe/close вызываются через Docker exec stdin, без HTTP fixture endpoint. Observe после настоящих HTTP/UI лишь читает результат; browser не передаёт произвольные ORM/FS команды/пути. Полные body/черновики/пароли/CSRF/session не печатаются. Обязательный secret-canary check ledger/audit не раскрывает значения canary в отчёте.

Close сначала доказывает точный набор собственных user/Page/revision/operation/stage/media IDs и run-canary. Чужой живой объект/изменённое владение/непонятное состояние — сохранить fixture и FAIL, не очищать БД слепо. Физическая очистка только собственных известных медиа после доказанного удаления своих refs; незавершённые операции не маскируются нулём. Permanent IdentityReservation, minimal OperationReceipt и append-only audit сохраняются по подтверждению координатора: live users/pages/assets/revisions/stages могут стать нулём, вся БД пустой не объявляется. Исторические receipts вне своего набора допускаются только при уже отсутствующем Page и не удаляются.

Новые файлы ограничены tools/version_http_fixture.py, tools/version_http_probe.mjs, tools/test-version-http.mjs, scripts/test-versions.ps1 и этим документом. Зависимости/установки/Docker-запуски делает только координатор; новые пакеты не нужны. Используются прежние утверждённые Playwright1.64.1 image digest и подготовленные node_modules.

Runner: фиксированный http://host.docker.internal:8767; browser fixed-origin route до первой страницы во всех actor contexts; API maxRedirects0. Секреты только в stdin/in-memory, no Docker socket/DB secrets у браузера. Именованный runner со scope/run labels и image check перед stop; finally сначала подтверждает остановку браузера, потом close fixture. SHA скриптов/inputs до/после и foundation source/images/worker/container guard — независимые проверки; drift даёт FAIL.

Максимум один последовательный прогон без retries; первый сбой прекращает набор. Docker/HTTP runtime выполняет root только после готовности app snapshot и независимого ревью тестовой когорты. Команда: powershell -ExecutionPolicy Bypass -File scripts/test-versions.ps1. Секреты fixture только stdin; host отдельно сохраняет SHA14 QA-скриптов/inputs до/после и foundation guard. Engine APIs используются исключительно для seed, observe только читает ORM/ФС и не импортирует producer services.

Подготовлены все пять ограниченных файлов. Node syntax/PowerShell parser/diff-check прошли до freeze; root отдельно подтвердил Python AST в утверждённом app runtime (work/dev05-20261031/fixture-ast.txt), поскольку локальный Windows alias не подтвердил выполнение ast.parse.

## Фактический результат 2026-10-31

Координатор выполнил первый реальный прогон: [report.json](../work/foundation/test/version-http/0cf08d4d-b486-4a75-a707-c7dfb4700a46/report.json), runId 0cf08d4d-b486-4a75-a707-c7dfb4700a46. Все 15 групп PASS: VH-001–009, объединённая VH-010-011, VH-012–016. QA-provenance14 файлов совпала до/после, fixtureClosed=true. Root просмотрел реальные desktop1280/mobile390 PNG этого прогона. Повторных запусков после результата не требовалось.

Отдельные проверки координатора: 150 PostgreSQL unit/integration PASS за133.008с;11 FOUNDATION PASS за7.2с; migration drift — «No changes detected». Итоговое независимое ревью положительное. Это результаты соответствующих разных наборов, не дополнительные browser-группы.

Независимое наблюдение уборки — [fixture-restored-fixed.json](../work/dev05-20261031/fixture-restored-fixed.json): все14 счётчиков живых таблиц нулевые, обычных media-файлов0, testClockEnabled=false. Сохранены46 identity reservations,28 minimal consumed receipts и133 append-only audit records; вся БД пустой не объявляется. Четыре QA-программных файла после проверенного freeze этим обновлением документа не менялись; стенд останавливает координатор.

PASS ограничен перечисленными VH HTTP-проверками. Engine commit/rollback/concurrency подтверждаются отдельным PG-набором, seed не является browser-save. Полный rich editor/несохранённый ввод DEV-07, public renderer DEV-08, Page/URL publication DEV-29 и Header/Footer не имитировались. Полный audit-export/двухсторонний midnight-clock HTTP-профиль, unknown-schema Stable/restore и остальные ветви вне HTTP-корпуса не объявляются пройденными этим browser-результатом. Подробная граница реализации — [dev05-implementation.md](dev05-implementation.md).
