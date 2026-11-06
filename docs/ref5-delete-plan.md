# REF-05N — подтверждённое удаление страницы и всей истории

Дата: 2026-11-06.
Основание: D-047/D-048, D-244, D-590, D-601, D-629 и поручение владельца «Продолжай».
Статус: короткий приёмочный контракт записан до кода опасной операции.

## Граница

Только `nesadmin` удаляет одну страницу без детей после актуальной owner-сессии, повторного пароля и точного ручного подтверждения имени и PRIMARY URL. В одной transaction удаляются Page, все её Route (PRIMARY/alias/redirect), все revisions/metadata/current state/Stable, owner draft, restore stages/base pins, PageGrant, PageMediaHome и только AssetUsage этой страницы/её revisions/draft. Asset, AssetFile, MediaFolder, общие/чужие usages, append-only audit, OperationReceipt и IdentityReservation сохраняются.

Это не удаление поддерева, не массовая очистка, не физическое удаление файлов, не REF-Q004 и не удаление legacy-архитектуры.

## Приёмочные сценарии

- **DEL-001 — права.** GET/POST только `nesadmin`; employee/anonymous/GET mutation запрещены, CSRF обязателен.
- **DEL-002 — пароль.** POST повторно проверяет текущий пароль владельца до destructive transaction; после блокировки сверяет неизменность password hash/generation/editor-session. Пароль не возвращается в HTML/audit/log.
- **DEL-003 — точное подтверждение.** Форма показывает и требует точный ввод актуальных Page.name и PRIMARY target, числа revisions/Stable/drafts/stages/routes. Signed token связывает actor/generation/page/operation и locked `xmin` Page, exact routes, children, history composition и media-home/grants.
- **DEL-004 — дети.** Любой непосредственный ребёнок, включая hidden, блокирует prepare/apply. Late child делает confirmation stale; поддерево не удаляется и не перемещается.
- **DEL-005 — полный page scope.** Успех удаляет одну Page, все её Route, revisions включая current/manual/Stable, metadata/state/draft/stages/pins, page grants/media home и соответствующие current/ordinary/stable/draft usages.
- **DEL-006 — shared media.** Asset/AssetFile/MediaFolder не удаляются; usages других pages/versions/shared blocks/retained HTML сохраняются. Физическая media cleanup остаётся отдельной командой.
- **DEL-007 — URL после удаления.** PRIMARY, alias и все входящие redirect этой Page исчезают; read projection возвращает unknown. Новая Page с бывшим URL/новым UUID не затрагивается повтором старого подтверждения.
- **DEL-008 — atomicity/fault.** Любая ошибка usage/history/route/Page/audit откатывает всю transaction; частично удалённой страницы нет.
- **DEL-009 — stale/concurrency/replay.** Page/routes/history/children composition и `xmin` закрывают stale/ABA; один concurrent submit удаляет, второй возвращает безопасный replay/gone. Lost response после commit повторяется без второго audit и не затрагивает новую Page с тем же URL.
- **DEL-010 — отсутствие нового ledger.** Новые OperationReceipt/IdentityReservation/tombstone table/TRUST intent не создаются; существующие receipts/identity tombstones и audit сохраняются. Остальные команды и HTML fallback не меняются.

## Проверки

Focused command/HTTP/fault/concurrency/media tests; затем полный `content`, `media_library + page_versions`, migrations/diff, независимое review, read-only main DB/login и Stop.
