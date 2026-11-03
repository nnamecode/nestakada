# PG29: независимое ревью пакета

Актуализация Q008/D-419: перед первым Audit Docker API показал CAP_ и Linux Desktop host-drive представления. Только controller/core/selfcheck обновлены по CAPS-REVIEW-001/BIND-REVIEW-001 APPROVED без изменения полномочий/продукта. Latest run50a66937-6be2-4d76-bf50-9849f3601986, canonical708495a6…/rawafdf2f3e…, source31 unchanged; точные SHA и gates — [dev29-q008-runtime-review.md](dev29-q008-runtime-review.md). Старые prepared runs/хэши ниже — история, они не переписывались и не выпускали Audit/admission.

2026-11-03, D-414/D-415. Итоги **PG29-PACKAGE-CODE-REVIEW-002 APPROVED для offline preparation** и **PG29-PACKAGE-RESULT-REVIEW-003 APPROVED для offline prepared result**. Audit/Run/Docker/SQL не допускаются этим отчётом. Рецензент работал read-only, чужой код не редактировал, субагентов не создавал.

## Замечания первого ревью и закрытие

| ID | Приоритет | Первое ревью | Повторное ревью002 |
|---|---|---|---|
| PG29-PKG-REV-001 | P1 | Audit lock препятствовал Run и не связывал phase/run/plan | CLOSED: phase-bound operator ledger + audit-complete с raw audit-result SHA, подписанная baseline и отдельный exclusive transfer-lock; append-only RUNNING/COMPLETE/FAILED, повтор Run запрещён |
| PG29-PKG-REV-002 | P1 | После probe FAIL/timeout отсутствовал обязательный независимый after-witness | CLOSED: общая executeFlow вызывает cleanup witness после любой попытки, включая null/timeout/FAIL/expiry; cleanup сохраняет signed run/db/source/package binding, failure-after/PRESERVATION_UNPROVED отделены от функционального результата |
| PG29-PKG-REV-003 | P1 | Fingerprint не учитывал посторонние non-.py файлы candidate | CLOSED: non-.py и reparse отвергаются; exact candidate/working lists, owned FS negatives .so/.pth/.json/.bin/.pyc/junction |
| PG29-PKG-REV-004 | P2 | Неполные inspect predicates | CLOSED для static gate: helper tmpfs/log/entrypoint/cmd/exact merged env/mount/caps; DB CapDrop/CapAdd/no-new-privileges и полный signed ID. Actual Docker/cgroup/backend — NOT_RUN |
| PG29-PKG-REV-005 | P1 runtime | Нет orchestration VM negatives | CLOSED для offline gate: wrong identity/source/permit/topology, nonempty/session, timeout/lost output/partial cleanup/preservation/expiry/artifact failures и запрет retry; helper inspect/cleanup contracts и owned filesystem negatives отдельно |

Рецензент независимо выполнил syntax/inert import, selfcheck41 PASS, orchestration VM66 PASS и Python guard3/3 PASS. Filesystem-test не повторял с мутацией/escalation; его исходник проверен, фактические7 PASS исполнены координатором. Ошибок инструментов рецензента не было. Новых замечаний P0–P3 нет.

Конфликт expected в core исправлен после сверки всех9 paused SHA: локальный список переименован expectedMounts. Проверки зависимостей выполнены по отдельным последовательным вызовам, а не batch с продолжением после ошибки. Один EPERM файловой fixture устранён штатным require_escalated; изменённые условия дали PASS, ACL не менялись. Предыдущие FAIL/пауза сохранены в resume-документе.

## Привязка результата

Точные SHA девяти проверенных code/test файлов входят в append-only план ignored run `1b296fa0-2cff-4dbf-bcb0-623770d7bf85`. После review002 координатор выполнил offline Prepare/Verify:

- candidate source31, fingerprint `1d25e6fc62f675d63de1226889e19eea3ac17df22f11b40a9f1a04450ea9940e`;
- canonical plan SHA256 `7123610f733ea5d1a9a1b2e38ee1d5b134def01b3e8d7f5dd500f2fb0dc507c9`;
- raw plan.json SHA256 `78badff5441eb6d01f0d8b89f4de286fd632722142ea53914bdf653af847444b` (отличается от canonical SHA из-за записи newline);
- Prepare=PREPARED, Verify=VERIFIED, оба `runtimeAdmitted=false`.

Prepare/Verify проверяют замороженный исторический source/EV63/config/archive signed lineage и отдельный новый candidate; старые подписи/manifest/env/permit не пересоздаются. Admission-файлы/attempt/operator lock отсутствуют, runtime не начинался. Факты файлов не заменяют свежий SQL witness сохранности MAIN/UNIT/архивов.

Пакет готов к подготовке отдельного точного runtime-допуска, но пока не к исполнению. Реальные SQLSTATE/rollback/quota1000/deadline/TLS/container/backend cleanup требуют будущего разрешённого запуска. P29-A и общий DEV-29 не завершены; DEV-29 около35%, этап8 около31%. Старый сайт/VPS не затронуты.

## Независимая сверка подготовленного результата003

Рецензент независимо выполнил только read-only Verify того же UUID и pure hashing: VERIFIED/runtimeAdmitted=false; все9 package SHA и все31 source SHA совпали с plan, canonical/raw plan hashes подтверждены. Verify также подтвердил frozen30/EV63/config/archive signed lineage и пустой disk permit. Run-каталог содержит только plan.json и exact source snapshot; audit/runtime admission/attempt/operator/transfer locks отсутствуют. Документы соответствуют этому ограниченному результату. Замечаний P0–P3 и ошибок инструмента нет, Docker/SQL/Prepare/Audit/Run и filesystem fixture рецензент не запускал.
