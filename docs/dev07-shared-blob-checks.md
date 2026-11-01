# DEV07-SH2 — приватные immutable HTML-файлы: первый инкремент

2026-11-01. DEV-07 около96%, этап8 около20%. Основание: владелец разрешил DEV07-SH-Q001/D-347 — подготовить и локально проверить вариант docs/dev07-shared-blob-proposal.md. Историческая надпись «не принято» в начале исходного предложения не отменяет последующего решения D-347. Это pre-code контракт ограниченного первого инкремента, а не включённый профиль записи или приёмка полного shared редактора. REQ-013/017/018/022/028/029/050, AC-013/017/022/028/029/050, AC-DTL-017/AT-117; действуют SHI07 и ограничения старого сайта/VPS/зависимостей/ресурсов.

## Разрешённый результат первого инкремента

1. Собственный SharedStorage для immutable UTF8 bytes внутри существующего тома, низкоуровневые положительные/отрицательные storage тесты, включая1МиБ. Это подготовка хранилища, **не успешный HTTP Apply**.
2. Новая migration0002 добавляет storage metadata к SharedRevision/SharedDraft;0001 не переписывается, существующий inline HTML сохраняется.
3. Все shared read/check/history/compare/restore source чтения используют единый обязательный content resolver; file-mode не получает fallback на пустой/старый inline HTML.
4. quota.measure учитывает actual allocation собственных файлов/каталогов/orphans/journal вместе с прежними восемью PG roots. Unknown/unvetted reservation profile продолжает запрещать новые product mutations. Low-level подготовка файла в тесте не обходит этот gate в HTTP.

Новый global prebook/reserve/finalize protocol и включение bounded PG metadata profile **не реализуются** этим первым инкрементом. До них новых accepted draft/apply/restore нет. Нельзя выдать отдельный storage PASS за crash-consistent DB+FS commit.

## SHB07-STORE — закрытая область и имена

SharedStorage всегда использует фиксированный subroot `MEDIA_LIBRARY_ROOT/private/shared-content`; MEDIA_LIBRARY_ROOT берётся из уже принятого server setting, а не HTTP. Не добавлять этот prefix в media_library.paths/storage_key, не менять общий MediaStorage и публичные media endpoints. Доступ к файлу не становится URL: editor/read возвращают владельцу экранированное содержимое через существующие private views.

Закрытый относительный key: `blobs/<hh>/<uuidhex>.html`, где uuidhex —32 lower-case hex server UUID, hh —его первые2 hex. Leaf identity никогда не берётся из HTML/HTTP, UUID назначает trusted storage producer до записи. File key в модели — внутренний pointer, не произвольный путь. Полный path/hash/client-supplied filename из DTO не принимается. Существующий leaf не перезаписывается, даже если байты/SHA совпадают; повтор operation позже разрешает только будущий проверенный journal/receipt protocol, не новый overwrite.

Root/все ancestors открываются последовательно через dir_fd от `/` с O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC. Нет Path.resolve как единственной проверки и нет последующего строкового open после проверки. Существующие MEDIA_LIBRARY_ROOT/private не chmod/chown и не расширяются правами; shared-content и созданные blobs/fan-out/journal каталоги создаются0700 и fsync их родительских dirfd. Собственные каталоги требуют directory/текущийeuid/без group-world access; symlink, другой owner или writable чужими объект — отказ. Системные предки `/var` и т.п. не обязаны принадлежать app UID, но symlink traversal запрещён. Создание новых предков вне MEDIA_LIBRARY_ROOT запрещено.

Immutable leaf создаётся O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600. После открытия проверяются regular file, st_uid=effective UID, st_nlink=1, mode0600; bounded UTF8 bytes≤1048576B полностью записываются с обработкой partial writes. Невалидная UTF8/превышение отклоняются до durable pointer. SHA256/длина определяются по фактическим bytes, не аргументу клиента. Порядок durable success: finish write→flush/fsync(file)→проверенный fstat неизменного inode/размера→fsync(parent directory). В возвращаемом descriptor: storage_kind,file_key,byte_size,file_sha256; никакого ready/success до завершения fsync.

При write/fsync ошибке partial leaf **не считается опубликованным и не теряется из учёта**. Первый инкремент не делает автоматический unlink: созданный собственный partial/orphan остаётся scanner-visible и учитывается actual allocation. Если имя исчезло/подменено или не подтверждается инвентаризация, measurement недоступно, приём закрыт. Полный journal/prebook позже обеспечит сохранение самого резерва при таком сбое; пока это только неиспользуемый product gate и storage fault evidence.

