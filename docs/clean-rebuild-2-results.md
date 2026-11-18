# REBUILD-2 — результат локальной runtime-проверки

Дата: 2026-11-17. Result ID: `RB2-RUNTIME-001`. Статус: **PASS; independent result review APPROVED P1/P2/P3=0/0/0 (D-1428)**.

## Граница

- Проверен только новый `src/`: config и три модуля audit/accounts/pages.
- Использован существующий локальный pinned Python runtime `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951` и остановленный до сеанса foundation-test PostgreSQL.
- Python-контейнеры были одноразовыми, read-only, nonroot, cap-drop ALL, no-new-privileges и без установки/скачивания.
- Старые app/DB rows, source/target migration data, media, ingress, live/VPS не читались и не изменялись.

## Проверки и исправления

1. `manage.py check`: PASS, 0 issues.
2. Первый drift check вернул `No changes detected`, но TLS history lookup использовал container name вместо сертификатного alias `db`; повтор с доказанным alias: PASS без warning.
3. Первый test setup остановился до migrations: least-privilege `app_migrator` не имеет CREATEDB. Права роли не расширялись.
4. Exact DB `estakada_rb2_test` была создана локальным postgres owner. Первый migration attempt выявил отсутствие expected schema `app` при role `search_path=app,pg_catalog`; общая роль не менялась, schema создана только в isolated DB.
5. Миграции accounts/audit/pages и Django auth/contenttypes/sessions применились. Первый выполненный набор 26 тестов выявил три bounded defects: legitimate empty audit detail field validation, empty inherited password test fixture и private cross-module test import.
6. Delta исправлен без новых сущностей: audit `blank=True` с exact initial-migration mirror, unusable password fixture, Django `get_user_model()`. Independent delta review: APPROVED P1/P2/P3=`0/0/0`.
7. Финальный drift check: `No changes detected`.
8. Финальный focused/full RB2 run: `26/26 OK` за 2.485s; system check 0 issues.

## Cleanup

- Exact `estakada_rb2_test` удалена и read-only lookup подтвердил отсутствие.
- PostgreSQL test container возвращён в остановленное состояние.
- Финальный running foundation-test container count: 0.
- Новые compose service/image/dependency/helper/volume/runner: 0.

## Оценка

Принятый фазовый диапазон REBUILD-2 был 4–6 продуктивных часов. После independent result review для WBS принято `4/5/6h` в optimistic/likely/risk: completed credit `10/13/16h`, remaining `23/30/44h`, total basis остаётся `33/43/60h`. Готовность приблизительно `30%/30%/27%`, сообщается как `27–30%`. Ожидание владельца, live/production, external operations, новый scope и destructive REBUILD-8 не входят.

## Следующая граница

REBUILD-3 не открыт автоматически. До кода или runtime нужны согласованные scope/acceptance для media schema и one-shot importer с сохранением deferred unmatched-source freeze blocker. Target DB/media, transfer/freeze/cutover/live остаются закрыты.
