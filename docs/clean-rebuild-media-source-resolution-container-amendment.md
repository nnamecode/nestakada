# REBUILD-1 source-resolution ephemeral verifier amendment

Дата: 2026-11-17. Candidate ID: `RB1-MEDIA-SOURCE-CONTAINER-001`.

Статус: **CANDIDATE; implementation/runtime не разрешены**.

## Решение владельца и цель

Владелец выбрал D-1356 option1. Один future ephemeral verifier получает read-only доступ к existing foundation `state` volume и проверяет ровно unmatched descriptor. Existing compose/app service не изменяется и не запускается; новый image/service/script/dependency отсутствует.

## Container boundary

Runner использует только exact pinned app image digest из validated inactive foundation manifest и exact named volume `nestakada-foundation-dev-state`, предварительно сверенный по Docker labels. Container получает fresh unpredictable exact name и project evidence label, затем запускается с:

- `--network none`, `--read-only`, `--rm`;
- `--user 10001:10001`, `--cap-drop ALL`, `no-new-privileges`;
- bounded memory/CPU/PIDs и tmpfs `/tmp`;
- единственный volume mount `state:/state:ro`;
- никакие repo/private/secret/socket paths не монтируются;
- fixed `python -I -S -c <reviewed inline code>`; code не импортирует project/runtime modules.

До запуска project containers0 и verifier-name collision0. После любого outcome проверяются verifier containers0 и volume unchanged identity. Automatic retry0.

## Private input и RRRO lifetime

Existing runner держит одну reader `psql` TLS/RRRO session открытой. Aggregate classification и exact unmatched `key/sha256/byte_size` читаются из одной snapshot. Descriptor передаётся verifier только через redirected stdin как bounded canonical JSON, не argv/environment/file/log; stdin закрывается сразу после write. Snapshot закрывается `ROLLBACK` только после verifier result либо failure cleanup.

Key/SHA/bytes не выводятся. Host и container stderr/raw output не публикуются; unexpected output даёт constant failure.

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

`RESOLVED` не меняет exact301 и не разрешает transfer. Additive301+1 остаётся отдельным owner decision/review.

## Acceptance

- `RB1-MSRC-CONT-AC-001`: exact pinned existing image and exact labelled state volume; compose/service/image changes0.
- `AC-002`: network none, root+volume read-only, non-root, caps0, no-new-privileges, bounded resources/mounts.
- `AC-003`: descriptor stdin-only/bounded; argv/env/file/log/private output0; one RRRO snapshot held through verification.
- `AC-004`: dir-fd component walk and final one-fd `O_NOFOLLOW`; stable fstat and exact size/SHA.
- `AC-005`: one constant marker or allowlisted constant failure; raw output0, retry0.
- `AC-006`: pre/post project/verifier/volume identity checks and exact cleanup; source mutation0.
- `AC-007`: success does not grow exact301 or authorize transfer; eligible usages cannot be dropped.
- `AC-008`: no-bloat — new image/service/script/file/dependency/scanner/manifest/native layer0.

Следующий gate: independent amendment review. Implementation candidate/static checks и runtime имеют отдельные последующие gates.
