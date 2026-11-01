# DEV07-SJR — immutable journal primitive

2026-11-01. DEV-07 около96%, этап8 около20%. D-350/D-347/D-349; dev07-shared-quota-profile-proposal.md, SJR-001–005. Контракт до кода и независимого ревью. Только закрытая запись/чтение book, без DB writes, release/TTL/unlink, single-pending admission или включения quota profile. Существующие256МиБ/10000/75%, инфраструктура и запрет старого сайта/VPS сохраняются.

## API и данные

Новый `shared_content.journal.SharedJournal(storage=None)` использует существующий SharedStorage. Два метода: `create_or_replay(book:dict)` и `read(operation_id:UUID|canonical_uuid_string)`. Результат: `{book,sha256,replay,durable:true,profileAvailable:false,heldAuthority:false}`; read возвращает replay=true как чтение уже существующей записи, новое создание —false. sha256 вычисляется по фактическим canonical UTF8 bytes. durable означает завершённые file+directory barriers в этом вызове, **не разрешённый held reserve или подтверждённый DB commit**.

Ровно11 полей; unknown/duplicate keys, float/NaN, bool вместо integer или нестроковый UUID запрещены:

| Поле | Точный профиль первого primitive |
|---|---|
| bookSchema | literal `shared-held-book-v1` |
| profileId | literal `shared-unvetted-v1`; не HTTP-настройка и не разрешённый product profile |
| operationId,blockId | canonical lowercase UUID strings с дефисами |
| action | draft/apply/restore_prepare |
| actorId,generation | integer1..9223372036854775807, не bool |
| inputFingerprint,sourceStamp |64 lowercase hex |
| reservedBytes | integer0..268435456, не bool;0 допустим как данные unvetted primitive, не утверждение достаточности |
| snapshotIncrement | integer0/1, строго draft→0/apply→1/restore_prepare→0 |

Canonical JSON: ensure_ascii=false, allow_nan=false, sort_keys=true, separators=(',',':'), без BOM/newline; UTF8≤4096B. Reader требует не только правильную схему, но равенство прочитанных bytes canonical serialization; порядок/whitespace иначе INVALID. Не добавлять filler ради валидного4096B book: cap4096/+1 проверяется на raw reader отдельно от schema-positive corpus. Существование block/actor и достаточность размера этот низкоуровневый primitive не подтверждает; доверенный будущий coordinator передаёт значения после своей авторизации.

## FS/lock/durability

Закрытое имя: `journal/<operationIduuidhex>.json` внутри MEDIA_LIBRARY_ROOT/private/shared-content. Body operationId обязан совпасть с именем. Новый private helper SharedStorage._journal_parent(UUID,create=False) открывает trusted root и journal0700 через dirfd/O_DIRECTORY/O_NOFOLLOW и отдаёт `(rootfd,journalfd,leaf)`; на выходе сверяет named journal dev/inode/type/owner/mode с удержанным fd, существующий root-name bind сохраняется. Общие media storage_key/public пути не расширяются.

1. Валидировать caller dict/длину **до FS изменений**. Создание: O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_NONBLOCK|O_CLOEXEC,0600. EEXIST переключает в open-existing O_RDWR/no-follow/nonblocking без truncate/create. Проверить regular/euid/0600/nlink1/size≤4096.
2. На **том же file fd** получить `fcntl.flock(LOCK_EX|LOCK_NB)` до чтения/записи. Busy→фиксированный отказ; внутри primitive нет sleep/retry. Новый lockfile не создаётся. Creator/contender держат lock до окончания file+parent barriers и всех named-anchor проверок. Возврат происходит после закрытия всех fd/снятия lock в finally.
3. Creator полностью пишет canonical bytes с обработкой short write; затем fsync(file), strict фактическое чтение/схема/hash, сравнение с ожидаемым book, проверка leaf-name identity. Existing contender **не получает durable из EEXIST**: под lock strict-read/name check, затем сам fsync(file)+полный directory-chain barrier+повторная фактическая/name проверка и выход через named journal/root bind; лишь затем success replay=true. Reader выполняет ту же durability-процедуру, не читает незавершённый writer без lock.
4. Existing valid book с тем же полным canonical body возвращается без второго файла/новой брони. Любое изменение любого из11 полей при том же operationId —CONFLICT, без overwrite. Malformed/partial/noncanonical/неверная UUID привязка —INVALID, без repair/unlink. Ошибка fsync/name binding/read/write не возвращает success; созданный partial остаётся учтённым scanner.

