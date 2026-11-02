# DEV-15 — проверенный локальный прототип и остаток

D-379: подготовлены [предложение рабочего допуска](dev15-runtime-admission-proposal.md) и [конечный план20проверок](dev15-runtime-verification-plan.md), [независимое ревью положительное](dev15-runtime-proposal-review.md). Пакет согласован владельцем поD-380/DEV15-Q002; реализация и локальные испытания следующей сменой, новых реализации/тестов/активации ещё не было. DEV-15 остаётся85–90%, этап8 около28%.

Последняя сверка D-378: [условия завершения DEV-15](dev15-completion-audit.md) и [независимое ревью](dev15-completion-review.md). Открыты4конечныхлокальныхблока, общий writer ещёне готовдляновыхCMSопераций; DEV-15 вработе, оценкауточнена85–90%,этап8~28%. Реализация DEV-29 не начата. Прежние95% ниже — историческая предварительная оценка, результаты проверок сохранены.

Последующее продолжение D-377: полный snapshot/startup клиент,97unit и3native TLS фазы PASS, MAIN/архив сохранены, общий профиль disabled. Текущие факты — [dev15-snapshot-results.md](dev15-snapshot-results.md), ревью — [dev15-snapshot-review.md](dev15-snapshot-review.md). DEV-15 около95%, этап8 около28%; ниже сохранена история прежних срезов.

Актуальное продолжение D-376: 62 unit и15 native fault/recovery групп PASS, postfault archive verify PASS; DEV-15 около85%, этап8 около28%. Подробный новый результат — [dev15-write-results.md](dev15-write-results.md), независимое ревью — [dev15-write-review.md](dev15-write-review.md). Ниже сохранён предыдущий срез D-375/source17, его числа не заменяют новые проверки. General profile disabled, стенд остановлен; полный DEV-15 ещё в работе.

2026-11-02. Выполнен план возобновления DEV15-ACL-RESUME-001 по D-375: действительный ACL-контроль, четыре сетевые группы и двухфазная калибровка прошли. Ранее пройденные 20 unit/PG tests сохранены. DEV-15 остаётся в работе, около 70%; этап 8 — около 28% по числу основных задач (8/29). **Постоянная запись API DISABLED**, задача целиком и физический ARC-10 не закрыты. Итоговое независимое ревью текущего инкремента положительное; это не закрытие DEV-15 целиком или допуск постоянной записи.

Основания: D-307/D-373/D-374/D-375, dev15-proposal.md, SC15-001–016 из dev15-checks.md, PR-04/08 и связанная аналитика. Старый сайт/VPS не затронуты. Новые пакеты/образы/программы Windows, внешние подключения и deployment не выполнялись.

## Что реализовано

Отдельный проект trust/ и закрытая PostgreSQL хранят head, стадии операций, ограничения маршрутов и технические tombstones без тел заявок. API проверяет машинную роль до SQL, повторно проверяет серверную привязку credential/epoch под Head lock, отличает exact replay от нового CAS и не понижает terminal outcome. Неизменяемость поддерживается ограничениями/триггерами БД. Снимок читается ограниченными страницами с поколением и pageDigest. Ошибки имеют фиксированный безопасный JSON/log-формат.

Три контейнера на существующих pinned image IDs, отдельные internal networks/volume/ключи, без host ports; прежний foundation не меняется. Nginx — 128 МиБ/0.25 CPU, API или заменяющий его tool — 256 МиБ/0.5 CPU, PostgreSQL — 512 МиБ/0.5 CPU. Во время калибровки обычные API/ingress остановлены, tool заменяет роль API. Новых одновременных ресурсов сверх согласованного профиля нет.

Полный gate/main commit/пользовательское удаление отсутствуют: подтверждение записи TRUST всегда имеет workflowComplete=false. Никаких фиктивных gate ack или разрешения старого HTML. Локальная изоляция Docker моделирует независимость от APP/EDGE rollback; физическая потеря всего компьютера и откат самой TRUST этой моделью не покрываются.

## Связанные проверенные cohort

Продукт: **17 файлов / SHA256 4c7b0ad9601308725e2f756c53fa6c456634bbfc66edecd95bec005f05bb52d9**. Между unit, сетевыми проверками и калибровкой исходники продукта не менялись. Переиспользование unit проверено отдельно; это несколько связанных запусков, а не выдуманный единый прогон.

