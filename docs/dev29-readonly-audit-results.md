# DEV-29: завершённый read-only Audit Q007/Q008

2026-11-03, D-417/D-419. **Audit PASS, независимое ACTUAL-AUDIT-RESULT-REVIEW-001 APPROVED, стенд остановлен и очищен.** Это завершение разрешённой read-only области, не полного P29-A/DEV-29. SQL-запись fixture, Run, квота1000 и APP/EDGE admission не выполнялись.

## Выполненная цепочка

1. Сохранённый owned local volume и pinned images проверены. Независимо принятый RO-volume inspector подтвердил PG18 initialized/clean shut down, без SQL/сети/writable mounts; helper удалён. VerifyStart/fresh0inventory PASS.
2. Неизменённый compose поднял только DB512МиБ/.5CPU/PIDs128 и одну internal DB network. Init/migrate/API/ingress/working writer не запускались. DB ID `bfb589a914239dcd1aad4579b275d2923bf714fe9d75f985cf53571cece3aae9`, network `c0e60eddc8959269afd48c774a1f5f5d370eb48485c53f0cee6ab0d9cb7295c7`.
3. До первого Observe исправлены только представления Docker API: leading CAP_ для прежнего exact whitelist и Desktop host-drive prefix для exact bind paths. CAPS-REVIEW-001/BIND-REVIEW-001 APPROVED, настройки/полномочия контейнера не менялись. Нужные source/package/review SHA заново неизменяемо связаны; старые snapshots не переписаны и не содержат неуспешных Audit attempts.
4. Последний run `50a66937-6be2-4d76-bf50-9849f3601986`: source31 fingerprint `1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`, canonical plan `708495a6a6dc06ff673dd2d597e06078e669670f42211c1cc348f5d0fd32dcad`, raw plan `afdf2f3e58fd14e98b7a3103cc68933b3607757c9231804e692aaf278d750088`. SNAPSHOT-ADMISSION-REVIEW-001 APPROVED.
5. Один signed Observe PASS, независимая actual payload review APPROVED в пределах TTL; один IssueAudit PASS с signed provenance receipt; один controller Audit PASS. Helper только read-only repeatable-read/TLS verify-full к UNIT/MAIN и catalog закрытых архивов. Ключи/credentials/полные Docker dumps не выводились.

## Свежие результаты

| Проверка | Факт |
|---|---|
| MAIN | state-v2 `b42ec332cfcd39f3952210eedbfc9722b0302dd9e94fa76b3b3f03aa6f13599a`, совпадает с принятым ранее; row digest `2c7464d1a6e86164a8d48fff53f6f7901f2635455dc40f9eef6e21313cd16412` |
| UNIT | OID52766/owner postgres/marker `ESTAKADA-DEV15-CAPACITY:cdeb944a-b44c-4df2-ac8d-810db7b942db`; все7 предметных journal tables пусты, только3 migration rows; migration sequence `[4,true]` |
| UNIT row digest | `25fe39a22a807fbabceff911020af3991afe7b2bbe06020ab52c3e569af8fa7d` |
| Schema MAIN/UNIT | `4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7` |
| Архивы | OID16387/32563, owner postgres, allowConnect=false; строки закрытых архивов заново не читались, catalog/provenance проверены без открытия |
| Preservation digest | `a5422b40f83525de4a1aa57df94cd4f744fa339a6ff037057526b2a6a1f501c9` |
| Audit result raw SHA | `9e7ab1635279e28b669bd3a63e14fcf47cce3391d490b85e905f1419ef46555d` |
| Helper | memoryPeak79,986,688байт <256МиБ; oom0/oom_kill0, ExitCode0, stopped/exact-own removal подтверждены |

Фактический read-only Audit не подтверждает SQL commit/crash durability или rollback будущих fixture-тестов. MAIN state-v2 сопоставлен с ранее принятым состоянием; физические WAL/статистика от обычного DB-start/stop могли меняться. Метаданные закрытого архива не выдаются за новое чтение всех его строк.

## Остановка и сохранность

DB штатно остановлена и удалена по полному own ID; только созданная пустая internal network удалена по ID/labels/endpoints. Никакого down -v, удаления/переименования тома или чужих объектов не было. Независимый финальный Docker inventory: project containers0, trust-test networks0, latest helper containers0, exact retained volume dbdata/local/scope/project/volume labels сохранён. Старый write-profile.json точно `{}`. Post-run controller Verify PASS/runtimeAdmitted=false.

Phase/receipt/authorization/attempt artifacts сохранены как история. Operator.lock phase=AUDITING — намеренный immutable ledger, не работающий контейнер и не разрешение Run. Не удалять locks для повторной попытки. Все11 публичных входов authorization receipt с совпавшими SHA сохранены в authorization-inputs/ до обновления summary-документов; после добавления текущих итогов исторические input hashes проверять по этому архиву. Секреты/ключи туда не входят.

Основные доказательства — ignored `work/dev29-publication-20261103/pg-check/runs/50a66937-6be2-4d76-bf50-9849f3601986/`: current-code-binding, signed preflight/authorization/admission, audit-send/output/result/complete, cleanup-result, authorization-inputs. Доказательства не отправляются в Git автоматически.

## Следующий участок

Q007/Q008 выполнены и не требуют повторного согласования. Следующий непосредственный участок DEV-29 — конкретный ограниченный план PostgreSQL-проверок протокола публикации с synthetic fixture и rollback. Для него сохраняются отдельные условия Run: fresh DB instance/baseline binding и реальный resource/time budget; одного quotaEstimateAccepted=true недостаточно. Этот Audit даёт baseline и сохранность, но не разрешает fixture writes, новый Run, очистку UNIT или обход runner guard.

Старый сайт/VPS не затронуты, публичная публикация не включалась. DEV-29 около35%, этап8 около31%; оценки не повышены за готовность вспомогательного стенда. Текущий этап8; следующий общий этап9 только после завершения разработки и предусмотренных e2e.
