# REBUILD-3 — минимальный zero-row ledger genesis

Дата: 2026-11-18; S3 amendment 2026-11-22. ID: `RB3-LEDGER-AUTHORITY-001`. Статус: **S3 CORE + ADAPTER SOURCE + OPERATIONAL PLAN APPROVED; CORE EXACT23 AND ADAPTER EXACT12 ACCEPTED_PASS; REAL MATERIALIZATION NOT AUTHORIZED**.

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

## 7. D-1848 amendment: one POSIX primary + encrypted S3 authority

### 7.1. Что заменяется и что сохраняется

D-1848 заменяет только future materialization topology из разделов 3 и 6: вместо второй POSIX-копии на другом `st_dev` используется exact-version object в выбранном Selectel S3, зашифрованный до сети. Существующий canonical plaintext, `ZeroLedgerReceipt(identity, generation=1, plaintext_digest, row_count=0)`, source snapshot binding, request-count0 proof и fail-closed importer boundary сохраняются.

Текущий `create_zero_genesis(primary_root_fd, independent_root_fd)` / `verify_zero_genesis(...)` и их PASS13 остаются честным historical evidence старой topology, но не объявляются compatible с S3. До reviewed code amendment они не используются для materialization. S3 не монтируется через FUSE/rclone и не получает поддельный `st_dev`, directory fd, POSIX mode или `fsync` claim.

### 7.2. Закрытая authority boundary

Будущий code amendment принимает один уже открытый trusted POSIX primary root fd и узкий external-authority port: один read-only versioning capability proof до plaintext и ровно две data operations:

1. `GetBucketVersioning` exact bucket должен вернуть literal `Enabled`;
2. create-only publish encrypted canonical plaintext и вернуть закрытый immutable receipt exact object version вместе с read-back proof;
3. read exact pinned version, client-side decrypt в bounded memory и вернуть plaintext только после transport/decryption validation.

Это не generic object store, filesystem adapter, backup platform или произвольный key/value API. Bucket, endpoint, region, prefix, credentials, encryption recipient и limits принадлежат будущему reviewed runner configuration, не Django settings/model/DB и не `ZeroLedgerReceipt`. Product/importer modules не получают S3 client, network permission, bucket/key/secret или ciphertext.

Combined receipt имеет закрытую canonical schema из §7.4 и связывает canonical plaintext receipt, reviewed nonsecret authority-config digest, derived fixed object key, opaque exact object version ID и ciphertext count+SHA-256. Bucket/account/endpoint присутствуют только внутри separately pinned nonsecret config и связываются через его digest; secret values отсутствуют. Object key вычисляется только как `<fixed-prefix><lowercase-identity>/<plaintext-sha256>.age`; arbitrary caller key запрещён. `ETag` не является digest authority.

### 7.3. Creation order и атомарность

Future creation выполняет ровно этот порядок:

1. проверить retained primary root fd: directory, effective owner, mode0700, stable identity;
2. проверить canonical authority config и выполнить read-only `GetBucketVersioning` exact bucket; продолжать только при literal `Enabled`;
3. создать UUID, canonical plaintext+receipt только в memory;
4. client-side encrypt plaintext до первого network byte; plaintext, key и recipient не попадают в object metadata, key name, log или exception;
5. выполнить ровно один provider-supported conditional `PutObject` с `If-None-Match: *` в exact key; HEAD-before-PUT, ordinary versioned overwrite и fallback запрещены; `412 Precondition Failed` означает closed collision;
6. потребовать successful response с exact nonempty version ID, затем прочитать именно эту version, проверить ciphertext cap+SHA, расшифровать с ephemeral owner-supplied key и доказать exact canonical plaintext bytes+digest;
7. только после accepted S3 read-back создать local primary через прежние `O_NOFOLLOW|O_CREAT|O_EXCL`, metadata/fsync/named-entry/root checks;
8. повторно прочитать local primary и exact S3 version, доказать equality canonical plaintext/digest и только затем вернуть combined receipt.

