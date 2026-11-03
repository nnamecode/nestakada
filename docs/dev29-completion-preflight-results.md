# DEV-29: Q013 — результат первого code/QA gate

2026-11-03. **COMP29-PRECODE-001: offline preflight принят; допуск PostgreSQL NOT_PROVEN, фазы C/T NOT_RUN.** Q013 согласован владельцем (D-431); повторного ответа на Q013 не требуется. Root run `c5a2f73f-401e-4945-bb0a-88d4d17df43c` ещё не исполнялся. Это проверка предусмотренного планом условия, не запуск/повтор C/T.

## Что подготовлено и проверено

В отдельном ignored `work/dev29-publication-20261103/pg-check/complete/` подготовлены `preflight.mjs` и `preflight-test.mjs`: exact HBA bytes, closed resource samples и полный набор принятых roots как параметр, пороги/headroom, bounded progress-frame chain и безусловный запрет runtime при отсутствии физического доказательства. IO/runtime adapters отсутствуют; образец списка roots в тесте синтетический, не новый accepted inventory. HBA — константа в коде, не активированная конфигурация сервера.

Координатор и независимый рецензент: **4/4 offline tests PASS**. [COMP29-PREFLIGHT-REVIEW-001 APPROVED](dev29-completion-preflight-review.md) только для этого ограниченного слоя. Реальные collectors/ACK/timeout/kill/pg_hba_file_rules/negative TLS matrix/Django discovery не выполнялись. Четыре теста не подменяют full139 или SQL acceptance.

Сохранённый residual controller `Verify` → VERIFIED, runtimeAdmitted=false: старый source/package/ancestry не менялись. Новые файлы подтверждены `git check-ignore`. `git diff --check` с прежним исключением blank-at-eof прошёл; Git сообщил только существующую нормализацию LF→CRLF. Продуктовые source/runner, старые пакеты и evidence не редактировались. Новых Docker/SQL/секретных операций не было; прежний остановленный стенд не запускался, fresh runtime inventory/чтение тома здесь не заявляются.

## Почему SQL не допущен

План требует до C доказать физические границы: ≤32MiB на service step, ≤256MiB pending DB/WAL/buffer/preallocation, ≤64MiB rollback/cleanup. Для T требуется также ≤128MiB между измерениями за5с без изменения исходных139 тестов. Только сумма464MiB<512MiB обосновывает выбранный запас между abort1,5GiB и limit2GiB.

Ограниченный source-анализ исполнителя `/root/pg29_probe_builder` не дал конечной проверяемой derivation этих величин:

- Pinned PostgreSQL18.6 tar `work/foundation-security-20261030/pg-context/postgresql-18.6.tar.bz2`, SHA256 `555610c24d53e4316da5b7d3fc25c279d96856d5e0e23ee308c328c5fa881d9f`, проверен readonly без extraction/записи. Внутри `doc/src/sgml/config.sgml:3795–3799` max_wal_size описан как soft limit с возможным превышением; `src/backend/access/transam/xlog.c:2175–2193` рассчитывает checkpoint trigger при предпосылках, а не задаёт обязательный потолок pending growth.
- `environment/trust/compose.yaml:55` закрепляет shared_buffers64MB/max_wal_size128MB/min_wal_size32MB/full_page_writes=on; named volume в строке63 не задаёт filesystem quota. Эти параметры сами по себе не доказывают256MiB pending bound. Они не изменялись.
- `trust/journal/services.py:125–141` проверяет логические charge/reserve caps. Writes в строках144–174 затрагивают Operation/RoutePolicy/Head и связанные физические структуры. Логический cap не выдан за bound WAL/индексов/TOAST/cleanup; отдельный worst-case расчёт отсутствует.
- Статический AST учёт139 методов подтверждён исполнителем, но discovery/tests не запускались. В `trust/journal/test_admission_policy.py:79/102/111` есть настоящие migration fixtures, в `trust/journal/tests.py:95` — потоки. Ограничение128MiB/5с для полного исходного набора пока не выведено. Исторический PASS/замер времени этого не доказывает.

**Вывод: NOT_PROVEN, не утверждение математической невозможности.** Не хватает проверенной верхней оценки физических write sets/WAL/FPI/TOAST/index/предвыделения/cleanup для фиксированных workload и server facts. До устранения этой неопределённости callback/receipt/owner approval не превращаются в разрешение SQL. `runtimeGate(C/T)` всегда выдаёт `COMP29_PHYSICAL_BOUND_NOT_PROVEN`; phase admission/once lock/attempt не создавались и не потреблялись.

## Точка продолжения

COMP29-BOUND-001: сначала подготовить независимо проверяемую worst-case derivation физических границ из закреплённых исходников/фиксированных нагрузок и перечня необходимых readonly server facts. Если в существующем профиле такая граница не обосновывается, подготовить конкретную корректировку изоляции/лимитов для отдельного архитектурного решения до реализации; не ослаблять Q013 в коде. Новая БД/роль/том/квота сейчас не создаются. Остальные обязательные adapters/code/start/payload/result gates остаются невыполненными.

Q012 Run8 PASS и прежние5 принятых групп сохраняются, не повторялись. P29-A и DEV-29 не завершены: DEV-29 около35%, текущий этап8 «Разработка сайта» около31%. После P29-A — отдельные P29-B/C/D/E; общий этап9 после этапа8. Старый сайт/VPS/production/push не затронуты.
