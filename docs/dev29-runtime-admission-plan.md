# P29-A: точный порядок первого runtime-допуска

2026-11-03. Статус: **Q007 и уточнение Q008 выполнены по D-417/D-419: один read-only Audit PASS, независимое result-review APPROVED, own resources очищены, volume сохранён**. [Результаты и продолжение](dev29-readonly-audit-results.md), [ревью](dev29-readonly-audit-review.md). Run/fixture writes не выполнялись и не разрешены. Ниже принятой план/первоначальные параметры сохранены как история; фактический latest run50a66937… привязан в отчёте после reviewed compatibility corrections.

## Зачем это сайту и где заканчивается этот участок

Текущий этап8, задача DEV-29. Конечный продуктовый результат DEV-29 — владелец управляет страницами, их публикацией, адресами и удалением. P29-A проверяет только нижний слой публикации: журнал запретов должен хранить новое состояние без случайного открытия скрытого содержимого. Ни Audit, ни service probe не создают публичные страницы и не включают кнопку публикации.

Уже готовы в своих локальных границах дерево/rename/move/reorder/создание; TRUST publication protocol и consumer написаны и проверены без БД. Далее: PostgreSQL-доказательства P29-A → APP PublicationIntent/client → APP startup/cohort admission → owner publish → unpublish с реальным EDGE close. Это зависимости утверждённой архитектуры, не новые требования. Каждый из будущих участков должен иметь свой конкретный план; публикация не считается готовой от одного успеха тестового стенда.

## Фиксированная привязка

- run `1b296fa0-2cff-4dbf-bcb0-623770d7bf85`, каталог `work/dev29-publication-20261103/pg-check/runs/1b296fa0-2cff-4dbf-bcb0-623770d7bf85`;
- canonical plan SHA256 `7123610f733ea5d1a9a1b2e38ee1d5b134def01b3e8d7f5dd500f2fb0dc507c9`, raw plan SHA256 `78badff5441eb6d01f0d8b89f4de286fd632722142ea53914bdf653af847444b`;
- source31/fingerprint `1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`, exact9 package SHA из plan.json; имена/число файлов не заменяют сверку каждого SHA;
- schema `4fb7464026b738b4bc9cfd1dd23657d5e0425c7b3f859e1d9a9ddb97495d4de7`, UNIT `test_estakada_trust`/OID52766/owner postgres/полный marker из signed archive receipt;
- MAIN ожидаемый state-v2 `b42ec332cfcd39f3952210eedbfc9722b0302dd9e94fa76b3b3f03aa6f13599a`, не новый CAS и не разрешение записи;
- pinned images и protected hashes строго из plan.json, архивы OID16387/OID32563 закрыты; исторические source/EV63/manifest/env/permit/runner guard сохраняются.

Verify повторно выполнен при подготовке плана: VERIFIED/runtimeAdmitted=false. Это чтение файлов; свежие DB ID/SQL-состояние/ресурсы ещё неизвестны. Их нельзя подставить из старого отчёта или считать уже проверенными.

## A. Первый разрешаемый запуск — только Audit

Вопрос `DEV29-Q007` ограничен диагностикой и read-only Audit; fixture writes/Run/PG29-001–007 пока в него не входят.

1. После ответа владельца сверить checkpoint/git и выполнить Verify. Получить только локальный Docker context/engine/image/container/network/volume inventory. Если engine недоступен — сообщить это; автоматический запуск Docker Desktop не входит в Q007. Владелец запускает Desktop либо отдельно разрешает это действие.
2. Проверить ownership и прежнюю конфигурацию существующего TRUST DB/volume, caps512МиБ/.5CPU/PIDs128, отсутствие API/ingress/рабочих lease и непустого permit. Если существующая DB остановлена, Q007 разрешает запуск только DB через прежний compose/env без init/migrate/bootstrap/build/pull. Новые контейнеры API/ingress не создаются; новые постоянные сети/тома/базы/роли запрещены. При недостающем volume/image/network или неизвестном состоянии — остановиться, не создавать замену автоматически.
3. До запуска DB проверить local engine, полные labels/image/volume/mount/config identities. После запуска получить полный фактический container ID; controller.dbBoundary требует ровно один существующий DB-контейнер проекта и одну internal DB network. Любое расхождение — FAIL, без изменения конфигурации ради прохождения.
4. Подготовить **отдельный именованный операторский signer** вне девяти файлов пакета, только для audit-admission.json. До использования signer проходит независимое code-review и offline negative tests. Он не вызывает Docker/SQL, не меняет старый write-profile, не генерирует runtime-admission, не выводит ключ. Ключ HMAC-SHA256 читается из существующего operator recovery credential только host-процессом; helper этот credential не получает. При отсутствии/неоднозначности credential — отказ, без ротации/создания ключей.
5. Signer принимает только закрытый набор полей audit payload: scope=`PG29-EXACT-READONLY-ADMISSION`, runId, canonical planSha256, exact packageFiles, raw SHA актуального независимого package-review, фактический полный dbContainerId, expiresUtc (не более15минут). Перед подписью он сверяет явное решение владельца Q007, принятый код signer, точные source/review/plan и отсутствие audit-admission/attempt/locks. Запись `{payload,signature}` только once в выбранный run; ключи/секреты в Git, DTO и отчёт не попадают. Никакого будущего Run-допуска эта подпись не создаёт.
6. После независимой проверки точных SHA signer/пакета и audit payload выполнить единственную команду `node work/dev29-publication-20261103/pg-check/controller.mjs Audit 1b296fa0-2cff-4dbf-bcb0-623770d7bf85`. Helper256МиБ/.5CPU/PIDs64, bounded tmpfs/read-only mounts/verify-full; только read-only repeatable-read UNIT/MAIN, archived catalog без открытия архивов.
7. Проверить output/Audit baseline: UNIT empty кроме migration ledger, exact OID/owner/marker/TLS/schema/sequence/no other sessions; MAIN state-v2 равен ожидаемому; архивы закрыты с прежними catalog identities/proofs. Успех — audit-result.json и audit-complete.json, связанные raw SHA и phase-bound operator.lock. Это только свежие условия для следующего допуска, не PASS P29-A.
8. Независимое result-review Audit, Verify/protected hashes/пустой штатный permit и возврат DB в исходное stopped-состояние, если её запустили здесь. Не удалять данные/тома/phase locks. Если controller Audit FAIL/timeout, lock остаётся; helper cleanup и отсутствие оставшегося backend доказываются перед любым новым действием. Не повторять Audit с новым UUID для обхода старой ошибки.

