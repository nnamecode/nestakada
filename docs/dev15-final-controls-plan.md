# DEV-15: конечные подтверждения перед завершением

2026-11-03, D-402. План до кода и запуска, не PASS. Источник — F15-001–003 в dev15-final-coverage.md и RP15-006/012/020. Проводится только при подтверждении необходимости независимым gap-review. Прежние source30/014efc…, schema4fb746…, config24/EV63 сохраняются.

| ID | Наблюдение |
| --- | --- |
| FC15-001 | Actual UNIT52766/signedmarker/TLS/migrator/emptybaseline. Во внешней rollbacktransaction создать policy1 и pendingoperation с точным стабильным UUID; провести revisions2–16 и установить правильный lease policy16. Точно подписанный структурно полный intent17 запрашивает запрещённый policyepoch17 и получает ADMISSION_INTENT_REJECTED; full-state до/после равен. Это намеренное превышение закрытого лимита policy, не допустимая новая revision. История16rows сохраняется. |
| FC15-002 | После отказа17-й реальные read_head/operation_status/snapshot_manifest/snapshot работают; pending denial/receipt прежние. Новый разрешённый prepare и completion исходного pending через policy16 успешны; exact replay сохраняет receipt/полное состояние. Все16policy rows остаются. Это UNITservice, не новая MAIN policy и не HTTP. |
| FC15-003 | Outerrollback/doCleanups/reconnect и отдельный readonly witness подтверждают прежние UNITrows/migrationsequence; MAIN только readonly Head13/epoch2/policy1/v2b42ec…, обаархива beforeafter неизменны/closed. Runner/flush/teardown/DELETE/reset/migrations запрещены. |
| FC15-004 | На принадлежащем стенду DBконтейнере read-only du измеряет data directory доStop. К этому прибавляются логические байты всех фактических work/dev15* корней и preview из подписаннойcandidateattempt, резерв Dockerlogs8МиБ и конечныхартефактов8МиБ. Всё≤2ГиБ; WAL/temp/relations уже вdatadirectory и повторно не складываются. Это наблюдение доStop, не hardquota/точныйpostshutdownразмер. Freshwholehelper/cgroup и DBпериод измеряются отдельно, без сложения пиков. |
| FC15-005 | SHAcodegate/source30/config24/EV63/manifest/env/keys сохранны, privateACL owner/SYSTEM/reparse0 до/после, Stop0/permit{}. Исторические failures/архивы не стираются; независимые code/result/completionreview до изменения статуса DEV-15. |

Прежние DB512МиБ/0,5CPU/PIDs128 и один последовательныйhelper256МиБ/0,5CPU/PIDs64, закреплённые images/внутренняя сеть/том. Нет API/Nginx/hostports, новых программ/зависимостей/томов/сетей/повышения ресурсов. Новый guarded controller выводится из принятого RF15, старые файлы сохраняются. CommonUNITguard/readonlywitness остаются прежними. Передnative закрытыйgate с фактическимиSHA и независимымcode-review, exactintent до отправки. Deadlinehelper60с не повышать автоматически.

Иные подтверждённые gap-review замечания сначала отразить в этом плане, затем код; гипотетические/будущиеAPP/DEV29/READY не добавлять. Полный131 и TLS5120snapshot не повторять при неизменном source и принятыхSHA без новой причины. Старыйсайт/VPS/APP/DEV-29/production/push не входят. DEV-15 пока около98%, этап8 около28%.
