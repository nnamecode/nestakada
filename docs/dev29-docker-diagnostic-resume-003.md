# DEV-29: фактическое главное окно Docker Desktop

2026-11-04. **R016-DOCKER-DIAG-RESUME-003 / предложение DEV29-Q019. Не утверждено.** [Q018](dev29-docker-diagnostic-results-002.md) подтвердил actual existing main title `Containers - Docker Desktop`, но завершился STOP_UI по ошибочно узкому selector; CLI ещё ни разу не запускался.

Разрешить одну свежую ограниченную read-only попытку с тем же смыслом и границами [Q017](dev29-docker-diagnostic-resume.md), rawSHA `d84863fc7f77da4f643c551a82fd72ad81ca7b2cabfaccfdcdf2658043d8b518`, и следующими явными поправками:

- Единственный источник — уже существующее native-приложение Docker Desktop и unique окно с **exact title `Containers - Docker Desktop`**, подтверждённое свежим inventory. ID берётся из нового returned Window, не угадывается/не фиксируется по старому2033928. Settings/другие titles не выбираются. Разрешены только foreground/read нижнего левого Docker Engine status indicator. Closed literal RUNNING-only mapping из Q017 остаётся; никакой навигации/кликов/settings/запуска приложения.
- Новый UI≤60с/total≤120с с нуля, не продление завершённых Q017/Q018. Только при exact RUNNING — один всё ещё первый диагностический formatted CLI query из Q017,≤45с/combined64KiB, без quiet/label filter/inspect/Env/keys/SQL. No retry/stop-first-failure, никакого Root/Run.
- Новый report `work/dev29-bounded-20261104-resume001/diagnostic-report-003.json`, exact closed schema Q017, wx≤8KiB через штатный `exec_command require_escalated`. report001 остаётся отсутствующим, report002 неизменяем. До начала UI clock только read-only подготовка канала: source/proposal hash, отсутствие003 и writable parent через тот же разрешённый инструмент; никаких пробных записей/ACL изменений. При недоступности канала STOP до UI/CLI.

Все прочие clocks/privacy/complete flags/unique64hex validation/STOP_UI null rules/raw0/report failure no retry наследуются без ослабления. UI state недоступен/не RUNNING — STOP без CLI; report write failure — reportUnproven без fallback. После результата независимое файловое review. Даже PASS не разрешает функциональный Run/SQL или изменение кода/настроек. Source/старый сайт/VPS не трогать.

**DEV29-Q019:** разрешить прочитать уже открытое фактическое главное окно `Containers - Docker Desktop` и выполнить ровно эту одну read-only попытку с report003? Владельцу не нужно снова открывать приложение: окно уже обнаружено; требуется лишь разрешение корректного selector и свежего bounded attempt. Альтернатива — оставить паузу. До ответа UI/CLI/report003 не выполняются.
