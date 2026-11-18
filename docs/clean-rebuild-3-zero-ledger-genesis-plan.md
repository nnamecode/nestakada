# REBUILD-3 — минимальный zero-row ledger genesis

Дата: 2026-11-18. ID: `RB3-LEDGER-AUTHORITY-001`. Статус: **PLAN+CODE APPROVED 0/0/0; SYNTHETIC TESTS 13/13 PASS; MATERIALIZATION NOT AUTHORIZED**.

## 1. Разрешённая граница

D-1469 фиксирует выбор владельцем варианта 1 из `RB3-LEDGER-AUTHORITY-Q001`: подготовить отдельную минимальную durable authority только для текущего rebuild, где intake остаётся default-off, writers остановлены и source snapshot доказывает `ServiceRequest count=0`.

Этот этап разрешает acceptance/design и, только после независимого одобрения плана, code-only реализацию. Он не разрешает создавать реальные ledger-файлы/копии/ключи, запускать Python/Django/Docker/БД, выполнять rebuild, cleanup, deploy, live или push.

Genesis не является production deletion ledger из `docs/clean-rebuild-requests-contract.md`: он не содержит tombstones, не поддерживает append, не разрешает ненулевой request transfer, retention/delete, restore живого intake или включение формы. Полный ledger с hash-chain и independently encrypted external backup остаётся обязательным LEGAL/launch gate до intake-on.

## 2. Минимальная форма

Один отдельный модуль `src/rebuild3_zero_ledger.py`, не внутри `rebuild3_importer`, предоставляет только две операции:

1. `create_zero_genesis(primary_root_fd, independent_root_fd)` один раз создаёт одинаковый canonical genesis в двух заранее открытых trusted roots и возвращает immutable receipt;
2. `verify_zero_genesis(primary_root_fd, independent_root_fd, expected_receipt, snapshot_id)` независимо перечитывает обе копии и возвращает существующий `VerifiedLedgerEvidence` memory-to-memory.

Нового CLI, setting/env parser, config schema, model/table, service, daemon, registry, encryption layer, retry/resume, cleanup или generic ledger API нет. В `rebuild3_importer` изменения не требуются.

Canonical UTF-8/LF JSON имеет ровно пять полей в фиксированном порядке и без пробелов:

```json
{"schema":"estakada.zero-request-ledger-genesis","version":1,"identity":"<lowercase UUIDv4>","generation":1,"row_count":0}
```

Последний byte — LF. Ledger digest — lowercase SHA-256 exact canonical bytes. Receipt содержит только `identity`, `generation=1`, `digest`, `row_count=0`; ПД, абсолютные пути и snapshot ID в durable файле/receipt отсутствуют. `snapshot_id` добавляется только к in-memory `VerifiedLedgerEvidence` после проверки обеих копий.

## 3. Файловая граница

Caller в остановленном-writer preflight проверяет два absolute pre-existing POSIX directory roots и открывает каждый через component-wise no-link walk от отдельно trusted anchor с `O_DIRECTORY|O_NOFOLLOW`. Обе операции принимают только эти два уже открытых directory fd, дублируют их на время вызова и сохраняют исходные `fstat` identities. Каждый retained root fd должен оставаться real directory, принадлежать effective UID, иметь exact mode `0700`; roots должны иметь разные `st_dev`. Fixed filename — `zero-ledger-genesis-v1.json`; file owner — effective UID, type regular, link count1, mode `0600`, size bounded exact canonical maximum. Writer inventory0 и отсутствие других процессов той же service identity, способных менять эти roots, являются обязательной внешней предпосылкой; модуль не строит lock service.

Creation использует retained directory descriptors, `O_NOFOLLOW|O_CREAT|O_EXCL`, fixed filename, полную запись, file `fsync`, затем directory `fsync`. `fstat(file_fd)` и `stat(fixed_name, dir_fd=root_fd, follow_symlinks=False)` обязаны иметь одинаковые `(st_dev, st_ino)` и неизменные exact type/uid/mode/nlink/size: проверка выполняется после записи, непосредственно перед directory `fsync` и повторно непосредственно перед признанием каждой копии успешной. Retained root `fstat` также обязан совпасть с исходной identity до каждого успеха. Сначала durable independent copy, затем primary. Existing file, одинаковый device, root/entry identity drift, link/path substitution, short write, close/fsync ambiguity или любое несовпадение дают fail-closed. Автоматического удаления и повтора нет; частичный результат остаётся не-authoritative и требует отдельного owner-approved cleanup. Следующая попытка использует новую пустую пару roots.

