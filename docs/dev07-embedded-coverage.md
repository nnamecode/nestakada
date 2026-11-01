# DEV07-E3 — фактическое покрытие I07

2026-10-31. Матрица относится к первому локальному инкременту встроенных изображений и разрешённых текстовых slots. Она не закрывает все26 I07/28 P07, весь DEV-07 или production. Требования: [сценарии до кода](dev07-embedded-checks.md); контракт, история запусков и точные hashes: [интеграция](dev07-embedded-integration.md).

## Исполняемые свидетельства

Backend:21 тест `EmbeddedEditorHttpTests` в `app/page_editor/test_embedded_http.py`, SHA256 `aa48966d0ddec239a1f03f3ae31aed1e3ddc65fae73d4cf8a0c4345294c637f9`. Targeted21PASS103.201с подтверждает настоящие PostgreSQL/session/CSRF/child/worker/файлы. Framework Client не заменяет socket/Nginx. Три последних теста проверяют независимый parent gate на изменённом child-derived результате после настоящей положительной нормализации; это целевые fault seams, не доказательство HTTP-эксплуатации прежнего дефекта.

Браузер: `tools/editor_embedded_http_probe.mjs`, fixture `tools/editor_embedded_http_fixture.py`, host `tools/test-editor-embedded-http.mjs`. Только root запускает Docker/runtime; QA и reviewer готовили/читали материалы отдельно. История: первый прогон2 PASS, затем Timeout; второй2 PASS, затем отказ полноты текста; третий3 PASS, затем EUI-004 CSP_VIOLATION. Третий подтвердил native toolbar insert/loaded img/slot Unicode/strong/Enter→hardBreak/Check IDs/canonical Save без permit, но ещё не весь набор. Исторические FAIL/cleanup сохранены; актуальный финальный результат приведён далее.

**Актуальный итог:** общий серверный набор356PASS619.841с на backend cohort0b2cf/e4c393…; финальные **8/8 EMBEDDED_8 PASS и8/8 MEDIA_8 regression PASS** на UI cohort2591ef85…/manifest42c0faa8…/bundle6e264277…. Различие unit/UI cohort — только два JS-файла, остальные163 совпадают; все165 final workspace files сверены независимо,0drift. [Точные hashes и раздельная область доказательства](dev07-embedded-integration.md). E3 report `work/dev07-embedded-20261031/browser-seventh/host-report.json`, run `c6cbfebc-cf12-4306-9fb7-61d52f076e34`; E2 regression report `work/dev07-embedded-20261031/e2-regression/browser-first/host-report.json`, run `a40c4434-effe-4b83-b38f-9e955aad9efd`. Исторические FAIL не переименованы. Независимый итоговый reviewer подтвердил отсутствие блокеров в первом локальном E3-инкременте; стенд остановлен/fixtures очищены.

## Матрица

В колонке «подтверждено» указан только реально исполненный scope; «остаток» не становится принятым по сходству с прежним тестом.

