# DEV07-E1 — проверяемая карта существующих защищённых изображений

2026-10-31. **Ограниченный pure-подшаг E1 завершён: 74 теста PASS, независимое ревью без открытых блокеров.** Продолжение D-336/D-337, возобновление DEV07-Q004 выполнено раздельными code/doc правками. Основания: [carrier §7](dev07-format-carrier.md), [контракт редактора](dev07-editor-contract.md), [P07](dev07-protected-media-checks.md), существующая DEV05 schema. HTTP/UI не подключены; настройки, зависимости, роли и бизнес-лимиты не менялись. Полная protected/media интеграция не завершена. Ниже сохранён принятый технический контракт; фактические результаты — в конце.

## Граница E1

Подшаг разрешает pure проверку существующего изображения и сохранение разрешённого текста/оформления внутри прежних слотов. Ни DB READY, ни физические файлы, права на Page, HTTP, выбор/загрузка/вставка/замена медиа и PM-atom этим подшагом не подтверждаются. Они остаются последующими воротами. Owner replacement/insert не запрещается бизнес-правилом: соответствующего adapter в E1 нет. Неизвестные компоненты `protected_ref` не становятся изображениями.

Контекст поступает только от будущего доверенного server adapter выбранного current/draft/stage. Клиент не передаёт ProtectedContext, layout, embedded_images или собственный fingerprint. Пока этого adapter нет, production normalizer_child продолжает передавать пустой контекст и отказывать при protected markup. Временный fail-closed не снимается ради демонстрации pure положительного примера.

`processing.CONTEXT_BYTES` уже равен `MAX_BODY_BYTES`=64MiB, не 64KiB. Ресурсы не увеличиваются. В будущем выбранный source HTML и его schema-факты передаются в одном ограниченном context/одном child; parent не получает второй большой HTML parser. Rich HTML каждой области вместе со всеми marker attrs остаётся ≤1MiB, source20k nodes/depth32/200k text codepoints. Сам E1 не добавляет quota изображений, родителей, элементов schema или новую длительность.

## Pure API и типы для QA

Предлагаемый новый модуль `page_editor.protected_policy`, без Django, IO, сети и декодеров:

```python
build_protected_context(source_html: str, *, field: str, scope_id: str,
                        layout: list, embedded_images: list) -> ProtectedContext
```

`scope_id` — canonical PageUUID, field — intro_text/main_text. `layout` и embedded_images — действительные server snapshot данные, не PageInput. Builder не создаёт marker/slot UUID, не исправляет source и не выполняет запись. Проверяет закрытые типы/ключи относящихся к карте descriptor, canonical UUID, уникальность и точное соответствие HTML. Реальный READY/файлы builder не проверяет; UUID здесь не полномочие.

Существующий `ProtectedBinding` сохраняет все поля и смысл. В `types.py` предлагаются два новых frozen типа:

```python
ProtectedAncestor(tag: str, attributes: tuple[tuple[str, str], ...])
ProtectedParent(parent_id: str, layout_id: str, path: tuple[int, ...],
                ancestors: tuple[ProtectedAncestor, ...],
                sequence: tuple[tuple[str, str], ...])
```

`sequence` содержит только пары `('slot', UUID)` / `('marker', UUID)` в реальном порядке непосредственных детей. `ancestors` — цепочка от верхнего element фрагмента **включая сам parent**; attrs отсортированы по имени. `path` — индексы element-детей от корня fragment до parent, начиная с0; text/tail не индексируются. Это не offset символов и не индекс DOM, вычисленный браузером.

`ProtectedContext` сохраняет первый параметр `nodes=()` и добавляет defaults:

```python
scope_id: str | None = None
field: str | None = None
source_sha256: str | None = None
parents: tuple[ProtectedParent, ...] = ()
```

Builder возвращает nodes в документном порядке marker, parents в документном порядке parent, scope/field и SHA256 точного canonical source UTF8. Это source identity внутри доверенного процесса, не подписанный HTTP capability. `ProtectedContext()` остаётся прежним пустым контекстом. Непустой nodes без scope/field/parents/source_sha256 не получает доверие из одного `isinstance`: fixed PolicyError `POLICY_CONTEXT_INVALID`. При проверке candidate контекст обязан совпасть с переданными Page scope и field, и пройти строгую валидацию каждого вложенного типа/значения/связи, в том числе bool-vs-int для path и размеров. Нельзя заменить map только другим dataclass с тем же названием.

Публичный pure entry normalizer сохраняется:

```python
normalize_html(value, *, owner, field, scope_id, protected_context, ...)
```

