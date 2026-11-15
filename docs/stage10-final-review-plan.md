# Этап 10 — план итогового независимого ревью текущей ветки

Дата: 2026-11-15. Статус: первое ревью `CHANGES REQUESTED` (P1/P2/P3=`0/1/1`); точечная remediation применена, повторное ревью ожидается.

## Цель и база

Проверить только net diff текущей ветки после последнего опубликованного состояния:

- base: `origin/main` / `585750fa76daece236b396f5429c84fece9fbbb8`;
- frozen artifact candidate: `63085e15131be32a3474e1d2d1e2030e9a70425d` (`63085e1 Fix review whitespace findings`);
- 34 локальных коммита;
- 58 файлов, 3739 добавлений и 157 удалений.

Коммит `63085e1` — неизменяемая граница проверяемого артефакта. Более поздние коммиты могут менять только review metadata: `README.md`, `docs/currentprocent.html`, `docs/decisions.md`, `docs/pipeline.md`, `docs/tasks.md`, `docs/stage10-final-review-plan.md` и будущий итоговый review report. Они не входят в artifact verdict; рецензент отдельно проверяет, что `git diff 63085e1..HEAD` не содержит иных путей. Любое последующее изменение кода, реестров, acceptance-контрактов или другой документации создаёт новый candidate и отменяет эту границу.

Это ревью результата другого исполнителя. Рецензент не редактирует артефакты и не утверждает их по просьбе; он выдаёт фактический verdict с P1/P2/P3.

## Точная граница

### Исполняемые и тестовые изменения

- `app/page_editor/test10_database.py`;
- `app/page_editor/test_test10_fixture.py`;
- `scripts/test10-fixture.ps1`;
- `scripts/test10-registries.ps1`.

Production runtime-код Django в diff отсутствует. Python-изменения относятся только к TEST-10 fixture/tests. PowerShell-изменения относятся к подготовке/удалению TEST-10 fixture и offline-валидации закрытых реестров.

### Данные контрактов

- `acceptance/test10a-bindings.json`;
- `acceptance/test10a-evidence-policy.json`;
- `acceptance/test10a-observers.json`;
- `acceptance/test10a-payloads.json`.

Реестры обязаны оставаться fail-closed: `registryReady=false`, 40 bindings unbound, 7 observers unbound; они не являются разрешением TEST-10 execution.

### Документация и инструкции

Остальные 49 файлов — `AGENTS.md`, `README.md` и 47 файлов `docs/`. Их проверяют на согласованность решений, статусов и границ, а не как новую функциональность.

## Обязательные направления ревью

1. **Fixture/DB safety.** Exact marker до DROP; database owner; отдельная `test10_control` schema; отсутствие БД как недеструктивное recovery; запрет удаления при collision/marker mismatch; cleanup только БД, созданной текущим failed Prepare.
2. **Filesystem/receipt safety.** Containment и reparse-point chain; отсутствие следования по ссылкам; bounded terminal transitions `database_removed` → `secrets_removed` → `removed`; повторный Teardown не удаляет evidence и не раскрывает secrets.
3. **Registry closedness.** Exact40 order/IDs, payload hashes и projections; request/UI/state-transition разделены; secret values отсутствуют; all bindings/observers остаются unbound; validator не делает Docker/network/product writes.
4. **Requirements consistency.** AC-022 direct restore, AC-015 order, exact URL reconciliation 114→115, TEST-10 source gaps, deferred backup/monitoring/DEV-26/27 и stage9 PASS не должны противоречить `decisions.md`, `tasks.md`, `pipeline.md` и acceptance-реестрам.
5. **No-bloat/release boundary.** Нет нового runtime framework, endpoint, model, migration, dependency, browser runner, proxy, scheduler или live/VPS mutation. Нет секретов, PII, дампов и оригиналов фотографий в Git.

## Доказательства, которые не нужно повторять

`docs/stage9-local-regression-results.md` уже фиксирует один свежий immutable foundation lifecycle и точные PASS: all900, dev13 42/42, dev25 73/73, system check и migrations. Ревью не повторяет Docker/foundation/regression и не подменяет TEST-08/09/10.

Допустимы только read-only проверки diff/файлов и offline validator, если рецензенту нужно подтвердить конкретное замечание. Запрещены Playwright, network, VPS/live, persistent import/publication и произвольный широкий тестовый запуск.

## Формат результата

Каждое замечание: стабильный ID `R10-###`, приоритет P1/P2/P3, файл и строка, нарушенный контракт, последствие и минимальный вариант исправления. Рецензент не правит исходный артефакт.

Verdict `APPROVED` допустим только при P1/P2/P3=`0/0/0`. При замечаниях координатор фиксирует отдельный ограниченный remediation scope; повторное ревью проверяет исправления и затронутые связи. После второй эквивалентной ошибки работа останавливается без третьей попытки.

Успешное независимое ревью закрывает локальную часть этапа 10. Оно не открывает TEST-08/09/10, production apply, VPS или публикацию автоматически.