Любая ambiguous upload response, отсутствующий/пустой version ID, redirect/unapproved endpoint, timeout, partial body, size/hash drift, decrypt/authentication failure, wrong key/version/object, local write/fsync/close ambiguity или final re-read failure даёт constant `zero-ledger`, evidence отсутствует. Автоматического retry, overwrite, delete или cleanup нет. При ambiguous PUT main port сохраняет в bounded safe result только deterministic object key и state `UNKNOWN_VERSION`; он не выполняет LIST/HEAD/GET discovery и не утверждает, что object существует. Узкий inventory exact key/version разрешается только будущему отдельному owner-approved cleanup workflow. Remote object после ambiguous/final-local failure и local file после final-remote failure остаются non-authoritative; новая попытка возможна только после отдельного cleanup/reconciliation и использует новую identity/key.

### 7.4. Encryption и credential boundary

Плановый encryption profile — literal `age-x25519-v1-binary`: authenticated age file format v1, один X25519 recipient, binary output без ASCII armor. Конкретная pinned версия `age` и S3 upload client выбираются отдельным owner decision до скачивания/установки и обязаны доказать этот профиль, bounded-memory processing без plaintext/ciphertext temporary file, ciphertext cap4096 bytes, exact-version PUT/GET и no-secret output. Самодельный cipher/envelope, несколько recipients, passphrase mode, provider-only server-side encryption и ключ рядом с bucket запрещены.

Public recipient может присутствовать в reviewed runner config; receipt pin-ит lowercase SHA-256 его exact ASCII representation. Private age identity имеет две owner-controlled encrypted offline recovery copies вне VPS/project/provider; до bucket/materialization отдельная recovery rehearsal обязана расшифровать synthetic object. Для bounded creation/verification private identity и dedicated S3 secret подаются только через два exact read-only temporary secret handles/mounts, не argv/env/config/workspace/stdin общего процесса; runner открывает их после boundary checks, не выводит и доказывает removal/unmount+absence в `finally`. Утрата, rotation, fingerprint drift или cleanup ambiguity закрывают B002 без fallback. Создание recovery copies, ключей и secret delivery layout остаётся отдельным owner-reviewed gate.

S3 service user имеет только read-only `GetBucketVersioning` для exact bucket, conditional PutObject и exact-version GetObject/HeadObject на one prefix; delete, bucket settings, policy, account IAM и unrelated list/read запрещены. Runner обязан получить literal `Enabled` до UUID/plaintext generation; missing/disabled/suspended/unknown/error закрывают run без upload. `bucket_versioning="Enabled"` входит в authority config digest. Object Lock остаётся отдельным operational выбором и не заявляется этим amendment. Production scheduled-backup credential lifecycle не наследуется от one-shot genesis и проектируется отдельно.

Combined receipt имеет literal canonical UTF-8/LF JSON и ровно эти ordered fields: `schema="estakada.zero-request-ledger-s3-receipt"`, `version=1`, `identity`, `generation=1`, `row_count=0`, `plaintext_sha256`, `encryption_profile="age-x25519-v1-binary"`, `recipient_sha256`, `authority_config_sha256`, `object_key`, `object_version_id_b64`, `ciphertext_size`, `ciphertext_sha256`. SHA fields — lowercase64; object key строго derived и ≤512 ASCII bytes; raw provider version ID обязан быть1..1024 UTF-8 bytes без NUL и сохраняется как canonical unpadded base64url; ciphertext size1..4096. Extra/missing/reordered field, bool-as-int, cap/encoding drift или noncanonical JSON запрещены.

`authority_config_sha256` вычисляется из отдельного canonical UTF-8/LF JSON с ровно ordered fields: `schema="estakada.zero-request-ledger-s3-config"`, `version=1`, `provider="selectel"`, `endpoint_origin`, `region_pool`, `bucket`, `bucket_versioning="Enabled"`, `prefix="estakada/zero-ledger/v1/"`, `encryption_profile="age-x25519-v1-binary"`, `recipient_sha256`. Все три variable values — canonical lowercase ASCII без trimming/case folding: endpoint1..256 bytes имеет форму `https://<dns-host>` без userinfo/port/path/query/fragment и с valid DNS labels; region_pool1..32 matches `[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?`; bucket3..63 matches lowercase S3 DNS-name rules, начинается/заканчивается alphanumeric, допускает только `[a-z0-9.-]`, не содержит `..`, adjacent `.-|-.` или IPv4-form. Actual exact values остаются owner-pinned future config; arbitrary prefix отсутствует. Этот digest связывает version ID с reviewed authority, не раскрывая S3 secret/private key. Exact canonical config и combined receipt pin-ятся trusted owner-side вне primary root и bucket; хранение receipt только рядом с любой одной copy не является authority. Tool/version manifest digest также pin-ится будущим runtime plan, но не меняет canonical ledger plaintext.

