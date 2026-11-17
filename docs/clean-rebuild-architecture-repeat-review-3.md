# Короткое независимое review remediation — CRAR-REPEAT-003

Дата: 2026-11-16. Режим: read-only review только D-1247–D-1249 и cross-contract consistency. Workspace рецензентом не изменялся.

## Вердикт

**APPROVED — P1=0, P2=0, P3=0.**

Это независимый архитектурный verdict. Он не является согласованием владельца, не открывает `REBUILD-Q001/Q002` и не разрешает product code, migrations, DB/media mutation, runtime, cutover или live.

## Findings

| Finding | Статус | Evidence |
|---|---|---|
| `CRAR-R3-P2-001` content_version | CLOSED | Content envelope содержит только schema/schema_version/kind/fields. `PageContent.generation` — единственная monotonic CAS-axis вне payload/hash; Save создаёт current, Undo увеличивает generation и переставляет exact bytes/hash/provenance без reserialization/rehash. |
| `CRAR-R3-P2-002` literal SiteSettings | CLOSED | Один pages-owned singleton, separate structure/settings generation и ровно11 literal fields с type/cardinality/nullability/caps/authority. Strict URL policy, derived tel/mailto, one READY logo usage, owner CAS, employee read-only, audit и LEGAL/social gates закрыты без arbitrary JSON/link collection/schema DSL. |
| `CRAR-R3-P3-001` terminology | CLOSED | Plan ровно дважды использует `20 transport outcome types / 19 independent payload kinds`; MAP-088 остаётся alias без Page/payload copy и использует MAP-115 service_detail. |

## Cross-contract и механические факты

- D-927/D-1101 authority соответствует public phone/email; D-929 не превращён в публикацию legal facts: legal_name nullable/gated, ИНН/ОГРН отсутствуют.
- D-1229/default-off requests gates сохранены.
- `SITE_SETTINGS_CHANGED` уже входит в closed AuditEvent matrix; settings CAS не смешан со structure/PageContent generation.
- Content matrix rows20/memberships115/unique115/duplicates0/CSV mismatches0; outcome20/payload19; service_detail55/article18.
- SiteSettings fields11; `CONTENT-AC-001..010` definitions10/unique10; corrected plan phrase occurrences2.
- `content_version` остался только в отрицательном acceptance-утверждении об отсутствии; положительного поля/axis нет.
- `git diff --check` PASS с существующими LF→CRLF warnings. Product/runtime/DB/Docker/network не запускались.

## No-bloat и process

Используются существующие `PageContent.generation`, SiteSettings, AssetUsage и AuditEvent. Revision/history subsystem, settings JSON/schema DSL, generic social collection, новая таблица, feature platform и state machine не появились.

Tool errors, anti-loop events и owner blockers в `CRAR-REPEAT-003` отсутствуют. CONTACT-Q002/Q003, LEGAL-01 и отдельные publication/intake permissions остаются намеренными будущими gates; nullable values до них не рендерятся.
