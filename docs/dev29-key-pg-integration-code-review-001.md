# DEV29-Q031 — независимое code review

Статус: CHANGES_REQUIRED. Reviewer: q026_result_auditor. Дата: 2026-11-04. Разрешения на rehearsal/Prepare/native этот документ не даёт.

Frozen root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1. Package55 SHA256: cfd7aeb56b70ad386126e9225a002f08c9e48c72828434e288f808d8e507479c. План: df2c00f148f581c6f4113ccfe2febf4c76d385bfd2e36ccca87b3c44be184311.

## Проверенное основание

Совпали source55/package hash и девять переданных public artifact pins. Baseline50 совпал с checkpoint и исходными Q026/Q030 файлами. Protected24 независимо воспроизведены точными известными run/proposal substitutions и единственным derived bootstrap.sql SHA в supervisor; функциональные строки не игнорировались. Проверены 14 evidence hashes и восстановленный real-helper summary. Заявленные 192 distinct offline PASS не заменяют behavioral proof фактического runtime wiring.

Прочитаны новые key-origin/key-host/key-lease, reader-pg и изменения реальных Prepare/Run/Cancel/stage/Flow/review-facts/composite adapters. Проверены eight-file RO reader, special tag exclusion из ordinary privateFacts, runtime receipt linkage, сохраняемые SQL/workers/supervisor/capture контракты. Тесты повторно не запускались; private inputs, ключи, tag values, Docker и SQL не читались и не запускались. Tool/read ошибок при этом review не было. Ниже — blockers на этих frozen bytes.

## KEYPG-CODE-R1 / P2 — дополнительный secret byte сверх bound

Место: real-host/key-origin.mjs:11, boundedFdRead.

После чтения first.size <= max выполняется дополнительный io.read на один байт в позиции bytes.length. При росте original/copy с8192 до8193 функция действительно читает8193-й байт до KEYPG_READ_GROWTH. Для tag аналогично возможен33-й байт при bound32. Это нарушает KEYPG-A03 и явно согласованные read limits.

Исправление: убрать дополнительное чтение за cap, сохранив повторные pinned FD/path identity, size/core/ACL проверки. Growth должен отвергаться без превышения общего числа прочитанных байтов.

Проверка: считать реальные requested/returned bytes в fake FD adapter; стабильные8192/32 проходят, рост после начального stat отвергается, total read никогда не превосходит соответствующий cap. Сохранить short-read, inode/path drift и same-size content negatives.

## KEYPG-CODE-R2 / P1 — work budget блокирует Original-after в cleanup reserve

Места: real-host/controller.mjs:93 verify; :97 rawDocker; :150 original; capture/storage deadline по тому же original-after path.

verify безусловно вызывает lease.check('VERIFY'), использующий workEnd3000. Original-after начинает с verify и выполняется до innerTerminal=true. rawDocker также выбирает work HOST_IO, пока safetyDepth=0 и innerTerminal=false. Поэтому после workEnd, при ещё действующем cleanup reserve600, Original-after блокируется. Исправить только строку verify недостаточно: тот же lease context нужен downstream engine/create/attach/inspect/cleanup и их deadlines.

Исправление: явная узкая classification разрешённых terminal/original-after операций для выбора cleanup leaseEnd и shorter parents. Полный keyState.verify, host-key continuity, original+copy MAC, metadata/ACL и прежние guards/частота остаются обязательными. Никакого обхода integrity для Original-after.

Проверка: actual Original-after adapter после workEnd и до leaseEnd может выполнять только terminal proof при valid integrity; новые work/PG dispatch запрещены. Drift host-key/tag/original/copy по-прежнему отвергается. На/после cleanupEnd запрещён новый dispatch; awaiting/opaque IO и final checks не обновляют deadlines.

## KEYPG-CODE-R3 / P1 — stage safety cleanup зависит от отказавшего content guard

Места: key-stage/runner.mjs:38 qualifyForPg; real-host/controller.mjs:146 stage hooks.

Stage call adapter вызывает hooks.verify для всех операций, включая cleanup info/meta/stop/remove. Переданный root callback всегда вызывает keyState.verify. Content/tag drift во время qualification поэтому блокирует даже доказуемое прекращение owned helper. Это противоречит отдельному safety cleanup контракту KEYPG-A04/A07.

Исправление: отдельный guard только для strict owned helper stop/remove и необходимых RO code/authority/engine/identity/intent proofs. Он не требует успешно пройти именно отказавший content guard; work/create/start/PG сохраняют полный verify. Unresolved intents, чужая identity или недоказанная continuity не разрешают unsafe unlink. Это НЕ ослабление Original-after из R2.

Проверка: failure injection через actual stage call adapter при content drift прекращает/удаляет подтверждённый owned helper, запрещая новые create/start. Foreign id/nonce/engine, unresolved intent и недоказанный terminal proof должны оставлять UNPROVEN без unsafe unlink.

