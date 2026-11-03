# DEV-15: измерение общего ресурсного бюджета

2026-11-02, D-385, RA15-001–006/RP15-012. DEV-15 около95%, этап8 около28%. Независимый result-gate положительный для выбранного ресурсного аудита.

## Фактический результат

Один read-only аудит PASS. Общий observed+reservation **317325492байта, около302.62МиБ**, при пределе2147483648байт/2ГиБ. Это служебная среда TRUST и её тестовые данные, не размер всего сайта или будущей production-площадки.

| Состав бюджета | Байты | Область |
|---|---:|---|
| DB data directory du |271020032|Весь текущий кластер, включая обе архивные БД,MAIN,UNIT,WAL иtemp |
| Host task/private/evidence/preview |29528244|14точных корней: все work/dev15* плюс preview из подписанногоcandidateattempt |
| Docker log reservation |8388608|Подтверждённый json-file1m×2 для3сервисов+1helper; не точный замер DockerDesktop logfiles |
| Terminal artifact reservation |8388608|Последующие boundedартефакты/отчёт, каждый≤256КиБ; не выделенный объём диска |
| Итого |317325492|Резервы включены, hardQuota=false |

du повторён после финальнойchainverify доStop и не изменился. Host snapshot снят раньше, последующие файлы покрывает отдельно заявленный резерв. Shutdown после этой точки не объявляется измеренным. Это observed budget, не гарантия непрерывной квоты. Текущий WALdu67121152байта иtempdirsdu4096байт уже входят в271020032, повторно не складываются. SQL database/relation значения — детализация, а не дополнительные слагаемые бюджета.

## SQL-разбивка

| БД | ФактическийOID | pg_database_size | Таблицы/sequence |
|---|---:|---:|---:|
| MAIN estakada_trust |16384|8468159|8+1 |
| UNIT test_estakada_trust |52766|8509119|8+1 |
| Legacy archive cal_7e145c49 |16387|123025087|6+1 |
| Capacity archive cap_32563 |32563|38999743|8+1 |

В отчёте сохранены mainheap/table/index/TOAST/total для каждой relation, включая admission/migrations. Например, capacity AdmissionPolicy: heap8192/table32768/index81920/TOAST24576/total114688байт; TOAST уже входит вtable, table+index=total. Разные SQL и du способы измеряют разные виды размера и служебный overhead; совпадение их суммы не обещается.

temp_files/temp_bytes и wal_records/fpi/bytes записаны с scope/statsReset как накопительные счётчики. Уlegacyархива68tempfiles/1131235658tempbytes — историческая сумма, не текущие дополнительные1.13ГБ на диске. В остальных трёх БД tempfiles/bytes0. Актуальный du temp-каталогов4096 — размер каталогов в этом наблюдении, не исторический spill.

## Ресурсы и периоды

После полного выхода SQL-probe supervisor ещё в том же256МиБ/.5CPU/PIDs64контейнере снял cgroup: memory.peak26877952байта, PIDspeak6, OOM/kill0, CPUusage947064мкс. Собственные before/after внутриSQL-probe сохранены отдельно; post-exit measurement покрывает завершившийся probe до выходаsupervisor. Перед этим network-none smoke с искусственнымexit7 подтвердил сохранение кода отказа и post-exitmetrics; это проверка обвязки, не дополнительный SQL-прогон.

DB cgroup за собственное время жизни: memory.peak332627968/536870912байт, OOM/kill0; PIDscurrent10/limit128 — текущий счётчик, не peak. CPUusage7104193мкс/throttled819701мкс этого периода не выдаются за TLS или исключительно SQL-аудит. Прежние TLS CPU/memory/IDs сохранены отдельной ссылкой на принятыйreport4c78d149…; пики разных периодов не складываются.

## Сохранность

Оба архива возвращены кALLOW_CONNECTIONS=false/readonlydefaulton, ordinaryCONNECT=false/0sessions. ACL/default не менялись. Fullchainbefore/after SHA `601f675e8969895c57ffa2e09eee6f07df0cd65c69225455bf4756725c6d4b71` одинаков: архивные данные/OID/hash иMAIN сохранены, UNITidentity/marker прежние. Source30/014efc… иconfigdrift0. Бизнес-строки не записывались, MAINactivation/native/DEV-29 не запускались.

Final WinPS5.1 artifact:223privateобъекта/446ACLправил, owner/Allow только владелецSYSTEM, reparse0;0ownedконтейнеров, включаяstopped; inactive/disabled/permit{}. Артефакт связан с resource-report SHA `30f0510f5ea898c94d39cdb76730dcba6a5ff584206e12b7cf2477177e0f29d1`. До изменений сохранены59файлов. Старый сайт/VPS не затронуты, push не выполнялся.

Ignored evidence: work/dev15-resource-20261102/resource-report.json, подписанныйresource-attempt.json, review-gate.json, ast-result.json, supervisor-smoke.json/raw, final-check.ps1/final-preservation.json. Сырые helper/inspect/diskJSON — в закрытомprivate. Публичный plan/review — dev15-resource-plan.md/dev15-resource-review.md.

RP15-008legacyinclusion остаётся отдельной непроверенной границей. ДляRP009/010/011 независимое review приняло связь прежних неизменных29serverfiles с новым131/TLS; разрешённая64МиБinjection не требует физического заполнения диска. После ресурсногоresultgate ещё нужныlegacy008, настоящие закрытыеevidence manifests и соответствующийgate доMAINactivation, затемnative013–019. Весь DEV-15 завершённым не объявляется.

Рецензент независимо подтвердил HMAC/gate/inputSHA, rawframes,4DB/OID/14roots/preview, размер без двойного счёта, cgroup/OOM, closed/on/0sessions, chain/source/config и итоговыеACL/0owned. Повторных runtime-проверок рецензент не запускал. Scope и ограничения наблюдения приняты; RP15-012 ресурсный аудит закрыт в измеренной области, будущиеnativeпериоды не подменяются этимPASS.