E1 подключает внутреннюю проверку карты к этому pure entry, **не** к normalizer_child/HTTP. Новый контекст не позволяет caller задавать nh3 kwargs, разрешённые теги или обход исходной проверки. NormalizationResult сохраняет API; pending_assets выводится из проверенных marker как `(image_id,asset_id)` в документном порядке, по одной записи на image_id. Это список зависимостей для будущего adapter, а не доказательство READY. Client embedded/layout DTO не появляется.

## Однозначная canonical grammar

Для первого проверенного subset parent — разрешённый текущим carrier element с `data-es-parent=UUID`, который содержит хотя бы один image marker. Непосредственные дети имеют форму:

```text
slot, marker, slot [, marker, slot ...]
```

Все slots — `span data-es-slot=UUID`; слот может быть пустым. Один промежуточный slot является после предыдущего и до следующего marker. Слот содержит только разрешённые inline text/format/link/anchor/br, без parent/slot/protected marker внутри. Разрешённая slot-разметка проходит общий policy, а не собственный sanitizer. Parent.text и непосредственные child.tail пусты: весь редактируемый текст размещён в slots. Это конечная поддерживаемая canonical форма E1, а не запрет других утверждённых представлений навсегда. Если исторический source нельзя однозначно представить этой формой без преобразования/догадки, builder возвращает ControlledUnsupported `PROTECTED_SOURCE_AMBIGUOUS`; он не добавляет пустые slots и не переносит текст сам.

Image marker — пустой span с обязательными protected/image/asset/alt/image-align и необязательными width/height из carrier. Ни text, ни дети, ни slot/parent/font/anchor attrs на самом marker не допускаются. UUID всех parent/slot/marker в одной карте различаются; повторный Asset разрешён. EmbeddedImageRef.id не переиспользуется для двух marker E1. Разные references могут указывать на один Asset. Не вводится Page-local запрет повторного использования Asset.

Nested protected parent, slot внутри slot, marker за пределами родителя, пропущенные/переставленные границы, лишний повторный marker и mixed marker+slot attrs — не допускаются как успешная карта. Различаются неописанный безопасный source (controlled unsupported) и неверный/опасный candidate (whole PolicyError). Unknown active tag/attr/template/style всегда отклоняется общим unsafe policy до cleaner, даже когда map ещё не подключена.

Каждый marker.id обязан встречаться ровно в одном `layout` descriptor `kind='text'` этого field, `protected_nodes.id=marker.id`; его reference_id равен marker.image и EmbeddedImageRef.id. Все metadata marker равны соответствующему EmbeddedImageRef, отсутствие width/height означает null. Внешние main_image/preview_image и самостоятельные layout.image не подменяют эту связь. В одном field допустимы несколько DEV05 text-layout descriptors: принадлежность устанавливается **по точному уникальному marker.id**, а не выбором первого descriptor по field. Все markers одного parent E1 принадлежат одному layout.id; неоднозначный/mixed legacy source — controlled unsupported. Parent UUID не объявляется равным layout UUID: это разные identity, связь явно хранится в ProtectedParent.layout_id.

Соблюдается биекция source markers ↔ protected_nodes данного field. Ссылки других field проверяются их собственным вызовом; нельзя молча присвоить их текущей области. Снимок с generic protected_ref не расширяет допустимый image resolver. Builder не считает произвольный SHA в layout доказательством: вычисленный ниже fingerprint каждого marker должен равняться его сохранённому descriptor.fingerprint. Неизвестная старая схема fingerprint/несогласованность — `PROTECTED_SOURCE_AMBIGUOUS`, без перезаписи исторической версии.

## Детерминированный fingerprint

Хеш считается по UTF8 JSON: `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`, `allow_nan=False`; значения уже прошли общую принятую Unicode/attribute normalization. SHA256 — lowercase64hex. Ни text slot, ни их длина/внутренний разрешённый font/color/marks в descriptor не входят.

Для marker M canonical object ровно:

```text
{
 protocol: "es-protected-placement-v1",
 scope_id: PageUUID, field: "intro_text"|"main_text",
 layout_id: UUID, parent_id: UUID,
 parent_path: [elementChildIndex, ...],
 ancestors: [{tag: canonicalTag, attributes: [[name,value], ...]}, ...],
 sequence: [["slot",UUID],["marker",UUID], ...],
 marker: {marker_id: UUID, image_id: UUID, asset_id: UUID,
          alt: string, alignment: string, width_px: int|null,
          height_px: int|null},
 before_slot_id: UUID, after_slot_id: UUID
}
```

