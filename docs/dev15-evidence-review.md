# DEV-15: предварительная сверка достаточности evidence

## Продолжение после D-388, 2026-11-02

После разрешённого возобновления Node-preflight подтвердил 144 сохранённые SHA. Независимое code-review builder исправило EV-REV-001 (форма счётчика оставшихся контейнеров) и EV-REV-002 (точное происхождение прежнего/исправленного LG-контроллеров). Итоговый builder SHA: `7ecf9cb0c4daa6071a8c1159c7668b14e64f77d6a41c0c86614b98fa6078426c`.

Отдельно приняты код read-only validator и его запуска: Python SHA `e2dd4d7786b0f67a2dbdc2c2c18c47dfcb2a8e1ac401ad7eb6aed58f0e4dfdf8`, Node SHA `22f62baefe7fd0438623315d20f0748861acf839c0d9b48c989f0a3f5b73b53a`. Проверяется настоящий `_completed_evidence`, без SQL/секретов/UNIT-bypass; отрицательные содержательные варианты имеют пересчитанный тестовый SHA.

Независимое package-review: APPROVED CODE / QA / CAPACITY по точным SHA unit/calibration/provenance/review-definition и ожидаемому review `983cb3f34231de2ebb68505643402f571fa40570c183eb3b09981270358b015b`. Сверены 63 входа, 12 HMAC и 120 проверок файлов происхождения; исторические и составные области явно раскрыты. На этом основании Finalize создал review и подписанную квитанцию. Это разрешение завершить пакет, не активировать MAIN.

Фактическая проверка после Finalize: PASS трёх manifests и всех 10 отрицательных вариантов. Итоговая сохранность и ACL — PASS; подробности и SHA в dev15-evidence-results.md.

Финальное независимое result-review: **APPROVED**. Подтверждены receipt `666ba317…23f51`, validation `cbdb645b…08bb2`, HMAC и связи manifests/review/provenance, 63 неизменных входа и полный состав 30 host/frozen файлов. Raw logs согласованы с результатом; network none, readonly mounts, без БД и UNIT-bypass, exit 0/OOM false. Сохранность, ACL 283/566, контейнеры 0 и disabled/пустой permit подтверждены. Итоговое описание корректно сохраняет исторические FAIL, NOT_RUN предыдущих фаз и ограничение периода memory peak. Замечаний к принятой области нет. Пакет не является активацией, policy/run lease или native RP15-013–019. DEV-15 около 96%, этап 8 около 28%.

Последующий исторический текст описывает прежнюю паузу; она снята D-388.

2026-11-02, D-387, EV15-001–006. DEV-15 около96%, этап8 около28%.

Независимый рецензент подтвердил достаточность выбранных результатов для подготовки трёх manifest существующего B._completed_evidence. Это readonly-сверка плана/покрытия, не review ещё не существующего пакета и не разрешение активации.

Unit001–007: принятый131preview на014efc и соответствующие review; unit-context/commonCASprimitive нельзя объявлять фактическим restart/lease/native. Calibration008–012: LGsemanticPASS+independentrollback+отдельныйwrapper0/7 при originalhostFAIL961a…/post-fixE2ENOTRUN; oldcapacity5fbc+proof29unchanged+new131; reserve/injection010; TLS4c78…; RA30f… с раздельнымипериодами/budget/reserves. Общий manifest source014efc означает проверенную композицию длятекущегоартефакта, не переписывание historical5fbc.

Review CODE/QA/CAPACITY может получитьPASS лишь после независимогоreview точныхmanifest/indexSHA и результатаvalidator. Старые review-статусы не заменяют review нового пакета. Sidecar обязан сохранить реальные rawSHA/HMAC, происхождение и ограничения, без циклических self-hashes. Negativevalidatorcontentcases должны обновлять тестовыйpolicyhash, чтобы проверялось содержимое, а не лишь несовпадениеSHA. Validator безUNITbypass/БД/секретов; пакет не являетсяpolicy/lease.

Исполнитель подготовки остановлен отдельно поDEV15-EV-RESUME-001 после двух эквивалентных PowerShellParserError. Builder/manifests/index не создавались, ошибочные вызовы не исполнились, Docker/данные не менялись. Дальнейшая работа — только после решения владельца поAGENTS.md. Рецензент ничего не запускал и не менял; native013–019/старыйсайт/VPS не затронуты.
