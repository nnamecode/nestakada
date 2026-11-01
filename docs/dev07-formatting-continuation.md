# DEV07-F — ограниченное продолжение оформления и абзацев

2026-10-31. Техническое предложение к предварительному ревью, не разрешение реализации и не итоговый допуск DEV-07. Подготовлено только чтением текущего кода и требований. Действуют D-301/330/331, es-format-v1, права и selected current/draft/stage; новые зависимости, ресурсы, CSS inline или бизнес-ограничения не предлагаются. Основания: dev07-editor-contract.md, dev07-format-carrier.md, фактическая матрица dev07-embedded-coverage.md. Общие блоки и полная семантика reset остаются отдельными воротами.

## 1. Обнаруженная техническая граница

В carrier-editor.mjs импорт вложенных inline span объединяет наследуемые font/size/fg/bg в esFormat каждого текстового участка, а strong/em/u/s/sub/sup — в marks. Нынешний clearFormatting снимает эти marks, но отказывает всему документу при наличии любого protected parent. Это избыточная техническая граница для выделенного разрешённого текста.

Однако slot хранит собственные format attributes, а parent — block attributes. Их удаление меняет защищённую карту; обычное снятие marks не отменяет их наследование. Также protected_policy.py сопоставляет точный ordinal path каждого protected parent: вставка обычного p до него пока возвращает PROTECTED_STRUCTURE_EDIT_UNSUPPORTED. Настоящий обход этих границ требует отдельного проекта, не молчаливого ослабления map validation.

## 2. Предложенный первый реализуемый объём

### F1. Сброс выделенного inline-оформления

Существующая command('clearFormatting') сохраняет все уже безопасные ordinary workflows: без protected nodes — прежний caret reset stored marks и выделения в нескольких обычных блоках; при наличии protected nodes — обычные диапазоны, не затрагивающие protected map. Новый поддержанный случай внутри protected content — только непустое выделение целиком в одном проверенном esProtectedSlot. Для owner и employee действуют существующие права на field; проверка на сервере не заменяется UI.

Одна PM transaction удаляет esFormat и semantic marks strong/em/u/s/sub/sup только у выбранного текста. Текст, Unicode/codepoints, hardBreak, esLink с explicit target-field/anchor, esAnchor, тип блока, align/margins, slot/parent attrs, marker/image/reference IDs и actual media ledger не меняются. Невыделенные части сохраняют исходные marks. Для HTML canonical новые reset attributes/style не вводятся: выбранный текст просто сериализуется без снимаемых marks. Вложенное inline-наследование, уже отражённое в marks, таким образом снимается семантически, а не только визуально.

Непустое выделение с effective inherited slot font/size/fg/bg не объявляется поддержанным полным reset: команда целиком возвращает controlled unsupported без transaction. В новом protected случае также отказываются cross-slot/cross-block/atom/opaque-table ranges и пустой caret внутри slot; интерфейс просит выделить текст или сообщает границу поддержки. Это не запрещает прежние безопасные ordinary caret/multi-block операции и не является новым запретом согласованного редактора. CSS font-weight:normal, font-style:normal, text-decoration:none и vertical-align:baseline под semantic ancestors остаются STYLE_CONTEXT_UNSUPPORTED на input; F1 не снимает этот producer gate и не обещает полного HTML/CSS reset.

### F2. Обычные paragraph split/join рядом с защищённым содержимым

Новый поддержанный структурный сегмент: последовательность обычных root-level p после последнего protected parent; если protected parents отсутствуют — последовательность root-level p документа. Это добавление не блокирует уже безопасный Enter в ordinary headings/lists и другие прежние ordinary операции, не меняющие protected map. Остальные элементы F2 не преобразует. Разделение p перед существующим protected parent либо между protected parents пока явно unsupported, поскольку изменит их ordinal paths. Внутри slot Enter продолжает создавать hardBreak, а не новый paragraph/slot.

Enter с collapsed caret в поддержанном p выполняется PM transaction split, без native DOM restructuring. Block anchor остаётся только у исходного левого p; у нового правого p anchor=null. Остальные block attrs сохраняются у обеих половин; текст/inline marks делятся в точной позиции. Если split пересекает inline esAnchor, операция целиком отклоняется до dispatch, чтобы не дублировать его identity. Это не создание нового произвольного anchor ID.

