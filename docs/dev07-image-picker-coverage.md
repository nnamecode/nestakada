# DEV07-E2-first — фактическое покрытие M07

2026-10-31. Матрица относится только к двум внешним полям `main_image`/`preview_image` из [сценариев M07](dev07-image-picker-checks.md). Она не закрывает все 24 M07 и не активирует embedded/protected HTTP/UI. Запуски выполняет координатор; QA-агент готовил исходники и читал результаты, но не запускал Docker или стенд.

## Зафиксированные результаты

- **22 PASS, 127.851 с** — [media-tests-third.txt](../work/dev07-media-20261031/media-tests-third.txt), реальные PostgreSQL/session/child/worker/FS. HTTP framework Client использует утверждённый seam чтения body; это не доказательство Nginx/socket transport. Все Asset/производные создавались настоящим `uploads.upload` → WorkerClient; ORM READY не изготовлялся.
- **MEDIA_8 PASS** — [первый browser host-report](../work/dev07-media-20261031/browser-first/host-report.json), run `41f1ab93-d527-4ab1-9652-b323981db9d9`. Настоящие native uploads PNG/JPEG/WebP, UI/HTTP/check/save/draft/stage, фактически загруженные миниатюры с ненулевыми natural dimensions, отдельное сравнение HTTP SHA/bytes с физическими файлами, CSP/inline/storage invariants и снимки 1280/390.
- Первый browser использовал bundle `2ca55a892f5d0af33538c4c32361e725025ea4ba941f73b937d0d9075a3cd5a4`. После визуального осмотра координатор добавил видимые подписи «Папка»/«Поиск» и перенос кнопок. **Второй MEDIA_8 PASS** — [browser-second/host-report.json](../work/dev07-media-20261031/browser-second/host-report.json), run `6f39c24b-ab21-408a-b20a-12c1dac9b196`, уже на финальном bundle `72a0961920d09a3b18e1d29394f54dbea228c7273942b496d2706adb7e455fe2`. Финальный [mobile PNG](../work/dev07-media-20261031/browser-second/media-mobile.png) имеет SHA `36725fda4bddb0830180e772d753ca47b94df3b5a21e017a8e1e97c84c2626d0`; [desktop PNG](../work/dev07-media-20261031/browser-second/media-desktop.png) находится в том же отчётном каталоге.
- Первый полный регрессионный запуск остановился на устаревшем expected status: [regression-tests.txt](../work/dev07-media-20261031/regression-tests.txt), 153 выполненных случая / 156.489 с / **FAILED 1** после 152 PASS. Он не является PASS всех 335.
- **335 PASS, 395.879 с** — завершённый [regression-tests-final.txt](../work/dev07-media-20261031/regression-tests-final.txt), финальный снимок `a72941c2-5a93-4814-9508-80f226003ab9`. SHA source manifest `dce2ea7414804edf6b6f5ad765b97c10d95d8421e83b0ebb061b7baf51cbbee8` совпадает с app source в отчёте второго browser. Отдельная read-only сверка QA подтвердила все 160 workspace app-файлов по этому manifest: 0 расхождений. Только старые тестовые oracle были обновлены: check-файл SHA `70f2c917375eb626d637ef7f0a8ca94d3ada3f22a240eeb1cc1abde250fc3ab0`, save-файл SHA `8ba8de482e24b2abc0159f24d656f5607d03f74f1de8f878a3aed9bbc75e1019`. Оба их метода фактически прошли; дополнительный E1 `test_nested_parent_positive_uses_independent_ancestor_path_fingerprint` также имеет `ok` в этом полном запуске. Это pure placement evidence, не активация embedded HTTP/UI.

