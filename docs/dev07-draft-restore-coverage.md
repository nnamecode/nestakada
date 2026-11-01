# DEV07-D — фактическое покрытие D07 и незавершённые проверки

2026-10-31. Матрица к [сценариям D07-001..030](dev07-draft-restore-checks.md). Это30 сценариев требований, а не30 автоматически закрытых пунктов от наличия30 test methods. Подготовлены17 HTTP +4 cancel-admission +4 source-admission +5 PG-race methods и9 browser groups. Совпадение чисел не означает эквивалентность покрытия.

## Что действительно выполнено

- Первый отдельный HTTP-набор:16 PASS за51.746s, `work/dev07-draft-restore-20261031/draft-http-first.txt`, snapshot e0a02fec-8302-43d0-ad03-bebef7e37afa. Семнадцатый legacy-fingerprint testcase добавлен позже.
- Первый полный набор:286 tests за354.624s, **FAILED:1, остальные285 прошли**, `all-tests-first.txt`. Все новые17 HTTP/4 cancel/5 race methods прошли в том immutable snapshot (6b7…); единственный отказ — прежнее ожидание409 вместо нового400 в current-only check regression. Эта ошибка исправлена адресно; исходный полный run остаётся FAILED, а не переименовывается в PASS.
- Source-admission:4 PASS за7.307s, `source-admission-first.txt`, после исправления загрузки payload до EditorSlot, snapshot43a121a0…. Это отдельный SQL/order набор, не network/RSS proof.
- Второй полный regression: **290 PASS за381.948s**, `work/dev07-draft-restore-20261031/all-tests-second.txt`, latest snapshot43a121a0…. Включает17 HTTP/4 cancel/4 source-admission/5 race methods. После этого прогона product source не менялся; исправление источника до slot входит в проверенный snapshot.
- Legacy current-editor regression: **16 browser groups PASS**, `work/dev07-draft-restore-20261031/browser-legacy-first/host-report.json`, probe e32a7fd6973c79956e3288d82f69121c0507a6a6632e096d86ef3bd5f39551ad. Это current-editor/CSP/identity coverage, не автоматическая проверка всех новых selected draft/stage веток.
- D07 product UI: **9 groups PASS**, `work/dev07-draft-restore-20261031/browser-draft-second/host-report.json`, run8cffd97e-4470-47c0-af0f-3555f53f1659. Fixture SHA11ccc78ab753793525437d0c2f95bc45568831c614cd079397fcec671894898c, probe SHA0a2da7a146d32b2addbb5e2a38103e0aa4925bc5cd6811fbcdd537fca222ba6e. Root выполнил настоящий Nginx/browser/PG observer. Контексты закрыты; cleanup users/pages/versions/drafts/stages/pins=0, оставлен ровно системный Route. Permanent version/media tombstones215/28, operation receipts117 и append-only audit301 сохранены.
- Первый D07 browser run (`browser-draft-first/host-report.json`) остаётся **FAIL** с потерянным Node result, не переименован в PASS. Диагностический ограниченный прогон `browser-draft-diagnostic/host-report.json` —4 PASS с **scope DIAGNOSTIC_ONLY**, не9. Отдельный `dialog-listener-result.json` дал7 положительных булевых controls на синтетической странице и доказал ошибку QA dangling dialog handler; это **не product acceptance**. После scoped helper fix выполнен указанный выше полный9 PASS.

Runtime запускает координатор. QA-автор матрицы не запускал Docker/браузер/PG. Выводы ниже ограничены фактическими assertions перечисленных методов, а не обещанием всего D07/DEV07/140AC.

## Указатель тестов

H — [test_draft_restore_http.py](../app/page_editor/test_draft_restore_http.py), класс DraftRestoreEditorHttpTests. C — [test_draft_cancel_admission.py](../app/page_editor/test_draft_cancel_admission.py), DraftCancelAdmissionTests. A — [test_source_admission.py](../app/page_editor/test_source_admission.py), SourceAdmissionTests. R — [test_draft_restore_concurrency.py](../app/page_editor/test_draft_restore_concurrency.py), DraftRestoreConcurrencyTests. Номера H/C/A/R ниже — локальные ссылки матрицы, не новые REQ/AC/D07.

