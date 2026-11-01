# DEV07-CLOSE-03 — контроль мобильной ширины

Результат2026-11-01: CLOSE-03 выполнен, verify5групп/45измерений PASS и независимое ревью положительное; [итог](dev07-responsive-results.md). Ниже сохранён контракт до кода и запусков.

2026-11-01. До кода и браузерных запусков. Основания D-367, CLOSE-03, UX-08, dev07-completion-audit.md и прежние TP2/SID PNG406px при viewport390. Это ограниченное исправление layout, не новая дизайн-итерация и не полный TEST-10.

## Протокол

Проверенный обычный local_http/Nginx, без QA URLConf/settings/overlay. Неизменная tools/editor_normal_http_fixture.py создаёт только свои synthetic users/pages/READY media и удаляет только свои transient данные, сохраняя Shared baseline и permanent ledger. Новые tools/editor_responsive_http_probe.mjs и tools/test-editor-responsive-http.mjs используют прежние pinned browser/runtime/source/config/caps и freeze всех3inputs. Новых пакетов/контейнерных ролей/ресурсов нет.

Ширины320/360/390/768/1280 — конечные контрольные размеры, не все устройства. Малый320 согласуется с ранее проверенными эскизами admin-design-options.md; остальные — технические свидетели phone/tablet/desktop. После fonts и двух rAF измеряются document/body scrollWidth/clientWidth/innerWidth, реальные rects и видимость/доступность controls.

Режим diag собирает реальный дефект и возвращает DIAGNOSTIC_ONLY/OBSERVED, не PASS. Bounded top8 offenders содержат только tag/class/nth-path, числовые rects/widths/ancestor и computed min/maxWidth/flexWrap/gap/whiteSpace/overflow. Не экспортировать text/value/HTML/href/CSRF/password. Внутреннее переполнение ячеек внутри разрешённого local overflow:auto отмечается отдельно от document overflow.

Если реальный DOM подтверждает global owner nav как источник, выполнить причинный A/B/A на том же экране: измерение baseline → временный constructed CSSStyleSheet main>nav{flex-wrap:wrap} → удалить stylesheet и повторить baseline. Не менять сохранённый product CSS, не применять body/root overflow:hidden или маскировку ширины. Для другого источника сначала объяснить actual evidence и конкретное ограниченное исправление; не перебирать CSS вслепую.

После диагностики — независимое ревью конкретного CSS diff, новый immutable source cohort и verify. В verify временная коррекция запрещена; требуется document/root≤viewport+1px, видимые и достижимые кнопки/поля/ссылки, обычный вертикальный scroll. Широкие таблицы должны прокручиваться внутри собственного контейнера и давать доступ к последней ячейке. Не удалять элементы ради метрики и не прятать реальный контент.

## Конечные группы

Для price/simple table сначала измеряется фактическое внутреннее переполнение. Если таблица шире контейнера — прокрутить к последней ячейке и проверить доступность. Если она помещается — последняя ячейка должна быть доступна без прокрутки; не раздувать содержимое ради искусственного scroll, особенно на desktop.

| ID | Экран/действие | Обязательное свидетельство |
|---|---|---|
| RP07-001 | Owner dashboard и assigned employee comparison; owner-only Shared Header/Footer GET как контроль затронутого общего base | Global nav rects/scroll/child bounds и все ссылки доступны на5ширинах; employee без owner nav остаётся рабочим. Shared reads не сохраняют блоки и не меняют бюджет/историю. |
| RP07-002 | Основной редактор owner/assigned employee, current source | Toolbar/источник/редактор/Check/Save/ввод доступны; root не шире viewport. Ввод RAM не публикуется. Права и защищённые поля не подменяются. |
| RP07-003 | Price-only employee создаёт в RAM прайс2колонки/3строки | Поля/кнопки доступны; широкая таблица прокручивается локально, последняя ячейка достижима. Нет rich-text прав, скрытой публикации или изменения объёма данных ради ширины. |
| RP07-004 | Owner вставляет простую таблицу и использует существующий padding control в RAM | Table controls и ячейки доступны; локальная прокрутка сохраняет содержимое. Document не распирается, данных на сервере не меняем ради layout. |
| RP07-005 | Настоящий terminal/other-actor источник по действующему SID workflow | Терминальный экран сообщает недоступность без candidate, ссылки/кнопки/сообщение помещаются. Изменения состояния выполняются только прежними product handlers на собственном fixture; PNG после безопасного очищения canary. |

Снимки: editor390 baseline/candidate в diag при доказанном nav; verify editor390/price320/terminal390 и desktop1280 для визуального контроля. Просмотреть реальные PNG, не объявлять screenshots прежних прогонов новой адаптивностью. Исключения/оставшиеся дефекты указывать по actual evidence, не выдавать незавершённые группы за PASS.

Критерий CLOSE-03: указан actual DOM/CSS корень, минимальный проверенный diff, verify5групп на5ширинах с сохранёнными controls/local table scroll, просмотр снимков и независимое ревью результатов; исходники/данные сохранены, стенд остановлен. CLOSE-04, полная browser/version матрица и публичная адаптивность отдельно. Старый сайт/VPS не трогать.
