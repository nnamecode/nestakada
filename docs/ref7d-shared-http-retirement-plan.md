# REF-07D: удаление legacy HTTP/UI lifecycle Header/Footer

Дата: 2026-11-09
Основание: D-676 и разрешение владельца «Продолжай» (`REF-07D-Q001`, D-677).

## Цель и граница

Удалить только больше не используемую административную HTTP/UI-поверхность старого shared lifecycle после перехода обычных Header/Footer операций на simple inline PostgreSQL.

Удаляются маршруты и соответствующие view/UI/JavaScript ветви:

- `restore/prepare/`;
- `stages/<uuid>/cancel/`;
- `result/<uuid>/`;
- `cleanup/<uuid>/`;
- `cleanup/jobs/<uuid>/` и `resume/`;
- `diagnostics/<uuid>/` и `reconcile/`.

Остаются editor/check/draft/apply/history/version/compare/direct version restore и public renderer.

## Не входит

- модели, migrations и строки shared lifecycle;
- шесть legacy blobs, storage/file fallback и management-команды;
- `commands.py`, `commits.py`, `lifecycle.py`, journal/quota/reservations/profile;
- page receipts/identities/stages/pins;
- sessions/generation, CSRF, owner gate, normalizer, media checks, audit, scanner, throttle;
- production/VPS/старый сайт, deploy и backup.

## Приёмочные сценарии

- `R7D-001`: каждый из восьми классов старых URL более не разрешается Django и отвечает 404 для owner; никаких legacy rows/data/files не меняется.
- `R7D-002`: anonymous/employee не получают данные через удалённые адреса; отсутствие маршрута не открывает новый view.
- `R7D-003`: history остаётся owner-only, показывает версии/compare/direct restore и больше не запрашивает/показывает cleanup jobs или ссылки удаления.
- `R7D-004`: editor JavaScript и шаблон не содержат stage-cancel URL/control; check/draft/apply и retry точной исходной операции остаются.
- `R7D-005`: direct restore из существующей версии по-прежнему создаёт новую inline revision с действующими owner/session/CSRF/normalizer/media/audit checks.
- `R7D-006`: public Header/Footer rendering и обычные simple apply/draft/publish не меняются.
- `R7D-007`: schema/migrations и агрегатные main DB counts/storage inventory неизменны.
- `R7D-008`: targeted и полный shared regression проходят; затем независимое review.
- `R7D-009`: foundation штатно остановлен, named volumes и backup сохранены.

Если тест выявит зависимость нормального workflow от удаляемого URL, реализация останавливается: scope не расширяется автоматическим переписыванием lifecycle.

## Статус D-678: приостановлено владельцу

Реализация удаляет только согласованную HTTP/UI-поверхность. Модели, migrations, строки, blobs, storage fallback, внутренние lifecycle-модули и security runtime не удалялись.

Полученные доказательства:

- focused `ref7d`: 8/8 PASS;
- `shared-provenance`: 6/6 PASS;
- `shared-public`: 10/10 PASS;
- тестовая БД после исторической migration-проверки возвращена на актуальную `shared_content.0006`;
- foundation остановлен (`Active=False`, активных compose services нет), named volumes и backup не удалялись.

Полный shared regression ещё не пройден. Отдельный `shared-reservation` run подтвердил: arithmetic test PASS, затем первый из 11 методов `SharedReservationTests` получил `hits=[]` вместо старого ожидания `['metadata_written']`. Эти 11 тестов проверяют снятый file/journal HTTP writer, тогда как действующий simple inline путь намеренно его не вызывает. Попытка исключить весь класс была отклонена как слишком широкое ослабление проверок и **не применена**.

`REF-07D-Q002`: разрешает ли владелец удалить ровно 11 obsolete-тестов старого file/journal HTTP writer, сохранив `SharedReservationArithmeticTests`, используемый действующими тестами `ReservationFixture`, все active simple/public/direct-restore/security проверки и сами внутренние legacy-модули в рамках текущего REF-07D? Альтернатива — сохранить или переписать эти 11 тестов на прямой вызов внутренних legacy-модулей, что оставит тяжёлую архитектуру как поддерживаемый контракт.

После ответа Q002: один точный patch, повтор focused/full shared regression, финальные static/migration/data checks и independent review. До этого REF-07D не завершён.

## Решение D-679

Владелец ответом «хорошо, делай как лучше» утвердил рекомендованный вариант `REF-07D-Q002`. Разрешено удалить ровно 11 методов `SharedReservationTests`, относящихся к снятому file/journal HTTP writer. Не разрешено удалять `SharedReservationArithmeticTests`, `ReservationFixture`, использующие её active тесты, внутренние lifecycle-модули, schema/data/blobs/storage или security controls. После точного patch обязательны focused/full regression и independent review.

## Статус D-680: приостановлено владельцу

Точный Q002 patch применён: `SharedReservationTests` отсутствует, `SharedReservationArithmeticTests` и `ReservationFixture` сохранены. `shared-reservation` 1/1 и `ref7d` 8/8 PASS.