Backspace в начале либо Delete в конце поддержанного p объединяет только непосредственно соседний обычный root-level p того же сегмента. Сохраняется тип p и block attrs левого p, содержимое конкатенируется без вставки/потери текста, marks каждой части сохраняются. Join требует точной совместимости block attrs и сохранения всех anchor identities: правый block anchor не теряется молча, несовместимые либо дублируемые anchor identities дают controlled unsupported до dispatch. Для differing block attrs первое исполнение также предлагает целиком controlled unsupported вместо потери оформления; более широкая операция отдельно. Protected parent/slot/atom и opaque table никогда не являются стороной join. Interior Backspace/Delete остаются native с ранее проверенным selection sync; ручного удаления UTF16 code units нет.

Перед reset/split/join оба DOM endpoints проверяются на принадлежность одному текущему view; public DOM-to-PM mapping сверяет актуальные типы узлов, позиции, IDs и допустимый диапазон. Классификация операции и её transaction используют один и тот же проверенный диапазон, а не старую PM selection после отдельной DOM-проверки. Stale point, atom, cross-slot и неподдержанный cross-block hazard дают controlled отказ до PM transaction/DOM изменения; разрешённый ordinary multi-block reset из F1 не объявляется hazard только из-за числа блоков. Private observer API не используется. Кандидат проверяется до dispatch: функции canSplit/canJoin из уже установленного PM transform и неизменность protectedShape/IDs/paths. За один ввод — одна transaction; undo/redo атомарно возвращают текст и структуру, не выпускают новые media IDs и не вызывают issue/upload.

## 3. Сохранение и отказ

Команды проходят прежний dirty/proof invalidation до render/CSSOM; failed view не даёт cached successful export. Canonical source проходит обычный Check, явное принятие normalization при необходимости и отдельный Save. D334 permanent fingerprint/replay, draft basis, stage consume и source selectors не меняются. F1/F2 не записывают БД самостоятельно.

Ограничения source1MiB/text200k/nodes20000/depth32, body64MiB, один heavy slot, child AS384MiB/CPU10/wall20, CSP и ограниченный CSSOM registry остаются прежними. Разрастание кандидатного дерева проверяется до dispatch/DOM, затем независимо сервером; отказ по границе не обрезает текст и не сохраняет частичный результат. При нехватке ресурсов/занятости сохраняется доступный RAM-ввод, нет автоматического повтора или увеличения лимита. Фактические maximum-bound/time/RSS доказательства обязательны до допуска; счётчик дерева сам по себе не доказательство достаточности ресурсов.

## 4. Независимые сценарии до кода

| ID | Проверяемый результат |
|---|---|
| F07-001 | Nested span font/size/fg/bg и strong/em/u/s/sub/sup → native range reset части Unicode-текста → computed style + canonical → настоящий Check/Save/reload. Соседние marks, текст и переносы сохранены. |
| F07-002 | Документ с реальными READY-фото: owner/employee reset одного допустимого slot без inherited slot attrs; map/IDs/reference/bytes/Stable unchanged. Наличие фото в другом месте больше не блокирует ordinary text reset. |
| F07-003 | Link href/title/target/rel и explicit target-field/anchor, anchor identity переживают reset; block anchor после split только слева, правый=null; inline anchor split и join с потерей anchor отказаны. Inherited slot format/cross-slot/cross-atom reset дают отказ без doc mutation/receipt/версии; прежние ordinary caret/multi-block reset и heading/list Enter сохранены. |
| F07-004 | Native Enter в p после последнего protected parent: точный Unicode/marks split, затем Check/Save/reload, одна automatic version; undo/redo возвращают точную структуру и предыдущий accepted source при model equality. |
| F07-005 | Native Backspace/Delete на соседних ordinary p с одинаковыми block attrs: точный join, undo/redo; interior emoji/grapheme deletion positive отдельно. Rapid cursor movement без QA sleep/force/selection setters. |
| F07-006 | До/между protected parents, на границах atom/slot/table, mixed attrs и cross-block ranges — целый отказ, ни одного transient style attribute/CSP violation, неизменные markers/paths/text. |
| F07-007 | Current/draft/stage исходники: команды RAM-only до explicit Save, отдельно draft/check/apply; сотрудник не получает owner fields или private draft. Existing stale grant/session/base и unknown-result retry semantics сохраняются. |
| F07-008 | Source/node/depth/codepoint exact bound/+1, repeated reset/split/undo и CSSOM cleanup: реальные время/RSS/rule count, controlled failure до render/commit, прежний current/Stable/files/receipt целы. |

Эти сценарии пока не исполнены. Сначала reviewer/QA уточняют точный поддержанный scope и отрицательные случаи, затем root выдаёт ограниченный code gate. Публичный renderer, generic protected reparenting, full inherited reset, paragraph split внутри slots, list/table structural editing и shared Header/Footer здесь не реализуются и не закрываются.
