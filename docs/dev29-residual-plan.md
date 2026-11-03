# DEV-29: следующий ограниченный пакет P29-A

2026-11-03. **Предложение REG29-PLAN-001, ожидает независимого ревью и DEV29-Q012.** Основания D-426, A29-007/P29-A05, ранее согласованный способ outer rollback. Завершённые PG29-001/003/004/005/006 не повторяются. Старый сайт/VPS не трогать.

## Проверенная точка продолжения

Статический AST-инвентарь текущего source31 обнаружил139 test-методов в7 файлах/11 классах:131 прежний и8 publication (4 wire+4 DB). Инвентаризатор не импортировал Django/продукт, не выполнял тесты/Docker/SQL. Отчёт — ignored work/dev29-publication-20261103/pg-check/residual-inventory.json; исходник residual-inventory.py. Это карта исходников, не новый PASS139. Четыре wire-теста имеют прежний принятый результат; service evidence пяти PG-групп не присваивает PASS исходным131/DB test-методам.

Остаток делится по способу доказательства:

| Область | Что можно доказать сейчас | Что остаётся отдельно |
|---|---|---|
| Disabled/role/epoch, signed UNIT admission | Конечные реальные service/view calls в rollback | Native deployment/cgroup/worker exclusion/HTTP TLS e2e |
| Charge/reserve/replay | Модульные отказные ветви с явно обозначенной accounting/count injection | Настоящие1000 записей и отказ1001, физическая ёмкость |
| Fence/activate/lease revision | Реальные recovery services на synthetic policy/lease в UNIT | Многопроцессность, restart/crash durability |
| Прежние131 тестов | Точная карта и последующие отдельно выбранные безопасные probes | Полный штатный runner/migration/transport suite |

Защита tools/local_trust.mjs при capacity-attempt.json выдаёт TRUST_CAPACITY_CORPUS_PRESERVED. Не удалять/переименовывать/подменять guard, попытку, архивы, env или runner. AdmissionPolicyMigrationTests прямо требует guarded UNIT runner и использует MigrationExecutor: этот тест здесь не запускать. HTTPSWorkerTests не доказывается одним rollback-соединением. Новый DB/кластер/том/роль и альтернативный test-runner в этот пакет не входят.

## Конкретный предлагаемый прогон

Новый immutable namespace `work/dev29-publication-20261103/pg-check/residual/`, run `45d7428f-a1f0-47e8-914e-66fbc9c041b8`, закрытый scope `REG29-BOUNDED-ROLLBACK-ADMISSION`. Никаких пользовательских SQL/test selectors/списков групп. Четыре сценария, каждый отдельно с HIDDEN и LIVE_NO_SET: **ровно8 фиксированных cases**, каждый в отдельном helper/outer atomic/forced rollback/reconnect и независимом after-witness. Так credential/epoch/fence одного case не переносятся в следующий.

| ID сценария (два cases: -HIDDEN / -LIVE) | Предметные assertions | Основания в source |
|---|---|---|
| RG29-001 | Отсутствующий/поддельный synthetic permit, wrong HMAC/source/caps/config/runtime/extra fields; environment alone и disabled profile не дают write. Валидный route_publication payload, отказ до предметного SQL/ensure_connection для admission negatives. | BoundedAdmissionTests.test_rp002_signed_hmac_source_caps_config_runtime_and_closed_fail_before_sql; test_rp002_env_alone_and_wrong_cgroup_do_not_authorize |
| RG29-002 | Реальная ограниченная synthetic activation/start; reader endpoint через RequestFactory (401), неверный writer epoch и revoked credential не создают Operation и не меняют state. Корректный writer создаёт одну разрешённую publication operation; exact replay без нового изменения. | test_rp005_active_binding_wrong_epoch_and_reader_role_cannot_write; test_rp005_new_uuid_without_trial_whitelist_and_exact_replay; первая часть прежнего PG29-007 |
| RG29-003 | Принятая publication operation сохраняет completion reserve; исчерпание свободного logical+reserved budget не расходует резерв/не меняет state при отказе нового prepare. Existing unknown/final/replay выполняются. Отдельная явно помеченная count injection1000 проверяет отказ нового prepare при возможности completion/replay существующего. | test_rp010_combined_budget_preserves_existing_completion_and_replays; test_rp005_full_count_allows_existing_replay_and_completion_but_no_prepare |
| RG29-004 | Synthetic signed fence/reconciliation/activate реальными recovery services; exact activate replay не двигает generation, old credential со свежим epoch отозван, новый credential создаёт publication operation. Lease/runtime revision смоделированы в helper, native process exclusion не заявляется. | test_rp007_real_v2_recovery_activation_and_old_secret_with_new_epoch; test_rp006_lease_restart_no_new_policy_and_latest_revision_authoritative |

