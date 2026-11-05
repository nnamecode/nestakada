# DEV29-Q031 — независимое code rereview revision002

Статус: CHANGES_REQUIRED. Reviewer: q026_result_auditor. Дата: 2026-11-04.

Current package55 SHA256: 14bbe843bdbeafec4f6e337ce0ea3ff78d96f052b1a018b3bda4fda66f71e45b.
Root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
История первого review сохранена отдельно в dev29-key-pg-integration-code-review-001.md. Этот документ не разрешает rehearsal, Prepare или native.

## Закрытые findings

KEYPG-CODE-R1 CLOSED: extra-byte EOF probe удалён; сохранены повторные FD/path/metadata/ACL checks. Фактическое чтение ограничено8192/32.

KEYPG-CODE-R3 CLOSED: production stageCallAdapter разделяет full work verify и strict owned safety cleanup. Root safety hook проверяет host-key continuity, current code/source/authority, ancestry, lease и persisted intent. Create/start не допускаются safety ветвью.

KEYPG-CODE-R4 CLOSED: composite связывается с actual persisted signed receipt в явном RAW_SIGNED_RECEIPT_BYTES/v1 domain. Проверяются ledger raw SHA, authenticated readback, value equality/context и identity до/после чтения. Дополнительно сохранён canonical payload hash.

KEYPG-CODE-R5 CLOSED: actual Flow IO создан bindQualifiedFlowIO с реальным qualifier, удалён optional skip. Обязательная linked qualification и exact DB bind paths проверяются до admit/network/DB. Local review IO больше не владеет callback.

KEYPG-CODE-R6 CLOSED: Run и Cancel используют одну signed exclusive wx lifecycle claim с readback и pins до dependent effects. Два отдельных marker больше не являются механизмом взаимного исключения.

KEYPG-CODE-R7 CLOSED: actual terminal callback передаёт pinned copyMeta в qualified cleanup. Pin обязателен до FS операций; его identity/core сравниваются в unlink boundary. Replacement/unknown pin не авторизуют удаление. Unknown directory и unresolved intents сохраняют UNPROVEN.

## KEYPG-CODE-R2 / P1 — остаточный post-await parent-deadline дефект

Первоначальная ошибка workEnd classification исправлена: Original-after получил узкий cleanup scope, raw/capture paths ограничены им и не могут dispatch PG/work. Полный keyState.verify и прежние integrity guards сохранены.

Остаётся новая конкретная граница:
- real-host/key-lease.mjs:7 originalAfterAdapter выполняет await io.prove(); затем io.verify(); и лишь потом io.final(deadline).
- real-host/controller.mjs:94 verify первым вызывает keyState.verify.
- real-host/controller.mjs:88 actual hostOriginIO deadline ограничен leaseEnd и собственными10с, но не commandDeadline текущего Original-after.
- real-host/controller.mjs:153 подключает этот adapter к production Original-after.

Если prove возвращается на/после собственного90с parent deadline, но до leaseEnd, новый full verify запускает ACL PowerShell/secret FD operations ДО clock rejection. Поздний final делает outcome отказом, но не предотвращает уже начатый post-expiry I/O. Текущий overrun test проверяет rejection/выход из scope, а не отсутствие этих I/O.

Минимальное исправление: проверить deadline сразу после await и до full verify; выполнять pre-action clock checks также перед остальными verification/proof шагами. Actual integrity-I/O deadline должен быть shorter-parent bound с текущим commandDeadline, leaseEnd и своим budget, с отказом ДО ACL child launch/FD read при истечении. Не обходить keyState.verify, host-key/tag/original/copy MAC или metadata/ACL guards при valid remaining budget. Для уже начатого opaque I/O мгновенное прерывание не обещается; последующий dispatch запрещён.

Требуемые проверки: actual Original-after verification/host-I/O adapter с recorded dispatch/read counters. Overrun await до/за parent deadline даёт отказ ДО следующего verify/ACL/FD action; истёкший parent при ещё живом lease также не запускает I/O. Valid cleanup reserve выполняет полный verify; drift всех четырёх host-key/tag/original/copy inputs остаётся отказом. Сохранить no-PG/work, cleanupEnd и shorter-parent negatives.

## Closure и ограничения review

Совпали current source55/package, шесть revision pins, baseline/handoff/operator/addendum/plan pins. Проверен frozen checkpoint81:55 source+26 metadata, все совпали. Изменены только семь заявленных source files; старые metadata неизменны. Runtime package admission вычисляет текущий FILES/packageFiles и требует текущий digest, не берёт старый digest из исторического root manifest.

Совпали восемь current evidence hashes. Разделены148 current Node PASS и55 reused Python PASS на побайтно неизменённых Python sources;203 distinct, skip0, targeted11 не прибавлялись повторно. Это evidence builder, тесты reviewer не перезапускал.

При closure-проверке был один ENOENT из-за ошибочного предположения storage prefix checkpoint. После немедленного отчёта bounded inventory подтвердил source/metadata layout; чтение выполнено с новым подтверждённым prefix и exists/isFile checks. Второго real read/tool failure не было. Это не code finding.

Source edits, tests, private/tag/key reads, Docker/PG/SQL/native не выполнялись. Изменён только этот review-документ. До устранения residual R2 и независимого rereview положительный допуск закрыт.
