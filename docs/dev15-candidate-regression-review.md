# DEV-15: ревью контроллера регрессий кандидата

2026-11-02, D-383, PC15-001–005. DEV-15 около92%, этап8 около28%.

Первый draft SHA `f4b842f0f0dc6f4685c6b7a4bea096d0670e2ec1c209a6595bed9253b214ffc5` проверен независимым рецензентом, runtime не запускался. Gate пока не разрешён.

CAND-REV-001 — блокер: spawnSync timeout180с завершает Docker CLI, но не гарантирует остановку migrate-tool. Следующий verifier мог работать одновременно с тестами, превысив согласованный профиль и оставив запись в UNIT. Исправление: точный owned name/label, bounded private диагностика, scoped stop/reap/rm без-v перед verifier; при недоказанной остановке verifier не запускать. Финал подтверждает отсутствие owned tool. Исправленный SHA и новое заключение будут записаны после проверки.

Цепочка подписанных квитанций, отдельная копия исходников и GateRunner131 дополнительных замечаний в первом проходе не получили. Это code-review, не подтверждение прохождения131регрессии. Продуктовый consumer и старые свидетельства неизменны; старый сайт/VPS не затронуты.

Повторный code-review: APPROVED для SHA `a31151f36c9a9504556e8fca424a1f11d0065351a0470ac2871df25a1e0e10f5`. CAND-REV-001 устранён: уникальное имя/label и проверка принадлежности, bounded private диагностика, scoped stop/reap/rm без-v до chainAfter, отказ verifier при недоказанном reap, итоговый контроль отсутствия owned container. Внутренний alarm180с дополняет host cleanup. Node syntax PASS; draft побайтно перенесён в tools/test-trust-candidate-regressions.mjs с тем же SHA.

PC15-001 проверен только в варианте missing gate: контроллер завершился отказом до создания attempt/report и до вызовов Docker. Проверки bad signature/altered marker этим не объявляются выполненными. Положительный131прогон ещё предстоит.

Независимое result-review положительное:131PASS160.534с/newsource014efc…, HMAC/receipt/gate/preview/raw stdout, неизменность архивной цепочки и Stop0/owned0 подтверждены. Peak памяти не измерен; actual limit256МиБ, завершениеexit0/OOMfalse. Разница raw/report elapsed2мс — два измерения Date.now, не расхождение результата. ПолныйTLS/интеграция этим result-review не подменялись; точный перенос описан отдельно в dev15-candidate-regression-results.md.

Отдельное transfer-review положительное: все30локальных файлов побайтно совпали с испытанным preview/source014efc…, consumer15e. Прежний frozen manifest сохранён inactive/disabled, следующий Start создаст новый снимок. Пустая строка EOF consumer234 — косметическое замечание без блокировки; сохранены точные испытанные байты. Обычный diff-check сообщает её; проверка остальных whitespace через core.whitespace=-blank-at-eof PASS. Повтор131только ради EOF не требуется. Версия этого документа на момент допуска сохранена в ignored work/candidate-review-at-run.md с SHA, совпадающим с исходным gate; gate/attempt не переписаны.