Verification открывает оба файла через retained directory descriptors с `O_NOFOLLOW`, проверяет metadata до и после bounded read, exact bytes/canonical parse, byte equality, independently вычисленный digest и exact match с trusted expected receipt. Непосредственно перед возвратом evidence для каждой копии повторяются root `fstat` identity и `stat(fixed_name, dir_fd=root_fd, follow_symlinks=False)`; named entry обязан всё ещё совпадать по `(st_dev, st_ino)` с held file `fstat`, а exact type/uid/mode/nlink/size не должны измениться. Никаких файлов не меняет. Copy на том же `st_dev`, root/entry identity drift, receipt с нулевым UUID/не-v4 UUID, generation не 1, rows не 0, uppercase/non-SHA digest, malformed/extra JSON field или snapshot ID вне существующего source contract отклоняются.

Разные `st_dev` — минимально проверяемая граница независимости для этого zero-data rebuild genesis. Она не заменяет independently encrypted external backup production-ledger: если при будущем runtime две подходящие файловые системы не предоставлены, rebuild остаётся заблокированным, а требование не ослабляется до двух каталогов на одном volume.

## 4. Связь со snapshot и importer

Genesis ничего не знает о PostgreSQL и сам не утверждает, что requests равны нулю. Future bounded runner обязан:

1. доказать intake default-off и writer inventory0;
2. открыть approved source RRRO snapshot и получить exact `snapshot_id`;
3. вызвать `verify_zero_genesis(..., snapshot_id)` с заранее закреплённым expected receipt;
4. передать evidence через существующий one-shot `ProvidedLedgerVerifier`;
5. существующий `SourceReader` в той же snapshot transaction независимо требует source request count0 и exact snapshot binding до target mutation.

Evidence не сериализуется в private artifact и не раскрывает paths. Safe run result может сохранить уже утверждённые identity/generation/digest/count, но не заменяет две authority-копии.

## 5. Приёмочные сценарии до кода

| ID | Сценарий | Обязательный результат |
|---|---|---|
| `RB3-ZLG-AC-001` | Два retained trusted empty root fd на разных `st_dev`; deterministic UUIDv4 factory; creation | Root identities stable; два byte-identical mode0600 named files; entry `(dev,ino)` equals held file before directory fsync/success; independent→primary order; file+directory fsync; receipt digest пересчитан из exact bytes |
| `RB3-ZLG-AC-002` | Повтор creation, existing file, same device, symlink/non-directory/wrong owner/mode | Fail before overwrite; automatic cleanup/retry0 |
| `RB3-ZLG-AC-003` | Short write/open/fsync/close, root identity drift или named-entry replacement/metadata ambiguity на любой копии | Fail closed; primary не создаётся до durable independent copy; частичный файл не объявляется authority |
| `RB3-ZLG-AC-004` | Обе exact copies + exact externally pinned receipt + valid snapshot ID | Один immutable `VerifiedLedgerEvidence(identity,1,digest,0,snapshot_id)`; durable bytes unchanged |
| `RB3-ZLG-AC-005` | Copy drift, same-device aliases, root/entry identity drift, wrong/zero/non-v4 identity, digest/receipt mismatch, malformed/noncanonical/extra/oversize bytes | Constant safe failure; evidence отсутствует; paths/content не попадают в error/repr/log |
| `RB3-ZLG-AC-006` | Попытка generation>1, row_count>0, entries/tombstones/append или reuse как production ledger | Reject; формат и API не расширяются |
| `RB3-ZLG-AC-007` | Evidence связан с snapshot A, importer получает snapshot B или source count>0 | Existing `ProvidedLedgerVerifier`/`SourceReader` fail before target mutation |
| `RB3-ZLG-AC-008` | Static dependency/scope inspection | Изменения только one authority module + focused synthetic tests/docs; importer/product/migrations/dependencies/runtime0 |

## 6. Проверка и следующий gate

Independent plan repeat review закрыл первоначальный named-entry P1 и одобрил AC001–008 с P1/P2/P3=0/0/0. Independent code repeat review затем закрыл ambiguous-close P1 и test-coverage P2 и одобрил stable candidate P1/P2/P3=0/0/0: `src/rebuild3_zero_ledger.py=E257D3322581153B6D7567D442246779577C167A5A42AE4DDFE9176763D337B3`, `test_zero_ledger_authority.py=D609E3B01E174DDA71F585960C70F71655D996C48791A138BD6640912DDB7F50`.

D-1471 выполнил ровно один разрешённый synthetic run в одноразовом read-only/no-network контейнере existing image `nestakada-local/python-runtime:3.14.10-security-20261030`, с readonly `/src` и ephemeral tmpfs `/tmp`; PostgreSQL/Django/rebuild roots не подключались. Результат: `Ran 13 tests in 0.050s`, `OK`, exit0. Контейнер `--rm`; production genesis/root/copy/receipt/snapshot evidence не создавались. Следующий отдельный gate — materialization двух trusted roots на разных `st_dev`, двух exact copies и external receipt pinning.

Даже закрытый код не снимает `RB3-RUN-B002`, пока отдельно не разрешены и не выполнены materialization двух roots/copies, external receipt pinning и snapshot-bound verification. После B001 materialization+B002 возможен только новый bounded runtime preflight; сам rebuild остаётся отдельным gate.
