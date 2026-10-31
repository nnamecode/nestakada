# DEV-05 — технический проект Page-версий, Stable и восстановления

2026-10-31. **Ограниченный код DEV-05 завершён и независимо проверен:150 PostgreSQL tests PASS (133.008s),11 foundation PASS (7.2s),15 реальных Chromium/HTTP групп PASS; REV001–008 закрыты.** Итог и точные границы допуска — [dev05-implementation.md](dev05-implementation.md); это не закрытие всех приёмочных сценариев будущего редактора и публикации. Основание D-327/D-328, D-044/046/259–262/294, MAN-01/02, PR-08 и UI-S007–013. Рабочая область исполнителя — только `app/page_versions/**` и этот документ. Настройки/общие URL/навигация/окружение остаются координатору. Этот документ не разрешает rich editor/санитайзер DEV-07, публикацию дерева/URL DEV-29 или замену прав accounts.

## 1. Согласованные инварианты и техническая граница

Каждый успешный content commit создаёт immutable автоматическую версию и согласованно меняет current; обычная текущая входит в10. Manual checkpoint копирует только показанную сохранённую currentRevision, не owner draft/unsaved. История/Page payload неизменны; отдельно изменяемая владельцем metadata не переписывает реальный created_at/author. Stable — отдельная защита конкретной версии, не публикация и не наследуемый тип.

Сотрудник читает все версии назначенной Page, включая ручные/Stable и связанные допустимые изображения. Он не видит отдельный owner draft и не меняет owner-only поля. Восстановление: сравнение → явная подстановка в будущий редактор → его отдельное сохранение. Выбор/просмотр/stage не переключают current. Существующий owner-only `/manage/media/files/` не ослабляется.

Начальный producer — доверенный внутренний Python API, с типизированными DTO. Generic HTTP «сохранить этот JSON/HTML» не создаётся. Исторические HTML-строки показываются **только escaped** (как текст/код), никогда Template.compile/`safe`/неэкранированный innerHTML/iframe. Нормализация HTML, проверка ссылок, профили защищённых DOM-узлов и реальный rich editor остаются DEV-07. Тестовый DTO из доверенных fixture не выдаётся за проверку публичного редактора.

## 2. Закрытая схема snapshot `page-content-v1`

Ровно13 верхних ключей, неизвестные/повторные ключи, неверные scalar/union types и неизвестная версия схемы отклоняются целиком. Это storage schema, не новая коллекция визуальных блоков:

```json
{
  "schema_version": "page-content-v1",
  "page_kind": "article",
  "intro_text": "",
  "main_text": "",
  "price": null,
  "h1": "",
  "title": "",
  "description": "",
  "indexing_allowed": true,
  "main_image": null,
  "preview_image": null,
  "embedded_images": [],
  "layout": []
}
```

`page_kind` берётся из текущего Page.Kind, не из доверия к HTTP и не меняется этой операцией. `intro_text/main_text` — уже нормализованные producer строки, сохранённые без повторного рерайта. Профиль будущего producer: область≤1MiB исходного HTML/200000 текстовых символов/20000 DOM nodes/depth32, без усечки; schema engine ограничивает UTF-8/тип/целостность, но не объявляет себя отсутствующим санитайзером. Полная проверка DOM/ссылок/защищённых атрибутов должна предшествовать доступу пользовательского текста к этому API в DEV-07. H1/title≤255, description≤1000 с допустимой пустотой; allow_index — явный bool, без заполнения из текста/названия. Не применять новые нормализаторы к старым материалам молча.

**PriceV1**: null либо ровно `{columns,rows}`. Columns: упорядоченные `{id:UUID,label:plain_text}`. Rows: упорядоченные `{id:UUID,label:plain_text,cells:[...]}`. Cell — закрытый union `{column_id:UUID,kind:"text",text:plain_text}` либо `{column_id:UUID,kind:"amount",amount:decimal_string,from:bool}`. Числа не float; отсутствие/текст не превращаются в ноль. Связь каждой ячейки с существующей колонкой, уникальность row/column UUID, порядок и прежний row ID сохраняются. Профиль из analytics-content-detail:500rows/32columns/10000cells, label≤500, cell text≤1000, неотрицательная finite decimal≤999999999.99. Отображение матриц, «за ось» и правила сумм главной не изобретаются engine: producer сохраняет значения, будущий прайс-модуль использует действующие D-230–233/255–256. Никакого минимума из произвольной цифры HTML.

