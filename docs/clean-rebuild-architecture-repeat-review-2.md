# Независимое повторное review архитектуры чистой пересборки — CRAR-REPEAT-002

Дата: 2026-11-16. Режим: read-only independent review после remediation D-1239–D-1245. Исходные артефакты не редактировались.

## 1. Вердикт

**CHANGES_REQUESTED — P1=0, P2=2, P3=1.**

Все findings из `CRAR-REPEAT-001`, включая три P1, три новых P2 и P3, закрыты по существу. Регрессий в authority, concurrency, privacy, restore, lifecycle и gates не обнаружено. Найдены три новые локальные неоднозначности; ни одна не требует новой platform/service/state machine.

## 2. Статус предыдущих findings

| Finding | Статус | Доказательство |
|---|---|---|
| `CRAR-P1-001` content/outcome | CLOSED | `clean-rebuild-content-contract.md`: mapping115/unique115/duplicate0/mismatch0, permissions, caps, sanitizer; новые внутренние неоднозначности вынесены ниже. |
| `CRAR-P1-002` DAG/transactions | CLOSED | `clean-rebuild-architecture.md` §7.2/§7.4.1: pages-owned PageGrant transaction, accounts participants, generation, locks, races и lost response. |
| `CRAR-P1-003` current+previous | CLOSED, без регрессии | Architecture §7.3. |
| `CRAR-P1-004` coherent transfer | CLOSED | `clean-rebuild-transfer-contract.md` §2/§6–8: одна source snapshot, disposable pair, seal/failure/crash cleanup, separate promotion. |
| `CRAR-P1-005` requests/legal | CLOSED, без регрессии | `clean-rebuild-requests-contract.md`: D-1229 scope и default-off LEGAL gate. |
| `CRAR-P2-001..004` | CLOSED, без регрессии | User/media/Telegram-ledger/quality contracts сохранены. |
| `CRAR-P2-005` backup proof | CLOSED | Architecture §14.2–14.3: pre-run bitmap/catalog, mandatory finally, raw/reconciled counts. |
| `CRAR-P2-006..008` | CLOSED, без регрессии | Page lifecycle, estimate и optional-kernel contracts сохранены. |
| `CRAR-P3-001/002` | CLOSED, без регрессии | Exact DAG fitness и plan status сохранены. |
| `CRAR-R2-P2-001` backup reopen | CLOSED | Architecture §14.2 и `BACKUP-AC-006/011`. |
| `CRAR-R2-P2-002` AuditEvent | CLOSED | Architecture §7.7: closed fields/actions/details, access, retention и backup. |
| `CRAR-R2-P2-003` trusted client IP | CLOSED | Requests contract §1.1 и `REQUEST-AC-010/011`. |
| `CRAR-R2-P3-001` stale plan wording | CLOSED | D-1229/default-off wording и exact DAG; stale scan0. |

## 3. Новые findings

### CRAR-R3-P2-001. Неоднозначный `content_version`

- Место: `docs/clean-rebuild-content-contract.md`, §3; конфликтующая семантика — architecture §7.3.
- Нарушение: envelope требует positive monotonic `content_version`, но ось монотонности не задана. Owner Undo меняет current/previous payload/hash/provenance местами, тогда как exact monotonic CAS уже принадлежит `PageContent.generation`.
- Последствие: validator может отвергать корректный Undo либо переиздать envelope/hash и нарушить exact swap/provenance.
- Минимальная правка: удалить `content_version` и использовать существующий `PageContent.generation`. Допустимая, но менее простая альтернатива — назвать поле immutable revision ordinal и явно разрешить уменьшение ordinal current при Undo. Новый history/version subsystem запрещён.

### CRAR-R3-P2-002. SiteSettings назван closed без literal schema

- Место: `docs/clean-rebuild-content-contract.md`, §5; связанный список — clean rebuild plan §3.
- Нарушение: phone labels/numbers, address, hours, social links и organization SEO facts являются категориями, а не закрытыми именами полей, типами, cardinality и caps. Envelope limits к singleton не относятся.
- Последствие: importer/model/editor/Header/Footer могут реализовать разные структуры либо произвольный settings JSON/URL list.
- Минимальная правка: одна literal v1-таблица фактически нужных SiteSettings-полей: type, nullable/cardinality, cap/URL scheme и owner-only access. Schema DSL, generic settings engine и новые таблицы не нужны. Если exact состав нельзя доказать approved requirements/baseline, требуется вопрос владельцу вместо угадывания.

### CRAR-R3-P3-001. Outcome types названы content kinds

- Место: `docs/clean-rebuild-plan.md`, §2 и `WBS-FAMILY`.
- Нарушение: contract различает 20 transport outcome types и 19 payload kinds, но plan дважды говорит о 20 content kinds.
- Последствие: WBS/schema counting может снова считать transport alias отдельным payload.
- Минимальная правка: в обоих местах написать `20 outcome types / 19 payload kinds`.

## 4. Механические факты

- CSV: rows115, unique MAP115, unique paths115, proposed types20.
- Expanded contract: memberships115, unique MAP115, duplicates0, CSV mismatches0; payload kinds19; `service_detail=55`, `article=18`; MAP-031/053 article-only.
- Acceptance definitions: CONTENT10, GRANT10, TRANSFER13, BACKUP11, AUDIT8, REQUEST11; missing0, duplicate definitions0.
- Audit actions28/unique28.
- `git diff --check` PASS с существующими LF→CRLF warnings.
- Product/runtime/DB/Docker/network не запускались; workspace рецензентом не изменялся.

## 5. No-bloat conclusion

Remediation не добавила platform/service/state-machine bloat: transfer остаётся disposable pair; backup — один wrapper/finally; audit — одна bounded table; throttle — Nginx shared-memory+protected socket; PageGrant — прямые commands/participants. Три новые правки также документальные и не требуют новых runtime-слоёв.

## 6. Процесс и anti-loop

- ID-count attempt1: PowerShell интерпретировал literal backtick в double-quoted regex как escape; изменённый attempt2 извлёк IDs из acceptance-строк без backtick и прошёл.
- Отдельный `rg` attempt получил Windows literal wildcard path/error123; изменённый повтор использовал каталог `docs` и встроенный `--glob`, успешно.
- Эквивалентных вторых ошибок, третьих попыток, цикла или blocker не было.

Нерешённых owner-вопросов сейчас нет. Вопрос по exact SiteSettings нужен только если состав нельзя однозначно восстановить из approved evidence.
