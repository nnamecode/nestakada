# REF-3 — простой черновик и одностадийное восстановление

Дата: 2026-11-05.
Решение: D-605.
Статус: **APPROVED в ограниченной области**.

## Реализовано

- owner draft создаётся и обновляется как одна inline-запись PostgreSQL;
- публикация draft создаёт новую revision и удаляет draft/media usages одной транзакцией;
- редактор больше не зависит от legacy quota/profile и не показывает ложное сообщение о недоступности сохранения;
- страница исторической версии получила owner-only POST-форму с явным подтверждением;
- восстановление сразу создаёт новую revision без нового restore stage;
- перед restore исторический HTML повторно проходит текущий isolated normalizer, schema/policy и physical media validation;
- HTML bindings должны точно совпадать с сохранёнными `AssetUsage`;
- внутри commit повторно проверяются owner, session generation, current CAS, source block/schema и неизменность descriptor;
- существующие legacy file-draft и уже созданные restore-stage пока маршрутизируются по старому пути для безопасной совместимости.

## Проверки

- итоговый targeted Django suite: **8/8 PASS**;
- draft create/update/publish: PASS;
- restore с подтверждением и без создания stage: PASS;
- restore без подтверждения: отказ без изменений;
- запрещённый schema-compatible исторический HTML: отказ, current/revision/identity/usage/audit неизменны;
- legacy restore-stage compatibility: PASS;
- employee/anonymous write denial: PASS;
- независимое code review: **APPROVED** после закрытия P1 normalizer/media validation.

## Граница результата

Новый интерфейс не создаёт restore stages и не использует legacy quota/profile для обычного apply/draft. Однако уже существующие file-drafts и stages ещё поддерживаются старым кодом. Следующий REF-3 инкремент — read-only инвентаризация фактических legacy rows/files, безопасная миграция подтверждённых данных в inline и прекращение новых записей в старые структуры. Физическое удаление остаётся за REF-Q004.