**ImageV1**: null либо закрытый `{asset_id:UUID,alt:plain_text,alignment:"left|center|right",width_px:null|positive_int,height_px:null|positive_int}`. Alt≤300, может быть пуст. Измерения — нормализованные producer значения представления, не CSS/путь/URL и не новые лимиты raster input. Детальная допустимость оформления относится к DEV-07; raw arbitrary widths из HTTP не принимаются сейчас. `embedded_images` содержит те же записи с дополнительным собственным `id:UUID`, уникальным в snapshot, для привязки узла/места; переиспользование одного Asset в нескольких местах допускается без копий файла. Не создаётся внешний src/data URL. Main/preview могут отсутствовать; цепочка D-251 не заменяется случайной первой картинкой.

**LayoutV1** — ordered descriptors, отражающие расположение уже согласованных полей/ссылок; это не новый редактор visual block types. Закрытые варианты:

- `{id:UUID,kind:"text",field:"intro_text|main_text",protected_nodes:[{id:UUID,reference_id:UUID,fingerprint:sha256}]}`;
- `{id:UUID,kind:"price"}` — поле PriceV1;
- `{id:UUID,kind:"image",image_id:UUID}` — существующая embedded_images запись;
- `{id:UUID,kind:"protected_ref",reference_id:UUID,fingerprint:sha256}` — ссылка на доверенный server component, без его произвольного config/кода.

UUID layout уникальны, все ссылки разрешаются в своей Page/snapshot, fingerprint каноничен. HTML и список protected_nodes согласует доверенный producer; engine не доверяет клиентскому заявлению «это безопасный узел». Реестр компонентов/полная block compatibility — DEV-07: неизвестный protected_ref или неизвестный layout kind не восстанавливаются частично, а дают безопасную несовместимость. До появления реестра допустимы fixture snapshots с известными text/price/image slots; выдуманные визуальные типы не объявляются поддержанными. Width/height и neutral slot encoding — конкретные технические предложения на это ревью, не разрешение нового HTTP-профиля.

**Исключено из snapshot/write/restore:** Page.name, UUID/тип как редактируемое значение, URL/alias/redirect, parent, tree position, is_published, Header/Footer и их revisions, shared site settings/contacts, PageGrant/права/пароли, Stable flags/protection, owner draft, внешний head. Эти данные нельзя вернуть добавлением неизвестного JSON-ключа. Current показывается как сохранённая content revision; фактический public renderer/validator/external admission не подменяются engine и подключаются своими задачами.

## 3. Предлагаемые модели и границы атомарности

`PageContentState`: OneToOne Page(PROTECT), current_revision(FK PROTECT), monotonic revision sequence. Состояние появляется из явно разрешённого trusted initial snapshot; до первой правки сотрудника initial PageRevision уже существует. Инициализация не публикует Page и не создаёт начальные данные из пустых placeholder произвольно.

`PageRevision`: непереиспользуемый UUID, Page(PROTECT), sequence(unique per Page), schema, immutable payload/canonical SHA256, kind(initial/automatic/manual), actual aware UTC created_at, author ID, source revision UUID как историческое значение без FK, сохраняющего всю цепочку. Source может выбыть; история не имитирует существование удалённого payload. Identity/payload/serverdate/author/type не редактируются.

`RevisionMetadata`: OneToOne revision, metadata revision token, name≤200, comment≤1000, aware manual_date либо null; default label «Контрольная версия» для явно пустого manual name. Пользовательская дата не меняет created_at/sequence/author/prune. Техническое предложение: HTTP edit metadata сначала только manual по MAN-01; расширение на automatic не подразумевается без подтверждения root-чтения действующих требований. Дата необязательна при отсутствии; если передана — явная зона, без нового диапазона лет. 1960/2099 должны пройти; дата ОС/наивное время не подставляются молча.

`RevisionProtection`: OneToOne конкретной revision, marked_by/marked_at, protection token, цвет из принятого server UI palette (не произвольный CSS). Payload/metadata не меняются от Stable. Palette перед кодом сверяется с принятым оформлением; engine хранит один технический stable state, не вводит новые смысловые статусы.

