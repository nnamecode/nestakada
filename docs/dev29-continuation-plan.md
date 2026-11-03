# DEV-29: продолжение четырёх PostgreSQL-групп после Q010

2026-11-03. Основание — Q009/D-421 и явное возобновление Q010/D-423 по сохранённому плану PG29-FOCUSED-RESUME-001. Это уточнение исполнения прежних четырёх групп, без расширения архитектуры сайта. До независимого принятия saved001 и этого плана код continuation не начинается.

## Область

Один новый immutable run `d43d7a21-2ec0-4652-9c9a-00e95272db8a` в ignored `work/dev29-publication-20261103/pg-check/continuation/`. Только PG29-003/004/005/006; действия запуска001/002/007 отсутствуют. Старый focused namespace целиком неизменен, прежние admission/TTL/DB IDs/locks не переписываются. PG29-001 не повторять.

Закрытый scope `PG29-CONTINUATION-ROLLBACK-ADMISSION`, без quotaEstimateAccepted. Состав требований к операциям, UNIT52766/marker/schema/empty7tables/3migrationrows/sequence4true, внешней atomic/безусловному rollback/reconnect, MAIN/архивам, source31, SQL guards, workingpermit{}, ресурсам и очистке — прежний Q009. Никаких init/migrate/flush/reset/MAIN writer/API/APP/ingress/pull/build/новых образов/томов/портов/лимитов. Старый сайт/VPS/production/push исключены.

## Предпосылки и привязки

- Bounded saved-review validator должен пройти независимое code/offline review; затем actual Check/HMAC/proof/output/send/after/budget/cleanup review сохранённого001. Его фактические метрики/результат принимаются как prerequisite, а не новый SQL-прогон.
- Новый plan/checkpoint связывает raw/canonical старого plan, first-result/first-receipt, bounded validator/report/independent review и полный manifest frozen focused namespace. Старый source31/current source/protected/ancestry совпадают; старый executable Run не вызывается.
- Повторно RO осмотреть сохранённый том PG18/clean shutdown и measured budget; VerifyStart: full package/source/history/owner/permit, exact names+labels отсутствующих DB/networks, exact retained volume/images, signed receipt, поздний ключ/recheck. Только после reviewed actual start inputs восстановить неизменный DB-only compose.
- Fresh read-only baseline подписан для нового run и новых точных DB/network IDs. По databases/preservation равен принятому001/Q007; runId старого witness не переносится в новый witness. Допуск связывает owner Q010, new plan/package/source/code-review, принятую первую группу, new baseline/budget/DB/network, TTL≤15мин.
- Отдельное independent actual payload/provenance review и closed issuer до SQL. Ни code review, ни saved001 review не являются самодопуском нового payload.

## Исполнение и проверка кода

Новый профиль сохраняет reviewed IO-factory структуру: тонкая continuation-копия закрытого контроллера/валидации и flow только4 групп. Переиспользовать byte-exact probe.py/unit-witness.py и действительно profile-neutral hash-bound helpers (HMAC/canonicalBind/helperConfig/cleanupHelper). Старый factory напрямую имеет hardcoded RUN/GROUPS/scopes; не маскировать новый прогон фиктивным старым plan и не менять frozen modules. Новых универсальных frameworks не требуется.

До runtime — независимые code/QA-review и actual injected-controller offline tests: Prepare/Verify/Before/VerifyStart/Baseline/Authorize/Payload/Run, wrong DB/role/OID/marker/source/session/nonempty/permit, saved-first/ancestry/code/review drift, missing/substituted receipts/HMAC, wrong scope/group/new instance, expiry/timeout-after-send/partial output, mandatory after-witness, cleanup failure, once wx locks/no retry. Ни реальных Docker/SQL/ключей/FS writes в fake tests.

Перед каждой группой remaining≥200с и previous PASS/after-witness равен baseline. Helper hard60с/host90с, caps DB512MiB/.5CPU/128 и helper256MiB/.5CPU/64. Первый новый group003 не объявляется повторным measurement001; метрики всех helpers сохраняются, OOM/неизвестный исход/сохранность/истёкший допуск останавливают прогон. Cleanup-only authority обеспечивает witness и после expiry, но не делает FAIL успехом. Никакого автоматического продления допусков/retry.

Общий бюджет allocated DBbytes+accepted host roots+16MiB reserve<2GiB: до старта, фактическое измерение на живом стенде после успешных четырёх групп и после Stop. Frozen focused inputs сохраняются, новые public authorization inputs архивируются до правки bound docs. Итог — независимое result-review всех четырёх+связи принятого001, source/protected/ancestry/rollback/sequence/preservation и cleanup0/0/retainedvolume/permit{}.

## Приёмка

CONT29-001: no001 и immutable ancestry/saved-first review; CONT29-002: fresh exact start/baseline/budget/payload; CONT29-003: четыре отдельно доказанных group PASS; CONT29-004: rollback/MAIN/UNIT/archive preservation/sequence/source после каждого; CONT29-005: budget/caps/expiry/Stop и independent final review. До фактического выполнения NOT_RUN.

Полный P29-A, quota1000/007, прежние полные регрессии, admission/recovery/concurrency/crash и публикация Django остаются открытыми. Проценты35/31 не повышать за инструменты. При успехе Q010 уже разрешает это продолжение после независимых gates без нового вопроса владельцу; обязательное согласование при новой паузе или расширении области сохраняется.
