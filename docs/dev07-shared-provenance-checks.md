# DEV07-SH3-FK — постоянная принадлежность provenance

2026-11-01. DEV-07 около96%, этап8 около20%. Предварительный контракт SH3-FK-001/P1 до кода/независимого ревью. Основания: dev07-shared-results.md §остаток, dev07-review.md, dev07-editor-contract.md §6–7, REQ-017/018/028/029/050, AC-DTL-017/AT-117. Владелец поручил продолжение локальной DEV-07; профиль записи по-прежнему выключен. Старый сайт/VPS, зависимости и ресурсы не меняются.

## Проблема и ограниченный результат

В применённой0001 FK `shared_source_same_block`, `shared_receipt_source_same_block`, `shared_receipt_base_same_block` ссылаются на живой SharedRevision. Постоянная квитанция/новая версия тем самым удерживает старое HTML-тело навсегда, хотя это только provenance, не действующий pin. Нужна новая0003, без изменения0001/0002 и без CASCADE квитанций. Этот инкремент меняет identity/provenance и честное чтение результата; сам ручной cleanup endpoint и включение Apply не входят.

## Схема0003: существующая identity-таблица

Расширить SharedIdentityReservation nullable `block=ForeignKey(SharedBlock, PROTECT)`, добавить UNIQUE(block,id,kind). PK id и существующий kind не меняются; новой tombstone-таблицы нет, quota продолжает измерять те же8 PG roots, включая новые индексы. Null допустим только для legacy reservations, чей уже удалённый и нигде не упоминаемый объект нельзя однозначно связать с блоком; такую identity всё равно нельзя переиспользовать.

Для типизированных provenance FK добавить внутренние поля с Python+DB default `sharedrevision`, editable=False и CHECK ровно этого значения: SharedRevision.source_identity_kind; SharedReceipt.source_identity_kind/base_identity_kind. Заменить три перечисленных live FK на composite FK `(block_id,source_revision_id,source_identity_kind)` / `(block_id,base_revision_id,base_identity_kind)` → SharedIdentityReservation(block_id,id,kind). Nullable source/base остаются nullable. Таким образом нельзя подставить ID другого блока **или draft/stage ID того же блока** вместо revision identity; одного FK(block,id) для этого недостаточно.

SharedReceipt дополнительно получает nullable result_identity_kind: apply→sharedrevision, draft→shareddraft, restore_prepare→sharedrestorestage. Для ненулевого result_id kind обязателен и соответствует закрытому action map, для null result_id kind=null. Новый composite FK(block_id,result_id,result_identity_kind) ссылается на тот же permanent ledger. Неизвестный legacy action/result требует отдельного разбора и останавливает migration, а не получает угаданный тип. Будущие cancel actions добавляются своим контрактом, не этим default. Receipt хранит исторический result UUID, а не FK на живое тело.

Новые Record.save reservations всегда получают block: SharedBlock→собственный UUID, Revision/Draft/Stage/Receipt→их block_id, BasePin→block его live revision. INSERT reservation и INSERT record остаются в одной content transaction; self block FK должен быть DEFERRABLE INITIALLY DEFERRED, поскольку reservation блока создаётся до самой строки блока. Первичный ключ reservation и проверки PageIdentity/AssetUsage сохраняют nonreuse. Нельзя автоматически «привязать заново» уже существующий ID другого kind/block.

## Backfill и безопасность миграции

Одна atomic0003: Add nullable block/внутренние kind поля → точный исторический backfill → новые UNIQUE/CHECK/FK → замена старых трёх provenance FK. Обновления0001/0002 нет. Источники доказательства blockbinding: существующие Block/Revision/Draft/Stage/Receipt; BasePin через его revision; receipt source/base как revision provenance и result через закрытый action map. Каждое упоминание требует существующую reservation с правильным kind; создаётся **только новая привязка block** существующей identity, не новая identity взамен отсутствующей.

До backfill собрать все ID→(kind,block) свидетельства и проверить согласованность. Missing reservation, противоречивый kind, один ID у двух блоков, неизвестный action с результатом, missing required live target — фиксированный отказ/rollback всей migration без удаления/исправления данных наугад. Уже удалённый result допустим, если permanent reservation существует и все receipt-свидетельства однозначно дают его block/kind. Неупомянутые legacy tombstones остаются unbound и недоступны как provenance target.

