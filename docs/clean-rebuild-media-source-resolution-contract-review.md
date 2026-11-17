# REBUILD-1 unmatched media source-resolution contract review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-RESOLUTION-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P0=0, P1=2, P2=0**.

## Findings

### `RB1-MSRC-P1-001` — единая DB snapshot boundary

Aggregate classification и exact descriptor должны читаться существующим ограниченным eight-table reader через TLS в одной `REPEATABLE READ READ ONLY` transaction. Snapshot остаётся открытой до завершения file verification; key/hash/size находятся только в памяти. Новые role/grants/tables не нужны.

### `RB1-MSRC-P1-002` — portable key и same-open-file evidence

Нужно явно закрыть Windows/POSIX path aliases: ASCII slash-only `img/...`, rooted/drive/UNC/device forms, backslash, colon/ADS, trailing dot/space и case-insensitive device basenames; проверять каждый компонент единственного key под canonical non-reparse root. Size/SHA должны вычисляться из одного открытого no-follow/reparse-safe file handle. Результат — point-in-time evidence этой открытой file identity, а не обещание неизменности после close.

## Acceptance result

- `RB1-MSRC-AC-001`, `004–008`: PASS;
- `AC-002`, `AC-003`: CHANGES REQUIRED по двум findings выше.

Missing contract evidence2, overreach0. Files edited0, DB/Docker/runtime/media reads0, tool errors0, cycle0. Transfer/Q002/product/live закрыты.

Следующий минимальный этап после owner continuation: только документальная remediation двух findings и repeat contract review. Новый scanner/manifest не нужен.

Риск раздувания: отдельная portable native file-identity abstraction для одного локального evidence read несоразмерна. Предлагаемый лёгкий предел remediation — existing reader/RRRO, строгая key grammar, component checks и один existing-runtime `FileStream`; если безопасный no-follow/identity contract нельзя доказать штатными средствами, остановиться до реализации, а не строить framework.
