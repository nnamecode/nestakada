# DEV-07 — независимое ревью, работа продолжается

## Продолжение D-334: current-only save, adapter и Nginx

**Итог независимого ревью 2026-10-31:** подтверждённых открытых блокеров в ограниченной области current-only editor/check/save, визуального адаптера и временного локального Nginx overlay не осталось. Рецензент лично проверил итоговые 16/16 Chromium/UI/HTTP групп и header-only 401/413/400, успешный cleanup и сохранность системного route/постоянных ledgers. Независимая сверка 42 файлов final-source-manifest и 37 app-файлов с immutable snapshot дала ноль расхождений; последняя reviewed сборка совпала с фактически проверенной. Стенд остановлен, manifest active=false. Этот локальный cohort закрыт; **DEV-07 остаётся В работе, около70%**, основной маршрут и production не допущены. Остаются draft/restore-stage, protected media/reset, shared Header/Footer/квоты, GUI больших прайсов/таблиц, полный transport/resource/slow-abort/concurrency и остальные браузеры. Native advisory residual сохраняется.

Рецензент отдельно прочитал изменения engine/model/migration, закрытый save DTO, повторные права и session-проверки, UI/controller/bridge, test fixture и host coordinator. Исполнитель не подменял независимое ревью собственных исправлений. Фактические результаты и границы — [dev07-ui-save-implementation.md](dev07-ui-save-implementation.md).

- Устранён session TOCTOU: активная AuthSession проверяется под auth lock в обеих фазах commit, включая logout/revoke во время настоящего preflight.
- UI-замечания по invalidation proof до render failure, раннему перехвату paste/drop, HTML-only fallback и очистке actor-owned state исправлены. Ответы save проверяются закрытым контрактом; неизвестный исход не превращается в новый operation ID после позднего отказа. Смена generation того же actor отличается от смены пользователя.
- Fixture допускает только фактически существующий системный route с точной структурой. Очистка ограничена собственными live IDs, сохраняет системный ряд и постоянные ledgers; браузерный writer останавливается до cleanup. Отдельный DB mutex в runner не заявлен: прогоны сериализует координатор.
- Исправление LimitedStream ограничено точным классом и согласованными bound readers зафиксированной Django 5.2.18; неизвестный transport остаётся fail-closed. Фактические 11 runtime tests прочитаны; это не полный slow/abort admission.
- Однобазовый canonical cache использует immutable PM doc.eq, очищается вместе с actor/view и блокируется при style fault. Рецензент прочитал адресные доказательства настоящего изменения текста, computed styles вложенного emoji, undo и повторного server check. Это не обход проверки изменённого содержимого.
- UI-EDITOR-REV005 отозван после проверки фактического freeze SHA: прежний фрагмент не соответствовал текущему исходнику. ID не переиспользуется.

Четвёртый Nginx/browser запуск прошёл actual UI save/reload и исходный exact canonical roundtrip, затем остановился на новой проверке набора текста. Узкая диагностика двух последовательностей на одном fixed synthetic source показала: locator.press на нефокусируемом p переводит фокус в BODY и не меняет DOM/dirty/export; surface.focus + page.keyboard вводит текст и undo возвращает exact approved. До исправления тестового взаимодействия полный неизменённый прогон не повторяется. Полный набор браузерных групп и итог DEV-07 ещё не приняты.

Пятый запуск подтвердил 10 браузерных групп, включая actual edit/undo/opaque/style, paste/drop, четыре malformed-200, потерю ответа после настоящего commit с reauth/exact replay и employee save. Он остановился на EH007 после screenshot. Рецензент прочитал pinned Playwright coreBundle hideCaret и actual сравнение двух fresh synthetic contexts: default screenshot оставляет пять `style=""`, `caret:'initial'` сохраняет ноль до/после desktop/viewport/mobile, без style mutations/CSP/page errors. Разрешена только поправка screenshot options с дополнительными строгими pre/intermediate/post invariants; product DOM не очищается ради PASS, пустые style не игнорируются. Все ранние свидетельства сохранены. Cleanup пятого прогона подтверждён: live users/pages/versions ноль, системный route и постоянные ledgers сохранены.

