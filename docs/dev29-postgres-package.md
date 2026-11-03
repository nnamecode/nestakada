# PG29: проверочный пакет

2026-11-03, D-414/D-415. Статус: **возобновление завершено; code-review002 и result-review003 APPROVED для offline preparation/result, Prepare/Verify PASS; runtime не допущен**. Все5 прежних замечаний закрыты в текущей области. [Независимое ревью и точные SHA](dev29-postgres-package-review.md). [История паузы](dev29-postgres-package-resume.md). Способ: `dev29-postgres-proposal.md` по DEV29-Q006. Исходники/checkpoint/paused-source и подготовленный run находятся в ignored `work/dev29-publication-20261103/pg-check/`; в Git автоматически не включаются.

## Состав и команды

- controller.mjs — закрытые Prepare/Verify/Audit/Run; Prepare/Verify только filesystem, Audit/Run требуют отдельные signed admission и существующую DB. Сам контроллер DB/Docker Desktop не запускает. Защищённый runner не вызывается.
- core.mjs — чистые контрактные проверки аргументов, подписи, runtime admission, helper caps/mounts и результата.
- orchestration.mjs/vm-check.mjs — общая executeFlow с injectable adapters и66 offline VM-проверок; filesystem-check.mjs —7 owned filesystem negatives, без Docker/SQL.
- probe.py — PG29-001–007, закрытый execute(ARG), точная UNIT/role/marker/source/schema, advisory/table locks, service operations в forced outer rollback, cleanup/reconnect.
- unit-witness.py — отдельные read-only repeatable-read соединения UNIT/MAIN, schema/rows/sequence и независимый MAIN state-v2; архивы только catalog, без включения datallowconn.
- selfcheck.mjs/test_probe_guard.py — offline-проверки без Django/SQL/Docker.

Offline-команды из корня проекта:

```
node --check work/dev29-publication-20261103/pg-check/controller.mjs
node work/dev29-publication-20261103/pg-check/selfcheck.mjs
<bundled-python> -I -B work/dev29-publication-20261103/pg-check/test_probe_guard.py
```

Текущий последовательный прогон после исправления expected:9 paused SHA совпали, syntax core/controller и инертный import PASS,41 host contract checks PASS,66 orchestration VM PASS,3 Python tests PASS/0.019с,7 filesystem negatives PASS. Рецензент независимо подтвердил41/66/3 и syntax/import. Это offline evidence: actual SQLSTATE/rollback/TLS/backend cleanup и полные cgroup/container witnesses — NOT_RUN; успех этих проверок не разрешает Run.

Подготовлен run `1b296fa0-2cff-4dbf-bcb0-623770d7bf85`: source31, собственные manifests/защищённые ссылки; Prepare PREPARED и Verify VERIFIED, runtimeAdmitted=false. Точные canonical/raw SHA — в отчёте ревью. Существующие runner/guard/архивы/permit и источник продукта в этом возобновлении не изменены.

## Граница будущего запуска

Prepare создаёт новый run-каталог и read-only-mount candidate copy, отдельные source/package/protected manifests. Исторический frozen source/EV63/guard/permit не меняются. Verify сравнивает новый candidate с рабочим source и всеми ожидаемыми SHA.

Audit требует signed audit-admission.json с точными run/plan/package/review/DB ID/expiry; Run — отдельный signed runtime-admission.json с полной baseline Audit, MAIN reference и принятым budget estimate PG29-007. Эти файлы в текущей работе не выдаются. Контроллер не генерирует себе runtime-разрешение. Operator lock и append-only attempt не удаляются автоматически даже после успеха; отпускание lock требует проверки результата оператором, при потере output повтор недопустим до доказанного завершения backend и сохранности.

Runtime-план должен перед конкретным запуском связать реальные DB/container/network/mount/cgroup факты и точные SHA принятого кода. Пока это не выполнено, Audit/Run запрещены. PG29 не заменяет полный Django regression runner, многопоточность/restart/crash или APP/EDGE e2e. P29-A не завершён, DEV-29 около35%, этап8 около31%. Старый сайт/VPS не затронуты.