Чтение descriptor: открыть тот же закрытый key no-follow/nonblocking, проверить owner/mode/regular/nlink, точную длину≤1МиБ и SHA actual bytes, strict UTF8. Сравнить inode/dev/size/mtime_ns/ctime_ns до/после и после hash; проверка имени не должна разыменовывать symlink. File исчез/изменён/обрезан/другойhash/битаяUTF8 — SHARED_CONTENT_UNAVAILABLE, без empty/inline fallback. Размеры/name syntax в metadata не дают права читать другой private prefix.

## SHB07-META — migration0002 и resolver

Для SharedRevision/SharedDraft добавить:

| Поле | Inline legacy | File mode |
|---|---|---|
| storage_kind | literal `inline` (Python default и DB default) | literal `file` |
| file_key | пусто (Python default и DB default) | closed key выше |
| byte_size | null | integer0..1048576 |
| file_sha256 | пусто (Python default и DB default) |64 lowerhex SHA256 |
| существующее html | сохранён без изменения | пустая строка |
| существующее payload_hash | прежний | должен равняться file_sha256 |

DB CheckConstraint запрещает неизвестный storage_kind, смешанный inline+file descriptor, malformed file metadata и непустой html в file mode. Record-level validation дополнительно проверяет совпадение UUID/fan-out key и hash; DB pointer не переписывает immutable историю. Изменение default не переводит старые строки в file автоматически. Migration0002 только AddField/constraints; не удаляет и не переносит прежние html bytes, не делает массовых FS операций внутри migration. Старые сохранённые даты/UUID/hash/current/draft/pins/AssetUsage остаются неизменными.

Уточнение координатора после D-348/DEV07-SH-RESUME-002: **все существующие корректные legacy inline строки сохраняются**, включая непустые снимки/черновики; предположения «shared данных ещё нет» и требования отказать только из-за наличия старого HTML в первом инкременте нет. Это additive schema migration без conversion/deletion. Некорректные новые file descriptors отвергаются отдельно и не подменяются старым inline.

Конкретный план полей для принятого Django5.2: `storage_kind=CharField(max_length=6, default='inline', db_default='inline')`, `file_key=CharField(max_length=96, blank=True, default='', db_default='')`, `byte_size=PositiveIntegerField(null=True, blank=True)`, `file_sha256=CharField(max_length=64, blank=True, default='', db_default='')`. DB defaults сохраняются после migration, чтобы доверенный raw SQL fixture, не перечисляющий новые поля, получал корректный legacy descriptor; одного Python default недостаточно. Поддержку/DDL точных полей подтверждают migration review и фактический локальный прогон на принятой версии, не изменение версии Django. Для file mode explicit metadata и CHECK обязательны, defaults не превращают неполную file запись в допустимую.

Обязательный `content_html(record_or_descriptor, storage=None)` выбирает **ровно** storage_kind: inline возвращает сохранённый HTML, file вызывает verified reader. Не делать `record.html or storage.read(...)`, не возвращать inline при missing blob. Неподдерживаемый schema_version истории остаётся owner-readable как безопасные данные при доступных bytes; схема исполнения/whole restore отдельно проверяется как раньше.

Тяжёлое чтение/hash≤1МиБ выполняется вне content/auth transaction. Locked context собирает только immutable source descriptor и stamp по storage_kind/key/bytes/hash/payload_hash/IDs; после освобождения locks inspect_context разрешает descriptor в source_html. Перед commit будущий сервис заново проверяет metadata/source stamp и FS evidence под принятым протоколом. Нельзя спрятать filesystem payload read в ORM property, которую вызывает select_related/current transaction. Editor/history/version/compare/restore/check не должны случайно продолжить прямое чтение `.html` для file mode; проверяется inventory существующих call sites по подтверждённым файлам.

## SHB07-MEASURE — allocation, orphan и journal inventory

Scanner считает всю **свою** область shared-content, не только referenced descriptors: root/blobs/fan-out/journal directories, все immutable blobs, partial/orphans, journal records. Медиа фотографии/публичные variants/чужие private paths не обходятся. Root отсутствие считается пустым только когда существующий доверенный parent был проверен и no-follow lookup конкретного shared-content вернул ENOENT; unreadable/missing MEDIA root, invalid ancestors или I/O error не равны0.