Runner network разрешается позже только exact approved Selectel S3 endpoint через TLS. Application/Django containers и live site не получают outbound S3. Account creation, order/payment, bucket, service user/key, encryption key, tool install/download, network run и real materialization остаются отдельными gates.

### 7.5. Verification и snapshot binding

Future verification сначала валидирует externally pinned combined receipt, local primary metadata/bytes и exact S3 version ciphertext count+SHA. Затем ciphertext расшифровывается в bounded memory; remote plaintext должен быть canonical, совпасть byte-for-byte с local primary и дать тот же identity/generation/plaintext digest/row_count0. После final local+remote re-read к существующему `VerifiedLedgerEvidence` добавляется только current source `snapshot_id`; S3 coordinates, ciphertext digest и secrets в importer evidence не передаются.

Source writer inventory0, intake default-off и source request count0 по-прежнему доказываются отдельно. S3 authority не разрешает nonzero rows, append, intake-on, production deletion ledger или backup/restore claims.

### 7.6. Acceptance amendment до кода

| ID | Сценарий | Обязательный результат |
|---|---|---|
| `RB3-ZLG-S3-001` | Exact config; runtime GetBucketVersioning=`Enabled`; canonical genesis; successful create-only encrypted publish, exact-version read-back/decrypt; local create; final dual read | Versioning proof precedes UUID/plaintext; remote proof precedes local file; final canonical plaintext/digest equality; one combined receipt |
| `RB3-ZLG-S3-002` | Existing key/version, duplicate identity, overwrite or caller-controlled key/prefix; concurrent same-key conditional PUTs | Literal `If-None-Match:*`; exactly one winner+version ID, other `412`; overwrite/HEAD race/retry/delete/key fallback0 |
| `RB3-ZLG-S3-003` | Upload timeout/ambiguous response, missing version ID, redirect, wrong endpoint, partial/oversize ciphertext or GET failure | Constant failure; no local primary/evidence; safe `UNKNOWN_VERSION`+deterministic key only, main-port network discovery/inventory0 |
| `RB3-ZLG-S3-004` | Wrong version/private key, crypto-suite/recipient/config fingerprint drift, ciphertext bit flip/truncation/replacement, decrypt authentication failure, plaintext noncanonical/digest drift | Constant failure before evidence; no plaintext/secret/provider body in output; literal receipt schema/caps enforced |
| `RB3-ZLG-S3-005` | S3 success then local open/write/fsync/metadata/close failure; local success then final remote failure | No evidence or automatic cleanup; artifact(s) remain explicitly non-authoritative |
| `RB3-ZLG-S3-006` | Verification with local replacement/mode drift, receipt/object-version/ciphertext hash drift or snapshot mismatch | Fail closed before target mutation; exact local+remote final re-read required |
| `RB3-ZLG-S3-007` | Static secret/network inspection plus temporary-handle success/failure/cleanup and versioning disabled/suspended/missing/unknown/error subtests | Non-Enabled fails before UUID/plaintext/network write; two offline encrypted key recoveries+synthetic rehearsal required; no argv/env/config/workspace/temp-file/log secret; exact handle removal/absence; product/app S3 dependency/network0 |
| `RB3-ZLG-S3-008` | Scope/DAG inspection | One zero-ledger authority amendment + focused fakes/tests; no generic storage/filesystem adapter, model/migration/DB/settings/API/daemon/scheduler |
| `RB3-ZLG-S3-009` | Existing importer/source regression | `VerifiedLedgerEvidence` shape and snapshot/request-count0 gates unchanged; nonzero/append still impossible |
| `RB3-ZLG-S3-010` | Runtime/tool boundary audit | Tool/account/order/bucket/key/install/network/materialization remain0 until their separate reviewed permissions |

### 7.7. Gate после amendment

Independent security/architecture/no-bloat review закрыт после remediation `0/3/2 → 0/1/1 → 0/0/1 → APPROVED 0/0/0`. Atomic conditional PUT, literal receipt/config, age/key custody, ambiguous upload, versioning-before-plaintext, concurrency и exact10 приняты.

Source amendment по owner «Продолжай» сохранил historical two-POSIX API и добавил явные `create_s3_zero_genesis` / `verify_s3_zero_genesis`, immutable config/binding/proofs/receipt, typed `UNKNOWN_VERSION` и exact10 focused tests. Independent code/security/no-bloat review closed `0/2/3 → 0/1/2 → APPROVED 0/0/0`; runtime0. Stable candidate exact8 origins and SHA-256:

