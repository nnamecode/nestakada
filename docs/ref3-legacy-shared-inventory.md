# REF-3 — инвентаризация legacy shared data

Дата: 2026-11-05.
Среда: локальный изолированный профиль `foundation-test`, основная test-БД.
Метод: read-only агрегаты без вывода HTML, UUID, имён файлов, ключей и путей.

## Фактическое состояние

| Объект | Количество / объём |
|---|---:|
| SharedBlock | header 1, footer 1 |
| SharedRevision inline | 0 |
| SharedRevision file | 6; declared bytes 4 842 |
| SharedDraft | 0 |
| RestoreStage held | 0 |
| RestoreStage consumed | 2 |
| RestoreStage released | 2 |
| SharedReceipt | apply 24, draft 2, restore_prepare 6, restore_cancel 4 |
| SharedBasePin | 0 |
| SharedCleanupJob complete | 2 |
| SharedIdentityReservation | 96 |
| shared/draft AssetUsage | 17 |
| filesystem blobs | 6 |
| filesystem journals | 0 |
| filesystem logical bytes | 49 898 |
| filesystem allocated bytes | 69 632 |

## Вывод

Активных stages, drafts, pins, незавершённых cleanup jobs и journals нет. Поэтому можно прекратить создание новых restore stages и выполнить возобновляемую миграцию шести file revisions в inline PostgreSQL. Миграция обязана проверить каждый файл по существующему descriptor/SHA, не менять media usages/current/history, не выводить содержимое и не удалять blobs. Физические файлы и legacy metadata сохраняются до REF-Q004.