Предок включает **все** свои проверенные canonical attrs, включая parent identity и влияющее оформление, и свой tag. Это консервативное точное сравнение принятой структуры, а не обещание полного browser CSS cascade engine. Внешние CSS не берутся из клиента. Формат/текст внутри slot разрешён и не влияет на предков marker, потому что slot — его сосед, а не wrapper. Перенос marker под новый link/mark/wrapper не становится разрешённой text-правкой.

Сохранение текста перед изображением изменяет длину slot, но не path/sequence/boundaries/fingerprint. Обмен двух одинаковых по tag/attrs родителей не проходит: у каждого UUID собственный parent_path плюс порядок parents. Перенос целого parent в другой существующий контейнер меняет path и/или ancestors. Перестановка marker внутри прежнего parent меняет sequence/before/after. Смена formatting на предке marker меняет ancestors. Изменение незащищённого текста не хешируется; структурная правка вне slots, меняющая путь защищённого узла, E1 не объявляется поддержанной безопасной text-slot правкой.

Нужны одновременно равенство полного упорядоченного набора ProtectedParent и всех ProtectedBinding и корректное соответствие schema; одного совпадения присланного fingerprint недостаточно. Candidate сам не приносит fingerprint в carrier. Сервер вычисляет новый descriptor и сравнивает с доверенной картой. В E1 map/Asset/reference metadata сохраняются для обоих ролей. Owner replacement/insert, изменение layout и reset — controlled unsupported следующего подшага, а не готовый write API.

Уточнение gate E1: вставка обычного `<p>` перед защищённым parent, изменяющая его element path, пока возвращает `ControlledUnsupported('PROTECTED_STRUCTURE_EDIT_UNSUPPORTED')`. Это техническая граница подшага, не новый бизнес-запрет и не заявление полной поддержки carrier §7. Увеличение текста внутри прежнего slot остаётся обязательным положительным сценарием.

## Порядок проверки и отказов

1. Source и candidate проходят действующие byte/codepoint/node/depth/lexical EOF/HTML5/closed attrs/URL/CSS/template guards. Безопасный repair не скрывает опасный исходный token. Никакой native clean до whole admission.
2. Builder проверяет canonical source и однозначно строит map; source должен пройти closed serializer/nativeclean/secondparse без необъяснимой потери. Для переиспользования предлагается приватный refactor общего base admission, а не public `skip_protected=True` или новый caller-controlled kwargs. Canonical source не модифицируется builder.
3. Normalizer строго проверяет scope и типы context; candidate проверяется по map после общей нормализации разрешённого text-format, до первого native clean. Изменившаяся карта целиком отказывает. Пустой контекст+marker остаётся `ControlledUnsupported('PROTECTED_INTEGRATION_UNSUPPORTED')`.
4. После nativeclean и повторного разбора проверяются полная semantic signature и защищённая карта; после второго clean — idempotence. Удаление/mutation любого carrier не выдаётся за успешную очистку. В fixed errors нет raw HTML/URL/text/filename.

Предлагаемые fixed PolicyError: `PROTECTED_CONTEXT_INVALID` для неверных вложенных bindings/facts, `PROTECTED_SCOPE_MISMATCH`, `PROTECTED_MARKER_INVALID`, `PROTECTED_REFERENCE_MISMATCH`, `PROTECTED_PLACEMENT_CHANGED`. Верхнеуровневые неверные types сохраняют `POLICY_CONTEXT_INVALID`. Валидный ещё не поддержанный source/owner operation использует ControlledUnsupported, а не успех с пустой картой. Точные names сверяются QA до реализации.

## Gate E1 и отложенные утверждения

До application кода reviewer должен принять API/dataclass defaults, strict context binding, parent_path/sequence/ancestor fingerprint, source-layout ownership, supported grammar и сохранение default unsupported. QA владеет отдельным `test_protected_policy.py`; исполнитель не меняет его oracle. Требуются независимые положительные controls с непустой картой: text grows до/после marker, emoji, форматирование только slot, несколько marker/parent/field. Отрицательные: перенос целого parent, swap одинаковых parents, descriptor/Asset/metadata/UUID tamper, marker content/mixedattrs, nested slot/parent, omitted/duplicate marker, source/schema hash mismatch, wrong scope/type и active source. Для whole rejection проверяется, что native clean не вызван; altered cleaner проверяется на divergence.