Существующие id/kind ledger, UUID/body/hash/storage descriptor/date/current/draft/stage/pins/AssetUsage/receipt fields сохраняются побайтно по прежней проекции. Новые block/type поля проверяются отдельным oracle. MigrationExecutor тест0001→latest должен сравнивать все **старые** поля identity и отдельно правильность нового binding; не удалять identity из manifest ради PASS. Обратная0003 допустима только пока все provenance снова имеют live target; после разрешённого удаления тела автоматическое восстановление live FK невозможно, reverse должен явно отказать, а не удалять receipts/tombstones. Проверка обратимости — до destructive step, внутри migration transaction.

## Live защита и terminal stages

Оставить live FK current revision блока, SharedDraft.base_revision, SharedBasePin.revision и source/base **held** restore-stage: текущие/действующие основы удалять нельзя. Текущая таблица Stage сохраняет FK и для terminal rows; эту зависимость нельзя игнорировать.

Принятый ограниченный путь: при будущей явной ручной очистке подходящей истории terminal Stage (consumed/released/invalidated) может быть отдельно перечислен в актуальном подтверждении и удалён как metadata dependency в той же transaction перед телом. Его permanent identity и receipt остаются. Held Stage не удаляется и продолжает блокировать cleanup. Этот инкремент не вводит автоматическое удаление stages, не меняет их status и ничего не чистит при migration. До реализации такого confirmed cleanup терминальные stage FK остаются **явным gate полной очистки**, а не заявлением о готовности cleanup. QA показывает допустимость удаления только после явного удаления terminal fixture; не выдаёт fixture SQL за действующую кнопку владельца.

## Replay/gone без воскрешения

Result lookup/повтор сначала проверяют свежие owner/session/generation и принадлежность receipt блоку; exact actor/action/request fingerprint обязательны. Затем читается receipt до требования живого старого source/base/draft/proof и до новой reservation. Квитанция не создаёт новую версию, не переносит payload и не требует вернуть старое тело ради replay.

При живом результате вернуть тот же UUID/resultCode, replay=true,gone=false. Если typed result уже отсутствует — тот же UUID и исторический resultCode плюс replay=true,gone=true; это сообщение «операция завершалась, сохранённый результат больше недоступен», не новый успех применения. UI/adapter обязаны отдельно проверять gone и не показывать «Сохранено сейчас». Отсутствующий source/base сам по себе не делает живой result gone. Fingerprint mismatch409, чужой block/type constraint violation, устаревшая/чужая сессия отказ; ни одна ветка не восстанавливает тело по повтору. Исправление HTTP/child порядка для stale/consumed source — обязательная часть этого ограниченного replay результата, не обход авторизации.

## Предварительные проверки

| ID | Проверка и oracle |
|---|---|
| SHP07-001 | Actual0002→0003: непустые inline/file revisions/draft, current, pins, held+terminal stage и receipts; все прежние поля/bytes/refs прежние, bindings/types точные; applied0001/0002 hashes неизменны |
| SHP07-002 | Конфликт ID/block/kind, missing reservation, unsupported receipt action/result → migration FAIL/rollback без частичного backfill; known deleted-result reservation корректно backfilled |
| SHP07-003 | Прямой SQL source/base/result другого блока или неверного kind того же блока отвергается actual PostgreSQL FK/CHECK; unbound reservation не пригодна для provenance |
| SHP07-004 | Допустимое старое тело без current/draft/pin/held dependencies удаляется trusted test command; source/base provenance новой версии/receipt и permanent identities остаются; UUID повторно выдать нельзя |
| SHP07-005 | Current/draft base/pin/held stage по-прежнему блокируют удаление; terminal stage сначала явно удаляется fixture-командой с сохранением receipt/identity, затем old body может исчезнуть; live cleanup UI не объявляется выполненным |
| SHP07-006 | Fresh owner exact replay/result lookup после body/result удаления возвращает original receipt UUID+gone без нового snapshot/refs/receipt; deleted source при живом result не даёт ложный gone; changed request409/old session/employee denied |
| SHP07-007 | Actual quota8 roots/индексы учитывают schema growth, profileAvailable=false сохраняется; прежние shared/file/read regression отдельно и exact frozen source для нового кода |

Спорные места для независимого ревью: reverse0003 preflight после tombstone-only history; terminal metadata removal требует будущего явного cleanup confirmation; nullable legacy binding не должен разрешить новый unbound record. До закрытия конкретных замечаний код не меняется.
