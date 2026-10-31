# DEV-07 — визуальный редактор, сохранение и локальный Nginx

2026-10-31, D-334. DEV-07 остаётся **В работе**. Оценка: этап 8 около 20%, DEV-07 около 70%; это ориентир, а не доля прошедших AC. Старый сайт и VPS не использовались. Исходные изменения сохранены в ignored `work/dev07-ui-20261031/before/` до начала этой части работы.

Итог текущей области: **16/16 настоящих Chromium/UI/HTTP групп через Nginx PASS**, три header-only socket проверки PASS. Временные пользователи/страницы/версии очищены, системный route и постоянные ledgers сохранены. Это локальный допуск current-only editor/save, а не завершение всего DEV-07 или разрешение подключения основных маршрутов/production.

[Независимое ревью](dev07-review.md) завершено: открытых подтверждённых блокеров в этой ограниченной области нет. Рецензент отдельно сверил итоговые отчёты, все 42 файла freeze и соответствие 37 app-файлов immutable snapshot; расхождений нет. Оценка70% не заменяет готовность оставшихся функций и AC.

## Реализованная область

Закрытый current-only save DTO связывает operation ID с фактическим запросом и check proof. Новая миграция `page_versions/0002_editor_request_fingerprint.py` хранит fingerprint в постоянном OperationReceipt. Проверенный Snapshot/TextPricePatch сохраняется прежним атомарным DEV-05 engine; перед обеими фазами commit повторно проверяются настоящая сессия, generation и полномочия. Exact replay использует прежнее намерение и возвращает прежний результат, включая случай очистки обычной версии; legacy receipt без editor fingerprint не становится wildcard.

Добавлены закрытая страница редактора, актуальное состояние разрешённых полей и whitelist статических assets. Реальный transport bridge проверяет личность через session endpoint, затем Page state. Обрыв ответа сохраняет прежние body/operation ID в RAM для явного повтора. Ответ 200 с неверным контрактом не выдаётся за успех. При смене пользователя прежний ввод и доступные UI-копии очищаются; при смене generation того же сотрудника ввод сохраняется для явного повторного входа и проверки. Физическое обнуление памяти браузера этим не обещается.

Собран фактический Tiptap adapter с закрытой схемой/serializer и оформлением через CSSOM под CSP без unsafe-inline/eval. Неизвестный HTML остаётся в textarea до серверной проверки и принятия. Clipboard/drop перехватываются до стандартного HTML parser. Таблицы сейчас сохраняются точным approved opaque фрагментом с HTML-режимом; полноценный визуальный редактор таблиц не заявлен. Восстановленный неизменённый PM doc и undo возвращают точный server-approved canonical HTML; изменённый doc проходит собственный serializer. Этот cache не принимает raw HTML и блокируется при ошибке оформления.

## Фактические проверки

Свидетельства находятся в ignored `work/dev07-ui-20261031/`. Образ приложения: `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`.

| Набор | Результат | Свидетельство |
|---|---|---|
| Pure policy/runtime | 72 PASS, 10.482 с | pure-current-first.txt |
| Настоящие PG/session/CSRF/child/atomic save через Django Client | 16 PASS, 50.795 с | save-http-first.txt |
| Объединённая регрессия после изменений engine/model | 258 PASS, 222.748 с | all-tests-first.txt |
| Адресная регрессия настоящего Django LimitedStream после транспортного исправления | 11 PASS, 0.819 с | django-stream-fix.txt |
| Изолированный настоящий Chromium: базовый adapter/controller/CSP | 8 PASS | visual-first.txt, visual-report.json |
| Реальный набор текста, computed style вложенного emoji и undo с canonical cache | 4 PASS в Chromium и 3 PASS настоящего серверного normalizer | format-cache-probe.mjs, format-cache-result.json, format-cache-check.py |
| Настоящий Chromium/UI/HTTP через Nginx на последней сборке | 16 групп PASS | browser-seventh/host-report.json |
| Настоящий Nginx/socket, anonymous header-only | 401 / 413 / 400 PASS | browser-seventh/socket-report.json |

Это отдельные прогоны. 258 тестов выполнены до адресного LimitedStream исправления; они не объявляются единым запуском последнего состояния. Проверенный bundle: SHA256 `d5c383c17d13b52b6613f96ffd38fba6aa0f909a9e36e9cf2d7d3506eb9b6b53`, 893878 байт, 49 build inputs. Сборка использует ранее согласованные версии и esbuild binary, без скачивания новых пакетов.

Последующая узкая правка сообщений имеет отдельное red/green свидетельство `controller-css-before-result.json` / `controller-css-result.json`: на старой сборке не проходят четыре сообщения; на новой проходят специальное CSS-fault сообщение и три приоритетных session/permission/base alias. В обеих пробах модель с размером 18 сохранена, старое сохранение блокируется, явный исправный check даёт один save. Callbacks в этой пробе синтетические: это настоящий browser/controller, **не HTTP/SQL доказательство**. Новый bundle SHA256 `6b0febe5594215ad56d9c412c5ceaa0c4f92ab6582f3507595a6761cfa343a14`, 894806 байт, 49 inputs; остальной adapter и серверная policy неизменны.

## Локальные сетевые пробы и обнаруженные расхождения

Ниже сохранена хронология промежуточных отказов и их диагностики. Актуальный успешный итог седьмого запуска приведён в начале документа и в разделе точки продолжения.

