# DEV07-CLOSE-04 — карта прежних доказательств и конечных пробелов

Итог DEV07-CLOSE-04, 2026-11-02: Все CF001–007 имеют достаточные связанные свидетельства; [итог](dev07-final-results.md), независимое ревью положительное. Finalsource232/8374, immutable linkedcohorts/CF001split+reuse и unit отдельно. Рецензент лично перепроверил18reuseстрок badRows0 и oldE3/CM manifests; изменённые модули не признаны автоматически unchanged. Шесть RP PNG допустимы к reuse, новых CF PNG не заявлено. Ниже сохранена исходная карта до запусков.

2026-11-01. Read-only сверка до новых тестов. База4528388, normal source231 SHA `2d8186af6462e1856bd067b447d5a3b8098eb65d392f6ea9b6f51c8b7362f8c9`, run83135551-5ec5-46f3-8f9d-f7418335fdca. Финальный manifest будет зафиксирован после QA-кода/возможных фактических исправлений. Эта карта не выдаёт будущие CF-группы за PASS.

| Область | Существующее доказательство | Что переиспользуется / что проверяется вновь |
|---|---|---|
| Normal core/admission | dev07-normal-profile-results.md, NH07-001–008, source230/217492c9…/fe5d5ce3…; actual20framework+8native | Ранние auth/CSRF/framing/budget/BUSY/body120 доказательства остаются при неизменных relevant guards/config. CF001 снова наблюдает текущую normal связку; Shared Check не засчитывается за Apply. |
| Price/simple GUI | dev07-price-gui-results.md, dev07-table-gui-results.md и model/framework/native vectors; TP2 frameworkfe4f2687…/final59351653… с указанной3pathdelta | Не переписывать прежние содержательные UUID/undo/padding/PM-capability векторы. CF001 — current normal Save/reload smoke; CF003/004 закрывают отсутствующий complex/history/selectedrestore roundtrip. |
| Shared lifecycle/provenance/quota | dev07-shared-reservation-results.md, dev07-shared-lifecycle-results.md, dev07-shared-public-results.md | Прежние pure domain/grid/accounting/fault vectors остаются с source-bound reuse. PUB QA-only URLConf не normal main-host proof. CF002 впервые наблюдает полный Apply/restore/cancel обоих блоков в конечном ordinary cohort. |
| Shared cancel | dev07-shared-cancel-results.md:7framework/13regression/2native, source2832ddd4…; позже только25CSSbytes | Exact replay/UNKNOWN/pins/atomic/debt vectors не повторяются целиком. CF002 даёт конечную normal привязку и сохраняет terminal LC-защиту. |
| Responsive | dev07-responsive-results.md:5групп/45measurements,6PNG, final2d8186af… | CSS/mainnav/source proof сохраняется; не повторять все5ширин в каждой новой CF-группе без layout finding. Это не полная TEST10. |
| Media cleanup | app/page_editor/test_media_http.py::test_referenced_asset_cleanup_refuses_without_unlink | Был последовательный commit→cleanup refusal, а не конкуренция. CF005 нужен новый actual2PG controlled case с READY bytes/refs и наблюдаемой блокировкой. |
| Embedded/source media | E3 browser-seventh8PASS и E2 regression8PASS, точные локальные артефакты ниже | Private draft/stage image/edit/Save существовали. Actor switch/unknown с непустыми maps не проверены, поэтому CF006 новый; текстовый SID не заменяет его. |
| Combined maxima | CM07-001–003:3framework tests/5Check PASS63.227s, source8631fa33… | CM001 owner/employee request2097356B/response2098396B и exact hashes/receipt/child/domain полезны для corpus/producer. Reader seam прямо не является Nginx/GUI proof. CF007 закрывает обычную GUI/ingress связку одного представителя, не весь CM002/003/worst-case. |

## Проверенные исторические артефакты

- E3: work/dev07-embedded-20261031/browser-seventh/host-report.json SHA256 `9600b8a0e957f179650cf06be75cf13276b5e1d7163b343db089eb516acb420d`, native runc6cbfebc-cf12-4306-9fb7-61d52f076e34.
- E2 regression: work/dev07-embedded-20261031/e2-regression/browser-first/host-report.json SHA256 `04ac3cda5d9cb917002775de976e3fece6292f7b0731c66981ca9940d275b152`, native runa40c4434-effe-4b83-b38f-9e955aad9efd.
- Оба использовали app source2591ef85-c96b-49dd-b897-23023ab097b5, manifest SHA256 `42c0faa8878a1eeab1fb1db81ea5402d083b2bb5cb929f37a40b578f190756ae` (work/foundation/test/source-2591ef85-c96b-49dd-b897-23023ab097b5.json).
- CM: work/dev07-combined-20261101/combined-first.txt SHA256 `e56d9ec06d0a1471570a0aeee8732cabdd50c2feb8186475e5a582b5b565328b`; source6c5aec22-0219-4a8f-93cd-91fba43915af, manifest SHA256 `8631fa3352c9185321cc796f1f93dd564918fc0038609ace040376d7928b6f00`.

## Граница source reuse

Root независимо повторил сравнение actual E3/CM manifests с текущими модулями: work/dev07-final-20261101/source-reuse-audit.json. В нём раздельно отмечены присутствие старого файла и равенство SHA: test_combined_http.py отсутствовал в E3 и совпал только с CM; html_policy.py и normalizer_child.py изменились после E3, но совпали с CM. Различия bootstrap/editor/carrier не считаются unchanged proof. Это выбранный relevant closure, не заявление о равенстве всего приложения.

QA лично сверил actual старые manifests с текущими файлами, а не только имена тестов/краткие PASS. Relative app paths checks/media/embedded/saving/views, media-editor/embedded-editor/editor-bridge, page_versions/engine и editor_runtime/processing byte-identical относительно E3 и CM. test_embedded_http.py SHA `aa48966d0ddec239a1f03f3ae31aed1e3ddc65fae73d4cf8a0c4345294c637f9`, test_combined_http.py SHA `4672147cc3e1578e27a5bcfc7426597e6b3e8bccd320e194f7b7b05d688bfc36` совпали с соответствующими историческими источниками; test_combined_http.py отсутствовал в E3.

Но editor.mjs/carrier/bundle изменились. normalizer_child.py совпал с CM, не с E3 (между ними memo/failure правки). Child bootstrap diff с CM добавляет shared dispatch; прежние Page branch/frame64MiB/AS384MiB/CPU10/wall20 сохраняются. После CLOSE01 новые main routes/templates/middleware/runtime/ingress threads требуют normal witness — старый overlay PASS этого не доказывает. Эти различия исключают слепое перенесение старого browser/media/MAX PASS.

CF001–007 исполняются/оцениваются по [конечному контракту](dev07-final-checks.md). Итоговые actual source/config/QA bindings и independent reuse verdict будут в результатах, не в этой предварительной карте. Known allowed MAX refusal не откладывается как TEST09; новые обнаруженные дефекты получают конкретные ID. Полная приёмка/нагрузка/устройства/public/import остаются по исходному плану.
