# DBPRE identity-state sub-checkpoints

Дата: 2026-11-17. Contract ID: `RB1-IDENTITY-SUBCHECK-001`.

## Область

Только разделение ранее одобренной группы `IDENTITY_STATE` на три фиксированные группы: `IDENTITY`, `ROLE_STATE`, `SETTINGS`. Existing session/relations/privileges/revoke-drop checkpoints и вся cleanup-семантика сохраняются.

## Приёмочные сценарии

- `RB1-ISC-AC01`: `IDENTITY` marker стоит перед exact role name/OID proof; failure самого `ALTER ... NOLOGIN` также остаётся в этой группе.
- `RB1-ISC-AC02`: `ROLE_STATE` marker ставится только после успешного exact identity proof и `ALTER ... NOLOGIN`, перед full flags/connlimit/exact-validity proof.
- `RB1-ISC-AC03`: `SETTINGS` marker ставится только после успешного role-state proof, перед exact one-row settings proof.
- `RB1-ISC-AC04`: literal candidate list, internal exception mapping и external allowlist содержат одинаковые seven unique stages.
- `RB1-ISC-AC05`: unknown/no marker сохраняет generic `DBPRE_FAILED_CLEANUP_ROLE`; raw output наружу не выходит.
- `RB1-ISC-AC06`: proof SQL, receipt values, transaction, fallback, revoke/drop, first-failure cleanup semantics и facts path не меняются.
- `RB1-ISC-AC07`: нет нового процесса, функции, logger, file, retry или dependency; runtime0.
- `RB1-ISC-AC08`: independent review обязателен до отдельного owner gate на DBPRE.

Следующий этап — независимое read-only review кандидата.
