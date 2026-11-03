# DEV-29: первый предметный PostgreSQL-прогон публикации

2026-11-03. Статус: **FOCUSED-PLAN-REVIEW-001 APPROVED; DEV29-Q009 разрешён по D-421, code/payload reviews приняты. PG29-001 локально PASS; independent result-review не завершён, пауза PG29-FOCUSED-RESUME-001 по D-422. Остальные4 NOT_RUN, стенд остановлен**. [Результаты и сохранённый план возобновления](dev29-focused-postgres-results.md). [Ревью плана](dev29-focused-postgres-plan-review.md). Основания: D-410–D-422, dev29-postgres-proposal.md, завершённый dev29-readonly-audit-results.md. Исходная редакция входов прогона сохранена с SHA в pause-inputs до обновления статуса.

## Продуктовый результат

Проверить реализованные правила публикации в настоящем PostgreSQL: pending не открывает страницу; итог HIDDEN/LIVE_NO_SET соответствует запросу; одинаковый запрос не выполняется дважды; неизвестный исход остаётся закрытым; ошибка PostgreSQL полностью откатывает изменения. Это проверка нижнего слоя DEV-29 до подключения Django-кнопок, не новый проект стенда и не готовая публичная публикация.

Проверяем существующий source31 и принятый probe.py. Состав первого прогона фиксирован: **PG29-001,003,004,005,006**. PG29-001 уже проверяет assertions replay/fingerprint двух policy, поэтому одинаковое тело PG29-002 второй раз не запускаем и отдельный PASS этому ID не присваиваем. PG29-007/квота1000/admission/recovery и полные прежние регрессии остаются NOT_RUN. Уменьшение первой области предлагается явно, не выдаётся за завершение всего P29-A.

| ID | Наблюдаемый результат |
|---|---|
| PG29-001 | Prepare HIDDEN и LIVE_NO_SET создаёт PENDING_DENY; неверный objectId отклоняется до SQL; report policy mismatch не меняет state; final/replay/basis/receipt/incarnation conflicts корректны |
| PG29-003 | Unknown/status/abort и terminal replay не снимают deny и не регрессируют |
| PG29-004 | Реальные service snapshot/read методы и consumer принимают LIVE_NO_SET без html_admission; повреждённые key/generation/policy/digest отклоняются |
| PG29-005 | Поздняя настоящая SQLSTATE22012 после uncommitted Operation/phase/RoutePolicy откатывает state/charge/reserve; тот же UUID retry/replay корректен |
| PG29-006 | Ограниченные регрессии прежних HIDDEN/DELETED/REDIRECT/tombstone/abort/replay; LIVE_NO_SET не разрешён старому kind |

## Изоляция и разрешаемая запись

Только точная UNIT test_estakada_trust/OID52766/owner postgres/полный marker/schema из принятого Q007 baseline. До и после каждой группы — независимый read-only UNIT/MAIN/archive catalog witness. Перед fixture — пустые7 journal tables, только3 migration rows, sequence4true; любое расхождение STOP без очистки данных.

Одна группа — одна внешняя atomic, внутри реальные service transactions/savepoints, затем **безусловный rollback** и reconnect. JournalFixture только builder setUp/doCleanups по принятому probe, не TransactionTestCase lifecycle. No flush/TRUNCATE/reset/drop/rename/migrate/init. SQL22012 — намеренная injection, не физическое заполнение диска. Synthetic UUID/тексты/credentials не являются данными владельца; временные файлы только tmpfs.

MAIN/закрытые архивы не получают write-соединений; MAIN state-v2 должен оставаться b42ec332…; архива catalog/proofs проверяются без открытия соединений. Рабочий writer/permit остаются disabled/{}. Никакого API/ingress/APP/URL/delete/production/старого сайта/VPS/push.

## Конкретный пакет и цепочка допуска

Текущий executeFlow/controller Run и его signed admission жёстко рассчитаны на7 групп с quotaEstimateAccepted. Их нельзя запускать с ложным quotaEstimateAccepted=true или подменять список групп в старом signed plan.

По Q009 предлагается **отдельный закрытый focused-профиль** в новых ignored файлах `work/dev29-publication-20261103/pg-check/focused/`: controller/flow/authorizer, synthetic tests и immutable run records. Список пяти групп — константа; группы/код/SQL/пути от пользователя не принимаются. Новые signed scope только PG29-FOCUSED-ROLLBACK-ADMISSION, без поля quotaEstimateAccepted; старый runtime scope/Run остаются закрытыми. Product source, прежние9+7 files/snapshots/receipts/locks не менять.

До выполнения — независимое code/QA-review focused adapters и offline negative tests. Проверить wrong DB/role/OID/marker/source/nonempty/session/permit, отсутствующий/подменённый baseline, лишнюю группу007, source/review drift, expiry, timeout-after-send, ошибку cleanup/witness, частичный output, retry/ledger. Проверки зависимы: запускать следующий gate только после успеха предыдущего.

Порядок после code-review:

1. Новые immutable source/package/run/checkpoint и явная связь с завершённым read-only run50a66937… . Старые operator locks/attempts не снимать; новый focused namespace не является повтором ошибочного Audit — предыдущая операция успешно завершена, область и authority иные.
2. Повторно безопасно восстановить **те же** temporary compose ресурсы по принятому Q008: свежий per-run RO volume metadata/PG18 initialized/clean shutdown, VerifyStart, existing owned volume+images, только DB/internal networks/no pull/build/init/migrate/API. Имена/ресурсы/томы/порты не расширять; cleanup в finally по own full IDs.
3. Fresh read-only witness уже на новом DB container ID, exact baseline равен принятому MAIN/UNIT/schema/sequence/archive catalog; старый DB ID после удаления не переносить в допуск. До fixture подписанный exact focused payload связывает owner Q009, run/plan/group-list/code/review/helper+DB IDs/baseline, actual resource budget и expiry≤15минут. До реального send — независимое payload/provenance review без чтения/вывода ключа в отчёт.
4. PG29-001 выполнить один раз; сохранить фактические duration/peak/DB bytes и after-witness. Она одновременно первый функциональный результат и ограниченное измерение бюджета, не отдельная повторяемая calibration. Если preservation/ресурсы/время не доказаны — остановиться, не повторять группу и не продолжать остальные.
5. Перед каждой оставшейся группой проверять signed scope/code/source/current DB/baseline/remaining time. Только после предыдущего PASS и after-witness равенства. При любом probe FAIL/timeout/expired admission — exact helper cleanup и обязательный независимый after-witness с bounded cleanup-only authority; итог остаётся FAIL, никакой автоматический retry.
6. После пятой группы independent result-review, source/protected hash recheck, fresh preservation и Stop/удаление собственных временных ресурсов. Том/история/phase receipts сохраняются. Все public inputs подписанного допуска архивируются до обновления документов; secrets не копируются.

Нормализация CAP_ и Desktop bind-пути уже принята и должна переиспользоваться с теми же строгими predicates, без новой реконфигурации контейнеров. Несовпадение actual API format расследуется до отправки SQL, а не ослаблением guard.

## Бюджет первого прогона

Действующие caps неизменны: DB512МиБ/.5CPU/PIDs128, единственный helper256МиБ/.5CPU/PIDs64; максимально768МиБ одновременно. Исторический реальный read-only helper peak79,986,688байт — ориентир, **не измерение будущей fixture**. Первый PG29-001 даёт actual peak/duration; OOM/недоказанные metrics запрещают продолжение.

По закрытому probe максимальное число новых Operation в одной внешней транзакции —5 (PG29-006), всего успешных prepare в пяти группах≤10, без1000-loop. UUID primary keys не используют необратимый sequence increment. Logical charge/reserve проверяется до/после service ошибки и rollback; физические WAL/dead pages не откатываются, поэтому их не выдавать за неизменный том.

До start — RO allocated DB directory bytes + host artifact bytes с прежними резервами, общий согласованный предел2ГиБ. Перед продолжением после001 — actual fresh disk/peak/duration report. Порог времени первого шага: probe001≤20с, его witness≤20с; иначе BLOCKED после доказанного rollback и остановки. Эти soft thresholds не повышают прежние hard helper60с/host90с. Остальные helper limits те же, перед началом каждой группы admission remaining≥200с (90probe+90after-witness+20cleanup); недостаток — STOP до отправки SQL, без автоматического продления/подмены timestamp. Истечение admission после send не мешает cleanup witness и не делает функциональный FAIL успехом.

Первый measured report и независимая его сверка обязательны до продолжения003–006; Q009 при положительном ответе разрешает такое условное продолжение без ещё одного пользовательского согласования. Невместившаяся группа/неизвестная сохранность — BLOCKED/FAIL с артефактами, не повышение caps/deadline и не mock PASS. После Stop физический размер снова проверяется read-only; это бюджетная проверка, не очистка корпуса.

## Приёмка области

F29-001: code/payload reviews и закрытый focused scope; F29-002: fresh baseline/new DB instance before writes; F29-003: пять отдельно доказанных PG29 groups; F29-004: обязательные after-witness/rollback/source/sequence preservation; F29-005: actual resource/time budget и Stop0/0/volume retained/workingpermit{}. До исполнения все NOT_RUN. Полный P29-A, quota/admission/recovery/concurrency/crash и публикация Django остаются открытыми.

## DEV29-Q009

Разрешить подготовку кода focused-профиля, независимые code/payload/result review и один ограниченный PostgreSQL-прогон этих пяти групп с synthetic UNIT-записями, обязательным rollback/сохранностью/бюджетом и остановкой стенда? Это единственное новое разрешение на fixture writes только в UNIT. Quota1000/старый Run/MAIN writer/APP/production/старый сайт/VPS/push не разрешаются.

До ответа — только предложение и независимое ревью. Q007/Q008 завершены и повторно не согласовываются. Принятое разрешение Q009 будет охватывать код, измерение первой группы и условное продолжение остальных после независимых gates — без дополнительных промежуточных запросов владельцу при успешных проверках. DEV-29 около35%, этап8 около31%.