В узком промежутке open(O_EXCL)→flock другой процесс может первым взять lock пустого файла: тогда strict reader откажет, а creator может получить BUSY. Это допустимый fail-closed outcome, не гарантия успеха одной из двух гоняющихся операций. Нельзя лечить его overwrite или новым lockfile. После прежнего fsync fault целый валидный book допускает exact replay **только после новых успешных barriers**; это восстановление durable состояния, а не утверждение успеха прежнего вызова.

Directory-chain barrier обязателен **на каждом create/read/replay**, включая EEXIST после crash старого creator между mkdir и parent fsync. Закрытый helper `_sync_journal_chain(rootfd,journalfd)` заново открывает no-follow цепочку MEDIA_LIBRARY_ROOT→private→shared-content→journal, сверяет held root/journal identities, выполняет fsync в порядке journal→shared-content→private→MEDIA_LIBRARY_ROOT и повторно сверяет named identities перед success. Это journal fd и3 parent dirfd; pre-existing MEDIA_LIBRARY_ROOT — anchor, durability `/`/системных предков не обещается. Ошибка любого barrier/rename закрывает вызов, file lock удерживается до всех проверок. Fault/restart test обязан отдельно покрыть недостигнутый fsync предка после mkdir и отказ/успешное повторное подтверждение полной цепочки новым instance.

Факты fd до/после чтения и leaf lookup сравнивают dev/inode/mode/owner/nlink/size/blocks/mtime/ctime. Directory bind сравнивает identity/owner/mode, не mtime, меняющийся от собственного create. Защита предполагает сотрудничающих writers с тем же protocol/content domain; не объявлять её атомарным snapshot против root/того же UID в обход lock. Scanner продолжает считать actual journal bytes/directories, а reservationReadiness/profileAvailable=false; синтаксический book не добавляется как доказанная authoritative бронь.

Ошибки SharedFault: SHARED_JOURNAL_INVALID503 (схема/raw bytes/binding), SHARED_JOURNAL_BUSY503 (flock занят), SHARED_JOURNAL_CONFLICT409 (валидный existing отличается), SHARED_JOURNAL_UNAVAILABLE503 (missing/I/O/unsafe FS/barrier/anchor). Нет фактических private paths/payload в сообщении. Никаких delete/release/finalize методов.

## До-кода сценарии

| ID | Обязательный конечный oracle |
|---|---|
| SJR-001 | Actual create→file fsync→journal fsync→close/reopen новым instance; все11 полей/фактические bytes/SHA/0600/owner/nlink/UUID binding; invalid field/type/profile/float/bool/duplicate/unknown/noncanonical/UTF8 и raw4096/+1 отказ; fd closure; allocation book+dirs в scanner |
| SJR-002 | Exact replay один inode/файл/тот же body и raw reservedBytes, fresh barriers; каждый изменённый binding/reserve/action conflict без overwrite; missing read не превращается в0 |
| SJR-003 | Два реальных ограниченных процесса с одним ID: writer держит flock на реально созданном/частичном fd, contender BUSY/INVALID без durable success; после writer barriers exact replay выполняет **свои** barriers. Разные book при одномID не дают две брони |
| SJR-004 | Реально достигнутые partial write/filefsync/parentfsync faults и named journal replacement: no success, исходные/частичные bytes не удалены, scanner считает остаток либо fail-closed incomplete. Fresh reader partial отказывает; whole valid после fault получает success только при новых подтверждённых barriers |
| SJR-005 | Durable book переживает завершение своего процесса и независимый actual SQL rollback; business receipt/история не появились. Existing product draft/apply/restore остаются503/no incoming blob. Productheld authority/суммарный single-pending/release/crash DB+FS commit не заявляются |

Первый scope кода после ревью: новый journal.py и только необходимый закрытый storage helper; QA пишет отдельные tests. Профиль/commands/quota admission не включать. Дальше отдельным инкрементом — координация единственной pending брони, reconciliation и конечная калибровка резерва, а не обещание готовности по факту этих пяти групп.
