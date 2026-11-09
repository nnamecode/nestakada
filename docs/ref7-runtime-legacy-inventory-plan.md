# REF-07C: read-only инвентаризация оставшегося legacy lifecycle

Дата: 2026-11-09
Основание: D-674 и продолжение владельца D-675.

## Цель

Определить следующий действительно безопасный кандидат удаления после REF-07A/B. Инвентаризация не меняет код, миграции, БД, media, backup или окружение.

## Границы

- проверить чтения и новые записи `OperationReceipt`, `IdentityReservation`, `RestoreStage`, `VersionBasePin`;
- отдельно проверить legacy lifecycle `shared_content`: reservations, stages, pins, receipts, cleanup, budget и file-backed storage;
- получить только агрегатные counts/status/storage-kind без HTML, payload, имён, cookies или секретов;
- сопоставить runtime refs с уже переключёнными простыми командами REF-05A–G;
- классифицировать каждый объект: оставить, сначала переключить runtime, либо кандидат отдельного удаления;
- `AuthResourceState` не удалять: throttle использует модель; одна устаревшая строка `sessions` сама по себе не оправдывает миграцию.

## Проверяемый результат

- `R7C-I001`: точный список active imports/queries/writes для page lifecycle;
- `R7C-I002`: точный список active imports/queries/writes для shared lifecycle;
- `R7C-I003`: агрегатные counts и terminal/current/storage-kind распределения;
- `R7C-I004`: доказано, создаются ли новые legacy rows простыми командами;
- `R7C-I005`: file-backed shared rows и физические blobs не удаляются и не читаются в отчёт;
- `R7C-I006`: security runtime — sessions, CSRF, roles, throttle, audit и scanner — вне удаления;
- `R7C-I007`: сформирован один небольшой кандидат либо честно зафиксировано отсутствие безопасного удаления;
- `R7C-I008`: foundation после чтения остановлен, named volumes и backup сохранены.

Любое удаление файлов, строк, таблиц, полей, URL или тестов требует нового отдельного плана и явного решения владельца.
