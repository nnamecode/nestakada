# DEV-15: полный TLS-снимок нового worker

2026-11-02, D-384, WB15-005/RP15-011, WT15-001–007. DEV-15 около94%, этап8 около28%.

## Принятый результат

Один ограниченный полный TLS-прогон **PASS за26.060125с** при неизменном общем лимите30с/request6с. Успешны54из54запросов: manifest,52страницы и final head. Получены4096routes+1024tombstones=5120items на корпусе1000FINALопераций. Head2002/epoch1 и whole SHA `5933ad132f7586c38996084248dd7cd90b7bd2fd8b3c5b0ef80ed51ff4625315` совпали.

read_snapshot вызван один раз, retries0, pacing0.11с. Трасса54события, всеPASS, dropped0. Fetch min/median/max0.317791/0.402734/1.054083с; запас до общего deadline3.939875с именно в этом прогоне. Host execution29.034с включает preflight и завершение probe; он не подменяет таймер read_snapshot.

Это максимально заполненный согласованный корпус и совместное использование API/client прежних256МиБ/.5CPU. Многопользовательский поток, иной хост и воспроизводимость при произвольной нагрузке не проверялись. Прежний resume003FAIL не отменён; диагностический004PASS27.543813с и новый26.060125с не являются контролируемым полным A/B и не доказывают процент ускорения TLS.

## Привязка данных и кода

Архив test_estakada_trust_cap_32563 сохранил OID32563 и историческую policy/source5fbcb9… без изменений. API/probe использовали принятый source30 `014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672`, consumer15e6… и собственное evidence131previewPASS. Подписанный read-binding отдельно связал старую архивную квитанцию с точными принятыми SHA candidate-report/integration/historicalB и новым source. В результате sourceMatchesHistoricalWritePolicy=false; это ожидаемая раздельная привязка чтения, не изменение writer-validator или разрешение записи.

Codegate принят после WTLS-REV-001/002; синтаксис и missing-gate отказ проверены до запуска. До служебного открытия существовал подписанный attempt, доGRANT — подписанный ACL baseline/read-intent. Старые инструменты/receipt/attempt/FAIL не переписаны. Текущий source/config и9gatedfiles после прогона без расхождений; исходники продукта в этом инкременте не менялись.

## Ресурсы

| Компонент | Наблюдённый memory.peak, байт | Лимит | OOM/kill | CPU delta, с | Throttled delta, с |
|---|---:|---:|---:|---:|---:|
| API вместе с клиентом |109019136|256МиБ|0/0|14.102278|7.658304|
| PostgreSQL |299745280|512МиБ|0/0|2.230234|0.034516|
| Nginx |9031680|128МиБ|0/0|0.570974|0.097405|

CPU получен между отдельными observations тех же containerID. Окно API30.871с включает накладные расходы наблюдения; это не CPU-время только read_snapshot. memory.peak относится к времени жизни соответствующего контейнера, пики не складываются в якобы одновременный суммарный пик. API throttling наблюдается и приPASS; запаса до30с нельзя обещать для другой нагрузки. Новые ресурсы, образы и host ports не добавлялись.

## Сохранность и завершение

После остановки API и подтверждения отсутствия его DB-сессий временные права отозваны. Raw/effective ACL совпали с baseline; archive ALLOW_CONNECTIONS=false, database readonly-default=on, сам database-default не менялся. Полный chain verifier до/после вернул тот же SHA `601f675e8969895c57ffa2e09eee6f07df0cd65c69225455bf4756725c6d4b71`: оба архива и MAIN по прежним полным данным/OID/hash, новая UNIT52766 по прежним identity/marker. Затем пересоздан обычный MAIN API с фактической SQL-проверкой БД/ролей и Head9/epoch2/disabled.

Final Stop:0ownedконтейнеров, включая остановленные, inactive/disabled, permit{}. WindowsPowerShell5.1 проверил215объектов/430ACL-правил: Allow/owner только владелец иSYSTEM, reparsepoints0. Проверочный script/artifact сохранены в ignored work, секреты/логи вGit не добавлялись. Старый сайт и VPS не затронуты, push не выполнялся.

Независимое result-review и дополнение postflight положительные. Принят выбранный WB15-005/полный снимок RP15-011 в области одного прогона. Преднамеренные timeout/lost-response/повреждённые gate варианты этого нового harness не исполнялись; минимальные SQL permission-denied controls и успешный restore проверены реально. Весь RP15-012/прочие границы/рабочая MAIN activation/native и завершение DEV-15 остаются отдельными воротами; DEV-29 не начинался.

Артефакты в work/dev15-wb005-20261102: worker-tls-report.json SHA `4c78d149065a124450292ba77bf69530693eb50172ca0145cfd80478adc799d7`, подписанный worker-tls-attempt.json, review-gate.json, final-preservation.json и final-check.ps1. Сырые probe stdout/stderr/transport/startup/counters/ACL находятся в закрытом ignored private. Заключение — dev15-worker-tls-review.md; сценарии — dev15-worker-tls-plan.md.