`OwnerDraft`: отдельный OneToOne Page, UUID/draft revision, immutable-public base_revision(FK PROTECT), payload, owner author/date. Сохранение draft обновляет только его revision и draft media refs, не public current/общую историю; один актуальный draft, не неутверждённая история черновиков. Employee commit оставляет draft без изменений и делает его базу устаревшей; последующий owner commit не перетирает employee silently.

`VersionBasePin`: revision + holder_kind(owner_draft/restore_stage/active_operation) + holder UUID; FK PROTECT/unique. `RestoreStage` содержит только actor/Page/source/base IDs, current permission/schema/protected-structure stamps и статус held/consumed/released; полный пользовательский ввод и отдельный duplicate snapshot в operation ledger не хранятся. Stage candidate вычисляется из сохранённых pinned source/base; возвращаемый DTO держится в памяти/DOM будущего редактора. Pin создаётся только явным POST stage/началом сохраняемой операции, не от обычного просмотра истории. Отмена/release — отдельное явное действие; no auto TTL/no молчаливое освобождение abandoned bases. UI/owner resolution длительных holds нужно явно показать; не добавлять скрытое принудительное снятие удержания ради лимита.

Уточнение технического ревью: restore_stage/active_operation освобождаются своим explicit cancel/consume либо terminal semantic invalidation вследствие явного изменения current/generation/grants. Причина/actor/operation provenance фиксируются в той же транзакции до prune. Это не таймер/сборщик устаревших браузеров и не новое право владельца отменять чужой stage. OwnerDraft base **не освобождается** от одной смены current: сохранённый закрытый draft и его основа остаются до явного сохранения/ребазы/отмены. Persistent consumed receipt не содержит FK pin на snapshot. Если10 ordinary остаются актуально удержанными, операция отказывает атомарно.

Фактическая фаза реализации — ленивая проверка в следующем version command, который выполняет prune (content commit/manual create/demotion), перед расчётом ordinary-лимита. Accounts.set_grant/reset/disable не меняются и не вызывают немедленный version hook; права уже закрыты в accounts. Terminal actor/operation — автор команды, которая обнаружила семантическую неактуальность и записала invalidation в своей транзакции, не обязательно исходный автор отзыва. OwnerDraft в эту проверку не входит.

`VersionIdentityReservation`: минимальный UUID tombstone для revision/draft/stage/operation, не удаляемый prune. Блокирует повторную выдачу уже использованного ID; не сохраняет старые тексты/пароли.

Все writes: `transaction.atomic`, CONTENT_LOCK7342810401 → AUTH_LOCK7342810301 → актуальные user/profile/grants → Page/current/version/protection/pins по стабильному UUID-порядку → media ledger. Выход за лимит/отказ snapshot/refs/audit/receipt откатывает **всю** операцию, включая выбранные prune candidates. Никакого сначала prune, потом попытаться сохранить. Нет сети/decoder/внешней сборки под этими locks. Проверка связи Asset и сохранённых manifests выполняется локально; физического unlink/копирования медиа engine не делает.

MediaUsage: current_page consumer=PageUUID; ordinary_version consumer=RevisionUUID; stable_version consumer=RevisionUUID; draft consumer=OwnerDraftUUID, slot — детерминированное место из ImageV1/LayoutV1. Ordinary→Stable переключает только соответствующие version ledger kinds в одной транзакции; current usage остаётся отдельным. OwnerDraft удерживает свои Asset независимо от current. RestoreStage удерживает source/base через pins их существующих revision refs; новый восьмой media kind не вводится. При prune/delete удаляются только refs именно исчезающей версии; последний ref делает Asset лишь кандидатом D-263, не удаляет байты.

## 4. Commit, лимит и manual

`commit_employee(actor,page,base_revision,TextPricePatch,expected_generation,operation_id)` — внутренний producer API: актуальные allowed_fields(accounts), тип/назначение Page, только выданные intro/main и отдельное price. Начало от **current**, не OwnerDraft и не произвольный supplied whole snapshot. Protected nodes/медиа/структура/H1/SEO остаются текущими. Все запрошенные разрешённые изменения проверяются вместе; устаревший base/право/схема — полный отказ, ни одного нового current/истории/refs.