Шестой запуск прошёл 11 групп, затем EH008 выявил несоответствие сообщения при реальном CSS fault. Рецензент подтвердил code path: специальный текст показывался только при Save, adapterFailure и command catch давали generic. Исправлен только выбор сообщения: закрытые alias `EDITOR_SESSION_ENDED`, `EDITOR_FIELDS_FORBIDDEN`, `EDITOR_BASE_CONFLICT` имеют приоритет над latched view error; lookup проверяет Object.hasOwn. Прочитаны источник и actual browser/controller red/green: четыре отсутствовавших сообщения исправлены, модель/старый proof block/явное восстановление сохранены. Callback scope синтетический, не HTTP/SQL. При неизменённой строгой QA e32a7fd6…551ad допущен седьмой локальный Nginx/browser прогон на свежем immutable snapshot с bundle 6b0febe5…43a14. Итог всего DEV-07 этим не выдан.

Примечание координатора: один doc patch не нашёл указанный заголовок и ничего не изменил. Перед отдельным корректирующим patch прочитан фактический заголовок; эквивалентный неподтверждённый поиск не повторялся.

## Исторические срезы D-330–333

2026-10-31. Следующие записи отражают состояние своих ранних frozen cohort; более поздняя реализация и проверка D-334 описаны выше. Рецензент `/root/base_image_security_review` не редактирует проверяемые исходники. Это промежуточное ревью ограниченных частей, не приёмка DEV-07 и не разрешение production.

| ID | Замечание / результат | Статус и основание |
|---|---|---|
| DEV07-REV-001 | Vendor ammonia4.1.4 имеет три actual affected advisory; одного npm/PyPI scan недостаточно | Остаток открыт. Допущены изолированные restricted-profile пробы; до product integration нужны whole-input rejection, один закрытый nh3 call, source guard и PoC regressions. dev07-package-security.md |
| DEV07-REV-002 | Стандартный Tiptap inline style несовместим с действующей CSP при reload | Открыто: реальный PKG-JS006 FAIL. CSP не ослаблять, необходим semantic adapter и actual roundtrip |
| DEV07-REV-003 | Cross-field anchor target нельзя угадывать после reload; literal cross-page URL не равен работающему resolver | Исправлено на уровне технического контракта: explicit target attrs roundtrip, cross-page resolver остаётся отдельным публичным gate. Код ещё проверять |
| DEV07-REV-004 | Stock TableMap может выделить огромную виртуальную сетку из малого HTML | Исправлено на уровне проекта: sparse precheck до TableMap, aggregate20000 UI capability, opaque exact approved canonical+HTML-mode fallback без усечения/нового content/save cap. Конкретный код ещё проверять |
| DEV07-REV-005 | Client embedded_images/layout сверх HTML-бюджета допускает необоснованный transport maximum | DTO исправлен: metadata в richHTML1МиБ; producer выводит Snapshot fields из проверенного markup/server context. Реализация pending |
| DEV07-REV-006 | Runtime guard: socket interrupt, nonblocking slot, fixed child protocol, kill/reap/resource limits | На неподключённой helper-границе блокеров не найдено;20 actual unit/socket/process PASS. HTTP auth/CSRF/framing и полный pipeline не закрыты |
| PRICE-REV-001 | Лимит1000 измерялся до CRLF normalization и отвергал допустимый canonical текст | Исправлено: type/UTF8/controls→newline normalization→codepoint count. Reviewer повторно прочитал код;9 corrected tests PASS0.208с, work/dev07-20261031/price-policy-crlf-fix.txt |
| PRODUCER-REV-001 | HTML5 parser может отбросить запрещённые атрибуты закрывающего тега до проверки дерева | Исправлено: ранний отказ attributes-in-end-tag и EndTag с attrs; actual regression до nh3 PASS, рецензент подтвердил |
| PRODUCER-REV-002 | CSS reset внутри унаследованного semantic mark мог незаметно сохранить неверное выделение | Silent loss устранён: reset normal/400/none/baseline получает ControlledUnsupported после полной проверки исходника; actual regressions PASS. Сама semantic reset capability остаётся не реализована |
| PRODUCER-REV-003 | Предположение, что URL2048/title300 являются новыми лимитами | Отозвано после точной проверки analytics-content-detail.md, TECH01 таблица полей, строка40: оба предела уже приняты D-301. Caps сохранены; ID не переиспользуется |
| PRODUCER-REV-004 | Незавершённый currentToken на EOF может исчезнуть до проверки дерева и дать ложный успешный пустой результат | Исправлено: lexical EOF errors отвергаются до tree/cleaner, actual href/script EOF regressions PASS. Reviewer сверил html5lib source и тесты |