Уборка первого browser подтверждена тем же host-report: `closed=true`, живых users/pages/versions/drafts/stages/pins/assets/files — 0; остаётся один неизменный системный Route. 18 наблюдений missing leaf относятся к **9 уникальным файлам** трёх Asset: список содержит текущие файлы и повторённый host-known allowlist, а не 18 различных файлов. Parent unavailable не принимался за отсутствие. Identity tombstones, permanent OperationReceipt и append-only audit сохранены. SHA 13 QA/input файлов и снимок четырёх контейнеров/source/worker совпали до/после. Это отдельные guards, а не утверждение, что стандартный foundation collector покрывает изменённый editor overlay.

Второй browser независимо завершился с `closed=true`, теми же нулевыми live counts, одним сохранённым system Route и 9 уникальными missing leaves. Permanent counts после него: version identities251, media identities52, operation receipts135, audit341; они намеренно не очищаются. Его foundation before/after равны, QA/input hashes неизменны. Финальные source/bundle и завершённые отчёты согласованы; новых runtime запусков при записи этой матрицы не было.

## Ссылки на исполняемые проверки

Все B01–B22 — методы `EditorMediaHttpTests` в [test_media_http.py](../app/page_editor/test_media_http.py), фактически прошедшие в targeted22. B-номера — локальные ссылки этой матрицы, не новые бизнес-требования.

| Ссылка | Точное имя метода |
|---|---|
| B01 | `test_picker_owner_actual_ready_files_and_cross_page_reuse` |
| B02 | `test_picker_main_preview_bytes_are_real_distinct_worker_outputs` |
| B03 | `test_picker_employee_visitor_and_private_source_closed` |
| B04 | `test_picker_closed_query_and_boundary` |
| B05 | `test_picker_pagination_51_actual_worker_uploads` |
| B06 | `test_owner_main_preview_metadata_save_and_usage_slots` |
| B07 | `test_employee_media_keys_denied_even_unchanged_or_null` |
| B08 | `test_current_context_membership_and_private_source` |
| B09 | `test_initial_media_has_context_urls_without_employee_write_keys` |
| B10 | `test_referenced_asset_cleanup_refuses_without_unlink` |
| B11 | `test_unattached_picker_asset_does_not_grant_context_membership` |
| B12 | `test_stable_old_asset_bytes_survive_owner_replace_and_null` |
| B13 | `test_draft_context_uses_actual_private_reference` |
| B14 | `test_stage_owner_candidate_a_employee_candidate_b` |
| B15 | `test_check_typed_metadata_invalid_and_alt_boundary` |
| B16 | `test_media_changes_cannot_reuse_check_proof` |
| B17 | `test_exact_permanent_replay_precedes_new_file_availability` |
| B18 | `test_missing_retained_image_text_only_check_has_no_proof` |
| B19 | `test_corrupt_retained_preview_refuses_verified_context_bytes` |
| B20 | `test_late_context_grant_revoke_closes_verified_file` |
| B21 | `test_late_picker_session_revoke_closes_verified_file` |
| B22 | `test_actual_media_commit_post_ledger_fault_rolls_back_refs_and_bytes` |

EMUI-001–008 — реальные группы [editor_media_http_probe.mjs](../tools/editor_media_http_probe.mjs), результаты в host-report выше. Смысл групп: 001 native uploads; 002 Add here/RAM/metadata/current; 003 Replace here/cross-Page/history/files; 004 draft/bytes/apply; 005 native history/actual restore candidate/edit/apply; 006 ACL/readonly/original/exact public key denial; 007 invalid dimensions и свежий proof после metadata edit; 008 CSP/desktop/mobile. Поле `m07` в раннем JSON — теги подготовки групп; оно не доказывает все пункты указанных там сценариев. Нормативное сопоставление и остатки приведены ниже.

## Матрица 24 M07

«Частично» означает PASS перечисленных проверок, но не всего сложного сценария. «Не исполнен» не означает обнаруженный дефект продукта. Ни один широкий M07 не получает полный статус только по совпадению ID в JSON.