`save_owner_draft(...)` и `commit_owner(...)` различаются действием и основанием. OwnerDraft не становится публичным от сохранения/просмотра/ручного checkpoint. Publish-tree/изменение is_published/URL не входит в commit_owner. Будущий DEV-07/29 должен вызвать точный API, а не raw ORM.

После нового auto/manual или demote выполняется детерминированный ordinary-prune по `(created_at UTC, sequence, UUID)`; пользовательская дата/metadata не участвуют. Ordinary current считается в10, но не удаляется. Stable исключены из count и кандидатов; pin/OwnerDraft base/active operation защищены от удаления. Если невозможно разместить новую ordinary без удаления защищённой базы, операция отклоняется целиком с причиной, а не тайно снимает pins/оставляет11. Назначение Stable может уменьшить ordinary count — искусственно не восполняется. Demote не меняет дату, и старая подходящая версия может сразу выбыть по лимиту; current остаётся.

`prepare_manual`: показать точную Page/URL/current ID/source actualdate; подписать owner/generation/Page/source/current stamp + metadata draft. `create_manual`: перепроверить base, копировать payload именно source current, создать **один** ordinary manual, media refs/audit/receipt/prune; не менять current pointer, Page, owner draft или unsaved DOM. Metadata даты/автора не принимаются как серверные поля. Manual create/delete не требуют нового пароля.

`prepare_delete_revision` + `delete_revision`: подписать точный target UUID, Page/name/URL context, type/metadata token/created_at/author/protection/pin state; подтверждение не список-индекс. В commit отказ при current/Stable/pin/используемой базе, изменившихся показанных условиях. Уже отсутствующий target возвращается как gone, не удаляется соседняя версия. Никакой новой PageRevision ради удаления, никакого filesystem delete. Удаление всей Page/истории/Stable — DEV-29, не этот endpoint.

## 5. Stable и подтверждённый просмотр

Read/compare выдаёт подписанный view receipt: actor/generation/Page/revision UUID/payload SHA/metadata token/schema/protection stamp. Это свидетельство выдачи конкретного закрытого представления, не доказательство того, что человек прочёл каждый символ. GET ничего не публикует/не создаёт новую PageRevision и не освобождает pins.

`set_stable` — owner-only POST с exact view receipt, protection state и operation UUID; актуальные owner/metadata/source/schema проверяются под общим lock. Не меняет current/payload/draft, обновляет только защиту и её media ledger. Stable не наследуется последующим commit/manual.

Schema check при назначении Stable — только equality/view binding сохранённого schema/hash/identity, **не** проверка пригодности к restore. Безопасно просмотренный несовместимый исторический snapshot можно защитить; его payload/media не переинтерпретируются при promote. Restore такого snapshot по REQ023 по-прежнему отклоняется целиком.

`prepare_demote` показывает exact version/current status/старую дату и актуальные последствия ordinary-prune; confirmation связывает current revision, ordinary/protection/pin composition digest и metadata token. `demote_stable` отдельно проверяет **текущий** пароль nesadmin, текущую generation и подтверждённый состав; password не часть operation fingerprint/log/receipt даже в hashed виде. Любое существенное изменение требует нового подтверждения. После снятия применяются обычные правила, а не новая дата. Replay также требует current password, а не повторяет прежнюю успешную аутентификацию.

## 6. Restore без скрытой публикации

`prepare_restore` проверяет право чтения Page/version и выдаёт сравнение + signed preparation (source UUID/schema/hash/meta, current base ID, permission profile, generation, protected-node/layout fingerprints). Не создаёт current/automatic/manual и не заменяет ввод. Подготовка не раскрывает owner draft.

Owner candidate включает разрешённые snapshot поля H1/SEO/text/price/image refs/layout. Employee candidate проецирует **только** текущие granted intro/main/price поверх current; отличия исключённых H1/SEO/медиа в старом snapshot сами по себе не разрешают их перенос. Для связанной разрешённой области несовместимые/удалённые protected nodes, недоступные Asset, изменившаяся схема/тип или отозванный requested field дают **полный отказ всему candidate**, не частичное восстановление. Unknown component compatibility остаётся безопасным отказом до DEV-07 resolver, а не угадыванием.