Это новые отдельно именованные service probes, не вызов test.run/__call__/_pre_setup/_post_teardown. JournalFixture/BoundedFixture разрешены только как проверенные builders setUp/start/doCleanups; конкретные assertions и SQL guard проходят code-review. Bound resource facts, keys/pin/permit/exclusion proofs в fixture синтетические, только tmpfs. Working permit/credentials/mounts не меняются. Real snapshot/state fingerprints сравниваются, результат содержит injection/native limitations как обязательные поля.

RG29-003 **не является PG29-007 capacity PASS**: Operation.count injection и accounting injection отмечаются в результате; real1000CapacityProved=false. Не менять B.CAPS, не понижать квоту ради успеха, не присваивать quotaEstimateAccepted=true. Исходный1000-loop не вызывается и остаётся NOT_RUN. A29-007 после этого пакета может получить только частичное свежее service coverage; весь P29-A остаётся открыт.

## Изоляция, бюджет и последовательность

Продуктовый source31/модели/миграции/compose/runner и прежние пакеты/receipts/locks не менять. Новый candidate byte-exact source31, marker/schema/UNIT OID52766/owner/migrator/TLS/empty7journal tables/migrations3/sequence4true из принятого baseline. MAIN только read-only, архивы16387/32563 закрыты; их content не открывать. При nonempty/drift/session/permit/чужом ресурсе STOP без repair/очистки/kill чужих sessions.

Жёсткий верхний предел на case:2 Operation,2 AdmissionPolicy,2 RecoveryReceipt; восемь cases≤16 успешных prepare, без1000-loop/16-revision loop. Фактические assertions/лимиты счётчиков фиксируются до кода. Если реализация не укладывается — исправить план/review до исполнения, не ослаблять guard. Максимум один helper одновременно с DB; caps DB512MiB/.5CPU/PIDs128 и helper256MiB/.5CPU/PIDs64 неизменны. Helper60с/host90с, output/log≤1MiB; общий allocated DB+accepted host roots+16MiB reserve<2GiB. Исторические пики не присваивать будущим cases.

Последовательность после ответа Q012:

1. Сохранить checkpoint/исходные SHA; новый closed code/controller/probe/tests/issuers, независимое code/QA review. Один исполнитель (координатор), адресные одиночные patches; зависимые gates только после успеха предыдущего. Actual injected-IO tests wrong DB/role/OID/marker/source/session/permit/baseline/scope/group/signature/drift/expiry/timeout/partial output/cleanup/once locks; offline без реальных keys/Docker/SQL.
2. Prepare/Verify; fresh RO volume PG18 initialized/clean shutdown и budget; exact-name+label zero inventory/retained volume/pinned images; signed VerifyStart с повторными source/resource checks. Независимое actual start review; только прежний DB-only restore без init/migrate/API/pull/build.
3. Fresh read-only MAIN/UNIT/archive baseline сравнить с принятым continuation; Authorize связывает source/package/ancestry/owner/code-review/baseline/DB/network/budget/eight-case list/expiry≤15мин. Отдельное независимое actual payload review, closed Payload issuer, поздний ключ/recheck/wx.
4. Один последовательный Run8. Перед каждым case previous PASS+after-witness и remaining≥200с. После любого FAIL/timeout/expiry/неизвестного output — обязательный after-witness/own cleanup, STOP без retry/автопродления. Невместившиеся cases остаются NOT_RUN/BLOCKED, лимиты не повышать. Отдельного нового owner-вопроса между успешными cases не требуется.
5. Actual disk/peaks/OOM, Stop exact own IDs/empty endpoints, RO After PG18 clean shutdown/budget. Независимое final result review,0containers/0networks/helpers/volume retained/permit{}, source/config/guard/прежняя ancestry неизменны. Public inputs архивировать до изменения bound docs; ограничения injections/service-only сохранять явно.

## Приёмка и дальнейший остаток

REG29-AC01: ровно8 закрытых cases и preservation исходников/истории; REG29-AC02: fresh exact start/baseline/budget/admission; REG29-AC03: отдельный proof каждого service case/injection labels; REG29-AC04: rollback/reconnect/MAIN/UNIT/archive/sequence после каждого; REG29-AC05: caps/TTL/budget/Stop и independent result-review. До исполнения NOT_RUN.

Даже успешный пакет не закрывает полный131/139 runner, additive migration regression, native admission/exclusion, HTTP transport/restart/crash/concurrency и настоящие1000/1001. Для них следующим шагом нужен отдельный конкретный вариант, совместимый с сохранением корпуса и запретом обхода runner; новые ресурсы/изменение guard не получать молча. Известный конфликт отдельно вынести владельцу, а не выполнять текущий PG29-007 или старый Run.

**DEV29-Q012:** разрешить подготовку кода и один ограниченный прогон этих8 service cases в UNIT с rollback, независимыми code/start/payload/result reviews, прежними ресурсами и остановкой стенда? Это добавляет случаи, отсутствующие в точном Q009/Q011 допуске, включая synthetic bounded admission/recovery и явные unit injections. Настоящий1000-loop/изменение runner/новый кластер/MAIN/APP/старый сайт/VPS/production/push не разрешаются. Предложение не является утверждённым новым решением. DEV-29 около35%, этап8 около31%.
