# REBUILD-1 media DB binding scope remediation

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-DB-BIND-SCOPE-REMEDIATION-001`.

## Закрываемые findings

- `RB1-MDB-SCOPE-P1-001`: eligible теперь включает `ordinary_version|stable_version` только для selected current/previous. Nonselected ordinary/stable, non-current shared, draft и retained образуют явную excluded-группу. Приёмка требует `eligible + excluded = AssetUsage total` и `unclassified=0`; orphan/unknown/overlap остаются fail-closed.
- `RB1-MDB-SCOPE-P2-001`: принятые filesystem counts/digest отделены от ожидаемых DB inputs и ещё не выполненной binding hypothesis. `candidate-only63` обозначено условной производной; DB/binding values не называются evidence до owner-gated probe.

## Неизменные границы

Reader role, восемь таблиц, TLS, одно соединение, `REPEATABLE READ READ ONLY`, timeouts, output cap и cleanup не расширены. Новых grants, OwnerDraft/reserve reads, exporter, manifest, temp table, model, service, dependency, product code, DB/Docker run или target mutation нет.

Статус: **candidate for independent repeat review**. Этот документ не закрывает findings самостоятельно и не разрешает DB probe.

## Follow-up remediation D-1320

`RB1-MDB-SCOPE-R2-P2-001`: consumer existence явно ограничено `current_page`, ordinary/stable revision и `shared_block` через существующие таблицы. `draft`/`retained_html` остаются count-only excluded; OwnerDraft/reserve grant0 сохраняется.