Других блокеров в чистом price policy рецензент не нашёл. Это не проверка прав сотрудника, доменного commit, реального UI или HTTP. Синтетическое измерение43469413байт/1.141с/cgroup246403072байта прочитано с сохранением scope: только JSON/pipe, без productPolicyValidated/httpAdmission.

Ограниченный pure producer:23 actual tests PASS4.403с; QA SHA256 `57626f73f30fd35ff421fd73d3111822d35ec4e0887eadf5e3c7cffbe017dcd4`. Рецензент лично прочитал исходник/протокол/регрессии и разрешил дальнейшие изолированные интеграционные пробы: открытых подтверждённых блокеров в этом bounded cohort нет. Native residual не устранён; table/protected/relative-context/reset функции ещё недоступны.

Рецензент также прочитал обе resource probes и actual evidence, включая совместные1МиБ/200000codepoints/20000nodes/depth32 в каждом HTML с большим прайсом: PASS8.688с/cgroup343117824байта без увеличения пределов. Текущий cohort можно фиксировать завершённым в его ограниченной области. Это не универсальный максимум времени и не полный DTO/Django/HTTP допуск. Frozen source manifest15файлов — `work/dev07-20261031/pure-cohort-manifest.json`, SHA256 `633cc88a984eed8f920e33914984275de9ad5d9c2e1e1958009497d715921f87`, productAdmission=false.

До итогового ревью DEV-07 остаются завершение producer/semantic adapter, actual end-to-end разрешённые и опасные операции, исходные и повторные права/base, bounded полный pipeline и общие блоки/квоты. Удаление строк PostgreSQL не считается доказанным уменьшением физического размера отношений. Absolute same-site URL требует real origin/private-target context при интеграции; одного root-relative `/manage` отказа недостаточно для объявления полного URL контекста готовым.

## Продолжение D-332/D-333: pure таблицы/URL и изолированный HTTP check

Независимый рецензент проверил AVL/sparse geometry, реальный URLContext и QA с самостоятельным dense oracle.64actual tests PASS6.054с. Caption/scope/nested/giant spans и единый remaining budget подтверждены; GUI/ProseMirror faithful mapping ещё не проверены. Private-target проверка теперь использует actual origin/public route context в child, основной HTTP маршрут ещё не подключён.

| ID | Замечание | Исправление и фактическая регрессия |
|---|---|---|
| CHECK-HTTP-REV-001 | CSRF мог разобрать multipart до Page admission/slot | Exact-path process_view JSON/session/Page admission перед настоящим CsrfViewMiddleware; owner/foreign multipart exploding-read и JSON positive PASS |
| CHECK-HTTP-REV-002 | Check proof не был связан с реальной semantic policy | actual policy constants→context→child reported policy→receipt/current verifier; old-proof после смены policy409, unchanged positive PASS |
| CHECK-HTTP-REV-003 | Fields-denial child branch обходил bounded audit | note_denial для403; отдельный actual audit test1.946с PASS: counter1/2/3 и одна первая запись, без input canary/изменения content |
| CHECK-HTTP-REV-004 | Позднее прекращение сессии возвращало Page403 вместо401 | Отдельный session recheck failure→EDITOR_SESSION_ENDED401; actual session invalidation после real child PASS |

Рецензент лично прочитал19framework tests40.675с PASS и отдельный audit1PASS1.946с. Положительные пробы используют настоящие PG/session/CSRF/child; Client body-reader seam и отдельные именованные fault/order/race seams не являются socket proof. Дополнительно после принятого trim однострочных полей прочитаны8actual child tests5.343с PASS; новых замечаний нет. Это отдельные прогоны, а не20/92 combined latest-source запуск.

Вердикт: текущие pure и isolated readonly-check области можно фиксировать завершёнными; подтверждённых открытых блокеров в этой области нет. Global URLs/settings/Nginx/Save/GUI/shared и полная resource/transport admission остаются отдельно. [Результат и точка продолжения](dev07-check-implementation.md).
