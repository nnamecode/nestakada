# REBUILD-4 — минимальный Audit журнал и retention

Дата: 2026-11-22. ID: `RB4-SLICE-005-AUDIT-MINIMAL`. Статус: **plan и source independently APPROVED 0/0/0; PostgreSQL/runtime 0**.

## Основание и граница

D-925/`LOG-Q001=1` оставляет минимальный MVP: owner-only read-only экран существующих `AuditEvent`, bounded keyset pagination и закрытая retention command. Более поздний D-1243/architecture §7.7 является authority точных clean-rebuild правил: action/date/target UUID filters, retention180 суток, batch≤5000 и один `AUDIT_RETENTION_BATCH` при ненулевом удалении. Срез реализует этот минимум на существующей модели; новых models/migrations/dependencies, scheduler/daemon/queue, Telegram, badges/read state, grouping/search, ручного удаления и mutation HTTP нет.

## Read-only экран

`GET /manage/audit/` доступен только active OWNER через существующую session boundary; anonymous получает существующий login redirect, EMPLOYEE — 403 до audit query. Другие методы — 405. Все ответы private/no-store.

Фильтры ровно утверждённые: optional single `action` из `Action.values`, optional single `date` exact ASCII `YYYY-MM-DD` как календарные сутки Europe/Moscow `[00:00, next 00:00)`, optional single `target` как lowercase hyphenated canonical UUID. Других фильтров нет.

Optional single `before` имеет ровно60 ASCII bytes и grammar `YYYYMMDDTHHMMSS.ffffffZ_<lowercase-canonical-uuid>`: UTC timestamp всегда с шестью microseconds, literal `T`, `Z`, `_`; parse→format обязан дать тот же token. Весь raw `QUERY_STRING` ≤512 bytes; максимум четыре known keys `action,date,target,before`, каждое ровно один раз и с nonempty canonical value. Duplicate/unknown/noncanonical/oversize query даёт constant `400 INVALID_AUDIT_QUERY`, значение не отражается. Canonical next URL сохраняет active filters строго в порядке `action,date,target,before` и кодируется одним `urlencode` без альтернативной формы.

Порядок строго `-occurred_at,-id`. Следующая страница использует compound keyset `occurred_at < ts OR (occurred_at = ts AND id < uuid)`, не offset. Один bounded query читает максимум51 row, показывает50 и строит один canonical cursor только при наличии 51-й. Actor отображается только существующими snapshot полями UUID+role/kind, без User join/current username. Каждая row проходит существующий `AuditEvent.clean()`, а detail сериализуется canonical JSON с exact cap2048 UTF-8 bytes и HTML escaping. Corrupt row, DB/serialization fault → constant503 без event/filter/error content. Допустима только GET filter form; POST/mutation forms, mutation links и raw exception отсутствуют.

Показываются только: MSK time, action, actor kind/UUID/role snapshot, target type/UUID, secondary UUID и safe canonical detail. Detail escaping обязателен. Новые category/level/result или аналитическая классификация не создаются.

## Retention command

`python manage.py cleanup_audit` не имеет scope/age/dry-run options. Один cutoff = `timezone.now() - 180 days`. В одной transaction выбираются максимум5000 oldest UUID по `(occurred_at,id)` среди `occurred_at < cutoff`, удаляются только эти exact rows и проверяется exact count. При count>0 в той же transaction через существующий audit API добавляется ровно один SYSTEM `AUDIT_RETENTION_BATCH`, target AUDIT/null UUID, detail `{"reason":"RETENTION","count":count}`; при count0 event0. Exact boundary и более новые rows сохраняются; повтор продолжает следующий batch.

Success output — только `AUDIT_RETENTION_OK deleted=<0..5000>`. Любой select/delete/count/audit fault откатывает delete+event и даёт constant `AUDIT_RETENTION_UNAVAILABLE` без SQL/error/data. Команда не создаёт расписание и не меняет другие tables. Retention fixtures сначала создают valid rows, затем задают controlled `occurred_at` только scoped `QuerySet.update()`, потому что `auto_now_add` является authority обычного create.

## Acceptance before code

| ID | Сценарий | Доказательство |
|---|---|---|
| `RB4-AUD-001` | owner list newest-first | bounded51/render50, literal compound cursor, page2 без overlap/gap при equal timestamps, filters preserved canonical |
| `RB4-AUD-002` | exact filters/query grammar | action/date/target только closed grammar; query512/cursor60, duplicate/unknown/cursor drift → constant400 |
| `RB4-AUD-003` | auth/privacy/read-only | anonymous redirect, employee403/query0, owner200, POST/PUT/PATCH/DELETE405, private/no-store |
| `RB4-AUD-004` | safe projection | UUID+role snapshot/detail escaped, current User join0, fixed fields only, GET filter form без mutation controls/raw fault |
| `RB4-AUD-005` | corruption/fault | invalid row/detail>2048 bytes/DB or serialization fault → constant503 and no disclosure |
| `RB4-AUD-006` | retention boundary/batch | 5001 old + boundary/recent: oldest5000 deleted, exact boundary/recent/one old remain, one SYSTEM batch count5000; repeat deletes1/event count1; next zero/event0 |
| `RB4-AUD-007` | retention isolation/rollback | only audit changes, no options, injected delete или audit-insert fault restores exact rows/events and constant error |
| `RB4-AUD-008` | scope fitness | model/migration/dependency/scheduler/Telegram/read-state/grouping/mutation additions0 |

Новые tests: domain/retention4 + HTTP4 = exact8. Runtime/Docker не входит: после source review срез ждёт общий безопасный PostgreSQL transport вместе с другими source-approved ветками. Будущий PostgreSQL cohort обязан отдельно запустить две concurrent cleanup commands на >5000 old rows и доказать lock serialization, disjoint exact deletion batches, aggregate count equality, duplicates0 и preserved boundary; это не подменяется in-memory тестом.

## Stop line

Если для реализации потребуется новая колонка/index/table, persistent read state, background process, IP/user-agent storage, полнотекстовый поиск, notification channel или расширение audit detail, остановиться и вынести отдельный выбор владельцу.
