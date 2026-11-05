# DEV29-Q031 — независимое code rereview revision003

Статус: CHANGES_REQUIRED. Reviewer: q026_result_auditor. Дата: 2026-11-04.

Current package55 SHA256: eb3970ae23ed7821d247113991139e7d83d9720053dcaff91155ac1be8d9bac6.
Root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
История предыдущих reviews — отдельные архивы code-review-001.md и code-review-002.md. Этот документ не даёт допуска к rehearsal/Prepare/native.

## Результат узкого rereview

R1 и R3–R7 остаются CLOSED; относящиеся к ним гарантии сохранены. Первоначальная workEnd/cleanup классификация R2 и последующий command-parent/post-await дефект исправлены: Original-after проверяет deadline сразу после await и до verify; actual origin IO получает min command parent/lease/own budget. Full verify при действующем времени сохранён. Per-action guard запрещает новые действия при уже истёкшем parent; поздно вернувшийся open закрывает FD при отказе post-check.

Остаётся own-limit renewal дефект ниже. Поэтому весь R2 ещё не закрыт.

## KEYPG-CODE-R2 — остаточный own10 renewal / P2

Места: real-host/key-host.mjs:11 integrityIoAdapter; real-host/controller.mjs:88 actual Run originIo provider и следующий checkHostKey callback.

integrityIoAdapter вызывает check до и после action, но каждый check заново вычисляет deadline(). Actual provider содержит lease.cleanupDeadline(10000) либо now+10000. При ещё действующем command parent own10 поэтому сдвигается вперёд на post-check.

Конкретный допустимый пример: parent90с, now0; pre-check возвращает end10с. open блокируется и возвращает FD в t15с. Post-check получает новый end25с и пропускает FD/read, хотя собственный исходный10с budget уже истёк. Это не требует истечения общего parent и не исправляется уже добавленным immediate post-await guard. Новая late-open проверка использует constant ()=>10 и этот actual rolling-provider случай не покрывает.

Минимальное исправление: capture preActionEnd до каждого действия; после сравнивать время с min(capturedEnd,current shorter parent), без renewal own budget. Если поздний open превысил захваченный deadline — закрыть FD ровно один раз, не начинать fstat/read. Close/disposal остаётся возможным после expiry. Full integrity не обходить.

Проверить тот же принцип у manual originIo.check pre/post вокруг host-key read: возвращённый pre-action deadline нельзя отбрасывать и заменять новым rolling10 на post-check. Предпочтителен единый actual action wrapper с fixed captured deadline и dynamic shorter-parent clipping.

Требуемые behavioral negatives: actual provider вида min(parent90,now+10), open t0->t15, ровно один close и ноль последующих reads; аналогично late FD read/fstat и host-key read. Если parent становится раньше captured deadline, он выигрывает. При valid own+parent budgets полный verify проходит; host-key/tag/original/copy drift и запрет post-expiry dispatch сохраняются. Opaque уже начатый I/O не обязан мгновенно прерываться, но его поздний возврат обязан отвергаться без следующего I/O.

## Closure

Совпали семь переданных revision003 pins, current55 source/package hash, baseline/handoff/operator/addendum hashes. Checkpoint71 полностью совпал; изменены только пять объявленных source files. Runtime admission по-прежнему считает текущий packageFiles из исходников и не использует исторический root manifest как текущий digest.

Совпали шесть current evidence hashes. Проверены37 captured reuse dependencies: previous/current/actual hashes совпали, changed0/unknown0. Разделены127 current Node +24 reused Node +55 reused Python =206 distinct, skip0; target3 входит в focused40 и отдельно не прибавлялся. Это данные builder, reviewer тесты не перезапускал.

Review ограничен residual R2 и затронутыми integration/admission/evidence boundaries. Новых real tool/read ошибок не было. Исходники и public evidence читались только для review. Код не изменялся, тесты не перезапускались; private inputs/tag/key values не читались, Docker/PG/SQL/native не запускались. Изменён только этот review-документ. До исправления own-limit renewal и независимого rereview положительный допуск закрыт.
