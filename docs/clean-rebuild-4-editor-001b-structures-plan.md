# RB4 typed editor 001B-S — owner-only literal structures

Дата: 2026-11-19. ID: `RB4-EDITOR-001B-S`. Статус: **S1-PROCESS, S2A-LINKS and S3A-ACTION-COPY completed; S4-REFS no-code deferred by D-1642 review0/0/0/product0/no-bloat; S2B/S3B/media remain B002-bound**.

## 1. Граница и порядок

`RB4-EDITOR-001B-P` закрыт принятыми PostgreSQL exact47 и Chromium exact8. Следующий этап не создаёт единый редактор повторяющихся объектов. Текущие owner-only структуры имеют несовместимые контракты и поэтому остаются отдельными буквальными срезами:

1. `RB4-EDITOR-001B-S1-PROCESS` — `home.process_steps[]`, exact shape `{title, body}`, cap12;
2. `RB4-EDITOR-001B-S2A-LINKS` — `legacy_partner_links.links[]`, separate literal no-media plan; `S2B-REVIEWS` remains closed until B002/exact thumbnail-position contract;
3. `RB4-EDITOR-001B-S3A-ACTION-COPY` — fixed-position action title+rich body only; count/order/internal URL/banner remain immutable because action order is positionally coupled to media; structural S3B stays B002/S4-bound;
4. `RB4-EDITOR-001B-S4-REFS` — `home.service_refs[]`, `brand_refs[]`, `review_refs[]`, только после утверждения допустимых target kinds, проверки существования целей и bounded owner-facing projection.

`S1-PROCESS` is closed by D-1601, `S2A-LINKS` by D-1618 and fixed-copy `S3A-ACTION-COPY` by D-1640. `S4-REFS` is explicitly deferred no-code by D-1642 until per-field B002/public authority; S2B/S3B remain ordering markers, not code permission. `001B-M` stays closed until B002. Универсальный repeater/form/schema builder, registry адаптеров, JSON editor/carrier, общий selector, raw UUID input, media picker и новая зависимость отсутствуют.

Это минимальный полезный срез: frozen authority содержит пять реальных `process_steps`, а три home reference array сейчас пусты. Объединение steps, URL-объектов, rich actions и UUID refs создало бы абстракцию до появления общего доказанного контракта и является stop condition.

## 2. `S1-PROCESS` exact product scope

Только активный OWNER на единственной странице `kind == home` видит и редактирует ordered `process_steps`. EMPLOYEE не получает названия, значения, count, carrier или DOM-маркеры этого поля при любых PageGrant. Все другие page kinds не получают process control/wire.

Контрол представляет существующий payload буквально: не больше12 ordered objects, каждый имеет required NFC/control-free `title` длиной1..500 code points и NFC/control-free `body` длиной0..4,000. UI поддерживает add, remove, move up/down и редактирование этих двух plain-text значений. Пустой массив допустим; пустой title запрещён; body не является rich text, никогда не интерпретируется как HTML и всегда escaped шаблоном. Отдельного markup detector нет: literal `<`/`>` допустимы как обычный plain text. Переносы строк, табы и другие control characters запрещены существующим canonical plain contract.

Существующие пять элементов выводятся сервером как escaped inputs из уже провалидированного payload. Адаптер не хранит draft/history/autosave, не генерирует идентификаторы и не меняет другие поля.

## 3. Literal multipart wire и server assembly

Существующий Save endpoint, multipart-only policy, CSRF, operation UUID, base generation/hash и PageCAS остаются единственной командной границей. Для home OWNER добавляются только:

- `process.changed=0|1` ровно один раз;
- при `0` ключ `process.step` отсутствует, а текущий `process_steps` сохраняется без изменений;
- при `1` `process.step` повторяется0..12 раз в exact display order;
- каждое значение — один `title<TAB>body` record; ровно один separator обязателен;
- tab/control characters запрещены canonical plain contract, поэтому escaping dialect и второе представление не нужны.

На иных kind/role любой `process.*` неизвестен и весь request отклоняется до команды. Duplicate flag, malformed record, cap+1, invalid NFC/control/title/body, extra key/file и несовместимая роль/kind дают constant400, command/audit/mutation0.

Для OWNER adapter deep-copy текущего validated snapshot, применяет уже разрешённые scalar/rich/price изменения и только при `process.changed=1` заменяет `fields.process_steps`. Полный candidate проходит `validate_payload` до `save_page_content`; PageCAS повторно блокирует actor/current, решает replay/stale/conflict, валидирует, продвигает current/previous и пишет один AuditEvent атомарно. Adapter не сравнивает basis, не пишет модели и не создаёт отдельную транзакцию.

Максимум процесса добавляет13 multipart fields (`1 flag + 12 records`). Максимальный HOME request имеет exact27 fields: `1 CSRF + 3 basis + 4 scalar + 3 rich flags + 3 rich values + 1 process flag + 12 steps`. Price существует только на `service_detail`, process — только на `home`, поэтому они не суммируются и глобальный field-count worst case остаётся price request exact10,545.