- `rebuild3_zero_ledger.py=2EC82BE030D815AB40B633AF0939323EAAD0030DB327F8E9FAB2A6E080347171`;
- `test_zero_ledger_authority.py=E61823D6E6F1DF00853FB7E362A8F0BBD6611FF7C402FDD9E81CD02F2EA43503`;
- `test_zero_ledger_s3_authority.py=35FFA205C0AC72F7BB5AFAA1BEDA1E9067AAA1E03567EBF4BCCFF467DE04E175`;
- `rebuild3_importer/__init__.py=B1A4E8EA6FAD18EB2A9DA3F558FF7EC731D0BEDD2FB1C70F0BD421479ED47FF6`;
- `rebuild3_importer/tests/__init__.py=E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`;
- `source.py=EAB0EF6824B85744656F20C887F3100988EBF8B89CAEF3319B69D5E0F0B24580`;
- `runtime_source.py=88AFC30A0090CF3BF4367212E3795B6DFDF0ADC5C4335F93B598532D6C607337`;
- `errors.py=C712353A501F0BA544E7263BF8DD6B8C2A065B6F4052F7339BB0AE386F0F1DE4`.

## 8. Focused synthetic exact23 run candidate

One future owner-authorized run reuses the already existing `nestakada-local/python-runtime:3.14.10-security-20261030` image, trusted digest `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951`, with pull disabled. It runs only the historical13 and new S3 exact10 modules. The sole success oracle is the literal closed marker set `discovered=23`, `ran=23`, `failures=0`, `errors=0`, `skips=0`, `result=PASS` plus process exit0; standard unittest formatter lines are neither required nor allowed.

Boundary: one fresh named/labeled `--rm` container (`estakada.task=rb3-zlg-s3-synthetic-001`), created directly from immutable image ID `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951` with `--pull=never`, `--network none`, `--read-only`, exact `--workdir /src`, UID/GID10001, `--cap-drop ALL`, `no-new-privileges`, pids64, memory128MiB/no swap, CPU1, readonly exact current `src` at `/src`, tmpfs `/tmp`32MiB `noexec,nosuid,nodev` and `PYTHONDONTWRITEBYTECODE=1`. Broad `PYTHONPATH` is absent. DB/Django, S3/provider endpoint, DNS, secrets/keys, bucket, media/source DB, project writable mount, Docker volume, port, extra file, image build/pull/install and persistent output are absent.

Preflight must prove all exact8 SHA values above, exact module method counts13+10, exact local image digest, names/label count0 and no project-labeled container already running. Lifecycle is fixed: `docker create --rm` by immutable ID → record nonempty container ID → inspect that ID for exact name/label/image/security/mount/network boundary → `docker start -a <recorded-id>` once. Any pre-start mismatch removes only the recorded ID and stops. Cleanup may target only that ID; post-audit requires exact name/label/ID absent while preserving the primary result.

The container command is a fixed inline stdlib `python -I -S -B -c` runner, not broad discovery or a new file. Isolated mode, disabled `site` initialization and disabled bytecode writes are mandatory; the command has no `PYTHONPATH`. Before its first project import, the reviewed runner recursively examines literal `/src`, rejects every directory named `__pycache__`, every `*.pyc`, `sitecustomize.py` or `usercustomize.py`, rejects any non-regular/symlink exact8 origin, and re-hashes all exact8 origins against the pinned values above. Only after those checks does the runner insert literal `/src` at `sys.path[0]`; no other project path is added. It then loads exactly `rebuild3_importer.tests.test_zero_ledger_authority` and `rebuild3_importer.tests.test_zero_ledger_s3_authority`, requires `suite.countTestCases()==23`, and runs through a closed `unittest.TestResult` subclass that counts but never formats/stores/prints traceback, exception, test repr or assertion values. It catches terminal runner exceptions into one fixed code. Atomic output is at most ten fixed ASCII marker lines/512 bytes: discovered, ran, failures, errors, skips and `PASS|FAIL|RUNNER_ERROR`; success requires exact23/23/0/0/0/PASS and exit0. Overflow, malformed/extra marker, nonzero exit or mismatch stops without raw fallback. No env/inspect dump is emitted.

