# DBPRE role-state sub-checkpoints

Дата: 2026-11-17. Contract ID: `RB1-ROLE-STATE-SUBCHECK-001`.

## Область

Только разделение `ROLE_STATE` на `ROLE_FLAGS` и `VALID_UNTIL`. Значения OID/validity не выводятся. Existing IDENTITY/SETTINGS/SESSIONS/RELATIONS/PRIVILEGES/REVOKE_DROP, transaction, fallback и cleanup semantics сохраняются.

## Приёмочные сценарии

- `RB1-RSS-AC01`: `ROLE_FLAGS` marker идёт после успешного exact IDENTITY proof и `ALTER NOLOGIN`.
- `RB1-RSS-AC02`: ROLE_FLAGS proof содержит exact OID/name, все семь safe flags и `connlimit=1`, но не validity equality.
- `RB1-RSS-AC03`: `VALID_UNTIL` marker идёт после ROLE_FLAGS proof и перед единственным exact epoch-microseconds equality.
- `RB1-RSS-AC04`: `SETTINGS` и последующие markers остаются после exact validity proof.
- `RB1-RSS-AC05`: marker/candidate/mapping/external allowlist sets совпадают; old ROLE_STATE refs0; unknown→generic cleanup role code.
- `RB1-RSS-AC06`: receipt values/expressions, proof meaning, BEGIN/COMMIT, fallback, revoke/drop, guards и facts path не меняются.
- `RB1-RSS-AC07`: raw values/output скрыты; нет нового process/function/logger/file/retry/dependency; runtime0.
- `RB1-RSS-AC08`: independent review обязателен до отдельного owner gate на DBPRE.

Следующий этап — независимое read-only review.
