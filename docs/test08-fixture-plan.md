# TEST-08 — минимальный план изолированного fixture

Дата: 2026-11-15. Статус: **APPROVED**, repeat independent review P1/P2/P3=`0/0/0`; implementation/execution NOT AUTHORIZED. First review P1/P2/P3=`1/4/0`; remediation below chooses one-process fixture/HTTP boundary and closes F08-PLAN-R01–R05. Review: `docs/test08-fixture-plan-review.md`.

Основание: утверждённый base-MVP plan `docs/test08-base-mvp-plan.md`, снятый DEV-09N content gap D-1109 и readiness audit `docs/test08-fixture-readiness-audit.md`.

## Цель и строгая граница

Создать только воспроизводимый reusable test-only builder для будущих десяти групп TEST-08. Fixture contract доказывает, что текущие утверждённые packages/writers и exact gallery bytes можно собрать в одном изолированном Django test state. Он не выполняет группы TEST-08, не переводит acceptance rows в PASS и не доказывает production import/publication, Nginx, VPS, TEST-09/10 или launch.

`fixtureReady=true` означает готовность builder contract, а не сохранённое состояние БД. Будущий approved execution suite вызывает этот же builder один раз внутри своего named Django test process, выполняет exact10 групп через Django server-level `Client` с фиксированными host/origin до teardown и затем очищает state. Отдельный foundation HTTP app использует другую БД и fixture не получает; новый app/runtime над unit DB не создаётся.

Постоянный runtime, main DB, live/VPS и исходные фотографии не меняются. Intake/ПД, SMTP/Telegram, analytics, external embeds/widgets и DEV-26/27 остаются выключены.

## Измеренный вход

Fixture использует только 12 уже allowlisted package-файлов frozen foundation source и точный локальный media set:

- gallery originals: 214 файлов / 41,176,391 bytes;
- home design media: 15 / 2,545,932 bytes;
- DEV-09N remaining media: 7 / 1,394,676 bytes;
- MAP-019 infographic: 1 / 104,682 bytes;
- всего exact237 / 45,221,681 bytes, hard cap 64 MiB.

Маршруты сверяются только с `docs/analytics-route-map.csv`: exact114 legacy path+query и один approved extra `MAP-115`. Expected assembled state: 113 Page aggregates and 115 Route rows; three legacy/runtime aliases account for the route/page difference. Значения пересчитываются из packages и registry, а не из результата сборки.

## Минимальный будущий diff

Ровно два новых test/tool файла и один существующий wrapper:

1. `scripts/prepare-test08-fixture-assets.ps1` — host-only exact237 staging в `work/foundation/test/test08-fixture/<run-id>/source`; no network/child download/image conversion. Он принимает только current active test run, читает четыре утверждённых package manifests, отклоняет absolute/traversal/link/non-regular/duplicate paths, проверяет каждый size/SHA, общий count/bytes/cap и пишет canonical manifest без секретов. Ошибка удаляет только созданный run-scoped staging directory.
2. `app/content/test_test08_fixture.py` — один test-only `TransactionTestCase`, reusable builder и exact fixture-contract acceptance; future execution test module may import only this builder after its own plan/gate. Production import/URL/command не добавляются.
3. `scripts/test-editor.ps1` — только named suite `test08-fixture`, read-only mounts exact staging root + exact route-map after manifest/hash validation, and a bounded result-marker parser. Test stdout may contain exactly one canonical `TEST08_FIXTURE_RESULT=` base64url JSON marker no larger than16KiB; wrapper validates closed keys/types/caps/no secret fields and writes the receipt on host. Остальные suites/mounts не меняются.

Новых model/migration/dependency/settings flag/API/management command/endpoint/template/JS/CSS/Playwright/acceptance framework или generic importer/runner нет.

## Сборка внутри test boundary

Suite работает только на frozen source одного fresh foundation run, в existing `estakada_foundation_unit` под `app_migrator`, с временным `MEDIA_LIBRARY_ROOT` и default-off integrations. Порядок фиксирован зависимостями и не настраивается пользователем:

