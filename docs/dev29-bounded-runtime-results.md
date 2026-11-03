# DEV-29: первый запуск подготовленного Q014-контроллера

2026-11-04, BOUND29-REAL-RUNTIME-001. **FAIL / PREFLIGHT / HOST_DOCKER**. Независимое ACTUAL-RESULT APPROVED принимает достоверность раннего отказа и cleanup, а не успешное выполнение PostgreSQL-проверок. Единственный Run завершён; повторов не было.

## Разрешение и входы

Действующее Q014/D-434, [согласованный профиль](dev29-bounded-sandbox-proposal.md), [code/Prepare review](dev29-bounded-host-code-review.md). Независимый рецензент `/root/dev29_publication_review` отдельно одобрил один dispatch, не предодобрял START/INIT/PAYLOAD-C/C/PAYLOAD-T/T. Перед dispatch подтверждены code/plan/private pins, HMAC, native ACL owner/SYSTEM-only и пустые attempts/reviews. ACL не менялись.

- Run: `1e23c654-5baf-4b5e-a7b4-6235b1289c0a`.
- Package28 canonical SHA256: `c80072e83a98c25b6606b0c3ea332987b65d2f46e1f27526d12d74391048c6b9`.
- Prepared plan raw SHA256: `779285dfa6e644257ebb52157751ce7842661a736f2480fbb15c3812ce82256c`.
- Docker Desktop local npipe: Linux29.9.2, engine `18f3b425-a862-4cbe-ba14-438caef2aab2`; перед Run16 containers/0running. Чужие контейнеры не изменялись.

## Фактический результат

Сначала успешно получен engine info и сохранён engine-preflight receipt. Затем один из read-only preflight Docker calls завершился общим HOST_DOCKER. Helper boundary/create не достигнуты. Контейнеры/сети этого Run не создавались; original inspector, SQL, INIT/C/T и phase admissions/attempts не запускались. Старые5+8 probes не повторялись.

Result: `status=FAIL`, `phase=PREFLIGHT`, `code=HOST_DOCKER`, `fullP29A=false`, `cleanupProved=true`, `originalPreserved=false`, phases/witnesses пусты. Последний false означает отсутствие pre/post original proof, **не обнаруженное изменение тома**.

Signed stand-stop и terminal inventories: exact label queries containers/networks завершились exit0 с пустыми stdout/stderr; activeIds пуст, cleanupError=null. Четыре свежих engine boundaries подтвердили прежний engine. Все7 ledger hashes независимо сопоставлены с файлами рецензентом; координатор отдельно проверил HMAC всех7 envelopes и результата. Независимый рецензент ключ не читал и отдельную HMAC-проверку не заявляет.

| Свидетельство | Raw SHA256 |
|---|---|
| result.json | `4760812586b8727d80ee3d666c55c17ae4c3bdda00d75fad64c0dbd936b93cc0` |
| terminal-inventory.json | `b4151796b6389f774086d94be1ab0a8d1f6f5ee7c10cfac96384400d67ee0b5c` |
| read-only-diagnostic-001.json | `0bf1a6ed41b8757efc25a5807af7db32ba66cb4a3ac8a1d82a1be7b5fe56b0ca` |
| final-coordinator-witness-001.json | `96dcdc8332a4fd97f802ef6f69ccaf0132d373474d8041a0169fa66e8ebabad3` |

Файлы находятся в прежнем ignored private-real namespace. Coordinator witness после отказа подтверждает неизменность шести private inputs, package28 и source31 (`1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`). Старый runner не изменялся.

## Ограниченная диагностика

После отдельного независимого согласования выполнен один read-only диагностический проход: formatted container list, два exact image ID и имя original volume; только local npipe/очищенное Docker environment,15с/call,90с total, stop-first-failure/no retry. Массовый container inspect исключён. Все4 запроса PASS за1209мс; обе images и original volume доступны. Original volume не подключался. Это **текущая доступность**, не доказательство исторической причины отказа.

Точная причина NOT_PROVEN: исходный wrapper не сохранил отказавшие argv/rc/error/stderr. Из имеющихся receipts нельзя установить конкретную команду или объявить причиной timeout, отсутствие image/volume, права либо изменение данных. Один исходный FAIL, повторного Run/эквивалентного отказа/цикла нет.

## Продолжение

Старые package/plan/receipts/secrets сохраняются, их authority не продлевается. [Отдельное предложение возобновления](dev29-bounded-runtime-resume.md) предусматривает новый root run и append-only пакет с bounded failure trace. До решения и новых code/Prepare/runtime gates запуск не повторять. DEV-29 около35%, этап8 «Разработка сайта» около31%; P29-A открыт, далее P29-B/C/D/E, общий этап9 после завершения этапа8. Старый сайт/VPS/production/push не затронуты.