| Проверка | Фактический результат |
|---|---|
| Unit/PG | **20 PASS, 5.147 с**, run f8eb27bf-bab5-40ad-be10-f8330c5fbb5f. Два различных pg_backend_pid для конкурентного CAS, immutable terminal/replay/фencing, SQL/connect spies, 252 snapshot items на трёх страницах, безопасное логирование. |
| Исправленный Windows ACL | **PASS 4 файла**, один запуск через точный Windows PowerShell 5.1/Get-Acl, Stop на первой ошибке. Старое ошибочное сообщение PASS не используется. |
| SC15-H01 | Настоящий TLS reader200/Head identity, anonymous401, wrong-role401, no-cookie/no-store. |
| SC15-H02 | Неверные CA и имя TLS-сервера отвергнуты. |
| SC15-H03 | DB verify-full и фактический SSL, сервер отвергает plaintext, runtime не имеет schema CREATE, fsync/synchronous_commit/full_page_writes=on. |
| SC15-H04 | Persistent prepare503 WRITE_PROFILE_DISABLED; auth canary отвергнут, Nginx body>1МиБ→413/no-store; MAIN operation/policy/tombstone rows0 и Head неизменен. |
| Калибровка | **PASS, 150.673 с**, описанный ниже один corpus; не разрешение persistent writes. |
| Завершение | Start без bootstrap, Transport4, Calibrate и outer Stop завершены успешно; manifest active=false/calibrationAttempted=true. Данные сохранены. |

Сетевой и калибровочный run: **7e145c49-be90-478e-88fe-0aef34f0f3ab**. Точный проверенный QA: wrapper c217d620…, transport 9a22b66a…, corpus a3003e4f…, prepared ACL script c0f6e566…. Конфигурация/замороженные исходники связываются manifest и сохранёнными hash; полные значения находятся в ignored evidence.

## Реальная калибровка квот

Только отдельная **test_estakada_trust**, с явным тестовым процессом и code-owned calibration scope. Пустота проверена до записи; reset/flush/delete не делались. Данные генерировались детерминированным corpus с 256 правилами на операцию и плохо сжимаемыми точными путями по 2048 UTF-8 байт. Это DELETED route corpus; число tombstones в нём0.

1. Накоплены незавершённые операции: резерв вырос до **16 221 469 B (~15.47 МиБ)**. Следующая операция такого размера получила BUDGET_EXHAUSTED при ещё свободном основном logical budget.
2. При занятом резерве одна операция прошла UNKNOWN, затем все принятые операции получили terminal receipt и exact prepare replay. Резерв освобождён корректно, без потери запретов и без объявления полного пользовательского успеха.
3. В том же наборе продолжена запись/финализация до исчерпания 64-МиБ logical budget. Следующая большая операция отклонена целиком.

Итог: **60 операций / 15 360 правил / generation121**, logicalBytes=66 897 420, reservedBytes=0. Все правила выбранного набора DELETED, частичных записей нет. Максимум prepare/finish/replay цепочки3 545 мс, terminal/replay1 624 мс; это измерение одного локального corpus, не SLO API/сайта или мощности VPS. Hard alarm240 с и outer Docker300 с не сработали.

Калибровка сохраняет набор. **calibrationAttempted записан ДО subprocess**, последующие Tests и Calibrate отказывают: обычный Django flush не может незаметно стереть сохранённый набор. Это не автоматическая очистка или разрешение повторно инициализировать среду.

## Измеренные ресурсы

| Область измерения | Пик / предел |
|---|---|
| Калибровочный процесс, whole cgroup |65 220 608 /268 435 456 B; OOM/max events0 |
| PostgreSQL после corpus, whole cgroup включая cache |431 542 272 /536 870 912 B; OOM/max events0 |
| API только старт/readiness, не пик всего transport |57 028 608 /268 435 456 B |
| Ingress только старт/readiness, не пик всего transport |19 136 512 /134 217 728 B |
| Relation/index/TOAST bytes после corpus |114 892 800 B |
| Размер test DB после corpus |122 992 319 B |
| Allocated кластер PostgreSQL, включая WAL |289 918 976 B |
| Task files на момент post-check |3 781 118 B |
| Консервативный резерв Docker logs |8 388 608 B |
| **Общий проверенный бюджет после corpus** |**302 088 702 B (~288 МиБ) /2 ГиБ** |

CPU калибровочного процесса72 456 302µs за150.673с; PostgreSQL33 524 859µs за его lifetime в этом запуске. Это разные scope, не расход одного запроса. RAM/CPU caps не повышались. Дисковые2ГиБ — наблюдаемый preparation budget, не hard volume quota; 64+16МиБ — логический учёт, не размер PostgreSQL файлов. Оформление последующих документов/копий немного увеличит task files; приведено датированное измерение.

## Покрытие SC15 и обязательный остаток

