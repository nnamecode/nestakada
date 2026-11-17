# DBPRE create-receipt static analysis

Дата: 2026-11-17. Evidence ID: `RB1-RECEIPT-STATIC-001`.

После runtime code `DBPRE_FAILED_CLEANUP_ROLE_IDENTITY_STATE` проверена только статическая передача create receipt; Docker/DB/runtime0.

Результат:

- PowerShell parser errors0;
- current culture `ru-RU` не меняет decimal interpolation;
- sample max `UInt32` OID и large `Int64` epoch-microseconds проходят exact `digits|digits` regex, cast и round-trip без изменения;
- generated cleanup literals остаются plain decimal;
- `$roleOid` и `$roleValidUntilMicros` после null initialization присваиваются ровно один раз из принятой receipt line;
- create и cleanup используют одно и то же `floor(extract(epoch FROM rolvaliduntil)*1000000)::bigint` expression.

Вывод: статического доказательства ошибки transport/format нет; менять receipt representation было бы догадочной правкой. `IDENTITY_STATE` остаётся группой из exact name/OID, `ALTER NOLOGIN`, post-state+validity и exact settings.

Следующий минимальный proposal: не менять proof и не добавлять process/log/retry, а разделить только эту группу на три literal checkpoints: `IDENTITY`, `ROLE_STATE`, `SETTINGS` (ALTER остаётся между identity и role-state). После candidate нужен independent review; DBPRE требует отдельного последующего owner gate.