First nonzero/mismatch stops. No automatic retry/fallback. The exact inline runner and container create/start command require exact-source review before execution; no permanent coordinator/runner file is added.

Independent run-plan review closed `0/2/3 → 0/1/0 → APPROVED 0/0/0`; the final origin-isolation remediation requires `python -I -S -B`, pre-import rejection of customizers/bytecode caches and exact8 in-container re-hash. This run proves pure source behavior only. It does not install/use `age`, create credentials/account/bucket/object/local genesis, connect S3, materialize B002, capture source DB, import, deploy or enable intake. Its one-run owner permission was consumed by the result below. Real rebuild remains a separate gate even after materialized B002.

Owner-authorized sole run on 2026-11-22 passed exact8 host/container hashes, method counts13+10, forbidden origins0 and the exact6 marker oracle with container exit0. Independent terminal verdict: `ACCEPTED_PASS`, product/source P0/P1/P2=`0/0/0`, cleanup/privacy PASS; exact23 source gate closed. Host wrapper later emitted false-negative `POST_CLEAN=0`/exit1 because PowerShell counted the expected native error record from inspecting the already auto-removed ID. Separate read-only audit proved exact name0, immutable exact label0 and broad running task0; coordinator finding P2 only, rerun forbidden/unneeded. Do not reuse that post-clean count pattern. Account/order/bucket/key/tool/install/S3 network/materialization remain separate gates.

## 9. Minimal operational materialization plan

### 9.1. Решение и границы

Operational path не добавляет backup platform. Рекомендуемая реализация — один reviewed `S3AuthorityPort` adapter/one-shot runner на Python с isolated pinned `boto3` wheelhouse и один официальный `age` binary. Они не входят в Django requirements/image/settings и не импортируются application modules. Adapter разрешает только exact endpoint/bucket/prefix из canonical config, `GetBucketVersioning`, one conditional `PutObject(IfNoneMatch="*")` и exact-version `GetObject`; SDK retries, redirects to another origin, multipart, transfer manager, list/delete/head discovery, credential chain и ambient config отключены. Plaintext/ciphertext проходят только bounded memory/stdin/stdout child pipes; temporary plaintext/ciphertext files запрещены.

Tool candidates are pinned only for the later install review: official `age v1.3.2` Linux amd64 release asset SHA-256 `cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10`; current `boto3 1.44.9` wheel SHA-256 `aff889e8ca6f6006f0b5658b712941471d21e4675d6d48421974a20a5a17a918`. The future install manifest must pin a platform-specific all-wheel dependency closure with filename, version, size and SHA-256 and install offline with literal `--no-index --require-hashes --only-binary=:all:`; sdists, build isolation/hooks, resolver access and unlisted package/index are forbidden. The age archive and extracted executable each receive an independently reviewed exact hash, expected `age --version`, file type/mode and no-extra-binary inventory. The finished runner image receives an immutable image ID/config/source/tool-manifest digest and executes with `--pull=never`; mutable tag trust is forbidden. These values do not authorize download, install or image build and must be rechecked against primary sources at that gate.

Materialization must run where the durable local primary actually lives. Recommended authority is an owner-only `0700` directory on the native filesystem of the final Linux target host, not Windows, Docker Desktop/WSL/VHD, a container writable layer, named volume, network share or production legacy-site tree. Selecting/provisioning that host is a separate owner decision and does not itself authorize site deploy. The primary root is created empty, is opened by directory fd, and its device/inode/owner/mode are pinned before keys or network are admitted.

### 9.2. Control plane and least privilege

After code/tool review and only with owner approval:

1. owner selects one Selectel account/project, Russian pool, private bucket name/type and exact regional S3 endpoint; cold class is preferred when available, otherwise standard class is acceptable because authority semantics do not change;
2. owner creates the private bucket and enables versioning in the control plane; Object Lock remains off unless separately approved;
3. owner creates one dedicated service user with the narrow bucket role and one project-scoped S3 key; the secret is copied once into an exact temporary secret handle and never enters repo, argv, env, shell history, transcript or logs;
4. bucket policy is deny-by-default and allows this principal only `s3:GetBucketVersioning` on the exact bucket plus `s3:PutObject` and `s3:GetObjectVersion` on `arn:aws:s3:::<bucket>/estakada/zero-ledger/v1/*`; `ListBucket`, `ListBucketVersions`, delete, policy/versioning mutation, multipart, ACL, unrelated read/write and public access remain denied;
5. after accepted creation, the write-capable key is revoked. A separately approved read-only verifier key may retain only `GetBucketVersioning` and `GetObjectVersion` for the same prefix until import verification is complete.