Full shared нашёл 85 тестов, прошёл 65 и остановился на первом failure в `SharedReadHttpTests.test_owner_empty_editor_and_history_are_private_read_only`: старое ожидание текста «Применение и сохранение пока недоступны» не соответствует действующему simple-inline редактору с кнопками check/draft/apply. Workspace-test точечно исправлен: он требует действующие кнопки, отсутствие старого текста, прежние owner-only/private/no-mutation/history assertions сохранены.

Targeted `shared-reads` был затем ошибочно запущен без перезапуска foundation. Foundation использует immutable source snapshot со времени Start, поэтому контейнер повторно исполнил старый test-файл и получил тот же assertion. Это две эквивалентные ошибки; третьего запуска нет. Foundation штатно stopped, private files/named volumes/backup retained.

Возобновление только после ответа владельца: fresh foundation Start создаёт новый source snapshot, затем ровно один `shared-reads`; при PASS — один full shared, final static/migration/data checks и independent review.

## Решение D-681

Владелец ответом «Продолжай» возобновил D-680. Разрешена только зафиксированная проверочная последовательность: fresh foundation Start с новым immutable source snapshot, один `shared-reads`, при его PASS один full shared, затем final checks и independent review. Новых product/schema/data изменений это решение не разрешает.

## Статус D-682: проверки PASS, review ожидается

Fresh source snapshot подтвердил workspace patch: `shared-reads` 4/4 PASS. Итоговые проверки: `shared-reservation` 1/1, `ref7d` 8/8 и full shared 85/85 PASS; три finite large calibration-теста штатно skipped и остаются в dedicated runner. Django system check0, `makemigrations --check --dry-run` no changes, active legacy route refs0, Python/JS/PowerShell syntax и `git diff --check` PASS.

Main DB/storage aggregate inventory не изменился относительно D-676: blocks2, revisions6/all inline, drafts0, stages4, pins0, receipts36, cleanup jobs2, identities96, budget1, physical blobs6, journals0. Foundation stopped, private files/named volumes/backup retained. Independent review запущен; до `APPROVED` REF-07D не завершён.

## Review D-683: changes required

Reviewer подтвердил безопасность product removal и сохранность normal editor/check/draft/apply/history/version/compare/direct restore/public/CSRF/roles/no-mutation paths, но нашёл три harness-проблемы:

- P1: `test-editor.ps1` оставил choices/branches удалённых shared-cleanup/shared-cancel и удалённый cleanup label внутри dedicated calibration;
- P2: удаление cleanup test-файла унесло три прямых security regression сохранённого `SharedStorage.unlink_verified` для wrong hash/symlink/hardlink, inode replacement и parent rename race;
- P2: три cleanup browser-QA файла/refs продолжают обращаться к удалённым cleanup/diagnostics URL.

Remediation не меняет product runtime/schema/data: убрать stale CLI labels, перенести три security tests в retained storage suite, удалить obsolete browser-QA контур, затем выполнить targeted storage/calibration/static checks и repeat independent review.

## Статус D-684: приостановлено на Q003

Review remediation применена: obsolete shared-cleanup/shared-cancel CLI choices/branches и cleanup label удалены; три cleanup browser-QA файла удалены; три `unlink_verified` security tests перенесены в `test_shared_storage.py`. Static refs/syntax/diff clean, `shared-blob` 24/24 PASS, включая все три восстановленные race-защиты.

Dedicated `shared-calibration` теперь корректно собирает три существующих теста. Первый test после 105.766с получил один failure на удалённом UI-тексте «История занимает не менее 75% бюджета». Повтор не выполнялся. Static inspection показывает, что оставшаяся часть этого теста требует старые reservation bytes admission/debt/books/receipts, а второй large-count test требует `_fault_boundary('book_durable')`, legacy receipts и запрет 10001-й версии. Эти контракты сняты simple-inline путём и противоречат active regression, где 10000 historical rows не блокируют inline apply. Третий calibration test точных 1 МиБ для обоих блоков и 32 обновлений draft проверяет действующий путь и сохраняется.

`REF-07D-Q003`: разрешает ли владелец удалить ровно два obsolete calibration-теста старого reservation/file writer (`75percent...` и `9999...10001_denied`) вместе с их private helpers, сохранив exact-1MiB/32-draft calibration, quota arithmetic, storage security и все active simple/public tests? После разрешения — точный patch, dedicated calibration, full shared, final checks и repeat independent review.

Foundation stopped, private files/named volumes/backup retained. До ответа Q003 удаления нет.

## Решение D-685

Владелец ответом «Продолжай» разрешил `REF-07D-Q003`: удалить ровно два obsolete calibration-теста старого reservation/file writer и используемые только ими private helpers/imports. Exact-1MiB для обоих блоков и 32 draft updates, quota arithmetic, restored `unlink_verified` security regressions и active simple/public tests сохраняются. После patch обязательны dedicated calibration, full shared, final checks и repeat independent review.

## Статус D-686: remediation PASS, repeat review