| Ссылка | Фактический test method |
|---|---|
| H01 | test_current_source_legacy_shape_and_selected_draft_privacy |
| H02 | test_new_owner_draft_creates_no_automatic_or_current_mutation |
| H03 | test_owner_draft_update_and_exact_replay_do_not_increment_twice |
| H04 | test_edited_draft_publish_atomic_consume_and_exact_replay |
| H05 | test_actual_draft_revision_change_conflicts_with_old_checked_publish |
| H06 | test_normal_draft_proof_cannot_be_converted_into_rebase |
| H07 | test_explicit_rebase_proof_moves_basis_without_publication |
| H08 | test_rebase_target_change_after_compare_is_conflict |
| H09 | test_cancel_draft_stale_revision_then_actual_cancel_replay |
| H10 | test_stage_selected_load_check_do_not_publish |
| H11 | test_edited_stage_employee_save_preserves_projection_and_consumes |
| H12 | test_stage_foreign_actor_and_query_body_mismatch_denied |
| H13 | test_stage_revoke_after_check_cannot_save |
| H14 | test_draft_finish_fault_rolls_back_payload_refs_pins_receipt_audit |
| H15 | test_stage_publish_finish_fault_rolls_back_current_consume_pins |
| H16 | test_draft_session_deleted_during_real_preflight_cannot_update |
| H17 | test_pre_d07_current_editor_fingerprint_receipt_replays_without_recommit |
| C01 | test_employee_foreign_visitor_multipart_denied_before_post_or_body |
| C02 | test_owner_type_size_length_transfer_encoding_denied_before_csrf_parse |
| C03 | test_real_csrf_remains_required_after_small_json_admission |
| C04 | test_owner_header_csrf_actual_small_cancel_never_uses_heavy_slot |
| A01 | test_default_state_metadata_has_no_payload_sql_with_real_detector_control |
| A02 | test_cancel_denials_never_load_draft_or_current_payload |
| A03 | test_busy_check_save_draft_refuse_before_full_context_body_child |
| A04 | test_busy_selected_state_and_editor_get_refuse_before_source_payload |
| R01 | test_http_draft_create_loses_to_actual_second_connection_create |
| R02 | test_http_draft_update_loses_to_actual_second_connection_update |
| R03 | test_http_edited_draft_publish_loses_to_actual_cancel |
| R04 | test_http_rebase_loses_to_actual_draft_revision_update |
| R05 | test_http_stage_publish_loses_to_actual_employee_current_commit |

Browser: [editor_draft_http_probe.mjs](../tools/editor_draft_http_probe.mjs), DUI-001..009, **actual9 PASS в указанном final run**. Это ограниченный corpus. DUI-006 включает реальный dirty-history confirm dismiss/accept и отдельный actual-CSRF unchecked replacement POST, а не только переход page.goto. Результат группы не закрывает непроверенные ветки связанного D07 целиком.

## Матрица всех30 D07

