# DEV-15 — независимое ревью рабочего допуска

2026-11-02, D-380, DEV15-CLOSE-01. Автор bounded/CLI/новых тестов — dev15_policy, интеграций profile/services/recovery — координатор. Независимый readonly-рецензент dev15_review не менял файлы и не запускал код/SQL/Docker/тесты. Область — локальный код и UNIT, не допуск MAIN до capacity/native gates.

## Результат code gate

**Положительный перед общим UNIT.** Проверены closed/HMAC policy и run lease, operator role, подписанный ActivationIntent, текущая immutable chain до16версий, exact retry/CAS/predecessor/полное исходное состояние v2, retirement старой ветки, лимиты и replay-before-new-charge, новая recovery scope/version2/secret/binding. Смена ENV сама не активирует запись.

| Замечание | Последствие | Исправление и результат повторного ревью |
|---|---|---|
| DEV15-BREV-001, P1 | Prepare, новая policy или recovery metadata могли занять место, уже обещанное завершению. После переноса reserve в logical следующие replay/finish закрывались. | Working prepare и metadata соблюдают logical+reserved≤64МиБ, отдельный reserve≤16МиБ; atomic rollback и replay/finish подтверждены targeted accounting-injection тестами в131PASS. Закрыто в ограниченной UNIT-области. |
| DEV15-BREV-002, P1 | Одно имя БД в settings не исключало stale connection при обходе незавершённых evidence. | UNIT-authority подтверждает фактический current_database при входе и повторно перед bypass. Неподходящие metadata/ENV — отказ без SQL. Целевой тест в131PASS; закрыто в ограниченной UNIT-области. |

Дополнительно проверен общий direct-service предел canonical body1МиБ: quoted256REDIRECT с512путями по2048UTF8байт отвергается до SQL без truncation. Для completed-evidence validator добавлен22-йтест фактических tempfile/rawSHA/closedPASS и четырёх отрицательных вариантов без UNIT-bypass. Это синтетические fixtures валидатора, не реальные capacity manifests; узкое ревью теста положительное.

Новых блокеров ограниченного UNIT-прогона нет. Actual capacity/5120items TLS/host exclusion/новый container-bound lease/MAIN activation/native lost-response/ресурсы/внешняя freshness остаются NOT RUN. Наличие code gate не разрешает подписать production или непройденную capacity.

## Фактический result gate

**Итоговый scoped result gate положительный.** Рецензент прочитал отчёты и4точныхJSON с UNIT/budget/MAIN/final evidence; исходники не менял и сырые закрытые логи не читал. Общий прогон на frozen source30/5fbcb9d9ea04ee58853b9b8d9fe2131fc6b0d1122f087239f3c66bfded768986, run40a78681-46e6-4944-ae55-7bb8deba1ba2:131/131PASS154.169с. MAIN counts/fullSHA/Head9/epoch2 сохранены, AdmissionPolicy0. Final Status stopped/disabled/0running, host/frozen/configdrift0; DB OOM0. Наблюдаемый бюджет всех6DEV15hostпапок/DB/logs отделён от меньшего unit-budget однойпапки; capacity/whole-helper/hardquotaPASS не объявлен. Новых блокеров нет; предыдущий109PASS этот прогон не заменяет.

По редакционному замечанию уточнён порядок: capacity/code/QA → MAIN activation → native. Координатор сохранил actualRunningContainers0 в отдельный operator-final-status.json и добавил его в итоговый evidence. Это дополнение фактического Status, не изменение проверенного исходного кода.

DEV-15 остаётся в работеоколо90%, этап8 около28%; старый сайт/VPS не затронуты.
