# DEV07-N2 — поздние права и непрочитанный результат Save

2026-11-01, D-343. Ограниченный NET007/008 завершён локально: **NETWORK_LATE_2 first2/2 PASS**, независимое ревью без блокеров. DEV-07 около95%, этап8 около20%; полный редактор/production не принят.88 имеющихся изменённых/новых файлов сохранены в work/dev07-network-late-20261101/before.

## До кода и точные источники

Технический контракт dev07-network-late-checks.md9489915a4131508db05991ed9fb094d5c8e74e0e6841c6ba908dbda1f815e674, независимые сценарии dev07-network-late-scenarios.md2a445db0a31fe8b4fe19b944054b19d4d0da5df5ba2818ac4af0e15a9394e02c, read-only adapter dev07-network-late-adapter.md669b66252242e39936fa6a41fe6f0127c7e7d29ada13a141c052882a20eedb31 прошли предварительное ревью до реализации. Использованы только существующие owner HTTP actions и неизменный сетевой профиль: body120, app768MiB/1CPU/pids128, child384MiBAS/10CPU/20wall, один slot; test-only threading/proxy150 и observer1ed961… не расширялись.

Новые frozen QA: helperca12fca51b6f99bdc8b4061cc19bcd833baa7bb7fdf1945ea0135c9fe84e1f4b, probecc5eb9d764329d39f5d2baef954d9d6b5990664e1c7ebd33c3a7c96ef53e2705, host578e6cc73f5e34345204826e5896ccc1f9f6f610427330774d1799dfa8bb8e53. Node2/ASThelper/diff-check PASS. Старые772b fixture,2d845 witness и NETWORK_6 tools не менялись. App product source05c24609a2605d5fdf4352977f27ee883a543c9c0655a05c3f7946fc42796417 до/после одинаков; код продукта в N2 не менялся.

## Фактический первый прогон

Артефакт work/dev07-network-late-20261101/browser-first/host-report.json. Exit0/stderr0;12 traces завершены, observer ready=true/fault=false/installCount1/sequence121. QA/config/foundation guards до/после равны. Ни reader/clock/child/writer, ни commit не подменялись.

| Сценарий | Полученное доказательство |
|---|---|
| NET007.grant | Employee Check достиг actual body/slot/deadline barrier, owner настоящим POST отозвал назначение и получил303. Read-only witness подтвердил отсутствие grant при прежней generation/active/session counts; A завершён полным телом, actual child1, **403 EDITOR_FIELDS_FORBIDDEN**, без proof/result/content mutation. Owner healthy после отказа прошёл; grant восстановлен через реальный owner action, employee Check снова успешен |
| NET007.session | Employee Save с настоящим proof/op удержан на body. Owner POST password reset303; witness generation+1/AuthSession0/current-generation0/linked-native0. После полного тела/реального child1 — **401 EDITOR_SESSION_ENDED**, нет operation receipt/content mutation. Старый session endpoint401; owner healthy успешен, employee новый login с новым RAM-only паролем/новой generation и Check успешны |
| NET008.full | Socket paused до записи, без data/readable/read/resume/JSON consumer. Сервер фактически получил полное тело: reader/normalizer завершены, terminal200 и отдельный durable witness подтверждает один commit с owned actor/Page/generation/canonical editor fingerprint/result. Только затем paused client закрыт, не потребив application response; watchdog/error=false, readable buffer0. Это не доказательство потери сетевого пакета или отсутствия kernel/server write |
| NET008.replay | Отдельный явный запрос повторил тот же Buffer/query/operationId/CheckReceipt/base, с новым traceId. **200/replay=true**, тот же resultId/action/code/gone; domain/receipts/versionAudit не изменились после первого commit |
| NET008.negatives | Изменённое тело с тем же op —409 EDITOR_OPERATION_CONFLICT. Новый op со старым base/proof —409 EDITOR_BASE_CONFLICT. Дополнительных версий/receipt нет, исходный durable result не изменён; заключительный owner Check успешен |

Все12 traced requests действительно вызвали один normalizer: late-auth отказ не объявляется early/no-child. TimerAlive=false, duplicateClosed/slotFdClosed=true, expired=false, все события завершения присутствуют. Независимый reviewer лично прочитал отчёт и все12 observer rows, source/QA contracts и guards. Grant/generation/durable tuple проверялись строгими runtime assertions в probe; сырые промежуточные late-witness snapshots отдельно не архивировались, и reviewer не выдаёт их за прочитанные отдельные артефакты.

Raw Save wire SHA452da477f81e6abaaa99535a1819ee73ea3c96b7f40d019e41197c58598abe94 отличается от canonical editor fingerprint43dbff09328a5d4ddec7db866de17d0158dde2e4ad41ddfd47775a3350646842. Первый относится к точным переданным bytes; второй соответствует Python sorted-key UTF8 DTO digest. Подпись CheckReceipt независимо HMAC-верификатором harness не пересчитывалась: фактический сервер принял proof для настоящего write/replay, прежние crypto regressions остаются отдельным server207 cohort.

## Границы и продолжение

Проверены ровно два late cases и owner/current commit с client non-consumption/replay/двумя negatives. Не проверены все grant downgrade/disable/logout/session races, replay после отзыва прав, все draft/stage/media/identity/source сочетания, browser UNKNOWN RAM matrix или физическая потеря сетевого пакета между commit и server write. Auth witness читает только own metadata; linkedNativeSessionCount не доказывает отсутствие старой уже несвязанной native Session. Secrets/session data/keys/password hashes не извлекались в IPC/evidence, прямых auth ORM mutations не было.

CleanupClosed=true:0 live own users/pages/versions/drafts/stages/pins/assets/files, SYSTEM route/permanent ledgers сохранены; фото не создавались. Root подтвердил Stop exit0/manifest.active=false с сохранением данных/снимков. Старый сайт/VPS/214 originals не затронуты; новых программ, зависимостей, ресурсов, портов или production profile не вводилось. Git не сбрасывался; commit/push не выполнялись.

Дальше внутри DEV-07 — combined maximum retained-source/two-fields/tree resource gate, общие Header/Footer/квоты и оставшиеся table/price/legacy/other-browser/identity/FS матрицы по действующему плану. Пройденные NET001–006 и207server/22MODEL/6FORMAT+8E3 не переименованы в новый общий прогон.