Для каждого собственного object учитывать actual allocated bytes=`st_blocks*512` (st_blocks POSIX512-byte units) и отдельно logical st_size; directory allocation также входит. Нельзя выдать сумму payload lengths за footprint, исключить orphan, не заметить sparse allocation или прибавить directory дважды. Поддерживаемый FS/evidence st_blocks должны быть доступны; неизвестная семантика — fail closed до допуска profile. Дополнительный filesystem metadata/allocator worst-case reserve пока **не доказан**; actual st_blocks не называется верхней границей всех скрытых FS затрат.

Первый инкремент сообщает только `actualAllocatedBytes` и явно `fsMetadataReserveAvailable=false`, `reserveBytes=null`, `profileAvailable=false`. Ненулевой минимум «на inode» не выдумывается и не подставляется вместо actual st_blocks: такой floor ещё не подтверждён. Нулевая allocation отдельного пустого объекта не означает доказанного отсутствия скрытых FS затрат. Неполный upper bound запрещает включение product writes даже при небольшом измеренном actual allocation.

Scanner — descriptor-relative, не следует symlink, проверяет owner/mode/nlink/closed names/type; unexpected file/name/subdirectory, hardlink/FIFO/socket/device, duplicate identity или mutation во время scan закрывают measurement. Orphan с допустимым именем учитывается независимо от DB refs. Для orphan inventory не требуется читать/исполнять HTML и подтверждать schema; некорректный UTF8 orphan всё равно занимает место. Ссылочный read при этом корректно откажет.

Уточнение SH2-REV001/002 до первого прогона: ENOENT для `private` под успешно открытым существующим MEDIA_LIBRARY_ROOT также подтверждает отсутствие собственной области; MEDIA root missing/unreadable/symlink по-прежнему ошибка, не0. Перед complete scanner повторно открывает **каждый** сохранённый entry от pinned root dirfd, по компонентам O_NOFOLLOW, и сверяет все записанные inode/dev/mode/owner/nlink/size/blocks/mtime/ctime facts и named-leaf identity; затем проверяет, что открытый root по-прежнему связан с фиксированным именем MEDIA_LIBRARY_ROOT/private/shared-content. Это ловит, например, рост раннего файла во время обхода позднего без изменения mtime каталога. При absent-root дополнительно повторяется no-follow отсутствие конкретного компонента и named identity его проверенного parent. Неполная/неуспешная повторная проверка не возвращает complete=true.

Это metadata revalidation, **не атомарный снимок FS против несотрудничающего процесса с правами того же UID/root**. Будущие product writers/cleanup обязаны участвовать в content domain/prebook protocol; сейчас product writers выключены. Обход чужим процессом в обход этого домена не объявляется отражённой угрозой. Нового lockfile/тома/службы этот инкремент не вводит.

Уточнение SH2-REV003: одного named-root bind недостаточно для pinned `blobs`/fan-out dirfd. Перед успешным выходом read/write из `_parent` повторно открываются текущие `blobs` от root dirfd и текущий fan-out от заново открытого `blobs`, каждый O_DIRECTORY|O_NOFOLLOW, с проверкой type/euid/0700 и совпадения dev/inode с удерживаемыми дескрипторами. Mtime каталога для этого bind не используется: собственная запись законно меняет его. Rename/replacement любого из этих двух parent anchors даёт отказ до выдачи descriptor/HTML; исходные bytes не перезаписываются/автоматически не удаляются. Если вмешательство оставило неизвестную/неправильно названную область, scanner также отказывает, а не сообщает0.

Техническая граница scan первого инкремента: до32768 entries суммарно и до256 fan-out directories; при превышении — диагностический отказ, без удаления и без принятия частичного результата. Это bound инструмента измерения, **не новое бизнес-правило очистки истории**. В контракте scanner возврат complete=true разрешён только после полного проверенного обхода; fingerprint содержит stable ordered relative name/dev/inode/mode/nlink/size/blocks/mtime/ctime metadata, не payload. Ограниченный metadata-only scan может выполняться под content domain; чтение/hash всех HTML файлов туда не переносится. Scanner failure не обновляет cached SharedBudget нулевыми значениями.

Journal namespace первого инкремента: `journal/<operationuuidhex>.json`, regular0600/owner/nlink1, каждый record≤4096UTF8B; directory и actual allocated record bytes всегда учитываются. **Writer/release/finalize journal ещё отсутствуют.** До будущего prebook schema-профиля любое наличие journal record делает reservation readiness=false; scanner обязан вернуть фактические journal count/allocatedBytes (или диагностический неполный inventory), но не трактует неизвестный record как нулевой pending reserve и не позволяет mutation. Для будущего профиля отдельно потребуются exact duplicate-key-free JSON schema, block/operation/fingerprint/profile bindings, bounded pending count/bytes и durable reservation reconciliation. Нельзя считать наличие синтаксически похожего JSON уже доказанной authoritative бронью.

