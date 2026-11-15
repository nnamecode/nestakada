# TEST-08 fixture — независимое ревью плана

Дата: 2026-11-15. Итоговый verdict: **APPROVED**, P1/P2/P3=`0/0/0`.

Первое read-only ревью: `CHANGES_REQUESTED`, P1/P2/P3=`1/4/0`. Исправлены F08-PLAN-R01–R05:

- reusable builder и будущие exact10 группы работают в одном named Django test process через server-level Client до teardown; отдельный app/runtime над unit DB не создаётся;
- exact214 gallery originals получают bounded test-only seed через existing MediaStorage/legacy invariants до `apply_gallery()`, без product importer;
- employee grant создаётся после целевой Page; fault/replay ограничены атомарными/idempotent boundaries отдельных writers, cross-writer rollback не заявлен;
- DB/temp media очищает test boundary, host staging — validated helper в `finally`; receipt передаётся одним closed base64url marker <=16KiB и пишется host wrapper;
- fixture не выполняет contacts HTTP/group8, только проверяет default-off settings/state и ссылается на D-1109.

Reviewer подтвердил exact237 media / 45,221,681 bytes, 113 Page и115 Route; gallery writer18 pages/19 routes, combined writer24/25. Новый runtime/model/migration/dependency/settings/API/command/endpoint/Playwright/framework не предлагается. Implementation и TEST-08 execution остаются за раздельными owner gates.

Рецензент файлы не менял; тесты, Docker, Playwright и сеть не запускались.

## Pre-code ordering review D-1113

Дополнительный read-only verdict: **APPROVED**, P1/P2/P3=`0/0/0`. Exact237 media (`1+7+15+214`) готовятся до shared content; Header/Footer binds one already READY package-authorized gallery asset without extra Asset/File. Затем page writers, gallery/home aggregates, post-page grant and fixture-only publication. Previous findings remain closed; files/tests/Docker/network0.
