# DEV-15 — независимое ревью технического предложения

Последний пакет D-379 к согласованию DEV15-Q002: [рабочий допуск](dev15-runtime-admission-proposal.md), [план CLOSE-02–04](dev15-runtime-verification-plan.md), [положительное независимое ревью](dev15-runtime-proposal-review.md). Это не согласование владельца и не результат реализации.

Актуальный итоговый аудит оставшихся условий D-378 — [dev15-completion-audit.md](dev15-completion-audit.md), положительное независимое ревью — [dev15-completion-review.md](dev15-completion-review.md). DEV-15 остаётся в работе85–90%; прежние срезы ниже не закрывают четыре открытых локальных условия.

Новое ревью D-377/full snapshot/startup — [dev15-snapshot-review.md](dev15-snapshot-review.md), результат — [dev15-snapshot-results.md](dev15-snapshot-results.md). История предыдущих срезов ниже сохранена.

Последующее ревью D-376/write admission/fault recovery находится в [dev15-write-review.md](dev15-write-review.md); результаты — [dev15-write-results.md](dev15-write-results.md). Ниже история первоначального предложения и D-375, не отменяющая актуальные локальные проверки и не разрешающая production.

2026-11-02. Рецензент: combined_review, автор другого результата; readonly, без изменений файлов/запуска тестов/контейнеров. Область: dev15-proposal.md, dev15-checks.md по принятому D-307/PR-04/08, HTML §6, REQ-037/044 и связанным AC. D-373 разрешает предложение/review, конкретная конфигурация ждёт DEV15-Q001.

Ни код, ни протокол работающего сервиса, ни физическая независимость этим review не проверены. Все SC15 — сценарии до кода, не PASS. Первичные API/DB/Docker свойства проверены по официальной документации, полные ссылки в предложении.

| ID | Приоритет | Замечание | Исправление автора / статус |
|---|---|---|---|
| DEV15-REV001 | P1 | Общий старый writer-secret мог прочитать свежее epoch и подставить его; одного числового CAS недостаточно | §4/7: server-side credential-id/principal→epoch binding, revoke прежнего credential доrestore, новый случайныйsecret внеAPPbackup толькоrecovery послеreconcile. Проверка binding повторно подHeadlock; writer/GET head не перепривязывают ключ. SC15-011 использует настоящий старый secret со свежим прочитанным epoch. Закрыто независимой delta-проверкой на уровне предложения/сценариев. |
| DEV15-REV002 | P1 | Не определены prepare/report phase idempotency и запрет late UNKNOWN/другогоterminal поверхfinal. Replay мог навсегда получать CAS conflict после потерянного ACK | §5: immutable prepare fingerprint/отдельные phase fingerprints/одно terminal outcome; таблица переходов, повтор распознаётся послеauth/binding доCAS новой записи. Terminal не понижается; инойresult/target/receipt→409, точный старыйexpected retry возвращаетreceipt+currentstate безhead increment. SC15-004/005 усилены. Закрыто независимой delta-проверкой на уровне предложения/сценариев. |

Рецензент не выявил других блокеров: сумма профиля **896МиБ/1.25CPU** верна;2ГиБ явно budget, не hardquota;64+16МиБlogical резерв требует реальной калибровки доwrites. Полный gate/maincommit/in-flight/restore и own-TRUST recovery/провайдер/стоимость/production оставлены отдельными, автоочисткизапретов нет. Это не подтверждение реализации или закрытие ARC-10.

Дополнительно автор явно закрепил expected incarnation в TRUST private pin вне DBvolume/APPbackup и запретил автоматический bootstrap при потере БД. Проверка исходного прежнего кода/runtime не требуется: в этой задаче меняются только документы; Dockerinfo прочитан read-only, контейнеры не запускались.

Итоговый gate к DEV15-Q001 положительный: рецензент независимо сверил оба исправления, новых блокеров нет. Рекомендованное выравнивание имени FINAL_RESTRICTION в таблице §6 выполнено без изменения протокола. Владелец ещё не согласовал локальную конфигурацию; никакие новые ресурсы/ключи/сети не созданы.

Предложение и сценарии готовы к ответу владельца. DEV-15 в целом около15%, этап8около28%(8/29задач завершены локально). Реализация/реальные тесты не начинались; физический ARC-10 остаётся открытым.

## Локальная реализация по D-374 и текущая пауза

Владелец согласовал DEV15-Q001 поD-374. Доruntimeисправлены CODE001/INFRA001–002/WRAP001–003 иsafe logging/input/concurrency/pagination. FirstStartFAILTЛSkeyразобран offline, fix640/GID10001+/tmpпрошёлнезависимыйgate. ПоследующиеStartбезbootstrap/20unitPASS5.147/Stop0 фактическивыполнены; productsource17 неизменён. Native4/codegate иоднокорпуснаяcalibrationreviewподготовлены, новыйдвухфазныйcorpus/guarddiffещёожидаютfinalgate.

Работа приостановлена владельцу DEV15-ACL-RESUME-001 послеrootповторнойошибки дополнительногоACLконтроля. Reviewerпрерван, далее ничего неисполнял. ПодготовленныйисправленныйACL-check иpendingwrapper/corpusпотребуютresumeпоAGENTS. Это неотменяет20actualPASS и неразрешаетpersistentwrites/физическийARC10/production.


## Gate возобновления по D-375

combined_review послеответавладельца независимо проверил preparedACLscriptc0f6e566… иконечныйwrapper/corpustransport. Gate положительный наодинACLконтроль DesktopPS5.1, затемStartбезbootstrap→Transport4→Calibrate→finallyStop. ПровереныcalibrationAttemptedдоsubprocess/Testsblock, exactUNIT/emptyguard, hardalarm240/Docker300, reserve-saturation→UNKNOWN/finalize→logicalrefusal безreset. Реальные20unitPASS/source17 сохранены; persistentactivation/fullARC10 неразрешены. Рецензентничегонеисполнялинеизменял; actualACLrootPASS4files.


## Итоговый result/doc gate после D-375 — положительный в ограниченном объёме

combined_review независимо прочитал actual20unitPASS5.147с,Transport4PASS идвухфазнуюкалибровкуPASS150.673с/run7e145c49…:60ops/15360refs/gen121, reserve16,221,469B→отказ→UNKNOWN/finalize→reserved0;logical66,897,420B→отказ. Числаbyte/CPU/пиков вdev15-results.md совпали сreports. Лично сверены17host/frozen и10configSHA:drift0; manifestactivefalse/calibrationAttemptedtrue/Stopretained.

Документ корректно оставляетpartialSC15 иwritesDISABLED. DEV-15целикомне закрывать: следующийлокальныйсрез — source/schema-bound vettedwriteprofile, реальныеHTTPmutation/lostACK/crash, credentialrotation/recovery иполныйsnapshotconsumer/startup. Прочиеquota/count/REDIRECT/fault/admission проверяютсялибообосновываютсядоминирующимиквотами. Настоящиеgate/mainreceipt/in-flight/APPrestore ифизическийвнешнийTRUST/provider остаютсяотдельнымиворотами. Новыхfactualзамечанийнет. Reviewerне менялфайлы/невызывалDockerSQL.