Запуск DB сам по себе может менять WAL/служебную статистику и потребляет локальные512МиБ; это не изменение продуктовых строк MAIN. Поэтому Q007 явно разрешает такое изменение локального состояния и read-only SQL, но не fixture writes. Контейнер helper создаётся временно, точечно очищается по доказанному полному ID, сторонние объекты не затрагиваются.

## B. Run — условия будущего отдельного допуска

Runtime-admission.json сейчас не создаётся. Для него потребуются завершённый/независимо принятый Audit, фактический signed baseline и raw auditResultSha256, неизменные code/review/plan/source, допустимый budget estimate и актуальный DB container ID. Если DB после Audit остановлена и создан новый container ID, прежний Audit нельзя механически выдать за admission нового экземпляра: потребуется отдельно reviewed transition/revalidation; никаких ручных правок signed baseline/lock.

PG29-007 включает реальную1000-operation ветку. Одного Boolean quotaEstimateAccepted недостаточно как доказательства. До подписи будущего runtime payload нужен отдельный отчёт оценки времени/CPU/RAM/места на фактическом стенде: helper60с/host90с на вызов и общая15минутная admission window. Невыполнимость оценки — BLOCKED, не повышение caps/deadline и не mock PASS. Изменение способа измерения/деление группы/новый source проходит code-review и новый exact snapshot; текущий план не разрешает эти изменения автоматически.

Только после выполнения этих условий — отдельное разрешение владельца fixture writes/Run. При таком разрешении controller уже имеет обязательные cleanup-only witnesses после failure/expiry, append-only failure-after и immutable transfer ledger; сторонние ошибки/неизвестный backend не лечатся удалением locks/flush/reset. Будущий Run-план должен включать остановку собственного DB и отдельную проверку сохранности после последней группы; сам controller DB не останавливает и полноценный эксплуатационный cleanup этим не доказан.

## Проверяемый результат и стоп-условия

| ID | Результат первого допуска | Сейчас |
|---|---|---|
| RA29-001 | Exact source/package/protected hashes перед запуском совпали, runtime-подписей заранее нет | Файловый Verify PASS; runtime NOT_RUN |
| RA29-002 | Локальные DB/volume/network/image/mount/caps и полный DB ID проверены без новых постоянных ресурсов | NOT_RUN |
| RA29-003 | Operator signer code/negative-review и Q007 связаны с exact audit-only payload, once-write | Код готов, review003 APPROVED, synthetic21/21/329/188 PASS; actual payload/подпись NOT_ISSUED |
| RA29-004 | Единственный read-only Audit дал свежий UNIT/MAIN/archives witness без fixture writes | NOT_RUN |
| RA29-005 | Output/phase ledger/source/protected evidence независимо приняты, cleanup и исходный Stop подтверждены | NOT_RUN |

Любая ошибка provenance/marker/role/TLS/schema/source/непустой UNIT/permit/неизвестная сессия/контейнер/выход за caps — остановка. Согласованный лимит повторных ошибок AGENTS сохраняется; зависимые команды идут только после успеха предшествующей. Никакого force/init/migrate/flush/drop/rename/ALTER ROLE/открытия архивов/снятия runner guard.

## DEV29-Q007

Разрешить только RA29-001–005: локальные Docker diagnostics, при необходимости запуск существующей TRUST DB в прежних ресурсах, подготовку/ревью audit-only signer и один read-only Audit с независимым результатом и Stop? Docker Desktop автоматически не запускать; fixture writes/Run/MAIN writer/APP/старый сайт/VPS/production/push не разрешаются.

**Ответ получен:** D-417, «Разрешаю read-only Audit». Повторное согласование Q007 не требуется. По-прежнему не разрешён автоматический запуск Docker Desktop, fixture writes/Run/MAIN writer. Текущий этап8 около31%, DEV-29 около35%; следующий непосредственный результат для DEV-29 — свежие read-only доказательства на доступном engine. Исходный текст вопроса выше сохранён как граница принятого разрешения.