`stage_restore` — защищённый POST с preparation и явным подтверждением замены несохранённого ввода; повторяет все проверки, создаёт source/base pins + minimal stage, возвращает typed candidate для DEV-07. Текущая content revision/публикация не меняется. Можно показать отдельную **read-only escaped** prefilled карточку stage сейчас; кнопки «восстановить и опубликовать»/raw payload save не будет. Без существующего rich editor нельзя заявить прохождение browser unsaved/курсорных сценариев.

Будущий `commit_*` получает stage ID и ожидаемый current base, заново проверяет stage owner/current generation/grants/media/schema. Успех — новая automatic/current; stage consumed/pins released в той же транзакции, затем prune. Отказ оставляет stage/input и базовые удержания, не публикует часть candidate. Явная отмена освобождает только собственный stage без media unlink. UI разрешения бесхозных holds и окончательные component compatibility hooks — отдельные точные стыки этого технического ревью.

## 7. Закрытые HTTP/read-представления

Предлагаемый namespace `page_versions`, префикс `/manage/pages/<pageUUID>/versions/`: список; `<versionUUID>/` escaped read; compare; owner manual prepare/create/edit metadata/delete; Stable prepare/set/demote; restore prepare/stage/cancel. Root подключит точные URLs после ревью, не раньше. У каждой мутации POST+CSRF+server gate+generation, GET не исполняет мутации. Все private/no-store+Vary:Cookie; полные поля request в ошибки/логи не включаются.

Назначенный employee видит все **общие PageRevision**, metadata/type/actualcreatedauthor/current/Stable и их image refs; чужая Page/visitor запрещены. Отдельный OwnerDraft отсутствует в history/queryset/compare/DTO employee. Для истории вводится отдельный contextual file URL внутри Page+Revision: access проверяется заново, File.asset_id обязан реально присутствовать в refs именно этой Revision, File.kind только MAIN/PREVIEW, READY/hash pinned stream, image/webp+nosniff. Private-source всегда запрещён. Нельзя передать произвольный file UUID без Page/version context. Существующий owner-only media preview не меняется; legacy-public MIME до DEV-09 не притворяется WebP и этим endpoint не выдаётся.

## 8. Минимальный operation ledger — до кода

Технический профиль receipt согласован координатором по MAN-01:27/MAN-02:37/architecture:36/74/78: численного TTL/квоты Page operations в документах нет. Предлагается постоянный minimal consumed ledger, без автоматического TTL/роста payload. Не переносить 20000/16MiB receipt заявок или256MiB/10000 snapshot Header/Footer на Page. Последнее — отдельный бюджет **двух общих блоков**, не глобальная Page-квота.

Receipt содержит непереиспользуемый operation UUID, closed action, actor ID, Page UUID, исходный/целевой revision IDs, исходное generation binding, canonical nonsecret request fingerprint, серверный commit timestamp, closed result code и result IDs. Fingerprint — canonical DTO hash/структурные основания/метаданные; **никаких password/CSRF/sessionkey даже hash, никакого полного текста/HTML/comment в receipt/audit**. OwnerDraft payload живёт только в своём закрытом объекте, не в ledger.

UUID с другим action/actor/Page/source/target/каноническими параметрами отклоняется; прошлый UUID не становится «новым» после prune. Mutation+receipt+audit+usage+prune — одна транзакция, failed transaction UUID не объявляется успешно consumed. Успешный replay сначала проверяет актуальную identity/generation/права, затем возвращает прежний result ID. Старое request generation после смены пароля не получает старые права; новый generation не перепривязывает прежний consumed UUID. Существование result проверяется сейчас: pruned/deleted result возвращается как gone/consumed без реконструкции payload из receipt и без повторного создания. Demote replay отдельно проверяет текущий пароль. Отказ записи ledger/аудита/ресурса — полный rollback, не заранее prune.

Minimal ledger/reservations занимают служебное место и не очищаются по возрасту. Исчерпание диска/ресурса даёт атомарный отказ; численный/Page-specific budget не выдумывается. Если фактические измерения потребуют нового лимита/TTL, это отдельный профиль до введения, а не скрытый тестовый constant.

## 9. План проверок до реализации

