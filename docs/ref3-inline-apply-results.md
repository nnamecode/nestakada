# REF-3 — первый инкремент inline Header/Footer

Дата: 2026-11-05.
Решение: D-604.
Статус: **APPROVED в ограниченной области**.

## Реализовано

- `commit_normalized_current` сохраняет уже проверенный server-side normalizer HTML в PostgreSQL одной транзакцией;
- owner, актуальная generation, действующая Django editor-session, current CAS, media usages и audit проверяются до commit;
- обычный HTTP `apply` для current-source переключён на простой путь без reservation books, operation receipts, quota profile и filesystem journal;
- public renderer читает новый inline current;
- `restore_current` создаёт новую inline revision и не переписывает историю;
- migration `0006_simple_revision_source` заменяет legacy source-to-identity FK на обычный same-block FK и обратима;
- временная `SharedIdentityReservation` для новых revision сохраняет совместимость с ещё не заменёнными legacy draft/restore receipt FK.

## Проверки

- DACL directory probe: PASS;
- DACL file probe: PASS;
- migration apply: PASS;
- migration reverse `0006 → 0005`: PASS;
- migration forward `0005 → 0006`: PASS;
- итоговый targeted Django suite: **7/7 PASS**;
- mixed path `simple apply → legacy draft` и `simple apply ×2 → legacy restore prepare/apply`: PASS;
- независимое code review: **APPROVED**, первоначальный P1 закрыт, новых блокеров нет.

## Граница результата

REF-3 целиком ещё не завершён. Owner draft и UI-восстановление пока используют старую реализацию; она сохранена и проверена на совместимость. Следующий инкремент должен заменить их небольшими транзакционными командами. Старые таблицы, filesystem storage, receipts, reservation books, quota и тесты не удаляются до REF-Q004.
