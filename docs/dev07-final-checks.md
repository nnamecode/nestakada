# DEV07-CLOSE-04 — конечный компонентный набор

Итог DEV07-CLOSE-04, 2026-11-02: Конечный набор выполнен с source-bound свидетельствами и независимым итоговым ревью; [результат](dev07-final-results.md). CF001 prefix+readonly tail, CF002–004 отдельный normal run, CF005 unit, CF006/007 finaltail с четырьмя явно reused groups. Это7логическихсценариев, не7browsertests и не единый непрерывный runtime. Остаток проекта сохраняет completion-audit§3; ниже исходные сценарии и история уточнений.

2026-11-01. До нового QA-кода и запусков. Основания D-368, dev07-completion-audit.md §CLOSE-04, действующие REQ/AC/implementation-plan и [карта доказательств](dev07-final-evidence-map.md). Это конечная проверка DEV-07, не все140AC/TEST08/09/10 и не production.

## Один источник и неизменные пределы

Один final app source/config manifest для unit и native; обычные estakada.settings.local_http/estakada.urls/Nginx, app782/base094/проверенный media worker. Без QA URLConf/settings/compose overlay, новых пакетов, схемы, томов или увеличения caps. Новая unit-сценарная программа входит в final source; helper/host/probe имеют отдельный закрытый SHA freeze. Любое продуктовое исправление — только по actual finding, с отдельным diff/review и новым явно связанным final source; старые отчёты не перезаписывать.

Исполнители: tools/editor_final_http_fixture.py и tools/test-editor-final-http.mjs — helper/host; tools/editor_final_http_probe.mjs — native; app/page_editor/test_final_media_http.py — один framework case. scripts/test-editor.ps1 получает узкую suite final-media на существующей unit БД. Новые имена намеренные; прежние frozen инструменты не переписываются.

## Данные и честное сохранение состояния

Главная test БД до seed должна не содержать чужих активных principals/Page/Asset; системный route и существующие shared rows/receipts/identity/audit фиксируются baseline. Отдельные собственные Page core/FMT-A/FMT-B/mediaA/mediaB/MAX исключают случайное выбывание нужного источника из Page10; три отдельных READY Asset sharedLogo/privateA/privateB с настоящими worker bytes. Пользователи — nesadmin и два сотрудника с реальными grants; не подменять роли/сессии.

Shared Apply меняет current, поэтому **фикстура сохраняется целиком**: собственные users/Page/shared current/history/draft/stage/refs/READY files. Никаких raw current/generation/Budget reset, purge/TTL/force UNKNOWN или удаления referenced Asset. Перед seed/записями используются настоящие quota guards. Изменения derived cache отражаются отдельно от protected policy/debt и actual usage. Не обещать users/assets0 после этого набора.

Helper имеет только закрытые CLI-действия seed/resume/observe/verifyproof/retain, не HTTP endpoint. Resume добавлен 2026-11-02 только для сохранённого run56e66714: точный readonly checkpoint/проверка старых паролей и файлов, signed private intent до единственного оставшегося commit, постоянный operation UUID и проверка результата без повторной публикации. Подробности — work/dev07-final-20261101/media-resume-plan.md; восстановленный shared baseline явно обозначен checkpoint, а не первоначальным сохранённым hash. Guard: scope test, local_http, main URLConf, фактическая test БД/роль, own runUUID/IDs и frozen source. Observe/verifyproof/retain не меняют бизнес-строки; seed использует реальные domain/upload services. Credentials и ownership state сохраняются в существующем ignored private-каталоге work/foundation/test/private с прежними файловыми guards; в work/dev07-final-20261101 идёт redacted retention report без паролей/permit/CSRF. Не печатать private state в stdout/логи/Git.

При PASS и FAIL сохранить exact ownership/retention manifest и фактические refs/current/provenance/PG/FS facts. При FAIL — сохранить исходники, evidence и состояние, остановить стенд; затем конкретная диагностика/исправление/resume-план по finding. Автоматический reseed/reset не разрешён. Это synthetic retention в локальной тестовой среде, не новая продуктовая команда очистки/восстановления.

