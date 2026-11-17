# REBUILD-1 unmatched media source-resolution contract

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-SOURCE-RESOLUTION-001`.

Статус: **HOST-BOUNDARY AMENDMENT CANDIDATE D-1354; runtime/read не разрешены**.

## Цель и граница

Разрешить источник ровно одного принятого `unmatchedDb` descriptor: один READY/non-legacy/main AssetFile с `eligibleUsages=2` и `excludedUsages=1`. Descriptor исключать нельзя, но это не разрешает автоматически расширять exact301.

Контракт не решает duplicate pair, не создаёт exporter/manifest/scanner/registry и не меняет source DB, allowlist, target или media. Transfer/Q002/product/live закрыты.

## Authority и единственный путь разрешения

Переиспользуются существующие source DB `AssetFile.key`, `sha256`, `byte_size`, принятые aggregate reconciliation facts и существующий legacy media root.

DB boundary не расширяется: existing eight-table reader, existing literal grants, TLS и одна `REPEATABLE READ READ ONLY` transaction. Aggregate classification и ровно одна exact descriptor row читаются в этой transaction; snapshot остаётся открытой до окончания file verification. Key/SHA/bytes живут только в process memory и не попадают в output, file или log. Новые role/grants/tables/connection отсутствуют.

Разрешение выполняется только по exact DB key:

1. в одной snapshot агрегатно доказать, что unmatched descriptor ровно один, READY/non-legacy/main и имеет две eligible usages, затем прочитать только его exact key/SHA/bytes в память;
2. потребовать ASCII slash-only key `img/<segment>(/<segment>)*`: segment non-empty, не `.`/`..`, без control/non-ASCII, `\\`, `:`, trailing dot/space; отклонить rooted/drive/UNC/device forms и case-insensitive Windows device basename (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`) даже с extension;
3. использовать заранее утверждённый absolute canonical legacy media root; покомпонентно проверить единственный key, lexical+resolved containment и отсутствие reparse/symlink/junction/special components;
4. до DB/media read доказать trusted quiescent foundation boundary: project containers0, known project writer processes/jobs0 и approved canonical legacy root unchanged; открыть final regular file ровно один раз через standard `File.OpenHandle` с `FileAccess.Read` и `FileShare.Read`, удерживать handle до конца и вычислить size/SHA-256 из него без повторного открытия по path;
5. потребовать exact size/SHA equality DB descriptor и post-read проверить ту же открытую file identity/type; затем закрыть handle и DB snapshot;
6. после hash повторить component/reparse/type/containment checks и убедиться, что opened handle length не изменился; любая потеря quiescence или drift fail-closed. Native compatibility layer не добавляется.

Evidence доказывает только состояние одного открытого handle во время bounded read внутри trusted/quiescent local boundary. Оно не обещает неизменность после close и не заявляет защиту от привилегированного внешнего процесса, способного менять tree между checks. Эта граница допустима только для REBUILD-1 local evidence; migration freeze продолжает подчиняться более строгому coherent-transfer contract. Общей portable/native abstraction этот контракт не создаёт.

Исторический `docs/media-inventory.csv` может использоваться только как cross-check после успешной проверки exact key. Он не является authority и не даёт fallback path. Full-tree/hash/name/URL search, basename matching, nearest-file guessing и network fetch запрещены.

## Bounded result

Успех публикует только один aggregate envelope:

- `contract`, `status=RESOLVED`, `source=foundation-dev`, `elapsedMs`;
- `unmatchedDescriptors=1`, `resolvedFiles=1`, `eligibleUsages=2`, `excludedUsages=1`;
- `inventoryMatches=0|1` как необязательный исторический cross-check;
- `containmentErrors=0`, `typeErrors=0`, `sizeMismatches=0`, `shaMismatches=0`.

Path/key/SHA/bytes/UUID/asset/consumer/slot/source URL/row/SQL/raw error не выводятся и не записываются в Git. Любая ошибка возвращает constant phase code и facts0; расширенный диагностический ladder не создаётся. Один owner-authorized run, автоматический retry0.

## Decision rule

`RESOLVED` означает только доказательство доступного source file для обязательного asset. Оно не изменяет exact301. Следующий отдельный owner decision может разрешить reviewed additive amendment ровно `301 + 1` с пересчитанными exact total bytes/max/digests и conflict check против existing301.

Если файл отсутствует, выходит за root, имеет неверный тип либо size/SHA mismatch, результат fail-closed. Контракт не ищет замену и не исключает две eligible usages; дальнейший выбор источника требует отдельного решения владельца.

Duplicate matched pair остаётся отдельным вопросом target schema: physical bytes могут быть copied once, но distinct asset identities/usages не объединяются этим контрактом.

## Acceptance

- `RB1-MSRC-AC-001`: scope ровно один unmatched READY/non-legacy/main descriptor с usages2+1.
- `RB1-MSRC-AC-002`: aggregate+exact descriptor читаются existing reader/TLS/grants в одной RRRO snapshot, открытой до конца file verification; alternate search/network0.
- `RB1-MSRC-AC-003`: exact portable key grammar, trusted-quiescent precondition, component lexical+resolved containment/no-link, one read-only non-write/delete-share handle и pre/post checks обязательны; boundary drift fails before result.
- `RB1-MSRC-AC-004`: byte size и SHA из одного открытого handle дают exact DB equality; mismatch fail-closed.
- `RB1-MSRC-AC-005`: output только bounded aggregates/constants; private/per-row values0.
- `RB1-MSRC-AC-006`: success не расширяет exact301 и не разрешает transfer; additive301+1 требует отдельного owner decision/review.
- `RB1-MSRC-AC-007`: failure не исключает eligible usages и не включает guessing/fallback/retry.
- `RB1-MSRC-AC-008`: no-bloat — new scanner/exporter/manifest/model/service/logger/dependency/temp table0; duplicate semantics unchanged.

Следующий gate: independent contract review. Implementation/runtime требуют последующего reviewed candidate и нового owner continuation.