## KEYPG-CODE-R4 / P1 — composite pin не соответствует сохранённому inner receipt

Места: real-host/controller.mjs:165; real-host/failure-host.mjs commitResult; receipt('result',r).

innerResultSha256 вычисляется как sha(stable(sign(result,key))). Но receipt перед подписью добавляет recordedUtc/recordedMonoMs/engine/plan/package/run metadata, а commitResult возвращает исходный result, не persisted envelope. Поэтому указанное значение не является raw SHA сохранённого signed result.json; independent read-only audit не сможет замкнуть этот pin на реальный artifact.

Исправление: явно выбрать raw persisted receipt domain либо однозначный canonical value domain. Считать pin с фактически сохранённого/read-back validated inner artifact; не реконструировать подпись сокращённого объекта. Persisted=false или mismatch не должны давать успешный composite.

Проверка: real receipt adapter с добавленными metadata возвращает pin, воспроизводимый без private HMAC key из сохранённого artifact. Mutation/substitution/missing/readback mismatch отвергаются.

## KEYPG-CODE-R5 / P1 — qualification callback подключён к review IO, не к Flow IO

Места: real-host/controller.mjs:145-146 local io внутри review(kind,value); :148 actual const io={verify,...}; real-host/flow.mjs qualification-before-admit.

qualifyKey находится в local review IO. Actual Flow IO его не содержит. Flow условно пропускает отсутствующий callback и переходит к admit; там keyState.requireBound отвергает PENDING. Следовательно этот frozen Run не способен выполнить qualification и дойти до INIT/PG.

Исправление: перенести qualification callback в actual Flow IO; review IO не должен владеть им. В Q031 отсутствие обязательного callback должно явно отвергаться до mint/create/start, без silent skip; legacy mock контракты не должны создавать Q031 fallback.

Проверка: behavioral test через реальную Flow factory/adapter, а не includes строки: qualification ровно один раз до первого admit/network/DB. Отсутствие/FAIL qualification запрещает admit/create/start. Linked receipt/reader8/integrity проверяются тем же actual path.

## KEYPG-CODE-R6 / P2 — Run и Cancel не имеют общей атомарной claim

Места: real-host/controller.mjs:61 cancelPrepared; :86 Run claim; key-origin.mjs cancelTagProtocol.

Допустимый interleaving двух CLI процессов: Cancel unused() видит отсутствие KEYPG-RUN; Run видит отсутствие cancellation marker и wx-создаёт KEYPG-RUN; Cancel затем пишет другой marker и удаляет tag, пока stage ещё отсутствует. Cancel может завершиться PASS после уже активной Run claim. Два отдельных check-then-write marker не обеспечивают контракт Run OR CancelPrepared.

Исправление: shared exclusive lifecycle claim для Run и Cancel до использования/удаления tag, с проверкой mode/run/pins. Проигравшая ветвь не удаляет tag и не начинает dependent work; никаких повторов. Сохранить marker-before-unlink и честный partial/UNPROVEN outcome.

Проверка: детерминированные interleavings в обе стороны через actual claim adapter. Только один победитель; Cancel никогда не удаляет tag уже claimed Run, Run не стартует после Cancel claim. Проверить failed marker/claim и stale/foreign claim.

## KEYPG-CODE-R7 / P2 — terminal unlink игнорирует pinned copy identity

Места: key-origin.mjs:24 closeAfterTerminal; real-host/controller.mjs:165 unlinkCopyConfirmed; key-stage/runner.mjs:35 cleanDirectory.

Origin передаёт copyMeta в unlinkCopyConfirmed, но actual callback объявлен async()=> и игнорирует его. Stage.cleanDirectory закрепляет directory dev/ino, а file before/after сравнивает только с текущим snapshot. Если copy заменена после полного verify и до первого cleanup lstat, новая regular/nlink1 запись на том же пути может быть удалена без сравнения с qualified copy identity.

Исправление: передавать и проверять pinned copy identity непосредственно в actual unlink boundary, вместе с directory/path/reparse/nlink checks. Неизвестный или заменённый файл сохраняется с UNPROVEN; не рекурсировать и не удалять original/чужие файлы. Предыдущий full MAC verify не заменяет проверку identity удаляемого объекта.

Проверка: замена file inode/identity после integrity verification перед actual cleanup должна запрещать unlink; valid pinned copy удаляется. Directory replacement, hardlink/reparse, partial unknown ownership и unresolved helper intent остаются fail closed.

## Следующий допуск

Нужны минимальные fixes, новые targeted behavioral negatives и независимый rereview exact package с delta/checkpoint/evidence closure. Текущий пакет не одобрен. Source edits, тесты, private/native операции в рамках этого review не выполнялись; записан только данный review-документ.
