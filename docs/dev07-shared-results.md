# DEV07-SH1/SH2 — общие блоки и подготовленное файловое хранение

Продолжение D-350: journal primitive проверен65sharedPASS на203files; [актуальный результат](dev07-shared-journal-results.md). Координация pending/reconciliation и достаточный reserve ещё не готовы, успешные shared writes закрыты. Ниже история прежних срезов.

**Продолжение D-349:** ограниченное исправление SH3-FK проверено52sharedPASS210.166с на201files; новая0003 и metadata-first replay/gone, независимое ревью без блокеров. [Актуальный результат и границы](dev07-shared-provenance-results.md). Профиль записи остаётся выключенным; следующий шаг — journal primitive по проверенному technical plan. Ниже сохранён исторический результат SH1/SH2 и его отдельные cohorts.

2026-11-01. D-346/D-347/D-348. DEV-07 около96%, этап8 около20%. **Подготовлены модели, owner Check/read и закрытое файловое хранение. Успешные Draft/Apply/Restore пока не включены:** неизвестный reservation profile безопасно отклоняет новые mutations. Полный DEV-07 и публичные Header/Footer не приняты.

## Реализованный ограниченный результат

Отдельный shared_content содержит SharedBlock/Revision/Draft/RestoreStage/Receipt/BasePin/IdentityReservation/Budget. Header/Footer не являются Page, их история независима, Page10/новые Stable-команды к ним не добавлены. PostgreSQL composite FK запрещают связь current/base/source с другим блоком даже прямым SQL; immutable service boundary и permanent consumer identity не присваивают Page IDs. Миграция0001 проверяет обе начальные UUID на коллизии до любых seed writes.

Добавлены owner-only маршруты редактора/Check/history/version/compare/result и command pipelines. Сотрудник с назначенной Page не получает shared права; session/owner/JSON admission до CSRF/body, private no-store. Закрытая HTML-политика соответствует принятому компоненту, literal phone/social links требуют tel/HTTPS, img принимает server-validated Asset marker вместо клиентского src. READY main/preview проверяются по настоящим файлам. Тяжёлая нормализация использует прежний child CPU10s/wall20s/AS384МиБ/один slot, без новых зависимостей/ресурсов.

Canonical HTML хранится в собственном immutable SharedStorage внутри MEDIA_LIBRARY_ROOT/private/shared-content, без публичного URL и расширения общего MediaStorage prefix. Серверные UUID/fan-out,0600/0700, no-follow dir_fd, exclusive creation, fsync файла/каталога, проверка actual SHA/длины/UTF8/inode/name binding; максимум1МиБ. Ошибка записи не возвращает durable descriptor и не удаляет orphan автоматически. Ссылки на настоящие изображения остаются в существующем media ledger; фотографии в HTML blob не копируются.

Additive0002 добавляет явные inline/file metadata и DB defaults/CHECK, не переписывая0001 и не перенося/обнуляя прежние HTML. Legacy inline читает сохранённые bytes с проверкой SHA; file mode всегда использует verified reader, без fallback на пустой/старый inline. Current file Check и historical file restore-target читаются вне SQL transaction; immutable source descriptor входит в context stamp. Unknown schema показывается владельцу как экранированные данные, а не исполняемый компонент.

Actual quota-read суммирует прежние8own PG root tables с indexes/TOAST/forks ровно один раз и фактическую аллокацию своих FS files/directories/orphans/journal entries. Счётчик снимков берётся из настоящих rows, а не cached budget. Metadata/allocator upper reserve и pending operation authority **не вычислены**: fsMetadataReserveAvailable=false/reserveBytes=null/profileAvailable=false. Не выдаём st_blocks за полный предел всех FS затрат. Любой unknown journal не превращается в0pending reserve. Count10000 действительно отказывает новой версии; полная byte-admission пока не разрешена.

## Проверки и точные cohorts

| Прогон | Фактический результат | Source/scope |
|---|---|---|
| Первые shared HTTP |17PASS157.164с; отдельно исправленный owner Check1PASS3.056с |193files,87501ed673f7714fb255a7429a343cd6c9d8e0275b738f5cbaea45a2d03744b4 |
| Общие регрессии |402PASS864.686с, включая прежний17shared | Тот же193source; не повтор402на финальном199 |
| Owner GET дополнение |4PASS9.704с |194files,806d1ebe9d49448b60ea6fbdf76323e3e6b630530601397bf9259194f477a560; owner context views и новый read QA |
| Parent-anchor diagnosis | Один намеренный RED показал отсутствие guard; после правки тот же изолированный кейс GREEN1PASS | Без DB/сети/секретов, actual own-temp rename после открытия FD; RED не является product PASS |
| Исправленная metadata fixture |1PASS2.409с | Финальный199source |
| **Финальный shared набор** |**42PASS191.484с**:17HTTP+4reads+12FS+9file/migration |199files, f81d61da50b1829a59ada582f0246d831edc54ad82f4c4abc575a8ff367a713e, run ddd0dc23-3969-4184-8308-ffc5405384aa |
| Migration consistency |makemigrations shared_content --check --dry-run: No changes detected | Только проверка, новые миграции командой не записывались |

Независимый `/root/combined_review` лично сверил logs и все199frozen files/0drift. От193cohort изменены6файлов и добавлены6файлов, все внутри shared_content; исходники вне shared неизменны, удалений нет.402и42 — разные прогоны с пересечением тестов, их нельзя выдавать за444уникальных сценария или за402повторно на новом source.