Role assignment alone is not treated as least privilege: Selectel evaluates the role first and bucket policy second, so both exact service-user scope and explicit bucket policy are required. Versioning must return literal `Enabled`; suspended, missing or unknown stops before UUID/plaintext/upload.

### 9.3. Age key ceremony

Key ceremony is interactive and owner-controlled. The fixed contract remains classic one-recipient X25519 (`age1…`), despite newer age versions also offering other recipient types; changing the receipt schema/profile requires a new architecture decision. One dedicated identity is generated without terminal/stdout capture into project files. Its recipient and lowercase SHA-256 are nonsecret and pinned in config.

Before provider upload, the owner creates two independently encrypted recovery copies on two separate offline media outside the project, host and Selectel account. Each copy uses a distinct strong passphrase. Each passphrase has its own owner-controlled offline recovery record, stored separately from its encrypted medium, the other passphrase record, host and provider; neither memorization alone nor one co-located note is accepted as recovery. Each media+passphrase pair is independently restored into an ephemeral read-only secret handle, derives the same recipient, decrypts a fresh synthetic binary age object and is removed with absence proof. Failure or unavailable second independent path blocks materialization. The plaintext identity, passphrases and restored handles are never committed, logged or retained on the host.

The externally pinned canonical authority config and final combined receipt are copied to both owner recovery media and checked byte-for-byte; they are nonsecret but are not authoritative if stored only in the bucket or local primary. Receipt/config/tool-manifest hashes are recorded without secret material. The receipt transport is explicit: runner stdout may contain one canonical base64url-encoded receipt marker plus fixed hashes/result markers under an 8192-byte total cap, but no secrets/provider bodies. The host coordinator captures it in bounded memory, decodes through the reviewed canonical receipt parser, proves the exact byte cap/hash, atomically writes config+receipt to each already attached owner recovery medium, fsyncs each file and medium directory where supported, rereads both and requires byte equality before authority can be accepted or a write key revoked. If either durable copy fails, local/remote artifacts are non-authoritative, no receipt/evidence is claimed, and retry or automatic key revocation is forbidden pending separate reconciliation.

### 9.4. Network and one-shot execution

The one-shot runner has no broad application network. A reviewed secretless fixed-target TCP forwarder has one literal upstream `<approved-endpoint>:443`. The runner is attached only to one fresh `--internal` network and receives a recorded exact host mapping from the original endpoint hostname to the broker internal IP; it has no egress network or alternate DNS path. The broker alone joins both that internal network and one fresh egress network; its own resolver has no endpoint override, resolves the literal upstream normally, and its reviewed source can open only that hostname/port — no CONNECT, request-selected/generic target, listener beyond one internal port, TLS termination or payload/log output. Thus boto3 still connects using the original endpoint hostname, preserving end-to-end SNI and certificate verification through the byte-transparent broker. Broker source SHA, immutable image ID and argv are pinned; it runs nonroot with read-only rootfs, cap-drop ALL, no-new-privileges and fixed memory/CPU/pids/tmpfs. Runner and broker IDs, both network IDs and the exact host mapping are inspected before secrets/network use and cleaned by recorded identity.

Execution order is fixed:

1. re-prove exact source/tool/image hashes, empty trusted primary root, root metadata and absence of stale task resources;
2. bind exactly that native-host primary directory writable at `/authority-primary`; it is the only writable host bind. Before network, the nonroot runner opens it with no-follow directory semantics, requires numeric runner UID/GID ownership, mode`0700`, empty contents and the approved device/inode identity, retains the directory fd for `create_s3_zero_genesis`, and proves a created file plus directory fsync remains visible from the host after container cleanup. Container layer remains read-only; tmpfs is ephemeral and no Docker volume/other writable host mount exists;
3. mount two exact read-only secret handles (restored age identity and S3 key) plus readonly reviewed source/config; validate handles without printing contents;
4. `GetBucketVersioning == Enabled` through the fixed endpoint;
5. call reviewed `create_s3_zero_genesis`; encrypt before first network byte, conditionally publish once, capture nonempty exact version ID, exact-version read/decrypt, then create and fsync local primary and perform final local+remote rereads;
6. atomically emit the one bounded canonical receipt marker plus config/tool hashes and fixed result markers; host coordinator validates and durably writes/rereads exact receipt+config on both offline media before accepted evidence;
7. remove secret handles, runner, broker and both networks by recorded identities; prove name/label/resource absence without using the rejected native-error-record count pattern;
8. revoke the write-capable S3 key only after accepted dual receipt copies and one independent read-only verification. No object delete or retry is automatic.

