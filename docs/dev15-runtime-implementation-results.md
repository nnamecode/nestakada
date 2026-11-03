# DEV-15 — рабочая политика допуска: код и UNIT

2026-11-02, D-380, DEV15-CLOSE-01. Продолжение первого инкремента из dev15-runtime-foundation-results.md. Код и общий UNIT проверены; MAIN-активация допускается после capacity/code/QA gates, затем выполняются native проверки. Эти условия ещё не завершены. DEV-15 около90%, этап8 около28%.

## Подготовленный код

Добавлены closed Policy/Run lease версии2 с scope LOCAL_TRUST_BOUNDED_WRITER, подписью существующим recovery-secret, привязкой к полному source/schema/config/runtime/deployment и отдельными точными recovery descriptors. Обычные новые IDs не перечисляются заранее. До SQL проверяются форма/HMAC/source/config/runtime/ресурсы собственного процесса; под Head lock файл перечитывается, проверяются latest immutable policy, schema/incarnation и действующий binding/epoch.

Добавлена закрытая management-команда activate_trust_policy: signed ActivationIntent, actual trust_migrator role, полный исходный Head/state digest v2, predecessor/legacy seal, completed evidence, caps/charge, один атомарный policy row и Head advance; точный повтор возвращает прежний receipt. Перезапуск той же политики заменяет lease, не создаёт новую запись. Таблица и старый pin не очищаются; старые миграции не меняются. Сам CLI не выпускает runtime lease.

Сервисы подключены к новым count caps1000/4096/1024 и прежним64МиБ/16МиБ. Сначала распознаётся точный replay, затем проверяется расход новой операции. Working recovery использует новый scope и явный proof версии2, авторитетное отключение старого binding и новый secret; старый v1 остаётся только у прежнего trial до его retirement. UNIT-authority обходит только отсутствие окончательных reports и требует точную фактическую UNIT БД, не допускает MAIN или ENV-only разрешение.

## Независимое code-review и исправления

Исполнитель новых bounded/command/tests — dev15_policy, интеграции profile/services/recovery — координатор; независимый readonly reviewer — dev15_review. До запуска выявлены и исправлены:

- **DEV15-BREV-001:** независимые проверки logical/reserved позволяли новому prepare или metadata занять будущий logical charge завершения. В рабочей ветке теперь сохраняется invariant logical+reserved≤64МиБ: prepare учитывает свою пару size+reserve, policy/recovery metadata учитывают существующий reserve. Отдельный потолок16МиБ резерва сохранён. UNKNOWN не расходует повторно квоту, terminal переносит уже обещанный reserve в logical без изменения суммы. Targeted accounting-injection тесты проверяют отказы новых действий и сохранность replay/finish, включая whole transaction rollback fence.
- **DEV15-BREV-002:** одно имя БД в settings не исключало stale connection. UNIT-authority проверяет SELECT current_database() при входе и перед обходом evidence; неподходящие ENV/metadata отклоняются без SQL.
- Прямой working вызов сервиса теперь соблюдает тот же предел canonical message≤1МиБ, что и HTTP. Targeted quoted256REDIRECT/2048байт проверяет, что допустимая форма с слишком большим JSON целиком отвергается до SQL, без обрезки.

Повторное code-review положительное, BREV001/002 закрыты. Отдельная22-ятестовая проверка completed-evidence validator на фактических tempfile/их rawSHA прошла scoped code-review: она проверяет gate, не является настоящим capacity report. Code gate — dev15-runtime-implementation-review.md.

## Испытания и границы

Перед изменениями сохранены все13существующих изменённых/новых файлов с SHA в ignored work/dev15-runtime-20261102/operator-before. Исходно stopped/disabled, MAIN Head9/epoch2/4operations/3routes/1tombstone/2receipts, AdmissionPolicy0. Новые signed fixtures работают только в UNIT, под настоящей migrator DB role. Подмена count/head accounting в отдельных boundary tests явно является injection, а не полной калибровкой.

**Общий UNIT131/131 PASS за154.169с**, включая109прежних и22новых. Frozen source30 SHA `5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986`, run `40a78681-46e6-4944-ae55-7bb8deba1ba2`. Это первый прогон этого инкремента; новых FAIL не было. Прежний109PASS/source6e79… остаётся своей отдельной историей; старый FAIL six-table assertion сохранён в foundation-отчёте.

В точной UNIT фактически прошли операторская роль trust_migrator, подписанные фикстуры и атомарный переход/retry/rollback/цепочка16версий, новые UUID без trial whitelist, отказы прав/epoch/source/config/schema/ENV, точный replay/finish на инъекционных count/byte границах, fence/newruntime/newconfig/v2proof/activate/replay/oldsecret rejection/newwriter и evidence validator. Часть ресурсного/host evidence намеренно подменяется синтетическими UNIT fixtures; это не native реальный container exclusion или полный RP15 PASS.

Evidence в ignored work/dev15-20261102/runtime: unit-result-40a78681-46e6-4944-ae55-7bb8deba1ba2.json и unit-budget того же run; сырой вывод приватный. Штатный signed archive guard проверил сохранность старого корпуса до UNIT; он не мигрировался/не очищался. После UNIT отдельный readonly probe подтвердил MAIN Head9/epoch2, counts4/3/1/2/AdmissionPolicy0 и прежние full digests: v1 `64dd0a52dc0732cbc004d09b21d87f17a82d08a0cd885fa9d57f0656bf47f2c4`, v2 `dfdf4021db5dba1b807699b548e4370488fb3582e9c87734206f8f91ee3c6066`. MAIN signed ActivationIntent/новый permit не создавались и не применялись. Probe — work/dev15-runtime-20261102/operator-main-after-unit.json.

DB cgroup peak293724160/536870912байт, OOM/kill0. Наблюдаемый общий бюджет DB data+6hostworkпапокDEV15+logreservation —273225681байт (host16259025, DBdata248578048, logs8388608); это измерение до записи итогового небольшого evidence-файла, не hard quota и не whole-helper peak. Остальные части capacity/ресурсного proof не подменяются этим измерением.

Stop выполнен, Status stopped/activefalse/0running; writeModedisabled/permit{}. Проверены все30host/frozen исходников и config, drift0. Итог — work/dev15-runtime-20261102/operator-final-evidence.json; фактический Status также сохранён в operator-final-status.json и включён в итоговый JSON. ACL закрытого каталога и95егоэлементов проверены read-only через Windows PowerShell5.1: Allow только владелец/SYSTEM. Независимый result-review положительный, блокеров ограниченного code+UNIT инкремента нет.

До реальной активации требуются сохранный capacity corpus/байтовые и count границы/5120items TLS deadline/ресурсы, независимые code/QA/capacity manifests с настоящими SHA, operator host evidence/exclusion/lease на окончательном container ID. Затем native UNKNOWN/terminal lost-body/transport/failure/preservation по RP15. Все эти условия пока NOT RUN. APP/DEV29/HTML admission/external freshness/production остаются за своими воротами. Новых образов/программ/ресурсов не добавлено; старый сайт и VPS не затронуты, push не выполнялся.