В финальном наборе: реальные PNG→worker READY files, actual child/reap/streams/proof, owner/employee/anonymous/CSRF/HTML/URL/ID constraints; реальный count10000 без pruning/receipt; owner edit/history/version/compare/old literal contact/unknown schema escaped/crossblock404; actual1МиБ UTF8 filesystem roundtrip, fsync/FD, links/FIFO/modes/corruption, orphan faults, deterministic scan earlier-file mutation и named parent rename read/write. Genuine guarded unit MigrationExecutor0001→legacy fixture→0002 проверяет сохранность HTML/UUID/hash/current/draft/pins/AssetUsage и неизменность0001; latest schema восстанавливается ровно одной попыткой в finally.

Это framework HTTP seam и настоящие PG/FS/child проверки в одобренном image782f53c4… при прежних caps. Native browser/RAM, настоящий Nginx/WSGI transport, публичная композиция/ETag/меню и целевая VPS среда не проверялись этим набором. Базовый foundation image09433387… не содержит parser package; lazy import сохраняет его startup/migration, а для реального editor ingress нужен ранее согласованный candidate782f (локальный overlay пока только подготовлен). Framework результат не является передачей готового операторского стенда.

## Ревью, исправления и сохранённые FAIL

- SH1-REV001: запрет relative phone/social URL; SH1-REV002: seed collision preflight; SH1-REV003: FOR UPDATE OF self вместо блокировки nullable outer join. Закрыты в проверенных случаях.
- SH2-REV001: verified empty media root/private absence; SH2-REV002: финальная перепроверка всех scanner entries; SH2-REV003: named blobs/fan-out identity после pinned FD. Закрыты реальными FS случаями. Scanner не объявляется атомарным snapshot против произвольного некооперирующего FS writer; будущие product writers обязаны соблюдать content domain.
- Первый startup FAIL был вызван parent import html5lib в базовом образе; исправлен child-only lazy import. Первый HTTP503 вызван nullable FOR UPDATE и исправлен отдельно. Все первичные журналы сохранены.
- Первый blob набор остановился на18-м методе: QA value unknown длиной7 не помещался в varchar6, получался DataError до enum CHECK. Исправлена только fixture на bogus длиной5; ожидание IntegrityError не ослаблено. Не называем тот первый прогон21PASS.
- Автоматическая проверка однажды отклонила новую parent-anchor правку как эквивалентный повтор. После независимого реального RED-свидетельства тот же apply_patch принят; обхода альтернативным writer не было. ROOT пауза из-за двух неподтверждённых имён файлов снята владельцем D-348 по сохранённому плану, третьего такого обращения нет.

## Что ещё требуется до работающего сохранения

Долговечный authoritative reservation journal/create/finalize/reconcile и crash/unknown-result протокол; подтверждённые upper reserves PG metadata/FS allocator/transient growth/attributable AssetUsage; настоящий75%/256МиБ/last-reserve concurrency corpus. Один post-write rollback не доказывает hard physical cap; неопознанный профиль остаётся закрытым.

Перед включением будущих write branches исправить и положительно проверить metadata-first exact replay при устаревшем/consumed source, explicit draft basis/rebase/pins, draft/stage cancel и JS operation nonce/dirty state при изменении текста во время ответа. Эти dormant ветки не приняты по отрицательным503тестам.

SH3-FK-001/P1 независимо подтверждён: composite FK receipt source/base и revision source provenance сейчас ссылаются на живой SharedRevision. При постоянных receipts это удержит старые тела даже без активных pins и не позволит ручную очистку подходящей истории. До включения Apply нужна новая migration к постоянным block-bound identity/tombstone для provenance с сохранением crossblock/nonreuse/replay-gone; live FK оставить действительным held bases. Проверить удаление допустимого старого тела при сохранённой квитанции/честном gone. Не CASCADE удалять receipts и не переписывать уже применённую0001. Сейчас mutations выключены и cleanup endpoint отсутствует, поэтому это будущий write-enable gate, а не принятый дефект потери данных.

Затем actual editor candidate/ingress/native UI, unsaved RAM/UNKNOWN result, real media chooser/trusted icon assets, typed menu resolver и публичная композиция в DEV-08/DEV-29. Frozen Header paragraph acceptance binding требует явного адаптера на допустимый text slot без fake p; полная публичная приёмка остаётся открыта. Backup DEV-22/23 должен включить DB pointers+blob/journal поколения, отдельный backup PostgreSQL не считается полным.

## Локальные свидетельства и точка продолжения

work/dev07-shared-20261101: каталог before/, файлы backup-paths.json и git-status-before.txt (102предыдущих изменения побайтно); start-first.txt/shared-first.txt (первичные FAIL); regression-first.txt; shared-reads-first.txt; parent-anchor-red-first.txt/parent-anchor-green-first.txt; shared-blob-first.txt; shared-metadata-fixed-first.txt; shared-final-first.txt; migration-consistency-first.txt; cohort-final.json/source-delta-final.json/stop-final.txt. Runtime logs/секреты/синтетические binary corpus остаются вне Git.

Стенд остановлен, active=false; штатные тома сохранены. Старый сайт/VPS не затронуты. Текущий этап8/DEV-07 продолжается; следующий необходимый инкремент — проверяемая бронь квоты и положительные shared mutations, без перехода к новому этапу/production.