| ID | Реальная проверка PostgreSQL/FS/API, не fake public renderer |
|---|---|
| PV-001 | Закрытый13-key schema, неизвестные/дубли/неверные типы/UUID/float price/sourcecode-like data не превращаются в исполняемый код; escaped history |
| PV-002 | H1/title255, description1000/empty; manual name200/comment1000, aware manual_date1960/2099, naive datetime refusal; no silent cut/fallback |
| PV-003 | Immutable revision payload/UUID/serverdate/author/source; UUID не переиспользуется после prune/delete |
| PV-004 | Trusted initialization создаёт source до первой employee commit, без изменения URL/tree/is_published |
| PV-005 | Employee только current+granted intro/main/price; owner draft/H1/SEO/media/layout не публикуются; права/поколение перепроверяются |
| PV-006 | Current+automatic+media refs+audit+receipt вместе; реальные DB constraint/trigger failures в snapshot/usage/receipt дают полный rollback |
| PV-007 | 11-я ordinary удаляет actual oldest eligible `(created_at,seq,UUID)`; current/Stable/pinned bases сохранены; manual_date не влияет |
| PV-008 | Stable сверх10/no inheritance/no refill, current Stable, set/prune concurrent сериализуются |
| PV-009 | Все eligible ordinary held → новый commit/manual атомарно отклонён; pins не исчезают; explicit release позволяет корректный retry |
| PV-010 | Manual клонирует показанный current, не draft/unsaved; source stale rejected; current/draft/Page поля неизменны |
| PV-011 | Manual metadata edit не меняет created_at/author/sequence/payload/Stable; дата/имя отдельно |
| PV-012 | Manual create/delete/replay same operation UUID → один result; different fingerprint/action/actor/Page denied; result pruned → gone, не recreate |
| PV-013 | Stable set требует owner+exact view stamp; metadata/version state changed → отказ; employee прямые POST denied |
| PV-014 | Demote exact composition+current password, wrong password/current generation/relevant intervening change denied; saved_at прежний, prune может удалить demoted oldest |
| PV-015 | Delete confirmation exact target; current/Stable/draft/stage-base protected; target gone не выбирает соседнюю строку; metadata change invalidates confirmation |
| PV-016 | Current/ordinary/Stable/draft actual AssetUsage ledger обновлён атомарно; физических копий/удаления байтов нет; last ref only makes cleanup candidate |
| PV-017 | Read/compare owner+assignedemployee all revisions; visitor/otherPage denied; OwnerDraft canary не выходит в employee history/DTO/files |
| PV-018 | Contextual historical image: actualRevisionRef+MAIN/PREVIEW WebP+verified SHA, employee allowed; arbitrary Asset/private-source/legacy-public denied; closed cache/nosniff |
| PV-019 | Restore prepare/stage не меняет current/Page/history; source+base pins сохраняются; cancel освобождает только stage |
| PV-020 | Неизвестная schema/deleted protected slot/media unavailable/revoked grant → whole restore отказ; allowed projection не откатывает protected exclusions |
| PV-021 | Только отдельный trusted commit stage создаёт новую automatic; stale current/grants не теряют candidate и не объединяют автоматически |
| PV-022 | Реальные concurrent commit/commit, commit/revoke, Stable/delete/prune, media-cleanup/attach, restore-stage/prune с Barrier/Event; deadlock/partial commit не объявляются допустимым результатом |
| PV-023 | UTC actual timestamps и Europe/Moscow closed-history display serializer, equal timestamp sequence tie-break; original author/date не подменяются metadata. Реальный audit export — DEV17, полный AC059 здесь не заявляется |
| PV-024 | Receipt/audit failure atomic; no password/session/CSRF/body/hash-of-password в ledger/audit; resource failure сохраняет прежнее состояние и возможности объяснить отказ |

Существующие version-time/storage/editor-boundaries e2e остаются требованиями, но не объявляются исполнимыми через несуществующий редактор/renderer/общие HeaderFooter. В bounded DEV-05 доступны realPG model/service и closed history HTTP проверки; DEV-07/29/общие блоки подключат оставшиеся public/editor сценарии. Package/dependency/Docker/VPS/push действий исполнитель не выполнял.

## 10. Что требуется от технического ревью до разрешения кода