E1 не закрывает P07-001/002/HTTP/UI/READY/FS/ledger/CSP. Реальные media tests/bytegate/owner picker/PM atoms/reset/ресурсные measurements и доверенный source-context transport — последующие отдельные cohorts. Существующие preflight/final descriptor checks не называются повторным физическим SHA-чтением под SQL locks и не обещают защиты от произвольного внешнего bit flip. Старые214 фотографии не трогались. Состояние после разрешённого DEV07-Q004 возобновления: **ограниченный pure-код проверен, независимое ревью E1 закрыто без блокеров**. HTTP/normalizer_child/UI не подключены к новому контексту; зависимости, установки, ресурсы, сайт и VPS не менялись. Тесты запускались координатором только в существующем согласованном Docker-образе без сети.

## Фактический результат E1 и границы покрытия

Реализованы builder и strict validator карты, frozen context с Page/field/ancestor/placement facts, независимая проверка persisted descriptor SHA, сравнение candidate до cleaner и после обоих clean/parse. Разрешён рост Unicode текста и inline-оформление внутри прежних slots. Подмена metadata/Asset/reference, удаление, дублирование и перемещение marker/parent или изменение влияющего оформления целиком отказывают. Произвольный ProtectedContext не является HTTP-полномочием; source SHA остаётся доверенным provenance, а не подписью.

После остановки сохранены paused-snapshot и старый DEV07-D. По D-337 отдельно завершены guards нестроковых layout.field/image_id и вложенных context ошибок; отдельно обновлён полный прочитанный абзац документа. Затем первый frozen набор: 73 PASS 13.127с. После одного независимого test-only дополнения для unhashable source descriptors финальный полный bounded набор: **74 PASS 13.469с**, exit0. Это 22 новых E1 tests + 44 прежних policy/table/price + 8 InputPolicy с настоящим ограниченным child. Не сумма несвязанных прогонов.

Команда: `python -B -m unittest -v page_editor.test_protected_policy page_editor.test_policy page_editor.test_tables page_editor.test_price_policy page_editor.test_input_policy`. Образ `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`; Docker network none/read-only/user10001/cap-dropALL/no-new-privileges/768MiB/1CPU, tmpfs128MiB. Ресурсы не повышались. DB, Nginx и браузеры для этого pure-подшага не запускались; прежние290/16/9 результаты DEV07-D не выдаются за повторный прогон на E1.

Финальный снимок: `work/dev07-protected-20261031/frozen-final/`, 156 файлов; manifest `final-source-manifest-second.json` SHA `b726a29aab3b9b54f9518c17915a7026eefff224fa914a99814f4ca9c1fcf9af`; вывод `tests-final.txt`. Предыдущие frozen-app/manifest80d25…/tests-first.txt сохранены отдельно. Независимый рецензент лично сверил 156 SHA без расхождений, итог74PASS и test-only delta.

| Исходник | Финальный SHA256 |
|---|---|
| types.py | a692b48193904fe2416dd7d9cc6ae71da45dc9e8795c3f6e3f60b120e424b879 |
| html_policy.py | 0e6fbf4166141398bc8b35737c751d3247a2c7374029cec2aaea791f586db7ad |
| protected_policy.py | 3136267f21ce1bf0bc3d4217f655737986a4a222c80f7bcdff934454582b4c13 |
| test_protected_policy.py | 1b6ccc2b0d52e8fce00271778ade992bc299c112b44d1da8b263f6ff8bfd415d |

| P07 | Подтверждённая часть E1 | Статус всего сценария |
|---|---|---|
| 003–007 | Pure positives текста/формата и whole negatives metadata/identity/sequence/ancestors на непустой карте | Частично; actual employee/HTTP/PG/FS/UI впереди |
| 009 | Unsafe source/candidate до native clean, malformed marker, cleaner divergence | Частично; реальные HTTP/DOM остаются |
| 008, 010, 022–024 | Структурный capability-отказ, прежний empty-context отказ и сохранение общих policy guards | Не пройдены целиком; PM transactions, protected exact boundaries и selected-source integration впереди |
| Остальные P07 | E1 их не выполнял | Не выполнены |

Следующий шаг E2: доверенный adapter actual current/draft/stage внутри EditorSlot, READY/файлы/права/ledger, contextual derivative read без ослабления owner preview, owner picker/replace и PM carrier roundtrip. До допуска E2 добавить независимый положительный oracle существующей цепочки ancestors глубже одного элемента и её format mutation; текущее ревью считает это неблокирующим остатком E1. Source builder сейчас использует общий URL policy без URLContext; для выбранного реального source отдельно проверить context-relative/anchor ссылки и фактический origin, не подменять его текущей Page при draft/stage. New insert/server-assigned identities, reset, полноценные структурные операции, большие прайсы/shared Header/Footer и transport/RSS gates остаются открыты.
