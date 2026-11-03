# DEV-15: прежние записи в новых квотах

2026-11-02, D-386, LG15-001–006/RP15-008. DEV-15 около96%, этап8 около28%.

Независимое review приняло составное свидетельство: **semanticPASS трёх границ + preservationPASS + wrapper-smokePASS**. Исходный общий hostFAIL/exit2 сохранён; полный controller после исправления не запускался. Его нельзя называть end-to-endPASS. Повтор82секундного бизнес-прогона для закрытия выбранной границы не требуется по заключению рецензента.

## Проверенные границы

Readonlyfixture взята из точной локальнойTRUST MAIN/OID16384: Head9/epoch2,4operations/3routes/1tomb/2recovery/4credentials/policy0. Historicalrefs действительно3 по Operation.payload. Всеpersistentполя скопированы только в исходно пустуюUNIT/OID52766 внутри внешнейrollback-транзакции. До новойUNITpolicy сравнен полныйv2 `dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066`; Main/архивы не записывались.

| Ветка | Перед последним prepare | Последний разрешённый | Следующий prepare |
|---|---|---|---|
| Operations |999=4legacy+995bulkfixture|1000PASS, tombs997/refs3 ниже своихceilings|1001→COUNT_CAP_REACHED, full-state/raw не изменились|
| Historicalrefs |4095, operations20|4096PASS, operations21/tomb1|4097→COUNT_CAP_REACHED, атомарныйотказ|
| Tombstones |1023, operations8|1024PASS, operations9/refs3|1025→COUNT_CAP_REACHED, атомарныйотказ|

995PENDINGопераций в первойветке — явно syntheticbulkfixture с настоящимиDTO/charge/reserve иDBconstraints, не995пройденныхservice/APIпереходов. Refветка заполнена16реальнымиprepare по≤256policies, tombветка —4реальнымиprepare по≤256requestIds. НиCAPS, ниSQLcounts не подменялись.

Во всех3ветках новыйepoch2 prepare/replay→UNKNOWN/replay→committed/replay прошёл с проверкойgeneration/logical/reserve/receipts. На последнейгранице completion не требуетновойквоты. Старыеepoch1payload/receipts не переписывались и не воспроизводились какepoch2. Legacyвсехмоделей/credentials/recovery/pin неизменны; после каждойветки nestedrollback вернул общийadmittedcheckpoint.

Триsemanticgroups PASS за82.235451с при120с guard. Source30 `014efc288de0d32772fca15d63afbb0a4c23a9009ee6ef8bdc877cb1aa41c672`, schema4fb746… прежние. UNITadmission использовал реальнуюHMAC/роль/ресурсы/подпись/CAS/caps; B.unit_calibration заменял лишь незавершённое итоговоеevidence. Настоящий writer/MAINactivation не включались.

## Ошибка обвязки и исправление

Probe выдалPASS и завершилвсеassertions/rollback, post-frameметрик также получен. Но фактический Config.Cmd созданногочерезCompose контейнера содержал пустые строки вместо `$probe_exit`/`$metric_exit`: Compose выполнилподстановку доshell. Вstderr — `Illegal number`, итогконтейнера/hostexit2. Это ошибка завершенияharness после выполненияprobe, не провалграницквот. ИсходныйreportSHA `961a38fe4ebe03d46c846696b8974df09cbb63810a0dd847fa86f42b1446b3ae` осталсяFAIL без изменений.

Узкийfix controllerSHA `9030bcd847c15c71416ca88fbb6cb1627a5ca9ca293562799ef2cdabb5413f60` принят code-review: только для сериализованногоComposecommand `$` удваивается через callback, а actualConfig.Cmd проверяется доintent/start. Исходныйcontrollerе621… сохранён exactbackup; прямойCLI inithelper и обаPythonhelper неизменны.

Дваотдельныхnetwork-noneCompose-create/start/logs smoke проверилиточно тотжеwrapper/образ/256МиБ/.5CPU/PIDs64: fakeprobeexit0→actual0, fakeprobeexit7→actual7, actualCmdсовпадает, postframeполучен, OOM0. Mounts/сети/БД/секретов уsmokeконтейнеров нет, обаудалены. SmokeSHA `21dc96cc39cfd7b3dc5a7479773d79b02341807d1ff1ef7c86cc1a8fac426da1`. Это не повторLG и не end-to-end controllerPASS.

## Сохранность и evidence

Независимыйbootstrapreadonly UNITaudit до/после остановкиprobe подтвердил all8rawSHA `65337494041b01fabdef094fb2ce51d9e87e8f17079b856f820c71cfde743ae7`:7journalтаблиц пусты,3migrations, sequence lastValue4/isCalledtrue до/после. ExactOID52766/owner/marker/SSL/repeatable-read/0foreignsessions иschema совпали. Внутреннийprobe также переподключался и сравнивалraw/sequence; внешнийаудит не зависит отегоJSON. Никакихflush/delete/reset/третьегоархива нет.

MAIN иобаархива сохранили полныеchainпоказателиSHA601f675e… до/после. Приватныеexport/ARG сpayload/verifiers не попали в публичныйreport/Git. Fixtureintent подписан доstart с actualhelperID/facts/config/credentialSHA/baselineSHA. Python/source/config не изменялись, продуктовыйsource30прежний. Helperpeak55119872байта/256МиБ, PIDspeak6/OOM0; это периодLG, прежниеTLS/RAметрики не выдаются зановыйзамер.

FinalWinPS5.1:283объекта/566ACLправил ownerSYSTEMonly/reparse0,0owned, включаяstopped иsmoke; inactive/disabled/permit{}. Артефакт связывает оба исходныхSHA. Доизменений сохранены65файлов. Старыйсайт/VPS не затронуты, push не выполнялся.

Ignoredwork/dev15-legacy-inclusion-20261102: исходныйlegacy-capacity-report.json/attempt/review-gate, oldcontrollerbackup, wrapper-fix-gate/smoke-report/configs/inspect/logs, ast-result/inline-ast иfinal-check/final-preservation. Полныйfixture/args/сырыеprobeлоги — только вprivate. Независимыйgate проверил HMAC/actualID/args/raw/source/schema,3ветки иобаsmoke. Принят только выбранныйRP008; реальные закрытыеevidence manifests/gate доMAINactivation иnative013–019 ещё впереди.
