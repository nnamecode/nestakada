# DEV07-SH — изменение метода ограниченного PostgreSQL probe

2026-11-01. DEV-07 около95%, этап8 около20%. Техническое предложение **до изменения исполняемого теста**, для независимого ревью. Связи: dev07-shared-preparation.md, SH07-QEXP001/QEXP002-count-only/QEXP006-insert-rollback-only. Scope остаётся экспериментальным: нет shared product моделей/API/Apply или подтверждённой reservation formula. Старый сайт/VPS, роли/права, версии, зависимости и ресурсы не меняются.

## Первое фактическое исполнение — FAIL, не повторено

Исходный файл `app/page_editor/test_shared_quota_probe.py`, SHA256 `0083b4f40786d4644569dfd96ab5a8ffe687c920927c47470d6497f348d87432`, впервые запущен на выделенной estakada_foundation_unit. Свидетельство: `work/dev07-combined-20261101/shared-quota-first.txt`.

QEXP001 остановился на первом CREATE TEMP TABLE: PostgreSQL отказал роли app_migrator в TEMP для этой БД (`permission denied to create temporary tables`). Прогон:1test/error,0PASS; QEXP002/QEXP006 не исполнены. Первый CREATE не создал таблицу. Не было повторного запуска без изменения условий, GRANT TEMP, смены роли, установки пакетов или ослабления окружения. Это установленное ограничение принятой роли, не основание расширять её привилегии.

## Предлагаемый изменённый метод

Использовать обычные **экспериментальные** таблицы в существующем migration schema app. Все CREATE/INSERT/измерения выполняются внутри одной outer transaction, которая **всегда откатывается**, включая успешный результат. Product миграции или запись durable shared истории не добавляются. Имена остаются статическими `es_shared_probe_revision`, `es_shared_probe_draft`, `es_shared_probe_pin`, `es_shared_probe_receipt`, `es_shared_probe_identity`, `es_shared_probe_budget`; все SQL references явно `app.<name>`.

Основание выбора app подтверждено tools/foundation_db_init.py: роль app_migrator имеет search_path=app,pg_catalog; PUBLIC лишён прав на schema public; app создаётся AUTHORIZATION app_migrator, существующий владелец проверяется. До первого DDL probe обязан проверить actual owner namespace app = app_migrator и `has_schema_privilege(current_user,'app','CREATE')`. При несовпадении/false — диагностический отказ, без попытки исправить grants или применить другой schema/роль. Метод меняет способ тестовой изоляции, не конфигурацию сервера. Его применение допускается только после независимого технического ревью конкретной правки.

### SH07-PGA-001 — guards до DDL

1. Прежние exact guards: ESTAKADA_LOCAL_ENV=test, DJANGO_SETTINGS_MODULE=estakada.settings.local_http, settings.ENVIRONMENT=test, backend PostgreSQL, connection NAME и actual current_database() = estakada_foundation_unit, actual current_user = app_migrator. Вывести только не секретные version/block_size/метрики.
2. Убедиться, что это outer transaction probe; не использовать AUTOCOMMIT DDL/commit. SET LOCAL statement_timeout30s/lock_timeout5s сохраняются только для её соединения.
3. Получить OID существующего namespace app и OID текущего role из pg_namespace/pg_roles; проверить владельца schema и CREATE privilege.
4. До CREATE проверить отсутствие **любых** pg_class объектов app с собственным фиксированным prefix `es_shared_probe_`, включая таблицы/индексы/sequence/view. При коллизии остановиться и сохранить диагностику. Не DROP/IF NOT EXISTS/переиспользовать существующий объект. Это защита от потери или присвоения чужой таблицы.
5. Не принимать schema, prefix, OID, SQL, filename или object names из HTTP/fixture/user input. Измерительный corpus и identifiers закрыты в коде теста.

### SH07-PGA-002 — создание и измерение только собственных объектов