## Конечные сценарии

| ID | Действие | Обязательный результат |
|---|---|---|
| CF07-001 | Normal owner/assigned employee Check→явный Save→reload; price-only прайс и simple table; owner draft отдельно и выбранное восстановление с отдельным Save | Один receipt/версия на commit; canonical содержимое и UUID сохраняются; draft не публикуется. Несколько прямых owner/employee/foreign/session/CSRF запретов без запрещённых изменений. При employee Save защищённые поля неизменны; owner restore по D-261 возвращает полный content Snapshot (включая H1/SEO), сохраняя актуальные URL/tree/publication/grants/Stable и отдельные общие блоки. Exact source payload hash — положительный oracle owner restore. Перепроверить normal связку, не повторять120s NH body-timeout и неизменённую полную TP1/2 матрицу. |
| CF07-002 | Для каждого Header/Footer: Check/Apply A→Apply B→подготовка A→отдельный Check/Apply; затем отдельный held stage и явная отмена | Current/immutable history/буквальный contact/source provenance/refs/receipt верны, другой блок/Page не меняется. Restore не публикует до Apply. Cancel released/pins/ACK без новой версии. Только product handlers; current и referenced files остаются retained, quota/debt не сбрасываются. |
| CF07-003 | Корпус A: Check→явная безопасная нормализация при необходимости→Check→Save→history→выбрать источник→отдельный Save | Сначала independent semantic facts подтверждают caption/Unicode/marks/head/body/scope/rowspan/colspan/grid/padding, не слепое принятие первого200 как oracle. Сохранённый canonical HTML/семантика, история и restored source совпадают; protected поля/URL прежние. Exact opaque fallback допустим, новые merge/split команды не нужны. |
| CF07-004 | Тот же полный roundtrip для корпуса B | Сохраняются scope groups, цвета/marks и другой padding, без silent normalization/drop структуры. Исторический source не мутирует; выбранный restore создаёт новую версию, не перезаписывает старую. |
| CF07-005 | Один framework/2PG Save-wins cleanup race на отдельной unit БД | READY A без usages, настоящий prepare_cleanup даёт confirmation. Save вызывает настоящий engine.finish, затем test-only Event внутри TX. Второй PG confirm_cleanup действительно блокируется на Save PID, что видит pg_blocking_pids, а не только Event. После commit один Save, точный MEDIA_ASSET_RETAINED_OR_NOT_READY, A READY/3file SHA intact, настоящие current/ordinary refs. Bounded wait/finally release/connections close. Это не два socket-запроса; результат не мокируется. |
| CF07-006 | Native selected owner draft с реальными main_image A и embedded A; новый picker выбор/подтверждение, новый permit B; до switch настоящий Check, затем logout/login employee→явный Check | Initial media/embedded непусты, настоящие picker/issue ответы и projected Check с issued data-es-media-intent подтверждают ненулевые records/URLs/permits. После switch editor POST0, private draft URL403 при действующем Page grant; DOM/retained img/input/script handles очищены/отключены, source audit подтверждает destroy/clear, domain/refs/pins/receipts/files прежние. Не подменять Map/bundle, не заявлять прямые heap counts/zeroization. |
| CF07-007 | Точный представитель CM001: retained S/T и candidate C/D, каждый rich1MiB UTF8/200000codepoints/20000элементов/depth32; owner current GUI HTML обоих полей→Check через Nginx | Разные source/candidate hashes, independent stock-parser facts, реальное тело/ответ/подписанный CheckReceipt bound к actor/gen/Page/source/input. GUI подтверждает Check; domain не меняется. Наблюдаемые elapsed/app/browser peaks/caps/OOM относятся только к corpus. MAX Save и43MB CM002 price сюда не добавляются. Отказ разрешённого ввода — конкретный blocker, лимиты автоматически не повышать. |