quota.measure возвращает отдельно actual PG bytes прежних8 root tables (indexes/TOAST/forks включены один раз), actualOwnFsAllocatedBytes/actualAllocatedBytes, blob/orphan/journal counts/bytes, actualCombinedBytes и reservationReadiness=false/profileAvailable=false/fsMetadataReserveAvailable=false/reserveBytes=null. Если public UI использует usedBytes, это actualCombinedBytes, а не только PG. Warning75% рассчитывается от combined actual bytes; будущие held/transient/attributable AssetUsage/audit/FS metadata резервы не считаются покрытыми этой суммой и не получают fabricated0. При count10000/insufficient actualbytes можно показать честный отказ; unknown reservation gate остаётся закрыт независимо от actual vacancy.

## SHB07-COMMAND — порядок первого инкремента

В product draft/apply/restore pipeline вызов quota.reserve_locked остаётся до любого stage_file/write_new. При нынешнем unvetted gate product request не создаёт ни blob, ни журнал, ни metadata/receipt/version. Нельзя заранее записать файл ради proof, а затем назвать получившийся orphan не связанным с quota. Check принимает HTML из RAM, нормализует existing child и проверяет текущие source descriptors/Asset, но не сохраняет входящий HTML в private blob.

Положительные storage tests вызывают low-level SharedStorage **на собственных тестовых объектах**; fixture может создать file-mode row с реальным descriptor для испытания owner read/check/history. Это подготовка данных в выделенной unit DB/медиа области, не скрытый успешный пользовательский Apply. Профиль не включается через env/debug/тестовый bypass. Global prebook/PG small-batch bound/attributable ledger+audit и accepted mutations — следующий отдельный инкремент после review.

## Сценарии до кода

| ID | Действие и независимый oracle |
|---|---|
| SHB07-001 | Новый trusted server key: UTF8 малый/ровно1МиБ bytes→write/fsync→actual bytes SHA/length/read roundtrip;0600/owner/regular/nlink1 и fan-out verified. No product Apply claim |
| SHB07-002 | >1МиБ, invalidUTF8, traversal/absolute/foreignprefix/mixedcase/mismatchedfanout key, existing leaf/symlink/hardlink/FIFO/wrongowner/mode → отказ без overwrite/foreign traversal |
| SHB07-003 | Повреждение/обрезка/подмена/missing file/wrongSHA/invaliddescriptor/mutation during read → явный refusal; file mode не возвращает record.html/пустую строку |
| SHB07-004 | Fault до/во время write/filefsync/dirfsync: no durable success descriptor; partial/orphan counted by actual blocks; no automatic orphan deletion. Не имитировать crash-consistent globalbook |
| SHB07-005 | Scanner actual root+directories+referenced/orphan files, ledger-independent allocation, complete inventory и fingerprint; journal file counted, readiness=false; unknownentry/error/overbound → unavailable, не0 |
| SHB07-006 | Migration0002: actual inline oldUUID/hash/html/current/draft/refs unchanged; metadata constraints reject mixed/unknown/malformed descriptors; no applied0001 rewrite |
| SHB07-007 | File-mode synthetic header/footer actualowner read/check/history/compare/restore-source resolves real bytes, literaloldphone и separateblocks retained; missingbytes refuses. Text shown escaped, no directpublic blob URL |
| SHB07-008 | Unknownprofile real draft/apply/restore still503; actual FS+DB+usage/receipt manifests unchanged, input retained; compare before/after ownblobinventory confirms no staged incoming file |
| SHB07-009 | quota actualCombinedBytes equals actual8PGroot sum+completeOwnFS allocation; cache/fakecount не oracle; warning arithmetic observes combined values. Полные256МиБ/10000/concurrency reservation tests пока не выполняются |
| SHB07-010 | Existing shared17/Page402 regression cohorts remain separate; newexactfrozen source tests authoritative for changed code. Existing browser/Nginx evidence не переносится автоматически на blob method |

## Незавершённые ворота

Первый инкремент не закрывает simultaneous-last-reserve, journal crash/replay/release, PG metadata/index/fork/AssetUsage/audit attribution profile, полное восстановление DB+FS одного поколения, public nav/renderer и accepted Draft/Apply/restore. Полный backup shared теперь обязан включать pointers+blob+journal manifests; DEV-22/23 не объявляются реализованными. До product кода первого инкремента нужны independent review этого контракта и отдельные QA сценарии; до включения записей — новый tested reservation profile и independent review его фактов.
