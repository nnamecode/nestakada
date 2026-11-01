# DEV07-F — точное выделение для FORMAT-команд

2026-10-31. Адресный технический контракт до кода, QA и независимого review gate. Scope только font/size/fg/bg в carrier-editor.mjs; API/selectors, другие команды, серверные права/Check/Save, зависимости/CSP/лимиты не меняются.

## Фактическая причина

work/dev07-f-20261031/cssom-diagnostic/browser-first/host-report.json: до первого fg DOM находился в собственном surface, выделял5 codepoints (offsets0→5), тогда как PM selection1→1 была пустой. После команды DOM стал collapsed, PM остался empty, появился один stored mark, правила остались44 при baseline43 (исходный size12). После50 команд и reset также44; cleanup завершён, CSP0. Это подтверждает преждевременный view.focus→selectionToDOM, потерявший актуальный DOM range, а не дефект удаления чужих CSSOM rules. Исторический CSSOM_DESTROY_POSITIVE_RULE_MISSING не переименовывается в PASS.

## Предложенная transaction

1. Только для четырёх FORMAT-команд validateAttrs и existing commandSelection(view) выполняются до общего view.focus. Оба live endpoints принадлежат тому же текущему view, сверены model type/positions и protected slot/parent IDs; transaction использует именно этот один проверенный range.
2. Collapsed обычный caret и caret в одном проверенном slot разрешены: команда может законно менять только marks будущего ввода, без обещания нового CSSOM rule до actual text. Непустой диапазон внутри одного validated slot тоже разрешён. Иначе диапазон не должен пересекать protected parent/slot/image atom, opaque table или другой block atom. Обычное многоабзацное выделение разрешено. Hazard отказывает целиком до transaction/DOM mutation; endpoints вне view не подменяются догадкой по прежней PM selection.
3. Создаётся прежний Tiptap chain; только при !validatedSelection.eq(currentSelection) в эту же chain transaction добавляется public tr.setSelection(validatedSelection). При совпадении setSelection не вызывается: esLink/esAnchor и другие нетронутые stored marks сохраняются. При реально перемещённом caret старые stored marks прежнего места не переносятся.
4. Затем выполняется прежний setMark('esFormat',checkedAttrs) с существующей Tiptap mergeattrs semantics, включая сохранение остальных font/size/fg/bg и ссылок/якорей. Всё — одна chain/run transaction. До изменений chain запоминается protectedShape исходной модели. После setMark, перед run добавляется public chain.command(({tr})=>...): candidate protectedShape должен равняться исходному, а candidateBudget(canonicalDocument(tr.doc,...)) должен пройти прежние границы. На несоответствии вызывается фиксированный failure, прерывающий chain до run/dispatch; простого return false недостаточно, поскольку Tiptap run может dispatch transaction независимо от итогового boolean. При успешной проверке callback возвращает true. Только после run вызывается синхронный view.focus. Нет нового native selection setter, private observer API, ручного DOM formatting или inline style; frontend не получает authority на новый source/Asset/map.
5. Явный финальный guard из п4 добавляется именно FORMAT-chain: нынешний dispatchCandidate относится к reset/структурным командам и не является общей защитой FORMAT. dirty/proof invalidation, view-fault block и CSSOM lifecycle сохраняются. Bold/italic, align/margins, links, reset, split/join, undo/redo этим исправлением не меняются. Отказ по stale/unsafe range/map/budget сохраняет исходную модель, ввод не публикуется и не повторяется автоматически.

## Сценарии до code gate

| ID | Независимый oracle |
|---|---|
| FSEL-001 | Native DOM range5 при stale collapsed PM → каждая из4 команд применяет формат к actual selected text; первые/последние символы целы, canonical/actual computed CSS/серверный Check и reload согласованы; никакого QA delay/PMselection setter |
| FSEL-002 | Тот же caret и stored esLink/esAnchor + прежние esFormat attrs: FORMAT сохраняет нетронутые marks/attrs. Перемещённый DOM caret не наследует старые marks другого места; future typed text проверяется отдельно |
| FSEL-003 | Ordinary multi-block selection и один actual protected slot (включая collapsed slot caret) работают; cross-slot/atom/table/foreign view отказываются до изменения. Actual protected map/refs/bytes и текущие права неизменны |
| FSEL-004 | Настоящий FUI00550 циклов FORMAT/reset/CSSOM destroy, source refresh и две независимые views; CSP0, no inline style/colgroup, cleanup честный. Empty-caret stored-only control не выдаётся за selected-text positive |

Ранее пройденные серверные207 проверок относятся к своим зафиксированным cohort. Этот документ не объявляет новый GUI PASS. После заморозки независимых QA-сценариев и review root выдаёт отдельный bounded code gate; до него app остаётся frozen.
