# DEV-29: Q021 — ранний FAIL и остановка

Обновление D-458: [причина именно R021 установлена по backend log](dev29-docker-timeout-cause.md): cold start19,09с превысил оба9сdeadline. Ниже исторический postmortem до этого свидетельства; FAIL/once/history не меняются. Новых Docker/SQL/Run нет.

2026-11-04. R021 / BOUND29-RUNTIME-RESUME-002 — «Приостановлено владельцу» после двух equivalent CONTAINER_LIST timeout внутри одного разрешённого opaque Run. Owner D453/Q021 разрешил весь один lifecycle; повторного Run нет, новых Docker/SQL calls после возврата не выполнялось. Далее только файловый postmortem/независимое review.

## Подготовка и допуски

Новая COW36 package74e315a4f413665aeb07201c39fe8bbc68a1aa5fed43f526a2f8bed043877aa9:26inputs byte-identical/10 identity-only changes; syntax12Python+13Node и42Node+44Python offline PASS. Independent CODE APPROVED с собственными42Node PASS. Один Prepare PREPARED, independent public prepared-result/dispatch APPROVED. Rawplan66b398642a2394986d42f070f5e1b8088cf94c7671b8899d68db1ce1c0bcaf64, payload2a8e76225bdb1d5c89d420bd0d79e15b10ebbae9752caedca29521d1168e0699, source31 fingerprint1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e. Новый root7ead868c-8fe8-4096-97c5-641d4c72efa3. HMAC plan проверяется штатным Run доDocker; независимое public review не читало ключей и не заявляло HMAC verify.

## Фактический результат

Single Run exit1: FAIL/PREFLIGHT/HOST_CLEANUP_UNPROVEN, resultPersisted=true; cleanupProved=false, originalPreserved=false, fullP29A=false, diagnosticUnproven=false/evidenceIncomplete=false. Aggregate FAIL не заменяется последним удачным inventory.

| Call/stage | Факт |
| --- | --- |
| 2/PREFLIGHT/CONTAINER_LIST | ETIMEDOUT, timeout8999мс, duration9010мс, SIGTERM, получено0bytes/partial |
| 4/STOP/CONTAINER_LIST | ETIMEDOUT, timeout8999мс, duration9008мс, SIGTERM, получено0bytes/partial |
| TERMINAL inventory | container/network queries exit0/empty; activeIds0, cleanupError=null |

Fresh info перед calls2/4 подтвердил expected engine18f3b425-a862-4cbe-ba14-438caef2aab2 atcalls1/3. Причина timeout внутри CLI/daemon/метода запуска не установлена. Q020 PASS другого formatted async query не переименовывается в исправление quiet request. No third same attempt/new Run; по AGENTS остановка после обнаружения второй ошибки на доступной границе. Внутри opaque controller мгновенного прерывания не обещали.

PREFLIGHT завершился до original inspectors/create/admissions/INIT/C/T; отсутствие attempts/reviews/admissions/создания ресурсов и phase execution подтверждено независимым postmortem. OriginalPreserved=false = NOT PROVEN, не обнаруженная потеря данных. Последний inventory — доказательство отсутствия owned resources, не успешность всех промежуточных cleanup checks. Старый DB/корпус/runner/source/старый сайт/VPS не изменялись этой попыткой.

## Сохранённые evidence hashes

| Artifact нового private namespace | Raw SHA256 |
| --- | --- |
| result.json | c64150d91a85fbc96024b9a663ce67a7d010cab1fcafcadb73320f8c03ce7537 |
| docker-failure-2.json | b6e90acb0da4c25d30e007519e6de67f0985d463d7a167146739aface332f720 |
| docker-failure-4.json | fafee3d92e0b073cd4a770e4527c543dfcbf71f8abba09e1ee977eb51d523002 |
| terminal-inventory.json | 03b9023db9113c30c3a14137430d75e5235e10d57d4f16d17a9943e0a0f469cc |

Файлы append-only, подписаны штатным кодом; manual key/HMAC probe не выполнялся. Trace closed22fields/raw0, ledger7. Ключи/credential values/raw outputs не выводились и не копируются в Git. Независимый рецензент /root/dev29_publication_review: ACTUAL POSTMORTEM FILE REVIEW APPROVED как честный FAIL, P0–P2 findings нет. Самостоятельно совпали все7 ledger raw hashes/bindings и public attempts/reviews0/phases{}/witnesses{}. HMAC подписи независимо не проверялись, keys не читались. Это не diagnostic PASS/не новое разрешение. Старые packages/receipts/report003 с замечаниями/report004 остаются прежними.

Следующий участок: файловое сравнение sync/async/format/deadline путей и предложение конкретного отличающегося способа диагностики/исправления. Никакой новой Docker пробы, изменения timeout/query/runner или нового namespace до отдельного решения владельца. DEV-29 около35%, этап8 около31%; INIT/C/T/1000/139 NOT_RUN. После P29-A — план P29-B/C/D/E, общий этап9 после завершения разработки.

## Файловый анализ execution paths

Отдельный исполнитель read-only сравнил controller.mjs:57,63,102,115,116 и failure-host.mjs:36–50. PREFLIGHT/STOP/TERMINAL используют одну exact quiet ps query с root label и один rawDocker→executeDockerCall→spawnSync путь. Все имеют nominal10000/native8999мс; в этом раннем отказе commandDeadline изначально null, поэтому terminal reset не увеличивает budget. Успех TERMINAL не объясняется async/другим запросом/большим timeout. Менялись момент и предшествующая история CLI/daemon; причина NOT PROVEN.

Q020 отличался сразу async transport, formatted command безlabel,45с budget и моментом: это не контролируемое сравнение. Гипотезы ResourceSaver/прогрев/права/ошибкаSync не объявляются установленной причиной. Для следующего решения можно рассмотреть ограниченное новое read-only исследование точного quiet запроса через async при прежнем9с, без повторов; оно само по себе не докажет причину временного поведения и требует отдельного конкретного плана/review/ответа владельца. Сейчас ни исследование, ни исправление, ни новый Run не выполнялись.
