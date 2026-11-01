# DEV07-SH — фактические первые измерения PostgreSQL

2026-11-01, D-344/D-345. DEV-07 около96%, этап8 около20%. **3 ограниченных эксперимента PASS за2.274с**, независимое ревью `/root/combined_review` без блокеров этой области. Это подготовка учёта квоты, а не реализованная продуктовая квота или редактор Header/Footer.

## Факты

| Сценарий | Наблюдение |
|---|---|
| QEXP001 experimental shape | Шесть собственных отношений и реальные primary/unique indexes/TOAST:90112Б пустого общего footprint. Root total=table+indexes; уже включённый TOAST не складывается повторно |
| QEXP002 count-only |10000 реальных строк, по5000 для header/footer, sequence1–5000. Общий footprint1998848Б; два построчных manifest совпали, SHA256f6c3c791c0174bc639c5bb8cea99080a0345a741dd8e1dcca767f8b48c2497db. Это экспериментальная форма с короткими payload, не оценка размера10000полных HTML снимков |
| QEXP006 inner rollback | После вставки плохо сжимаемого1МиБ payload footprint90112→1245184Б. Внутренний rollback вернул0строк/исходный manifest, но footprint остался1245184Б. Следовательно, логический откат не освобождает автоматически занятые блоки |

PostgreSQL18.6, block_size8192. Все три группы проверили actual DB=estakada_foundation_unit, role=app_migrator, owner/CREATE права существующей schema app, отсутствие собственного prefix до DDL и новые собственные root OID/namespace/persistence/owner перед измерениями. Все экспериментальные CREATE/данные всегда откатываются одной внешней транзакцией; свежий каталог подтвердил отсутствие собственных OID и prefix после каждой группы. Ручного DROP/GRANT/создания schema/изменения ролей или настроек нет. Django TransactionTestCase отдельно сбрасывает выделенную unit-БД; сохранение произвольных данных этой БД не обещается.

## История метода и границы

Первый TEMP метод **FAIL**,1test/error/0PASS: действующая роль намеренно не имеет TEMP privilege. Неизменного повтора не было. Исправленный метод прошёл отдельное предварительное ревью: собственные schema-qualified app отношения внутри обязательного outer rollback при прежних правах. Первый FAIL не удалён и не переименован в PASS. Подробности — dev07-shared-probe-amendment.md.

Предохранитель32МиБ относится только к собственным измеряемым отношениям конечного эксперимента; он не ограничивает весь PostgreSQL/WAL/диск. Обычные отношения WAL-logged, rollback не отменяет WAL. Никакой универсальный коэффициент резервирования по этим трём образцам не принят.

**Не выполнены:** продуктовые модели/API/санитайзер/редактор, admission/отказ10001, реальное наполнение75%/256МиБ, полный overhead corpus/draft/receipt/pins/refs, concurrent reservations, ручная очистка и HTTP/UI квоты. SH-REV-001 открыт до sanitizer/binding: принятые canary fixtures нужно явно увязать с закрытой структурой принятого макета, сохранив смысл теста. Точный Asset marker и trusted menu resolver также остаются воротами до общего Apply. Подготовленный контракт — dev07-shared-preparation.md.

## Воспроизводимость и ревью

Тест app/page_editor/test_shared_quota_probe.py SHA25671a0e0590373bea8fd2bcd7fc0e6b78a2e24daf3e07df1297633f8601b189148; suite shared-quota сохраняет все прежние Docker/source/private DB guards и ресурсы. Продуктовый код не менялся.

Run32daef64-6920-4d5a-a199-5517fa792834,172frozen files/0drift, manifest SHA256c6daacd52948a3afe70c552039bcc502289eb7cce601d70f16a19c0ac2ad7ff4. Рецензент сравнил CM cohort8631fa33…: добавлен только этот тест, изменённых/удалённых файлов нет. Сами CM3tests/5Check здесь не повторялись; их факт остаётся в dev07-combined-results.md.

Локальные свидетельства: work/dev07-combined-20261101/shared-quota-first.txt (TEMP FAIL), shared-quota-transactional-first.txt (3PASS), cohort-shared-transactional-first.json и stop-final.txt. Рецензент лично проверил три actual reports, hashes/footprints/cleanup и исходники. Старый сайт/VPS не затронуты; к production или следующему этапу перехода нет.