- CREATE TABLE app.<fixed-name> вместо TEMP/ON COMMIT DROP; REFERENCES также schema-qualified. Объявления колонок/PK/unique/FK и три finite corpora из первого probe не расширяются.
- Сразу после CREATE прочитать root inventory: ровно6 ожидаемых имён, namespace app с полученным OID, relkind=r, relpersistence=p, relowner=actual role OID; сохранённые root OIDs новые, поскольку prefix перед CREATE был пуст. Имплицитные индексы/constraints/TOAST связаны с этими root через системные каталоги; не считать чужие отношения.
- Перед каждым измерением повторно проверить точное соответствие сохранённого root OID/name/namespace/persistence/owner/TOAST inventory. Не разрешать заменить имя другим OID или подставить произвольный OID.
- Для каждого root использовать pg_total_relation_size; отдельно pg_table_size/pg_indexes_size/forks и уже включённый TOAST служат контрольным breakdown, не слагаемыми второй раз. TOAST root проверяется через сохранённый reltoastrelid, relpersistence=p и namespace pg_toast; прежнее требование pg_toast_temp больше не применяется.
- Результат scope=`SH07-transactional-DDL-calibration`, с явными productQuotaImplemented=false/productApplyTested=false. Это normal persistent-relation shape внутри rollback transaction, а не TEMP. Сравнение с первым FAIL не превращает его в PASS.

### SH07-PGA-003 — обязательный rollback и проверка очистки

Общий context-manager/try-finally создаёт outer atomic; до выхода из неё обязательно помечает rollback, даже при всех успешных assertions. Нельзя полагаться только на teardown TransactionTestCase: успешный outer commit экспериментальных таблиц запрещён. Любая ошибка также выходит через rollback.

После завершения outer rollback свежим запросом проверить отсутствие собственных root OIDs **и всего собственного app prefix**. Catalog/index/TOAST объекты созданной транзакции откатываются PostgreSQL вместе с CREATE; broad DROP/ручная рекурсивная очистка не нужны и не разрешаются. Если очистка не подтверждается — FAIL, сохранить факты и остановиться; не удалять объект только потому, что совпал prefix. При невозможности нового запроса из-за обрыва соединения нельзя заявлять cleanup=true.

QEXP006 сохраняет отдельный inner savepoint: INSERT1МиБ → измерение → rollback только inner → logical manifest восстановлен, physical growth созданного outer relation остаётся видимым → итоговый outer rollback удаляет все экспериментальные отношения. Не путать наблюдение bloat после inner rollback с финальным удалением объектов outer rollback.

Стандартный Django TransactionTestCase teardown по-прежнему сбрасывает данные выделенной unit DB; это не обещание сохранить arbitrary unit fixtures. Рабочая foundation DB/старый сайт/VPS не являются объектами прогона.

## Неизменный ограниченный ресурсный профиль

Предел собственных измеренных отношений остаётся менее32МиБ, pre-write запас16МиБ, конечные действия —10000 коротких rows либо один плохо сжимаемый1МиБ payload. Pre/post guards не называются универсальным hard physical reservation. В этом варианте отношения WAL-logged: PostgreSQL WAL может вырасти даже при rollback. WAL не входит в pg_total_relation_size root и не выдаётся за освобождённый rollback байт;32МиБ — предел измеряемых собственных отношений, **не всего диска/WAL**. Дополнительный corpus/наполнение75%/256МиБ/benchmark не запускается.

QEXP003/004/005full/007, product count10001 refusal, actual quota warning UI, concurrent reservation и complete shared accounting остаются неисполненными. Исходные роли не получают новые полномочия; если измеренный overhead или WAL/место не позволяют безопасно выполнить даже finite corpus — остановка и новое конкретное предложение, а не автоматическое повышение бюджета.

## Порядок продолжения

1. Независимое read-only ревью этого метода; закрыть замечания до изменения теста.
2. Изменить только экспериментальный test file и явно обновить его описание/guard/cleanup, без product models/settings/grants.
3. Независимое ревью точного diff/hash до второго запуска; это будет **первая попытка изменённого метода**, не повтор прежнего TEMP CREATE.
4. Запуск serial на новом frozen source через существующий проверенный локальный test runner. Сохранить первый FAIL и новый отдельный report; проверить exit/result/own-object cleanup.
5. Отчёт отдельно фиксирует QEXP001/002-count/006 ограниченные результаты, не full shared quotas. Пока этот документ написан, исполняемый тест не менялся и повторный прогон не выполнен.
