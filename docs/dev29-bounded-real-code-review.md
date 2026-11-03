# DEV-29: подготовка реальных INIT/C/T helpers

2026-11-03. **BOUND29-REAL-HELPER-REVIEW-002 APPROVED ограниченно как source + mock-equivalence qualification. NOT_RUNTIME_QUALIFIED.** Это не разрешение фактического INIT/SQL без оставшихся Q014 gates. Независимый рецензент `/root/dev29_publication_review` код не редактировал.

Основания: согласованный Q014/D-434; [фактический Q015 mock QA принят](dev29-bounded-qa-results.md). Подготовлены12 ignored файлов в `work/dev29-bounded-20261103/real/`. Unit-init/suite/shared gate и tests написал `/root/pg29_probe_builder`; capacity/bootstrap COW/межпакетную qualification — координатор. Общие файлы параллельно не редактировались.

| Артефакт | Raw SHA256 |
|---|---|
| unit_init.py | `f448a6b2b8dcc1c7647fecba2c50146dce9e160677a70a675422fc21454e7cb0` |
| suite-runner.py | `311d513725bbc4744a3944745dcc773baf8bdf1bb158f2296f84d6c954a6009e` |
| helper-test.py | `54e2f9bcaa4b67055ce06ca02b0c160113794cfe06c21b726d978a6c781834fa` |
| helper-contract.txt | `33aa5b0e1e8e26a774a3c61701a6a42e6fad2d864b3acd618f33715782d452c6` |
| capacity.py | `d3f9257675b59aa4c3be77ad63833622eee951cd11f91425c8be7a57357fe58e` |
| capacity-test.py | `2b3cc3e2d56e8f20815bd56f7059850915f685a321ec22d45eba9e3258e707b3` |
| bootstrap.sql | `fcd10cdbe94d22825a9c93b706d9850f3196e50aa6ac8d4cecba389b4ec143f2` |
| bootstrap.hba | `528cf35647c7df33b8366f51b1f49eaa07c6cdefc66ad179ea49bf13b437d0ed` |
| runtime.hba | `4c2aa75544a7b6ce52c4a9aa2d18836a607c8f4a148d334bef8df314778d891b` |
| bound-db-supervisor.sh | `1d7a1c08c2d952190bfa6f2e9ed2ab4819d60108f13f9d9dcd97305c5253f38c` |
| bootstrap_spec.py | `05d4f6c1f8d98ce026f8c69d09b1b5ca9c261342c8a860b3e1e588d52877d1c8` |
| bootstrap-test.py | `dbd135f0057e6302dbbb536582ce997fbb53e0366fd19f33a2428e20a1f1d5cb` |

Canonical sorted filename→raw SHA JSON manifest SHA256 `9e9a47fb36c24a5af72fb603c36e4b6eaa1ef1fa20a1f1ccf5892042a7cfa012`. Это manifest только этих12 source inputs, не будущего полного host/runtime пакета.

## Проверенное поведение кода

Shared gate до DDL проверяет closed ARG, фиксированные UNIT/role/host/readonly secret paths, source31, настоящие TLS/DB OID/новый marker/owner/system identifier и schema/migration facts. INIT before имеет null fingerprint/пустые migrations; после migrate возвращается отдельный observed baseline без подмены исходного expected. Suite сохраняет стандартный DiscoverRunner/keepdb, guarded existing-UNIT hook до CREATE/setup; nodb/создание/удаление DB запрещены. Discovery должен фактически дать139 уникальных исходных IDs; результат не переписывается.

Capacity содержит настоящие1000 production S.mutate prepare, чередование двух policies,998 немедленных completion/2 pending,COUNT1001 denial с exact V2/state/charge/reserve/phase-receipt equality, prepare/terminal replay и completion при полном count. Raw counts, default B.CAPS, outer rollback/reconnect/schema/sequence checks; no flush/DDL/bulk seed/count patch. Fixture предоставляет только service policy/lease/resource facts; native lease/crash durability/fullRegression не заявляются.

Coordinator до внешнего ревью выявил отсутствие trusted path startup для Python -I и внутреннего deadline. Builder добавил fixed paths/sibling module load до app imports, INIT90/SUITE240/C600 hard-stop API с закрытием зарегистрированных drivers и os._exit124; timeout не превращается в пойманное unittest исключение с продолжением SQL. Host timeout/independent after-witness остаются отдельными обязательными защитами.

Исследован pinned PG18.6 source: pg_control_system() не содержит internal superuser check, default function ACL разрешает PUBLIC EXECUTE; отдельный pg_monitor/superuser или дополнительный GRANT worker не добавлялся. Неожиданный реальный privilege failure должен закрыть gate, а не включить fallback. Это source-вывод, не фактическое выполнение SQL.

## Замечание ревью и исправление

BOUND29-REAL-HELPER-REVIEW-001 — CHANGES REQUIRED. **BOUND29-REAL-REV-001/P1:** required UNIT marker отсутствовал в исходном reviewed bootstrap SQL; runtime HBA не позволил бы позже установить его postgres через UNIT. Координатор подготовил отдельную COW версию bootstrap с двумя exact COMMENT MAIN/UNIT; old reviewed prefix не изменён. Supervisor отличается только pinned SQL digest, обе HBA побайтно прежние. Межпакетная qualification проверяет marker из unit_init.RUN, отсутствие extra DDL/privilege изменений, правильный hash, byte-equivalent control flow и wait bootstrap SQL до runtime.

Повторное ревью: **REV-001 закрыто**, новых замечаний нет. Повтор шести mock cases не нужен: fake psql не читает SQL; hash-only substitution не меняет проверенный shell flow. При этом COMMENT syntax/effect и реальное PostgreSQL поведение не объявлены проверенными. Они ещё должны быть фактически измерены INIT target gate до product DDL.

## Фактические проверки и точка продолжения

Bundled Python3.12.14 `-I -B`: helper13 + capacity6 + bootstrap5 = **24 offline tests PASS**, errors/failures0. Дополнительно два isolated malformed-ARG smoke дают ARG_SCHEMA до SQL; syntax checks прошли. Это модели/инъекционный IO/контракты, actualConnections/SQL/secretReads0; ни1000, ни139 реальных test methods здесь не запускались.

**Следующая задача BOUND29-REAL-HOST-001:** подготовить host controller/real container profiles, closed MAIN auditor/UNIT witnesses, two original-volume RO inspectors/preservation, package/owner/QA lineage, signed once admissions/provenance/budget/source/target guards, persistent attach/cleanup. Потом независимые full code/start/payload reviews до любого real Docker create/init/SQL. Эти части ещё не реализованы; partial helper review не заменяет их. Объём уже согласован Q014, нового owner-вопроса при неизменном профиле не требуется.

P29-A/DEV-29 открыты: DEV-29 около35%, этап8 «Разработка сайта» около31%. Старый сайт/VPS/production/push не затронуты.
