# DEV-29: повторное ограниченное чтение после открытия главного окна

2026-11-04. **R016-DOCKER-DIAG-RESUME-002 / предложение DEV29-Q018. Не утверждено.** [Q017 завершился STOP_UI/reportUnproven](dev29-docker-diagnostic-results.md): в инвентаризации только `Settings - Docker Desktop`, требуемого main window нет; CLI не запускался, первая запись report001 получила EPERM и не повторялась.

Разрешить только одну новую diagnostic attempt **после того, как владелец сам откроет главное окно Docker Desktop** и явно подтвердит возобновление. Агент не закрывает Settings/не открывает Dashboard кликами/не запускает приложение и не меняет настройки за владельца.

Все условия [проверенного Q017](dev29-docker-diagnostic-resume.md), rawSHA `d84863fc7f77da4f643c551a82fd72ad81ca7b2cabfaccfdcdf2658043d8b518`, наследуются без ослабления: existing exact main-window/status source; только RUNNING → один fixed formatted local-npipe inventory≤45с/combined64KiB; UI≤60с/total120с; closed report/dispatched/null/unique64hex/fullness/raw0, stop-first-failure/no retry; никакого inspect/Env/keys/SQL/Prepare/полного Run/изменения исходников.

Только две конкретные поправки: новый artifact `work/dev29-bounded-20261104-resume001/diagnostic-report-002.json` вместо001; его единственная wx-запись выполняется штатным filesystem инструментом с `require_escalated` review до записи, а не неподходящим Node REPL filesystem каналом. Значения report — только разрешённые несекретные метаданные, в пределах8KiB/total120с; никакого изменения ACL и никаких private key/password reads. Report001 остаётся отсутствующим, первая неудача не переписывается. Отказ разрешений/записи или лимита → STOP/reportUnproven, без fallback/retry.

После результата — независимое файловое review. Даже успешная диагностика не разрешает функциональный Root/Run: R016 и P29-A остаются приостановленными за пределами этого чтения.

**DEV29-Q018:** после открытия главного окна разрешить одну новую read-only попытку по этим условиям с report002? Альтернатива — оставить паузу. До ответа владельца новых UI/Docker/SQL/code действий нет.
