# PG29-PACKAGE-RESUME-001

**Возобновлено владельцем и завершено в разрешённой области 2026-11-03 по D-415.** Все9 paused SHA проверены, конфликт expected исправлен; зависимые offline gates выполнены последовательно. Code-review002 и result-review003 APPROVED, Prepare/Verify PASS. Актуальный итог — docs/dev29-postgres-package.md; ниже сохранена история паузы, не текущий статус. Docker/SQL запрещены и не запускались; следующий шаг — отдельный точный runtime-допуск.

Дата: 2026-11-03. Статус: **Приостановлено владельцу** по AGENTS после повторной эквивалентной ошибки в batch. Разрешение D-414/DEV29-Q006 на способ и подготовку пакета сохраняется; повторное согласование архитектуры не нужно.

## Что сделано

Пакет в ignored `work/dev29-publication-20261103/pg-check/`: controller/core, отдельный probe, read-only unit-witness, injectable orchestration, VM/selfcheck/filesystem/Python guard tests. Начальный checkpoint.json сохранил существующие файлы/source/config. paused-source.json содержит SHA всех девяти текущих `.py`/`.mjs`; перед возобновлением сверить каждый SHA, не пересоздавать snapshot вслепую.

Независимое PG29-PACKAGE-CODE-REVIEW-001: **CHANGES REQUIRED**:

- PG29-PKG-REV-001/P1 — Audit оставлял пустой lock, Run не мог продолжиться. Добавлены phase-bound operator ledger, audit-complete с SHA и отдельный exclusive transfer-lock. Пока не перепроверено.
- PG29-PKG-REV-002/P1 — после probe failure/timeout не было обязательного after-witness. Вынесен injectable executeFlow, обязательный cleanup witness с прежним signed binding после expiry, failure-after artifacts. Пока не перепроверено на актуальном полном пакете.
- PG29-PKG-REV-003/P1 — non-Python candidate files не входили в SHA. Дерево теперь отвергает все non-.py; подготовлены `.so/.pth/.json/.bin/.pyc` и junction negatives. Их актуальный запуск заблокирован SyntaxError зависимости.
- PG29-PKG-REV-004/P2 — неполный inspect. Добавлены helper tmpfs/log/command/exact env и DB CapDrop/CapAdd/no-new-privileges проверки. Пока не перепроверено.
- PG29-PKG-REV-005/P1 runtime — не было VM orchestration. Исполнитель добавил общую pure executeFlow и vm-check; VM PASS66, realDockerCalls=0/realSQLCalls=0. Это не полная аттестация реального controller/cleanup adapters, независимое повторное review ещё нужно.

## Ошибка и число попыток

После изменений выполнен один shell batch: Node syntax controller, selfcheck, vm-check, filesystem-check, Python tests. Selfcheck получил `SyntaxError: Identifier 'expected' has already been declared` в core.mjs. Независимый filesystem-check затем импортировал тот же core и получил ту же ошибку без промежуточного исправления. Это две эквивалентные загрузки неисправной зависимости в одном batch. Третьей попытки нет, работа остановлена.

Причина известна: `helperConfig(..., expected)` имеет также локальное `const expected` для списка mount. Необходимый точечный fix — переименовать локальный список, например expectedMounts, и его использование. Этот fix до решения владельца не внесён.

VM66 и Python3/3 PASS в том batch не закрывают ошибку общего core и не делают пакет готовым. Предыдущие33 hostchecks/3Python PASS относятся к более раннему source, не к последнему. Filesystem-fixture не создавалась: импорт упал до исполнения её тела. Docker/SQL/candidate Prepare/Audit/Run не запускались, admission не выдавался, guarded runner/корпус/продукт не менялись.

## Возобновление

1. После разрешения владельца сверить все paused-source SHA и git status. Исправить только конфликт имени в core.mjs.
2. Сначала отдельная syntax/import проверка core/controller. Если ошибка — остановить зависимые тесты в batch, не загружать неисправную зависимость второй раз. После успешного gate — selfcheck, VM, Python, затем filesystem negative fixture. Каждое зависимое действие только после предыдущего успеха.
3. Повторное независимое code/QA-review полного актуального пакета против 001–005. Не выдавать fake adapters за проверку Docker/backend. Доработать фактические пробелы до APPROVED.
4. После code-review — offline Prepare/Verify с новым UUID для проверки source/catalog/protected lineage, если они ещё не выполнялись; новые исходники и review связать точными SHA. Никакого обхода historical fingerprints/runner guard.
5. Подготовить отдельный допуск точного Audit→Run при доступном Docker, fresh baseline и подтверждённом budget. До этого runtime запрещён. Operator ledger при ошибке не удалять вручную/автоматически.

DEV-29 около35%, этап8 около31%. Старый сайт/VPS не затронуты.