Только отдельный probe overlay: `127.0.0.1:8767`, enforced CSP и exact editor routes через настоящий Nginx. Основные URL/settings приложения не подключены к этому экспериментальному редактору. Приложение сохраняет 768 МиБ/1 CPU; ingress 128 МиБ/0.25 CPU. Browser runner — ранее разрешённый отдельный инструмент, без DB credentials и Docker socket.

Header-only проверки: анонимный запрос с Content-Length 64 МиБ получает ранний 401 без передачи тела, превышение на один байт — 413, конфликт Transfer-Encoding/Content-Length — 400. Это не передача разрешённого максимального тела авторизованным пользователем.

Первый запуск выявил существующую системную route `/manage/` в пустой тестовой БД: fixture исправлена на сохранение строго проверенного системного ряда, без удаления чужих данных. Второй выявил настоящий Django LimitedStream поверх socket: reader теперь разворачивает только точный тип и согласованные bound readers, сохраняя ограничения чтения. Третий выявил различие вложенности mark/span при неизменённом PM roundtrip: исправлено approved cache с проверкой реальной правки и undo. Четвёртый подтвердил actual UI check/save/reload и точный исходный roundtrip, но остановился на `ADAPTER_CACHE_MASKED_REAL_EDIT`. Отдельная диагностика `focus-sequence-result.json` доказала потерю фокуса из-за locator.press на нефокусируемом p: BODY active, DOM/dirty/export неизменны. Последовательность actual surface.focus/page.keyboard сохраняет фокус и действительно меняет текст; QA исправлена с дополнительными focus/selection/dirty assertions, без ослабления ожиданий.

Пятый запуск на immutable app snapshot `11617eda-51b7-4aa1-a6be-24d9b448561b` (source manifest SHA256 `91da1a428b3e1f26bead9d6695f0f7d9468c42f9e22b735f1f2331e81ee41bec`) прошёл 10 групп: UI save/reload, strict original/edited/undo roundtrip и оформление, opaque table, ранний paste/drop guard, известный отказ и новое намерение, четыре malformed-200/ручной exact retry, настоящий commit с потерей ответа и same-user reauth/replay без второй версии, employee save/foreign403. Затем EH007 остановился на `INLINE_STYLE_OR_COLGROUP` после desktop/mobile screenshot; проверяется воздействие screenshot hideCaret самого Playwright. `browser-fifth/host-report.json` фиксирует результат и успешную очистку. Полный набор из 16 групп пока **не прошёл**.

Диагностика `screenshot-style-result.json` подтвердила побочное действие оснастки: default screenshot оставляет пять пустых style-атрибутов, `caret:'initial'` сохраняет ноль и отсутствие style mutations/CSP/page errors во всех четырёх точках сравнения. QA исправлена только параметрами снимка и дополнительными строгими проверками до/после; DOM не очищается ради PASS. Шестой запуск подтвердил 11 групп, включая EH007/mobile/zero-inline. EH008 затем выявил отсутствие специального сообщения при искусственном CSS fault: модель и dirty-состояние сохранены, но показывается общий отказ. Исправляется только выбор сообщения с приоритетом явных session/permission/base кодов; полный повтор до адресной проверки исправления не допускается.

После каждого завершённого браузерного запуска удалены только временные собственные пользователи/страницы/версии. Системный route и постоянные identity/operation/audit ledgers сохранены. Пароли/сессии/proof/база/оригиналы не входят в Git.

## Остаток и точка продолжения

Седьмой итоговый запуск прошёл все 16 групп, включая EH008 fault/recovery, EH009 approved HTML-only save, EH010 actual different-user reauth/scrub, EH011 actual password reset/generation2/RAM/explicit reauth/check/save, EH012 different-user direct-save/no-old-POST. Immutable app snapshot `56e65eb6-035e-4e73-8d7c-5016f1acb0c7`, source manifest SHA256 `20a77e48305fcf779cbd646b788062179b8c47942d67c4bc2bb50e5f3e7bc42d`; QA probe `e32a7fd6973c79956e3288d82f69121c0507a6a6632e096d86ef3bd5f39551ad`; fixture `7e9dcaf8e19f12a64d479cfbd873f47f5ef61ee86acb0c8d6a4618bdd72f4ff3`. Дополнительный freeze 42 исходников/проверок: `work/dev07-ui-20261031/final-source-manifest.json`, SHA256 `7f1d201483a501b1097f4af98a9226aef678d76a60f6fa40174086634890d43c`.

Cleanup: users/pages/versions=0, routes=1 (системный ряд), version identities=132, media identities=28, operation receipts=71, append-only audit=221; постоянные записи не удалялись. Браузерный контейнер остановлен до fixture cleanup.

По окончании локальный test стенд остановлен штатным wrapper; named volumes и закрытые файлы сохранены. Никаких контейнеров editor probe не оставлено запущенными. Запуск этого overlay не является настройкой старого сайта или VPS.

Далее в DEV-07 остаются draft/restore-stage, protected media/reset оформления, общие Header/Footer и их квоты, полноценные элементы больших прайсов/таблиц, авторизованный максимум transport/RSS/slow-abort/параллельные отказы. Основные маршруты не подключать до оставшихся ворот. Native advisory residual из `dev07-package-security.md` сохраняется; этот результат не означает отсутствие уязвимостей или production admission. DEV-08 и выпуск не начаты.