Подтвердить конкретный13-field envelope/neutral layout descriptors и строгую несовместимость неизвестных component refs; границу trusted normalized producer без generic write; optional manual date/manual-only metadata edit; minimal permanent receipts с generation binding; pin/stage lifecycle без неутверждённого автоTTL; contextual historical preview без ослабления media gate. Это вопросы реализации/стыков root-review, а не повтор согласованных бизнес-решений владельцу. До чтения и ответа координатора код не пишется.

Техническое ревью выполнено координатором/независимым рецензентом, bounded implementation разрешена после трёх записанных выше уточнений. Checkpoint models/schema существует. Адресное DEV05-REV-001: factory больше не заменяет falsey dict/string/int/bool на пустой список; default используется только для None. Регрессии None/[] valid и {}/''/0/False invalid для обоих optional-list полей записаны в test_schema.py, исполнение остаётся координатору.

Адресное уточнение metadata: однострочный name проверяет C0 до strip, затем NFC/крайние пробелы и итоговую длину200; leading/trailing LF/TAB/CR не исчезают молча. Comment отдельно нормализует CRLF/CR→LF без strip. Добавлены точные положительные200+внешние пробелы/NFC и отрицательные control/201/1001 регрессии; служебный API остальной части checkpoint не менялся.

PV022 дополнен test_concurrency.py: actual preflight→Stable+manual→resume/prune и inverse prune→promotionGone; actual accounts.set_grant revoke во время Event-паузы после FS; actual media.confirm_cleanup orphan Y во время паузы и inverse new-reference-first→oldcleanupdenied; Stable после delete preparation. Наблюдающие wrappers вызывают реальные функции, Event ожидания находятся вне domain locks; sleep/retry/fake business outcomes нет. Исполнение остаётся координатору.

HTTP cohort сохранён после возобновления D-328: закрытые серверные history/read/compare, manual/metadata, Stable/demotion/delete confirmations, отдельные restore prepare/stage/cancel и контекстный file preview. CSS и шаблоны используют существующий accounts/base.html, данные экранируются; generic snapshot writer/publication endpoint и rich editor не добавлены. Формы используют реальный CSRF и текущую generation, операции — постоянный UUID. История выбирает metadata с deferred payload и пагинацией20; это не квота Stable.

Адресные REV003–006: authenticated page denial вызывает существующий bounded note_denial(page), visitor остаётся без per-request audit; terminal stage replay возвращает сохранённую квитанцию и released/consumed/invalidated/gone/stale без candidate, включая commit→render race; подтверждение удаления показывает Page.name/точный URL/тип и идентичность снимка; metadata result проверяет реальный action edit_manual. test_http.py содержит 8 real-session/CSRF/PG сценариев этих границ, ролей, экранирования, текущего источника manual, повторного пароля и restore без изменения current. Direct Django Client имеет только test override AUTH_TRUSTED_PROXY_HOST=None, production/browser proxy profile не ослаблен. Codec-positive исторические картинки и реальный browser остаются отдельной QA-проверкой, unit fixtures за них не выдаются.

Ошибки редактирования после D-328: первый WriteAllText получил Access denied, этот механизм не повторялся; apply_patch в существующих каталогах успешно сохранил правки. Первый многострочный автоматически сформированный patch для result.html отклонён на проверке hunk до изменения файла; после явной корректировки префиксов каждой строки patch принят. Новые каталоги исполнитель не создавал, Docker/установки/сервер не запускал. Фактические PG/HTTP результаты объявляются только координатором после исполнения.

Первый фактический PG-прогон координатора:150 tests,148 PASS,2 FAIL (120.837s, work/dev05-20261031/units.txt). Method-test отправлял POST без CSRF и правильно получал403 раньше проверки метода; теперь использует реальный CSRF helper и проверяет405. Второй отказ обнаружил настоящий capacity bug: новая manual могла сама попасть в prune при десяти удерживаемых предыдущих основах. Теперь только создаваемый manual-result исключён из кандидатов prune в этой транзакции (не новый persistent pin); отсутствие другого eligible приводит к атомарному HISTORY_BASES_HELD. Регрессия дополнительно сверяет полный набор revision/reservation IDs, sequence, audit/usage/receipt counts после отказа и существование успешной новой версии после explicit cancel. Повтор runtime допустим только после этой правки; исполнитель его не запускал.