CF07-005 исполняется одним framework case; остальные6групп — один native cohort. Все7 относятся к одному final source/config, но не объявляются семью native-тестами. Прайс/простая таблица в CF001 — финальный smoke, прежние детальные vector proofs связаны картой source reuse.

## Два конечных FMT-корпуса

Перед фиксацией QA рецензент сверяет допустимость обоих по принятому parser/policy; недопустимый новый ввод не объявлять разрешённым бизнес-правилом. Canonical после явной нормализации сравнивается byte/hash roundtrip, а initial semantic facts проверяются независимым parser/feature oracle, чтобы не потерять структуру уже на первом Check.

```html
<table data-es-cellpad="4"><caption>Цена 😀 <strong>до/после</strong></caption><thead><tr><th scope="col" colspan="2">Работы</th></tr></thead><tbody><tr><th scope="row" rowspan="2">Кузов</th><td><em>Осмотр</em></td></tr><tr><td>Ремонт панели</td></tr></tbody></table>
```

```html
<table data-es-cellpad="32" data-es-mt="8"><caption><u>Матрица Б</u> 🛠</caption><thead><tr><th scope="colgroup" colspan="2">Проверка</th></tr></thead><tbody><tr><th scope="rowgroup" rowspan="2">Группа</th><td><strong>А</strong><br>Б</td></tr><tr><td><span data-es-fg="#112233">Цена 0.01</span></td></tr></tbody></table>
```

Двухколоночная геометрия: thead colspan2; tbody первый th занимает колонку0 на2строки, td занимают колонку1; нет cross-group rowspan. Корпуса не обещают новый visual merge UX. Nested/billion-span/aggregate отрицательные и математические векторы переиспользуются отдельно.

## Ресурсы, артефакты, завершение

Визуальная граница этого набора: пока продуктовые UI/CSS/JS не менялись, переиспользуются6просмотренных RP07 PNG с exact source/asset binding; CF дополняет их фактическими DOM/semantic/history/ref оракулами. Новые CF PNG не заявляются, текущий host не получает RW screenshot mount. Если actual finding потребует продуктового UI-исправления, до его приёмки добавить конкретный безопасный снимок/экспорт и пересмотреть эту границу. Отсутствие нового PNG не выдаётся за проверку public renderer или полного table-layout MAX.

MAX source строится в helper реальным Snapshot/domain service; helper отдаёт только small facts/hashes S/T/C/D. Probe генерирует C/D по тому же известному алгоритму и сверяет с независимыми Python facts — не пересылает4MiB HTML через small observer pipe. Native private tokens/JSON остаются в памяти/приватном файле, redacted reports bounded. Только синтетические безопасные PNG; приватный canary очищается перед screenshot.

Итог: CF001–007 actual results с source/QA/config hashes, feature/receipt/ref evidence, reuse/gap map, independent review и redacted retention manifest; снимки просмотрены, контейнеры остановлены с сохранением volumes. Отсутствующий обязательный witness не превращать в PASS. Затем можно оценить DEV-07 как компонент; TEST08/09/10, DEV08/09/10/15/20/29, public renderer/import/gallery214/original URL/реальные браузеры и release отдельно. Старый сайт/VPS не трогать.


## Уточнение фактического продолжения D-369

2026-11-02: исходный native-resume-media остановлен на неверном QA сравнении employee-protected полей после owner restore. Readonly свидетельство подтвердило D-261 и точное совпадение всего Snapshot с источником. Исправляется только QA. CF001 закрывается связкой неизменённого source-bound prefix из сохранённого FAIL и нового readonly/UI tail без повторных записей; пять оставшихся групп выполняются в continue-restore на том же app source/config/fixture. В итоговом отчёте указываются оба runtime cohort, не заявляются шесть заново пройденных native групп или один непрерывный процесс. Прежние FAIL/credentials/retention не переписываются. Конкретные проверки — work/dev07-final-20261101/restore-continuation-checks.md.