| ID | Подтверждено в локальном прототипе | Остаток |
|---|---|---|
|001|Pinned profile/source/config, caps/internal networks/no host ports; отдельный TRUST runtime|Полное физическое размещение/внешняя независимость, вся negative network matrix|
|002|Unit auth/schema/query/size boundaries, ensure_connection/SQL0; HTTP auth/body413|Полная матрица разрешённых максимальных сообщений/всех транспортных сбоев|
|003|Настоящий two-connection CAS и четыре варианта object overlap|Интеграция с PR-08 основной CMS|
|004|Exact phase replay до CAS, terminal immutability, bigint boundaries|Повтор после реально потерянного сетевого ACK работающей write API|
|005|SQL transaction failure/rollback и durable settings|Реальный kill/ACK/crash matrix; потеря питания физического storage|
|006|TRUST работает при остановленном foundation и не использует APP settings/DB|Полный цикл отказа/возврата основного приложения|
|007|Disabled API отказ без мутации, client ambiguity описана контрактом|Consumer и основная mutation при недоступной TRUST|
|008|SQL monotonic head и проверка identity|Полный startup validator и валидный rollback APP/EDGE с настоящим gate|
|009|Request tombstone primitive, duplicate/abort protections|Предельный tombstone corpus; применение к restored payload/notes/consent в DEV-23/LEGAL|
|010|Точные targets/query/case и object identity|Настоящие CMS URL/301/hidden/deleted и D-300 в DEV-29/26|
|011|Старый реальный secret со свежим epoch отвергается|Полная recovery activation/rotation и исключение старого gate|
|012|Реальные252 items/100-100-52 pages/pageDigest/generation barrier|Полный consumer assembler/startup freshness proof|
|013|Один реальный reserve+logical saturation corpus, ресурсы/отказ/сохранность|Остальные count maxima/REDIRECT shapes/физическая нехватка диска/concurrent API admission; source-bound write profile ещё не включён|
|014|Safe log pipeline/bomb canaries, настоящий TLS/CA/hostname/plaintext refusals|Полная negative transport/log/resource matrix внешней службы|
|015|workflowComplete=false, фиктивных ack нет|**NOT RUN:** настоящий gate/main receipt/in-flight revoke/полное удаление|
|016|Нет автоматического bootstrap при утрате identity, ACL PASS/данные/Stop|Собственный внешний recovery TRUST и его доказательство свежести — физический ARC-10|

Следующий локальный блок DEV-15: закрыть нужные для persistent profile остатки, подготовить привязанный к source/schema/resource evidence допуск и отдельно проверить реальные HTTP мутации/потерю ACK/рестарт. Простого PASS этого corpus недостаточно, чтобы молча включить запись. После этого — consumer/startup и интеграции зависимых DEV; физический провайдер/стоимость проходят отдельное согласование.

## История отказов и исправлений сохранена

Первый Prepare прошёл; первый Start после явного bootstrap завершился TRUST_TLS_NOT_READY, unit не запускался. Offline Nginx -t подтвердил keyPermissionDenied: key10001:10001/mode600, ingress101:101. Исправлено mode640/ingress101:10001 с тем же содержимым ключа/узкими Windows ACL и только собственным key mount; tmp paths дополнены в принятом /tmp. Offline fixed -t PASS, независимый fix gate; повтор Start без bootstrap дал действительные20unitPASS/Stop0. Original failed cohort не заменён новым PASS.

При дополнительном ACL-контроле root ошибочно использовал несовместимый с PowerShell7 метод: четыре отказа внутри foreach, ложная итоговая PASS-строка. Работа была приостановлена, reviewer остановлен, файлы/данные сохранены. Эта ACL-строка недействительна. D-375 разрешил конкретный исправленный план; новый check через WindowsPowerShell5.1/Get-Acl действительно прошёл4файла. Ни ошибочное свидетельство, ни исходный FAIL не удалены.

## Evidence и сохранность

Ignored work/dev15-20261102: failed-first-config/, unit-passed-config/, paused-save/60 hashes, paused-final-hashes.json/7 metadata, resume-before/, acl-fixed-first.txt, start-native-cal-first.txt, transport-first.txt, calibrate-first.txt, stop-native-cal-first.txt. Под runtime/: unit-result-f8eb27bf-bab5-40ad-be10-f8330c5fbb5f.json, transport/calibration/calibration-budget с UUID7e145c49-be90-478e-88fe-0aef34f0f3ab и manifest. Полные private unit/error logs/ключи хранятся в защищённом private вне Git. Предыдущая редакция этого отчёта сохранена как results-before-final.md.

Существовавшие34изменения сохранены сSHA до реализации. Основной APP/его медиа/CF07 данные не обслуживались этим контуром и не изменялись; в TRUST сохранены исходные identity/credentials и отдельный corpus. Старый сайт/VPS не тронуты. Push не выполнялся.