| D07 | Методы / browser cases | Что подтверждено и что остаётся |
|---|---|---|
| D07-001 | H02, R01; DUI-001 | Подтверждён scoped framework/PG/browser create+normalization+pin без automatic/current mutation. Реальный media-ref corpus остаётся |
| D07-002 | H03, R02; DUI-002/009 | Подтверждены actual update, sequential replay, competing update и UI delayed-response/новая правка во время ответа с отдельным explicit save; полной истории draft не вводится |
| D07-003 | H01, C01; DUI-007 | Подтверждены selected-state privacy/cancel role denial и browser current/draft navigation/canary privacy. Вся матрица forged draft write/read ролей не закрыта |
| D07-004 | R05, прежний DEV05 current-based employee test; DUI-004 | Подтверждены competing current запись и новый UI employee-current→stale-owner-draft→explicit rebase без перезаписи current. Прочие stale-draft разрешения конфликтов отдельно |
| D07-005 | R01/R02 | Реальные два PG connection и Event interleavings create/update подтверждены. Нет второго heavy HTTP: при1slot он мог бы дать busy вместо domain race |
| D07-006 | H06/H07/H08, R04; DUI-004 | Подтверждены bound rebase proof/target conflict/concurrent draft revision refusal и actual UI escaped comparison+checkbox+перенос без merge/публикации |
| D07-007 | H04/H05, R03; DUI-002 | Подтверждены edited checked snapshot apply/atomic consume/server draft revision conflict и actual UI edited apply. Отдельный legacy strict-negative и весь media-layout scope этим не доказаны |
| D07-008 | H03/H04/H09/H17; DUI-003/008 | Подтверждены durable replay/consume/legacy current fingerprint, UI lost draft response→другая вкладка consume→source-gone exact manual replay. Old receipt после дальнейшего update ещё живого draft и concurrent same-op остаются |
| D07-009 | H09, C04, R03; DUI-005 | Actual stale cancel/отмена/replay/pins/publish-vs-cancel и browser explicit cancel с сохранённым RAM и без implicit Save подтверждены |
| D07-010 | H10; DUI-006 | Selected stage load/check и actual native history/read/prepare не меняют domain; подтверждён dirty-history navigation guard |
| D07-011 | прежний DEV05 confirmation guard; DUI-006 | Подтверждён scoped actual UI: dirty-history decline retains RAM, accept navigates; unchecked server POST409 не создаёт stage, checked native form создаёт stage без публикации. Это не plain page.goto |
| D07-012 | H11; DUI-006 | Подтверждены employee text projection/protected current payload equality и owner native UI restore safe corpus. Полноценные media/layout integrations остаются |
| D07-013 | DUI-006 safe branch; общие producer tests отдельно | Safe native historical branch с CSP controls подтверждён. Полный unsafe/legacy historical candidate + explicit normalization corpus ещё не выполнен; producer unit PASS не закрывает его |
| D07-014 | H11; DUI-006 | Подтверждены framework/PG и actual browser staged input→правка→separate Save, source provenance, consume/pins; engine replay проверен отдельно |
| D07-015 | H12 и closed source selectors H01 | Partial: malformed selector/body binding и foreign denial. Полная матрица forged base/generation/protected candidate/stage-field subset pending |
| D07-016 | прежние DEV05 compatibility guards | Новая end-to-end проверка protected/container/component/READY/files и unsafe historical producer не выполнена. Явный capability отказ не считается positive integration |
| D07-017 | H05/H08/H13, R04/R05 | Actual draft revision/current/grant conflicts подтверждены; stage generation transition и полный proof/schema/protected dependency matrix pending |
| D07-018 | H11 consume replay, H09 draft cancel replay | Partial: permanent operation replay. Новый selected terminal-stage GET/UI без candidate после всех released/consumed/invalidated/gone/stale исходов ещё не покрыт полностью |
| D07-019 | H12, C01 | Foreign Page/actor и cancel owner gate подтверждены частично. Owner/второй назначенный employee с доступом к той же Page и чужим stage требует отдельного case; Page-grant denial сам по себе не доказывает actor-stage binding |
| D07-020 | R01..R05, H03/H04/H11 | Пять реальных different-operation races + sequential replay; simultaneous exact same-operation race и весь action/body collision matrix pending |
| D07-021 | H14/H15 rollback; DUI-008/009 | Подтверждены SQL rollback и actual UI lost/delayed draft responses, unknown intent, exact manual retry после source consume, RAM newer typing/new explicit save. Остальные action/failure combinations отдельно |
| D07-022 | H16, C03/C04 | Настоящее позднее удаление AuthSession во время draft preflight и genuine CSRF подтверждены. Stage/session/gen reauth при новом selected basis, отказ до большого socket body и остальные late boundaries pending |
| D07-023 | предыдущая current-editor identity когорта отдельно | Новая D07 selected draft/stage same-browser different-user terminal cleanup ещё не проверена. Ни одни DOM assertions не обещают physical memory zeroization |
| D07-024 | A03/A04 (order only); DUI-005/009 | Injected Busy доказывает порядок, не network concurrency. Actual UI RAM/cancel/delayed-response и sampled CSP0/inline0/localStorage0/sessionStorage0 подтверждены; полного all-storage/no-exfil proof нет |
| D07-025 | H14/H15, R01..R05 | Фактический post-ledger SQL fault rollback с настоящими pins/receipts/current/draft/stage подтверждён. AssetUsage в corpus без изображений; реальные физические файлы и все отдельные SQL fault positions не покрыты |
| D07-026 | R01..R05, A01..A04 | Во время real E.preflight actual second PG PID получает domain locks; loser state/audit неизменны. Payload SELECT до slot запрещён actual execute_wrapper с genuine SELECT positive control. Network slow-read, parent+child peak RSS/CPU и maximum input resource proof отдельно pending |
| D07-027 | H02/H04/H09/H11, R03/R05; прежние DEV05 holds | Реальные draft/stage pins создаются/снимаются атомарно. Новый D07 all10-held prune/ref/file corpus не выполнен; прежние DEV05 engine checks не являются media UI proof |
| D07-028 | R05; actual DEV05 source semantics | Current competitor реально invalidates stage; owner draft сохраняется по engine rules. Нет нового clock/TTL/forced cancellation. Полный UI terminal provenance и abandonment behaviour runtime pending |
| D07-029 | C01..C04, A01..A04, H01/H12; DUI-007 | Framework private errors/metadata/admission и actual browser privacy подтверждены в пределах assertions. Host socket corpus — отдельные anonymous header-only controls, не доказательство authenticated slow-read/all framing из Client |
| D07-030 | H14/H15/R01..R05; final root host cleanup | Подтверждены no extra commit audit при rollback/races и actual new-fixture cleanup0 live users/pages/versions/drafts/stages/pins, system route/permanent ledgers сохранены. Полный no-input log/tmp/trace/backup scan и secrecy на всех носителях ещё не доказаны |

## Что эти результаты не доказывают

Framework Client использует явно обозначенный reader seam и настоящие child/PG/engine positives. Injected Busy/accessor bombs проверяют порядок, а actual SQL execute_wrapper ловит payload reads; ни один из них не измеряет Nginx body buffering, реальный deadline/framing, допустимый максимум64/5MiB, большой canonical price или parent+child RSS. Races имеют разные actual PG PID, first-thread-only E.preflight barrier и post-winner state/audit oracle; это не full simultaneous same-op HTTP proof.

Stage→draft остаётся controlled409 capability, не отсутствующая положительная ветка, которую можно засчитать по owner draft save. Protected nodes/media READY/component resolver, физические refs/files, полный price GUI, остающиеся native terminal/selected-source reauth ветки и публичный DEV08 renderer требуют своих положительных контролей. Scoped rebase UI теперь actual PASS, но не заменяет эти остатки. Dev07-D не меняет Header/Footer/URL/дерево/Stable/production и не закрывает все30 D07, DEV07 или140 AC.
