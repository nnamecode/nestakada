# DEV-29: результат Q023 — сохранность подтверждена, сетевой guard остановил INIT

2026-11-04. R023 / D466/Q023. Один условныйRun завершён FAIL/INIT/HOST_NETWORK_BIND; повтор не разрешён. Readiness и stdin-profile прошли настоящий preflight, включая запуск helper. Данные исходного тома сохранены, временные ресурсы удалены. Это фактический частичный результат, не завершение P29-A.

## Подготовка и фактический прогресс

Frozenpackage36 d7951336f23cff9c01c18d244cd913c0d4aff78dcbd9a77ee3397303a2b1a7cd, plan00b400f0d8b6aff861bd5e9b4592792c4b5010e472fc1902f6c4ca92698f537c. Syntax12Python/13Node и101 distinct offline PASS; AC6 subsethost33, independenthost33PASS. ПервыеACfixtureошибкиoldlabel/NoCopy исправлены конкретно, productionguards не ослаблялись. Old36/source31 unchanged1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e.

SinglePrepare PREPARED; publicprepared/one-dispatch reviews APPROVED. Rawpland70c7725476b3156d776399ff5c4f6e10cf447db14fb3e7f2bd3cf5d896a5c72, canonicalpayloadb6e044453d1031534c1c0da4dda8f118fba3891fe63204b07a7c4e785b172c48. Прогон прошёл readiness, image/source/VMmemory, preflighthelper и originalRO-before/budget; выдан одинINITadmission.

Реальный preflighthelper: statusPASS/sourceMatchtrue/exit0/stderr0, createdиexited StdinOncetrue, OOMfalse. Значит stdin-исправление подтверждено реальным выполнением. RO-inspectors безstdin также прошли guard. После этого создана одна новаяinternalnetwork и контейнерDB; самконтейнерDB никогда не запускался, supervisor/initdb/PostgreSQL/SQL не выполнялись. STARTreview не запрашивался, INITworker/C/T не начаты.

## R023-REV-001 (P1): CREATED не равен RUNNING

inspectGate spec.mjs:57 требует NetworkSettings.Networks[NET].NetworkID==expectedID для любого состояния. Сохранённый create-timeDBinspect:

| Свойство | Наблюдение |
| --- | --- |
| State.Status / Running | created / false |
| StartedAt | zero, не запускался |
| HostConfig.NetworkMode | точное ожидаемое owned network name |
| Networks keys | ровно одно ожидаемое имя |
| NetworkID / EndpointID | пустые строки |
| Сама owned network | точный64hex id, Internal=true, members0 |

Созданный объект содержит намерение подключиться к сети, а runtime IDs появятся при старте. Текущий guard остановил дальнейшие действия fail-closed. Mockcontainer() всегда задавал NetworkID даже дляcreated и не задавал EndpointID, поэтому скрывал различие стадий. Произвольное принятиепустогоID дляrunning запрещено; sourceне менялсяподотказ.

networkGate:43 проверяет только отсутствие foreign members (subset allowedIds), не требует присутствия всехallowedIds; пустаясетьдоstartне являетсяотдельнымблокером. Нельзя выдумыватьэтудополнительнуюошибку. DBrunning binding послеREADYиbeforehelpers существующийкодпроверяетстрого. EXITEDповедениеприкреплённогоhelper этимRunне наблюдалось — его нельзяугадатьпомокам.

Следующий безопасный участок: независимо квалифицироватьCREATED→RUNNING→EXITED наодномnonSQL pinnedPythonконтейнере/ownedinternalnetwork, безmounts/secrets/ports и сcleanup, доизмененияnetworkguard/ещёодногоPGRun. Это только предложение; текущийQ023исчерпан, nativequalificationне выполнялась.

## Сохранность, бюджеты и очистка

Signed result: resultPersistedtrue, FAIL/INIT/HOST_NETWORK_BIND, cleanupProvedtrue/originalPreservedtrue/fullP29Afalse, diagnosticUnprovenfalse/evidenceIncompletefalse, phases{}/witnesses{}. Все36ledgerhashes совпаливнезависимомreview; HMAC независимо не проверялся, ключи не читались.

OriginalBefore иOriginalAfter каноническисовпали: SHA256bf5336e983b3044984e12680d2f3e83551bc7e621b07f8fe3d2b4d56bf392323. ДваRO-inspectors работали безSQL поread-only/volume-nocopy. Protectedoldclusterне запускался.

| Budget | Base bytes | Conservative bytes | Limit |
| --- | ---: | ---: | ---: |
| Before | 328526400 | 1721035328 | 2147483648 |
| After | 329070770 | 1721579698 | 2147483648 |

HostRoots31 сохранены; разницаbase — новыеartifacts, не удаление/изменениестарогокорпуса. Publicattempts: ORIGINAL-before, INITadmission, ORIGINAL-after. Reviews0. DBstatuscreated/StartedAtzero, затемexactownedstop/remove/absence. Networkinternal/members0 удалена сabsenceproof. PreflightиROhelperstooочищены. Terminalsameengine containers/networks exit0/empty, activeIds0, cleanupErrornull.

| Evidence | Raw SHA256 |
| --- | --- |
| result.json | 15fe3a1755d4a6af6f8738eb34c15f9662c2be350bda6841602be7e374f9a7f9 |
| cleanup-db | 079df90877cc2e956635c2d45dda2d4691bb372f7b0c284c30e972bff8a2ab6b |
| network-cleanup | 75d8f4d108f4867f71c86f98fd8f45a405c3cbdba7c4784a08ffd283a4bf7de4 |
| terminal-inventory | 2a37c0688dfad597acf6e91b7d1896a89793802280281bda16349fb0701129f6 |

/root/dev29_publication_review: ACTUAL POSTMORTEM FILE REVIEW APPROVED какчестныйFAIL; R023-REV-001 P1 открыт. НикакихновыхDocker/SQL/Runпослерезультата. Старыйсайт/VPS/source/runner/корпуснетронуты. DEV-29≈35%, этап8≈31%; INIT/C/T/1000/139 NOT_RUN.