1. exact synthetic owner `nesadmin` и один synthetic employee; generated passwords остаются только в памяти и не попадают в manifest/log;
2. current Header/Footer через существующий closed normalizer/simple shared command, без прямого произвольного template/JS;
3. existing DEV-09 writers: articles → services catalog → roots → details → price details → diagnostics → planned maintenance;
4. exact MAP-019 media import → combined services;
5. exact7 DEV-09N media import → exact13 remaining content;
6. bounded test-only gallery seeding: package exact214 identities create only the required legacy folder/READY Asset/LEGACY_PUBLIC AssetFile and exact physical bytes through existing MediaStorage invariants; then existing `apply_gallery()` validates manifests and creates exact17 albums/root. Это fixture setup, не новый product importer и не migration evidence;
7. DEV-12 home exact15 media and home aggregate;
8. одна ограниченная employee grant создаётся только после появления exact target Page;
9. fixture-only publication of the exact package page identities after aggregate validation. Это только test setup для будущих public HTTP групп и не считается product publication evidence.

Каждый existing writer остаётся default-off вне `override_settings` этого test case. Package readers, media storage validators, transactions, replay/conflict checks и typed contacts validation не обходятся.

## Приёмка fixture

Постоянные сценарии до реализации:

| ID | Проверка |
|---|---|
| F08-FX-001 | Host staging принимает ровно exact237/45,221,681 и отклоняет missing/extra/duplicate/link/path escape/hash/size/cap+1 до Docker test call. |
| F08-FX-002 | Frozen source SHA, staging manifest SHA и route-map SHA закреплены в evidence; repo originals read-only, writes/network/download/conversion0. |
| F08-FX-003 | Admitted empty test baseline собирает exact113 Page/exact115 Route и все package-authorized revisions/state/drafts/pins/audit/media usages без unknown aggregate. |
| F08-FX-004 | Route set равен exact114 legacy path+query + approved MAP-115, missing/extra/duplicate0; redirect не подменяет exact URL. |
| F08-FX-005 | Gallery exact17/214 сохраняет original bytes/SHA; total exact237 media files physically match storage manifests. |
| F08-FX-006 | Owner/employee/post-page grant and current Header/Footer coherent; settings remain default-off and ServiceRequest rows0; PII/notifications/analytics/external embeds/DEV-26/27 absent. |
| F08-FX-007 | Prior D-1109 contacts HTTP evidence is referenced, not rerun. Fixture contract only asserts default-off settings/state; contacts HTTP oracle belongs to future TEST-08 group8. |
| F08-FX-008 | Fixture manifest records run/source/input/output counts and hashes only; passwords, cookies, CSRF, user data, file bytes and absolute private paths absent. |
| F08-FX-009 | Fault injection checks only the documented atomic boundary of the selected final writer. Replay assertions apply only to existing idempotent package/media writers. No cross-writer/filesystem rollback or owner/shared replay claim; any assembly failure relies on test teardown. |
| F08-FX-010 | TransactionTestCase teardown leaves DB rows at admitted before-state and removes temporary media. Host helper in `finally` validates run-id/path/link boundaries and removes only its own staging directory; foundation can Stop with active=false. |

No public/admin HTTP group is counted here. HTTP status/content evidence begins only in a separately approved TEST-08 execution module, which invokes the same builder and completes exact10 groups in the same named Django process before teardown.

## Evidence и запуск после отдельного разрешения

Allowed future sequence: fresh foundation Start → host staging self-check → exactly `scripts/test-editor.ps1 -Suite test08-fixture` → closed result-marker inspection/write → host staging cleanup in `finally` → foundation Stop. Wildcard, direct broad `manage.py test`, Playwright and external network are forbidden. Stage9 regression is not repeated.

Generated receipt is written by the host wrapper only below the validated ignored work directory and includes: fixture/run UUID, frozen source manifest SHA, exact input manifest SHA, route-map SHA, before/assembled/after count vectors, public route-set digest, media count/bytes/digest, default-off flags, suite result and cleanup result. The read-only container never deletes host staging or writes host files.

Первая ошибка сохраняется с причиной; один повтор допустим только после изменившегося условия. Вторая эквивалентная ошибка останавливает работу, третьей попытки нет. Host/Docker/staging failure не считается product failure.

## Gates

1. independent read-only review этого плана;
2. явное разрешение владельца на exact three-file implementation;
3. RED contract tests → minimal code → one named GREEN, independent diff review;
4. отдельный TEST-08 execution plan с exact10 HTTP/manual groups и evidence IDs;
5. отдельное разрешение владельца на TEST-08 execution.

Даже successful fixture не открывает production apply, publication, TEST-09/10, VPS или сбор ПД.