| ID | Подтверждено | Остаток / статус |
|---|---|---|
| I07-001 | Реальные PNG/JPEG upload→worker→READY, разные производные, no publication; EUI-001 | Pending/failed upload варианты не закрыты целиком |
| I07-002 | Server-issued IDs, closed input, owner/CSRF/early admission; EUI-002 toolbar→RAM | Полная матрица подмен IDs/source частичная |
| I07-003 | Child-derived refs/layout, single automatic, no permit в canonical Save; EUI-002/003; три parent-union отрицательных теста | Полный structural/derived adversarial набор частичный |
| I07-004 | Замена выдаёт новый reference; настоящий общий imageId в intro/main сохраняет другую позицию — HTTP. Native replace/Stable/retained files EUI-005 PASS | Двух shared occurrences в browser нет; широкая replacement matrix частичная |
| I07-005 | HTTP employee Unicode/strong сохраняет map/файлы; native owner+employee slot input/save EUI-003/004 PASS | MultiParent и остальные field/format варианты отдельно |
| I07-006 | HTTP strong и native bold owner с полным текстом/Save | Font/color/align/full ancestor matrix частичная |
| I07-007 | Owner native Enter→hardBreak→Check→canonical br→Save; native interior Backspace/Delete owner+employee; rapid Home→Backspace boundary/CSP0 EUI-003/004 | Full paragraph split/join/undo/redo открыты; Enter не выдаётся за split |
| I07-008 | Direct employee marker/parent/slot/Asset tamper и parent marker-erasure отказ | Дублирование/crossPage/full keyboard matrix не закрыта |
| I07-009 | Employee alt/ancestor align tamper отказ | Полная dimensions/properties матрица частичная |
| I07-010 | Поддельный/неверного field/изменённый permit отказ; три parent gate регрессии | EUI-008 rawpaste/drop PASS; полная unsafe/legacy матрица остаётся отдельно |
| I07-011 | Прежние общие бюджеты не увеличены | E3-specific exact1MiB/+1/codepoint/node/depth/resource открыты |
| I07-012 | Draft insert не меняет current, apply использует private selected map — HTTP; EUI-006 native draft bytes/reload/separate apply PASS | Полная stale/missing/employee матрица отдельно |
| I07-013 | Actual owner stage candidate/contextual bytes/edited apply — HTTP; EUI-007 native history→stage→slot edit→explicit Save PASS | Employee stage projection и широкая held-source matrix отдельно |
| I07-014 | Реальные embedded current/stage bytes, SHA/размер/права/original privacy — HTTP; owner loaded bytes EUI-002/003 | Full selected-source/late revoke/inflight/public-key matrix частичная |
| I07-015 | Подпись permit, field/image/IDs, changed image отказ, повторный Check сохраняет IDs, parent union | Отдельные stale sourceStamp/actor/generation negatives и полные stale proof/retained FS races открыты |
| I07-016 | Настоящий exact permanent save replay до missing FS | Draft/apply consume/replay wire matrix отдельно |
| I07-017 | Использованы прежние auth/source guards | E3-specific late auth/generation/different actor/two-PG races открыты |
| I07-018 | Проверка actual files в положительных сценариях | E3 cleanup/descriptor/FS races открыты; missing после совершённого commit относится к I07-016 |
| I07-019 | Post-real-SQL fault откатывает current/layout/refs/receipt | Draft/stage consume/pins rollback отдельно |
| I07-020 | Early roles/CSRF/framing before body — HTTP;7 socket header checks PASS | Полные SQL/locks/order/resource E3 probes открыты |
| I07-021 | Approved server mapping→loaded image, canonical без runtime URL; EUI-002/003; EUI-008 actual rawpaste/drop canaries остаются инертными до Check/отмены | Полная unsafe/canary матрица и прочие источники вставки частичные |
| I07-022 | EUI-004 final PASS: native employee text/format/ordinary Backspace/Delete, rapid Home→Backspace сохраняет marker/map/текст, прямой tamper и byte ACL отказ | Cut/drop/reparent/undo и другие браузеры открыты; диагностический4 PASS не подменяет final8 |
| I07-023 | RAM-only permits, exact captured ack очистка проверены кодом | E3 browser conflict/CSSOM/delay/lost/reauth matrix открыта |
| I07-024 | Реальные Stable/shared-reference retention — HTTP; EUI-005 native Stable/new ref/old files retained, EUI-007 восстановление, cleanup собственных unreferenced leaves | Cancel/prune/HTML consumer/concurrent cleanup отдельно |
| I07-025 | Scoped emission/security guards review; все8 EUI CSP/inline/storage invariants PASS, безопасные bounded diagnostic facts | Полная identity/privacy/inflight matrix отдельно; microtask observation не называется post-handler |
| I07-026 | 214 оригиналов не используются и не меняются; legacy/component resolver не подключён | Dedicated E3 unknown/ambiguous legacy negatives и миграция отдельно |

## Точка продолжения

Локальные E3-REV-001–005 закрыты только в проверенном первом инкременте: parent gate, clickable slots, sync focus и pre-native boundary/interior selection. Подтверждены356 Python,8 EUI и8 MEDIA regression в своих точных cohort; ограниченный независимый допуск получен. Продолжать открытые I07/M07/P07 resource/identity/race/paragraph/shared/price/legacy gates. Основные product URLs/settings и публичный renderer пока не подключаются; DEV-07 целиком не завершён. Этап8 около20%, DEV-07 около90%.