| M07 | Статус | Фактическое свидетельство | Что остаётся вне подтверждённого объёма |
|---|---|---|---|
| 001 | Частично | B01/B02, EMUI-001: реальные PNG/JPEG/WebP uploads, READY, независимые source SHA и физические MAIN/PREVIEW bytes; A/B имеют различающиеся производные | Pending/decoder-failure selectable-negative в новом picker не исполнялся; старые DEV06 проверки не переименовываются в новый E2 PASS |
| 002 | Частично | EMUI-002/003: видимое место main/preview, старое/новое, явные «Добавить здесь»/«Заменить здесь», RAM-only до check/save; B06 — фактические payload и current/ordinary usage slots; второй MEDIA_8 PASS включает финальные подписи/wrapping | Весь UI-S020–023/057 не объявляется закрытым одной группой; все варианты подтверждения/отмены конкретного места отдельно не перебраны |
| 003 | Частично | B01/B05 и EMUI-003: cross-Page reuse; 51 настоящий worker upload, страницы 50+1 без потерь/дубликатов | Folder/q descendant-positive, staged/deleting/bad-derivative inventory negatives и большой каталог/resource profile |
| 004 | Частично | B03/B04: роли, unknown/duplicate query, malformed cursor, traversal, query >16KiB; safe owner B01 | Специальный SQL/file-read ordering detector именно для нового picker и все варианты отзыва session до inventory |
| 005 | Частично | B07/B08/B09, EMUI-006: unchanged/null employee image keys403, readonly bytes, отсутствие image write controls/values, visitor/foreign denial; общие auth/CSRF регрессии прошли в финальном335 | Отдельный положительный employee text-save с непустым retained image и полная новая media-specific CSRF/revocation matrix |
| 006 | Частично | B06/B15, EMUI-002/007: обе ссылки, literal alt/emoji/quotes, left/right и default center, null/positive размеры, actual stored metadata и fresh check перед Save | Полная NFC/normalization-review matrix и история/reload для всех сочетаний metadata отдельно |
| 007 | Частично | B15: alt300/+1, bool/zero/negative dimensions, extra src; EMUI-007: invalid width не исправляется изменением alt, whole input не отправлен | Nonfinite/все неверные типы/все лишние поля и очень длинные digits в этом ImageRef HTTP потоке |
| 008 | Частично | B12: настоящая Stable A, current replace B/preview null, stable usage и физические SHA A сохранены; EMUI-003 удерживает обычную историю | Самостоятельный UI Stable flow; отдельные assertions каждого immutable snapshot поля/ненаследования метки новой ordinary не добавлялись |
| 009 | Частично | B10/B12/B13, EMUI-003/004: реальный referenced cleanup отказ, история/Stable/draft refs, shared asset reuse и отсутствие скрытого unlink | Полная матрица независимых чужих consumers и отмены/удаления своих refs во всех сочетаниях; конкурентность не подменяется последовательным reuse |
| 010 | Частично | B02/B08/B11, EMUI-002/006: owner/assigned bytes+headers, actual browser load, unattached UUID404, foreign/original/public exact-key denial | Embedded-only ledger negative и внутренние legacy-image варианты; это не разрешение embedded HTTP |
| 011 | Частично | B13, EMUI-004: private draft имеет отличающееся фото, current не публикуется при draft-save, selected draft bytes, employee draft403, отдельное apply | Stale/deleted draft media endpoint и employee с тем же Asset через иной допустимый контекст отдельно |
| 012 | Частично | B14 различает owner candidate A и employee candidate B с реальными bytes; EMUI-005 — native prepare/stage, actual selected candidate, check без publish и edited Save | Employee stage UI/edit/save и изменение candidate membership во время выдачи файла |
| 013 | Частично | B20/B21: реальный grant revoke после verified open и actual AuthSession delete, отказ и закрытие открытых FD | Contextual session/different-actor/generation/source/descriptor interleavings и HTTP-stream variants; это не полная race matrix |
| 014 | Частично | B16/B18: changed Asset со старым proof409, missing retained ref при text-only check409 без proof; EMUI-007: check→save, новый proof отличается и именно он передан Save | Все stale draft/stage/source/alt/dims/null binding variants и late media evidence races; свежий proof не заменяет preflight |
| 015 | Частично | B17: реальный committed media save, физический MAIN временно отсутствует, exact same-op возвращает старый result/replay без новой DB/audit | Media draft/apply replay после source consume/prune, same-op changed media wire и session/grant permutations |
| 016 | Не исполнен | B10 доказывает только последовательный referenced cleanup отказ | Настоящие два PG соединения/Events: media cleanup ↔ new ref/preflight/upload. D07 domain races без media не считаются этим доказательством |
| 017 | Частично | B18/B19: missing retained MAIN не выпускает proof, повреждённый PREVIEW не отдаёт bytes; неповреждённые B02/B08 — positive controls | Truncated/header-invalid/inaccessible files на каждой check/save/preview границе, FS mutation timing. Final descriptor digest не называется повторным physical rehash |
| 018 | Частично | B22: fault после настоящего E.finish SQL откатывает current/history/refs/ledger/audit и сохраняет физические manifests | Аналогичный media-bearing draft/stage consume/pins rollback и lost response/manual retry с media. Чистый D07 retry не закрывает новые image RAM races |
| 019 | Новый media ordering не подтверждён | Shared admission/source guards фактически прошли в финальном335: default-state SQL detector и BusySlot до full context для check/save/draft/editor/selected state; targeted22 не содержит нового media inventory ordering detector | Отдельно новый picker/file admission/slot/SQL-lock order и resource MAX/RSS. Mock BusySlot проверяет порядок вызова, не расход памяти |
| 020 | Частично | EMUI-002/003/008: actual images, literal alt, same-origin URLs, CSP0/inline0 и 1280/390; byte proof не ограничивается src | Новая raw paste/drop→media-selection negative и полная align/dims visual matrix; прежние editor paste проверки не объявляются image-picker-specific |
| 021 | Частично | EMUI-007: input инвалидирует старый proof; Save делает новый check и передаёт fresh proof. Все8 проверяют local/sessionStorage0 | Media-specific normalization cancel/CSSOM failure, delayed/lost response while changing image/metadata, exact manual retry intent и retained RAM |
| 022 | Не исполнен | Общие D07/legacy identity transitions существуют отдельно, но MEDIA_8 их не выполняет с image refs | Same actor generation и different actor с непустыми picker maps/metadata/initial.media/unknown intent; не заявляется физическое обнуление памяти |
| 023 | Частично | EMUI-006, fixture/host review и actual cleanup: original/direct key denial, own-run IDs, 9 unique physical leaves missing, permanent/system Route retained, no trace/HTML dump; fixed diagnostics и SHA guards | Независимая полная проверка продуктовых logs/URL/secrets, всех tmp/job failures/directory-listing путей и чужих consumers; synthetic cleanup не касается gallery |
| 024 | PASS ограниченной E2-first границы | В финальном335 фактически прошли exact old-check/save recognized protected carrier empty-context409 и pure E1 nested-positive; main/preview positives прошли22 и оба MEDIA_8 | Embedded HTTP/UI, layout/component resolver по-прежнему не подключены. Этот PASS подтверждает сохранённый отказ и внешние поля, а не будущую embedded функциональность |

## Ограничения и следующая запись

22 метода и 8 групп — количество проверок, а не равенство 24 M07 или 28 P07. Непроверенные race/resource/identity/legacy/embedded варианты остаются явно открытыми: M07-016 и M07-022 не исполнены, новое media-specific ordering/resource evidence M07-019 не появилось от общего335 PASS, остальные частичные строки не повышены до полного покрытия. Нет нового сервиса, пакета, image, порта, увеличения ресурсов или изменения живого сайта. Завершённые финальные335 и второй MEDIA_8 прочитаны и связаны с тем же source manifest/bundle; дальнейшее расширение матрицы требует нового фактического свидетельства.
