# DEV-15: восстановление доступа с сохранением запретов

2026-11-03, продолжение D-380/D-398 по «Продолжай». RP15-007/019; DEV-15 около98%, этап8 около28%. План до кода/native, не PASS.

Уже подтверждённое не повторяем без причины: 131регрессия на точном source014efc… включает basic bounded-v2 fence/activate/replay/старыйsecret и отказ v1proof; D-390 операторскаяpolicy+retry; D-392 реальный runtime/CID/leaseUnbind/Restart/stalelease/8lifecycle/9native; RB15 realUNITSQL rollback. Новая область — совместное сохранение pending/UNKNOWN/tomb/резерва при bounded-v2 recovery, late-failurefence/activate и реальный предел4receipts. Старые WPv1тесты не переименовывать в новые v2доказательства.

Прежний DB512МиБ/.5CPU и один последовательный helper256МиБ/.5CPU/PIDs64, pinnedimages, без API/Nginx/hostports/новыхсетей/софта/ресурсов. UNIT точно52766/signedmarker/рольmigrator/TLS/empty7tables/3migrations; source30/config24/EV63 и архивы до/после. MAIN только readonlyactualHead13/b42ec…; writerlease/activation/реальныхHTTP нет. Guardedcontroller/independentreadonlywitness используются из принятогоRB15, oldfiles сохраняются.

FixtureBounded: synthetickeys/identity/UNITpolicy1, outerrollback+doCleanups, без runner/flush/teardown/миграций/DELETE/reset. ValidROUTE иTOMB — разныеoperations. До recovery подготовить route(2targets), перевести его вUNKNOWN, отдельноprepare1tomb; сохранить полныйSHA их persistentrows ирезервов. Один поток2полныхrecoverycycles даёт4настоящихreceipts. UNITresource/evidencefixture явно отделена отMAINauthority.

| ID | Требуемое конечное наблюдение |
| --- | --- |
| RF15-001 | Исходные UNKNOWNroute/PENDINGtomb с fullpayload/phases/rowSHA/reserves, policy1; безexactdescriptor fence403 и full-state прежний. |
| RF15-002 | Fence lateENOSPCexception после реального Credential.update(activeFalse)+RecoveryReceiptINSERT, доHead.save. Полныйrollback сохраняет исходныйACTIVE/epoch/ключи/deny. Тот жеactionIDretry один раззамораживает иповышаетepoch, exactreplay безповторногоadvance/receipt. |
| RF15-003 | Смена runtime/config при старомenvelope закрывает доступ доSQL. Новый правильныйdescriptor не означаетавтоматическийactivate. ВоFROZEN старыйwriter со свежимepoch отклоняется; seeddenies/tomb/reserve прежние. |
| RF15-004 | Trustednewlease с неправильнымv2stateDigest илиpreviousRuntime(exclusion) отказываетactivate и оставляетFROZEN/fullstate безизменений. Bodyвалиден поactualR.validate, signatures действительны; это preconditionfailure, не malformedDTO. |
| RF15-005 | Правильныйactivate lateSELECT1/0SQLSTATE22012 после newCredential/RecoveryReceiptINSERT. Atomicrollback сохраняетFROZEN/noNewCredential/noActivateReceipt/deny. Тот жеactionIDretry активирует один newwriter, exactreplay прежнийreceipt бездублей. |
| RF15-006 | Старыйsecret со свежимepoch не пишет; новыйwriter реальноprepare новогоID, seedrows/reserves неизменны. Не выдавать это заHTMLworkflow/MainAPI. |
| RF15-007 | Второйполныйfence/activate cycle создаётровно4receipts с writer3. Следующийвалидныйfence descriptor получаетRECOVERY_COUNT_CAP безизмененияfullstate; точныйreplay действующейactivation иразрешённаяноваяwriteroperation всёещёработают. Policychain остаётся1, seeddataсохранны. Предел20credentials/16policy здесьне объявлятьнасыщенным. |
| RF15-008 | Outerrollback/reconnect и независимый UNITwitness возвращаютemptybaseline/oid/marker/schema/rows/sequence. MAIN/обаархива readonlybeforeafter прежние, source/config/EV63/keys сохранны; Stop0/permit{}, privateACLowner/SYSTEM. |

До мутаций подписанныйhostintent сточнымиUNIT/MAINbaseline/helper/controller/codegateSHA. Вchild сигнальныйdeadline60с, каждыйDTO actualvalidate; ошибки выводить безопаснымFault.code/checkpoint. Кодпродукта/caps/source30 не меняются. Ошибкиlease/proof не обходить; никакого третьегооднотипногоповтора. Independentplan/code/resultreview обязательны. Ожидаемыеотказы записывать какnegativePASS только при полномassertсохранности.

Это прикладные UNITреcovery операции/ошибки, не physicalpowerloss/откатвнешнейTRUST/провайдер/production и не перевыпускMainwriterlease. Итоговая RPматрица отдельно определит остаток007/019/соответствующихintegrationgates без циклической зависимости отещёненачатогоDEV-29. Старыйсайт/VPS/APP/DEV-29/push не входят. Основнаясводка толькоcurrentprocent.html, сопровождатьбезповторныхобъявлений.