До candidate validation каждый из трёх home rich values может занимать existing exact1,048,576 bytes. Process records в conservative four-byte Unicode bound занимают `12 × ((500 + 4,000) × 4 + 1 TAB) = 216,012` bytes; scalar values не больше6,041 bytes, CSRF+basis не больше183 bytes при positive-bigint generation, four flags —4 bytes. Сумма values не больше3,367,968 bytes. Даже conservative `256 bytes × 27 parts + 76 closing bytes` для RFC-max70-byte boundary даёт3,374,956 bytes, ниже exact4,194,304 с запасом819,348 bytes. Focused mechanical encoder обязан воспроизвести exact27 worst-case parts с RFC-max boundary, доказать `Content-Length ≤ 4MiB`, а отдельный exact cap+1 request обязан быть отвергнут existing ingress guard. Existing limits10,600/4MiB и middleware не меняются.

## 4. Browser и fail-closed behavior

Добавляется один локальный `process-steps-editor.js`, привязанный только к server-emitted `[data-process-control]`. Он знает лишь два exact поля и четыре операции steps; arbitrary schema metadata, generic row factory и другие structures отсутствуют.

Template изначально выводит inputs/buttons disabled, `process.changed=0`, пустой carrier container и Save disabled. После проверки exact DOM shape/cap локальный script включает только process inputs, ставит на exact form `data-process-ready="1"` и отмечает dirty при первой операции/правке. Перед submit он повторно проверяет DOM ownership, cap и plain constraints, затем создаёт только repeated hidden `process.step` carriers в текущем порядке.

Save разрешается только после готовности всех буквальных применимых адаптеров. Existing final `editor.js` получает одну явную проверку process marker рядом с уже явной price marker; registry/event bus/adapter discovery не добавляются. На home это rich+process, на service_detail rich+price, на остальных страницах только rich. Ошибка/unsupported DOM оставляет Save disabled и показывает существующее private error message. Без JavaScript process остаётся read-only и сохранение недоступно по существующей форме.

## 5. Acceptance до кода

- `RB4-EDPROC-001`: только OWNER+home получает exact process values/count/control/flag; employee и other-kind responses содержат process name/value/count/carrier/marker0.
- `RB4-EDPROC-002`: `process.changed=0` при owner scalar/rich Save сохраняет exact process array; process carrier при этом запрещён.
- `RB4-EDPROC-003`: OWNER сохраняет empty, current five, reorder, add, edit и remove вплоть до exact12; unrelated refs/media/scalar/rich сохраняются.
- `RB4-EDPROC-004`: duplicate/missing flag, malformed/multiple-separator record, cap13, empty/over-cap/non-NFC/control title/body, unknown key, file и forged role/kind дают400 до command, mutation/audit0; literal angle brackets remain escaped plain text without a markup heuristic.
- `RB4-EDPROC-005`: valid Save advances current→previous/generation/hash once and writes one safe audit event; stale/concurrent/replay/operation-conflict retain exact PageCAS behavior; injected validation/audit/DB fault rolls back all.
- `RB4-EDPROC-006`: static exact27 arithmetic and a mechanical RFC-max-boundary encoder prove maximum HOME wire ≤4MiB; exact body cap+1 is rejected. Process and price maximums are mutually exclusive by exact kind, so existing10,600 fields/4MiB/body guard remain sufficient without settings or middleware change.
- `RB4-EDPROC-007`: real Chromium proves escaped initial five, add/remove/move/edit, exact order serialization, empty body, cap12, dirty flag, rich+process readiness, malformed DOM fail-closed and no-JS read-only.
- `RB4-EDPROC-008`: static inspection finds model/migration/dependency/shared repeater/form/schema DSL/adapter registry/JSON/raw UUID/general selector/media code0.

## 6. Verification and gates

После independent architecture review реализация, если план принят, ограничена: fixed projection/dataclasses, one literal parser/candidate branch, one template section, one process-only JS asset, one explicit readiness condition и focused tests. Сначала static/code review; затем отдельно разрешённый disposable PostgreSQL focused regression; затем отдельно разрешённый isolated real-Chromium suite. Static review не считается runtime evidence.

`S2/S3/S4`, imported-data integration, public template E2E/responsive, B002/media, Nginx, live/deploy и push остаются отдельными gates.

## 7. Stop rules и лёгкие компромиссы

Работа останавливается и возвращается владельцу, если `S1` требует общий repeater/row model, schema metadata, adapter registry/event bus, JSON carrier, new dependency/model/migration/middleware/settings, rich/plain convergence, UUID selector или media work.

Лёгкий компромисс для спорного process behavior — оставить операцию read-only и сохранить exact payload, а не строить общую абстракцию. Для URL-структур — две маленькие буквальные формы позже. Для actions — переиспользовать canonical rich policy только после отдельного bounded плана, не делать nested universal editor. Для refs — продолжать показывать read-only count, пока target semantics не утверждены; raw UUID ввод не является допустимым компромиссом.