Q003 patch оставил ровно один active calibration test. Dedicated runner: 1/1 PASS за68.212с, exact 1MiB для header/footer и 32 draft updates подтверждены. `shared-blob`: 24/24 PASS. Full shared: 86/86 PASS за343.393с; единственный skip — dedicated calibration, отдельно выполненный PASS. Три восстановленные `unlink_verified` race-защиты прошли и targeted, и full.

Django system check0, makemigrations no changes, obsolete CLI/browser/calibration refs0; internal `reservations.py` остаётся по scope и закономерно содержит собственный `book_durable`. Python/JS/PowerShell syntax и diff PASS. Main aggregate inventory неизменен: blocks2/revisions6/all inline/drafts0/stages4/pins0/receipts36/cleanup2/identities96/budget1/blobs6/journals0. Foundation stopped, private files/named volumes/backup retained. Repeat independent review запущен; до `APPROVED` этап не завершён.

## Статус D-687: приостановлено на Q004

Repeat reviewer подтвердил закрытие D-683/Q003, но нашёл P1 в active final browser QA: `editor_final_http_probe.mjs` всё ещё выполнял positive shared restore-prepare/cancel. Probe переписан на direct version page restore для header/footer, проверку нового current revision/source hash, неизменность retained stages/pins, отсутствие cancel control и сохранность другого блока/pages. Coordinator source count обновлён до фактических 280 с полным per-file SHA/runtime admission; local freeze hashes сверены.

Первый coordinator run остановился до browser groups на `CF_QA_SOURCE_DRIFT`: в freeze вручную пропущена одна `d` в coordinator SHA; исправлено, все три SHA затем match. Второй run после изменённого условия снова остановился до browser groups с closed `SCOPED_DOCKER_COMMAND_FAILED`. Read-only aggregates доказали отсутствие partial seed и полное совпадение retained main cohort: users3/pages6/page revisions22/states6/draft1/stages3/pin1/assets3/files9/usages24 и shared counts D-686. Static fixture inspection локализует конфликт: new-seed path требует пустые User/Page/Asset и потому не может запускаться поверх обязательного retained CF07 cohort. Reset/delete/reseed запрещены.

`REF-07D-Q004`: разрешает ли владелец добавить bounded `continue-shared` режим в существующие final coordinator/fixture/probe, который использует сохранённый exact CF07 private seed/ownership, read-only валидирует retained cohort, запускает только обновлённую browser-группу CF07-002 direct restore и сохраняет результат без cleanup/reset? После PASS — final static/count checks, stop и repeat independent review. Третьего coordinator run до ответа нет.

Foundation stopped, named volumes/private seed/backup retained; product/schema/security не менялись.

## Решение D-688

Владелец ответом «Продолжай» разрешил `REF-07D-Q004`. Добавляется только bounded `continue-shared` в существующий final QA harness: до браузера сверяются exact private seed, pending/retained manifests, owned page/block identities, current pointers, version counts и известные aggregate counts retained CF07 cohort. Браузер выполняет только обновлённый CF07-002: apply A, apply B и direct restore A для Header/Footer с проверкой provenance/hash, неизменности другого блока/pages и отсутствия stage/cancel lifecycle. Reset, reseed, cleanup и product/schema/security изменения запрещены. После одного запуска обязательны final static/count checks, штатный Stop и repeat independent review.

## Статус D-689: bounded PASS, repeat review

Первый `continue-shared` вызов остановился до browser/DB mutation на `EXACT_PENDING_RESUME_REQUIRED`: общий guard ошибочно применил старый recovery source/hash к новой ветке, хотя её exact pending hash уже закреплён отдельным guard. Условие сужено только для `sharedTail`; прежние recovery/continuation/media guards не менялись. Failed output сохранён пустым, новый output/private path выбран без удаления. После изменившегося условия единственный повтор прошёл.

Exact private seed/pending/retained hashes, source/QA freeze, owned page/block identities, current/version counts и aggregates admission PASS. Единственная browser group `CF07-002` PASS: Header/Footer каждый создали A, B и новую direct-restore revision из A; source provenance/hash, неизменность другого блока/pages/stages/pins и отсутствие cancel control подтверждены. Retention: page version counts 8/4/4/3/2/1 неизменны; shared revisions стали6+6 ожидаемо; baseline/system route preserved; cleanup false, stderr0, OOM0. Django check0, makemigrations no changes, JS/Python/diff PASS. Foundation stopped, named volumes/private evidence retained. Repeat independent review запущен; до `APPROVED` REF-07D не завершён.

## Итог D-690: завершено

Repeat independent reviewer вернул `APPROVED`; P1/P2/P3 и remaining findings отсутствуют. Подтверждены direct owner-only version restore, bounded sharedTail exact admission/one-group execution, отсутствие reset/reseed/cleanup, неизменность guard прежних recovery/continuation/media modes и сохранность CSRF/session/current CAS/normalizer/media/storage race protections. Документы и browser evidence соответствуют коду. REF-07D завершён. Следующий возможный шаг из D-676 — новая отдельная read-only инвентаризация прекращения новых `SharedIdentityReservation` и file fallback; автоматически в REF-07D она не входит и до новой приёмочной границы не начинается.
