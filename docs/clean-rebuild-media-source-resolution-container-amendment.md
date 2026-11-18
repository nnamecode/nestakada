# REBUILD-1 source-resolution ephemeral verifier amendment

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-SOURCE-CONTAINER-001`.

Статус: **REMEDIATED CANDIDATE D-1365; implementation/runtime не разрешены**.

## Решение владельца и цель

Владелец выбрал D-1356 option1. Один future ephemeral verifier получает read-only доступ к existing foundation `state` volume и проверяет ровно unmatched descriptor. Existing compose/app service не изменяется и не запускается; новый image/service/script/dependency отсутствует.

## Container boundary

Runner использует только exact pinned app image ID из validated inactive foundation manifest и exact named volume `nestakada-foundation-dev-state`, предварительно сверенный по driver/scope/project labels. До media read exact image inspect обязан совпасть с reviewed Linux/architecture/config/entrypoint facts; runner явно переопределяет entrypoint на reviewed absolute Python executable из этого image и передаёт exact argv `-I -S -c <reviewed inline code>`. Любой image/config/entrypoint drift fails before descriptor read.

Verifier получает fresh unpredictable exact name и one evidence label. Runner использует literal `rebuild-media-verifier.cid` только под exact canonical existing private directory. Parent до create обязан быть contained, directory/non-reparse и иметь approved owner-only ACL; cidfile обязан отсутствовать. Затем runner делает `docker create --cidfile <exact-private-path>`.

После create и перед любым read/start cidfile обязан оставаться под тем же parent, быть regular non-reparse file с exact inherited private ACL/current-user+SYSTEM only и иметь ровно 64, 65 или 66 bytes. Content grammar допускает ровно одну из трёх форм: 64 ASCII lowercase hex `[0-9a-f]{64}` без ending; те же64 + single LF; те же64 + single CRLF. BOM, lone CR, additional newline/line/trailing byte запрещены. После удаления единственного разрешённого ending parsed ID обязан быть exact lowercase64. Runner читает bounded maximum66 bytes, inspect-сопоставляет ID/name/label/image/config/HostConfig, затем отдельно выполняет attached `docker start -a -i`. Validation failure запрещает start; exact-name created container переходит только в cleanup-only flow. Cidfile содержит только ID, не descriptor, и ignored Git-правилом. Create/start используют:

- `--network none`, `--read-only`, `--log-driver none`;
- `--user 10001:10001`, `--cap-drop ALL`, `no-new-privileges`;
- bounded memory/CPU/PIDs и tmpfs `/tmp`;
- единственный volume mount `state:/state:ro`;
- никакие repo/private/secret/socket paths не монтируются;
- explicit reviewed absolute Python entrypoint and exact `-I -S -c <reviewed inline code>`; code не импортирует project/runtime modules.

Sequence exact:

1. pre-run project containers0 и verifier name/label collision0;
2. existing runner запускает и identity-проверяет ровно expected DB container;
3. до verifier create допускается ровно этот DB container с exact captured ID/image/project labels; app/worker/ingress/tools/verifier0;
4. RRRO session остаётся открытой через verifier create/start/result;
5. при однозначном result verifier exact-ID cleanup, RRRO rollback, reader/role/secret cleanup, DB compose down и удаление cidfile только после доказанного container absence;
6. final project containers0, verifier exact ID/name/label0, cidfile0 и volume identity unchanged — только для доказанно clean outcome.

Automatic retry0.

## Private input и RRRO lifetime

Existing runner держит одну reader `psql` TLS/RRRO session открытой. Aggregate classification и exact unmatched `key/sha256/byte_size` читаются из одной snapshot. Descriptor передаётся verifier только через redirected stdin как bounded canonical JSON, не argv/environment/file/log; stdin закрывается сразу после write. Snapshot закрывается `ROLLBACK` только после verifier result либо failure cleanup.

Key/SHA/bytes не выводятся. Verifier ловит expected errors и пишет только allowlisted constant marker/code. Docker logging disabled. Host одновременно читает stdout/stderr с hard cap 256 bytes each and timeout15s; overflow, unexpected bytes, timeout или non-exact exit дают constant failure без публикации raw output.

## Exact verifier algorithm

Reviewed inline Python:

1. принимает один JSON object с exact keys `key`, `sha256`, `byteSize`, cap2048 bytes, strict UTF-8;
2. повторяет approved slash-only `img/...` grammar и SHA/size bounds;
3. открывает `/state/media` как directory fd с `O_DIRECTORY|O_NOFOLLOW`;
4. идёт по каждому directory segment через `os.open(..., dir_fd=parent, O_DIRECTORY|O_NOFOLLOW)`; final segment открывает один раз `O_RDONLY|O_NOFOLLOW`;
5. требует regular file через `fstat`, считает size/SHA-256 из этого fd, повторяет `fstat` и требует stable device/inode/size;
6. закрывает все fd в `finally`.

## Bounded result

Verifier success output — ровно один allowlisted constant marker. Host добавляет reviewed contract/source/elapsed and usages2+1 aggregate envelope only after exact exit/output validation. Failure exposes only one allowlisted constant phase code with facts0.

`finally` не полагается на auto-remove. Перед каждым cidfile read и literal deletion runner заново доказывает canonical parent containment, parent ACL/type/no-reparse и cidfile regular/non-reparse/exact ACL/bounded64|65|66 grammar. Residual verifier удаляется только если parsed cidfile ID одновременно совпадает с exact predetermined name, evidence label и pinned image ID. После stop/remove runner доказывает отсутствие exact ID/name/label, повторяет cidfile validation и только затем literal-delete exact path. Cidfile validation failure запрещает start/delete и передаёт exact-name created/residual container в cleanup-only case владельцу.

Inspect mismatch до start запрещает start; если exact identity доказана, created container удаляется по exact ID. Timeout, daemon/client loss или identity ambiguity после start дают только `UNKNOWN_ISOLATED`: `RESOLVED`, `stopped`, final containers0 и cidfile deletion запрещены. RRRO/reader/role/secret/DB cleanup продолжается лишь насколько это однозначно возможно; owner получает constant cleanup failure. Exact cidfile остаётся единственным local private cleanup state.

После восстановления Docker допускается отдельное owner-gated cleanup-only действие: прочитать exact cidfile, подтвердить ID+name+label+image, stop/remove только этот container, доказать absence и удалить cidfile. Broad search/removal, verifier/media rerun и automatic retry запрещены. Если identity не подтверждается, состояние остаётся `UNKNOWN_ISOLATED` владельцу.

`RESOLVED` не меняет exact301 и не разрешает transfer. Additive301+1 остаётся отдельным owner decision/review.

## Acceptance

- `RB1-MSRC-CONT-AC-001`: exact pinned existing image ID/config/explicit Python entrypoint and exact labelled state volume; compose/service/image changes0.
- `AC-002`: network none, root+volume read-only, non-root, caps0, no-new-privileges, log-driver none, bounded resources/mounts.
- `AC-003`: pre-run containers0 → exact DB-only → DB+one verifier → final containers0; descriptor stdin-only/bounded and one RRRO snapshot held through verification.
- `AC-004`: dir-fd component walk and final one-fd `O_NOFOLLOW`; stable fstat and exact size/SHA.
- `AC-005`: one constant marker or allowlisted constant failure; stdout/stderr cap256 each, raw output/log0, retry0.
- `AC-006`: canonical non-reparse owner-only private parent; pre-create cidfile absent; post-create/before-read/delete regular non-reparse exact-ACL file with bounded64|65|66 bytes and exact lowercase64 ID plus none|single-LF|single-CRLF only; ID/name/label/image cleanup only; post-start ambiguity UNKNOWN_ISOLATED, broad cleanup/rerun0.
- `AC-007`: success does not grow exact301 or authorize transfer; eligible usages cannot be dropped.
- `AC-008`: no-bloat — new image/service/script/dependency/scanner/manifest/native layer0; only one exact ignored private cidfile for cleanup identity, not a tracker.

Следующий gate: independent amendment review. Implementation candidate/static checks и runtime имеют отдельные последующие gates.
