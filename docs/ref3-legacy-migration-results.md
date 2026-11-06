# REF-3 — результат миграции legacy shared data

Дата: 2026-11-05.
Среда: изолированный локальный профиль `foundation-test`; production, VPS и старый сайт не затрагивались.
Решение: D-606.
Ревью: повторное независимое code review — `APPROVED`.

## Что изменено

- новый `restore/prepare` прекращён ранним `410 SHARED_LEGACY_RESTORE_DISABLED` до чтения request body;
- добавлена management-команда `migrate_shared_inline`: по умолчанию dry-run, изменение только с `--apply`;
- каждая legacy file row проверяется по descriptor, размеру и SHA вне транзакции;
- непосредственно перед UPDATE под глобальным content lock повторно проверяются held stages, pins и pending cleanup;
- file→inline UPDATE и `SHARED_INLINE_MIGRATE_ROW` audit выполняются одной транзакцией;
- операция возобновляема построчно, повторный `--apply` является no-op;
- команда не выводит HTML, UUID, file key или путь и не вызывает unlink/delete.

## Проверки

- синтетические migration tests: 3/3 PASS;
- полный затронутый HTTP-модуль вместе с migration tests: 22/22 PASS;
- проверены late blocker без UPDATE/audit, audit failure rollback, dry-run, apply, repeat/no-op, output redaction;
- проверена сохранность current, AssetUsage, SharedReceipt и физического blob;
- устаревший тест quota=10 000 заменён новым контрактом утверждённой архитектуры: inline Apply не зависит от legacy quota/admission и не очищает историю;
- фактический dry-run: verified 6, migrated 0, remaining file rows 6, deleted blobs 0;
- фактический apply: verified 6, migrated 6, remaining file rows 0, deleted blobs 0;
- повторный apply: verified 0, migrated 0, remaining file rows 0, deleted blobs 0;
- локальный `/manage/login/` smoke: HTTP 200.

## Постусловия основной локальной test-БД

| Инвариант | Результат |
|---|---:|
| SharedRevision inline / file | 6 / 0 |
| Current SharedBlock | 2 |
| Payload hashes | все валидны |
| SharedDraft | 0 |
| Shared AssetUsage / draft usage | 17, без изменения |
| SharedReceipt | apply 24, draft 2, restore_prepare 6, restore_cancel 4 |
| RestoreStage | consumed 2, released 2, held 0 |
| SharedIdentityReservation | 96, без изменения |
| Migration audit events | 6 |
| Blob / journal files | 6 / 0 |
| Blob deletion | 0 |

Шесть blob-файлов теперь считаются retained legacy orphans только в смысле отсутствия активных file descriptors. Это ожидаемое безопасное состояние: их физическое удаление, а также удаление старого кода, таблиц и метаданных запрещено до отдельного REF-Q004.

## Точка продолжения

REF-3 функционально завершён. Текущий общий этап — REF-05; следующий согласованный этап — REF-4, упрощение версий и восстановления страниц. REF-Q004 остаётся закрыт.
