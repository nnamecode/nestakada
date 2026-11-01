# DEV07-CM — результаты совмещённых максимумов

2026-11-01, D-344. DEV-07 около96%, этап8 около20%. Ограниченные CM07-001–003 завершены: **3 теста, 5 настоящих Check, PASS за63.227с**. Независимый `/root/combined_review` проверил код до запуска и фактические результаты после него; открытых блокеров этой области нет. Продуктовый код не менялся.

## Проверенный корпус

Каждое из двух разных rich-полей одновременно содержит1МиБ UTF8,200000 codepoints,20000 элементов и глубину32. Независимый stock parser подтверждает структуру. Два retained source также по1МиБ и отличаются от обоих кандидатов; случайного cross-field exact memo hit нет.

| Сценарий | Факт |
|---|---|
| CM07-001 | Current source, владелец и сотрудник с intro/main grants:2HTTP200, точные source/candidate hashes, проверенные подписанные CheckReceipt |
| CM07-002 | Те же поля вместе с прайсом32колонки/500строк/10000ячеек, label500 и text1000 четырёхбайтовых codepoints: owner и сотрудник со всеми3grants,2HTTP200. Запрос43966711B, ответ43967751B, точные хэши прайса/полей |
| CM07-003 | Реальный query/body owner-draft selector и наблюдение источника на границе настоящего normalize_input:1HTTP200. Выбранные draft ID/revision/base/hashes совпали; черновик не публиковался |

Во всех5случаях настоящий Popen ровно1, exit0, waitpid подтверждает reap, stdin/stdout/stderr закрыты, EditorSlot освобождён. Построчный digest полных выбранных отношений включает PageContentState, PageRevision, OwnerDraft, RestoreStage, VersionBasePin, AssetUsage, OperationReceipt, RevisionMetadata, RevisionProtection, IdentityReservation; до/после равны. Proof проверяется криптографически через verify_check_receipt, а не только по наличию поля.

## Ресурсы и предел свидетельства

Фактический cgroup peak478445568B =456.28125МиБ при лимите805306368B=768МиБ; CPU1/pids128 неизменны, OOM/oom_kill0. Peak lifetime включает подготовку fixture и предыдущие случаи, а не только текущий handler. Максимальный наблюдавшийся handler12.742с. На самом тяжёлом owner CM002 child CPU9.083user+0.500sys=9.583с при лимите10с: **запас всего около0.417с**, результат не доказывает устойчивого запаса для любого допустимого HTML или другой среды. AS384МиБ/CPU10/wall20 подтверждены неизменными константами/фиксированным bootstrap; отдельного чтения /proc RLIMIT child не было.

Framework reader seam возвращает те же bytes; Nginx/socket MAX и browser MAX не проверялись. Retained source здесь unprotected: его байты реально передаются/удерживаются, но разбор предельных protected maps не доказан. Save/draft commit MAX, restore-stage combined MAX, все adversarial/entity/attribute/table сочетания и другие браузеры остаются отдельно. Recovery branch присутствует и проверена в коде; при5PASS не исполнялась. Исторические207server/22MODEL/GUI/network наборы здесь заново не запускались.

## Воспроизводимость

- Сценарии до кода: dev07-combined-checks.md, SHA256 a4d4bf8113c317ee57e88574a6fd633673722c15a2816a4e9d8ad7463a7f29e6.
- Тест: app/page_editor/test_combined_http.py, SHA2564672147cc3e1578e27a5bcfc7426597e6b3e8bccd320e194f7b7b05d688bfc36; scripts/test-editor.ps1 -Suite combined сохраняет прежние guards/caps.
- Run6c5aec22-0219-4a8f-93cd-91fba43915af;171frozen files/0drift; manifest SHA2568631fa3352c9185321cc796f1f93dd564918fc0038609ace040376d7928b6f00.
- Локальные свидетельства: work/dev07-combined-20261101/combined-first.txt, cohort-first.json, start-first.txt. До работы95существующих dirty/untracked файлов сохранены побайтно в before.

Результат не закрывает весь DEV-07 и не разрешает production. Старый сайт/VPS не затронуты. Подготовка Header/Footer/квот продолжается отдельно по D-345; конкретный остаток — dev07-shared-preparation.md и dev07-review.md.