Timeout/connection ambiguity after PUT returns only deterministic key plus `UNKNOWN_VERSION`; it creates no local primary or receipt and requires a separately approved exact-key reconciliation. Any local failure after remote success or remote failure after local creation leaves explicit non-authoritative artifacts and stops. Same identity/key is never retried.

### 9.5. Acceptance before source/operations

| ID | Scenario | Required result |
|---|---|---|
| `RB3-ZLG-MAT-001` | Static scope/dependency inspection | One adapter/runner + focused tests; Django requirements/image/settings/model/migration/API/scheduler0 |
| `RB3-ZLG-MAT-002` | SDK client construction | Exact endpoint/region/bucket/prefix, TLS verify on, retries0, redirects/ambient credentials/config/multipart/list/delete0 |
| `RB3-ZLG-MAT-003` | Secret-handle success/failure | Exact two read-only handles, bounded reads, no argv/env/repo/temp plaintext/log, finally absence proof |
| `RB3-ZLG-MAT-004` | Age encrypt/decrypt adapter | Official pinned binary, one classic X25519 recipient, binary output, bounded stdin/stdout, ciphertext cap4096, wrong key/tamper fail closed |
| `RB3-ZLG-MAT-005` | Selectel policy and versioning | Dedicated service user; exact three allowed actions/resources; public/list/delete/admin0; literal Enabled before UUID/plaintext |
| `RB3-ZLG-MAT-006` | Fixed egress topology | Runner internal-only with endpoint→broker mapping; hardened secretless fixed-target broker has separate normal egress resolution; end-to-end hostname/SNI/TLS; alternate host/redirect/DNS path fails |
| `RB3-ZLG-MAT-007` | Offline recovery rehearsal | Two media with distinct separately custodied passphrases each derive same recipient and decrypt fresh synthetic object; restored handles removed |
| `RB3-ZLG-MAT-008` | One-shot happy path | Exact native-primary writable bind/fd, conditional PUT once, exact version, remote proof before durable local create, final dual reread, parsed canonical receipt/config fsynced+reread on two media |
| `RB3-ZLG-MAT-009` | Collision/concurrency/ambiguous PUT | 412 closed collision; 409/timeout/missing version become no-retry UNKNOWN_VERSION; local primary/receipt0 |
| `RB3-ZLG-MAT-010` | Partial failure | Remote-only or local-only artifact explicitly non-authoritative; no delete/retry/evidence/import |
| `RB3-ZLG-MAT-011` | Cleanup and credential transition | Local primary survives cleanup; recorded container/network cleanup and name+label absence; write key revoked only after dual receipt durability+verification; optional verifier key read-only |
| `RB3-ZLG-MAT-012` | Downstream gate | B002 closes only after receipt-bound exact remote+local verification and source snapshot/request-count0 proof; import/live/deploy remain separate |

### 9.6. Gates

Independent security/operations/no-bloat review closed `0/2/3 → APPROVED 0/0/0`; durable native primary, receipt persistence, all-wheel/age/image supply chain, dual-network fixed-target broker and two independent passphrase recovery paths are accepted without expanding product scope. This section authorizes documentation/review only. The tests-first source gate is deliberately narrower than operational acceptance: exact `RB3-ZLG-ADP-001..012` cover the port adapter, root-first composition, explicit SDK/read-only secret-handle construction, bounded age process, derived-key/ambiguity/read-back rules and canonical receipt marker. `RB3-ZLG-MAT-003` handle removal/absence, `MAT-005..007` control plane/recovery/egress, `MAT-008` real native-primary creation plus dual-media durability, `MAT-011` host cleanup+credential transition and `MAT-012` downstream import proof remain open until their later reviewed operational gates; no source-only claim closes them. Later gates remain separate: final Linux primary host selection; exact dependency/tool lock and external download/install; age key ceremony/recovery media; Selectel account/order/project/bucket/service user/key/policy; synthetic recovery rehearsal; one real network materialization; then receipt-bound import verification. No current step creates or changes external resources.

Owner agreement opened only this source gate. `src/rebuild3_s3_materialize.py` now provides the narrow port adapter, private exact client builder, root-first one-shot composition, read-only owner secret-handle validation, content-pinned classic age identity subprocess and canonical receipt marker; `boto3` remains a lazy future runtime dependency and was not installed/imported. Exact `RB3-ZLG-ADP-001..012` focused tests use fakes only. Independent review closed `0/3/2 → 0/2/2 → APPROVED 0/0/0`; runtime0. Stable exact7 origins:

- `rebuild3_s3_materialize.py=623EA7C13E2E8E9754F02106F10DFC5EE65CA9601089C9E46FAB65296B2A24C0`;
- `test_s3_materialize_adapter.py=8ECF9E3F9A46CAFF528E3DBE98F70E60768857C9754610593BC664A87686981C`;
- `rebuild3_zero_ledger.py=2EC82BE030D815AB40B633AF0939323EAAD0030DB327F8E9FAB2A6E080347171`;
- `rebuild3_importer/__init__.py=B1A4E8EA6FAD18EB2A9DA3F558FF7EC731D0BEDD2FB1C70F0BD421479ED47FF6`;
- `rebuild3_importer/tests/__init__.py=E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`;
- `source.py=EAB0EF6824B85744656F20C887F3100988EBF8B89CAEF3319B69D5E0F0B24580`;
- `errors.py=C712353A501F0BA544E7263BF8DD6B8C2A065B6F4052F7339BB0AE386F0F1DE4`.

## 10. Adapter synthetic exact12 run candidate

One future owner-authorized source-only run reuses immutable local image ID `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951`, `--pull=never`, and the §8 isolation envelope under a new literal identity: container name `estakada-rb3-zlg-adapter-synthetic-001` and label `estakada.task=rb3-zlg-adapter-synthetic-001`. It creates one fresh recorded `--rm` container with `--network none`, read-only rootfs and `/src`, `/tmp` tmpfs, workdir`/src`, UID/GID10001, cap-drop ALL, no-new-privileges, pids64, memory128MiB/no swap and CPU1. It imports only `rebuild3_importer.tests.test_s3_materialize_adapter`, requires exact12, and has no boto3/age binary/identity/S3 key/provider/DNS/DB/media/writable primary or persistent output. Preflight requires that exact name count0, exact label count0 and broad running `estakada.task` count0.

Preflight and in-container runner pin exact7 above, reject symlinks/nonregular origins plus `sitecustomize.py`, `usercustomize.py`, `*.pyc` and `__pycache__`, then use `python -I -S -B -c`, insert only `/src` and emit the same fixed six-marker oracle adapted to exact12: discovered12, ran12, failures0, errors0, skips0, PASS, exit0. A closed TestResult stores no traceback/test repr/assertion value; all incidental stdout/stderr is suppressed under the reviewed cap.

Lifecycle remains create→record ID→inspect exact image/name/label/network/security/mount/resource boundary→start-a once. Cleanup targets only the recorded ID. For any future reuse of this lifecycle, post-clean must query `docker ps -a --no-trunc --format '{{.ID}}'` with exit0 and require recorded ID absent, then independently require exact name0, exact immutable label0 and broad running `estakada.task`0. Missing-ID `docker inspect` stdout cardinality is forbidden as an absence oracle on this host. No retry/fallback or permanent runner file. This run proves only fake-based adapter source behavior; operational MAT gates remain open.

Independent run-plan review closed `0/0/1 → APPROVED 0/0/0` after assigning the new literal adapter-only name/label and exact absent-ID stdout/exit oracle. Docker/runtime0. Fresh owner permission is required for one exact12 no-network run.

The sole owner-authorized run completed the exact6 oracle at `12/12/0/0/0/PASS` with container exit0. Independent terminal verdict: `ACCEPTED_PASS`, product/source P0/P1/P2=`0/0/0`, cleanup/privacy PASS. Host wrapper later returned exit1 only because its approved post-clean assumption was false: on this Docker/PowerShell host even a controlled missing 64-hex ID produced inspect exit1 plus captured stdout count1. Separate exact immutable label0, exact name0 and broad running task0 prove cleanup; no rerun or further evidence is required. Coordinator P2 only. The one-run permission is consumed; §10 runtime gate is closed.
