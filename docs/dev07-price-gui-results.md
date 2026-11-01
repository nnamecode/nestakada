# DEV07-TP1 — визуальный прайс: результаты

2026-11-01, D-357. Основания: REQ-012/016, AC-DTL-005, AT-105/016, [контракт TP1-001–009](dev07-price-gui-checks.md). Реализация и проверка ограничены PriceV1 GUI; полный DEV-07 в работе, около98%, этап8 около20%.

**Итог:**6модельных групп,4HTTP/PG-теста и5Chromium/Nginx групп PASS. Независимое ревью ограниченного компонента положительное. Публичная выдача прайса и полный GUI MAX10000/resource run этим не закрываются. Первые отказы и диагностические запуски ниже сохранены отдельно.

## Что изменено

Отдельный компонент price-editor.mjs хранит полный PriceV1/null в памяти вкладки. Есть пустые, текстовые и денежные ячейки с признаком «от», подписи строк/колонок, добавление/удаление/перестановка и явное создание/удаление прайса. UUID сохраняются при переименовании и перестановке, cell binding следует columnUUID. Старые sparse-строки не дополняются без явной правки. Пределы500/32/10000 проверяются до структурной мутации без усечения.

Интерфейс показывает20строк за раз; Check/Save получает всю матрицу. Суммы остаются исходными строками, нормализацию выполняет прежний серверный producer, без float/округления в GUI. Текстовые ячейки используют textarea и сохраняют переносы. Ключ price в server values определяет право монтирования, включая price-only сотрудника. Основной editor получает completeRAM price, инвалидирует proof, проверяет согласованность ответа до принятия и очищает компонент при смене личности/destroy. Прежние current/draft/stage/replay/CSRF/grants сохраняются.

Модели, миграции, server price policy, квоты, ресурсы, зависимости, основные URLConf и Nginx не менялись. Для native проверок подготовлен отдельный QA-only URLConf/временный readonly конфиг; это не включение редактора в production.

## Фактические проверки

| Набор | Факт |
|---|---|
| Первый model | SyntaxError до запуска product: в QA matrix helper не было closing brace. Исходный model-first.txt сохранён, изменена только скобка |
| Исправленный model |5групп PASS, model-syntax-fixed.txt: реальный PriceModel,10k/500/32, stableIDs, sparse, raw invalid/decimal/text, detached copies и destroy. QA SHA b99cd41ced8ca9e47d627b316c839f4aed865373567fefc6a4a0d021021f24ce |
| Сборка |Существующие esbuild0.28.2/проверенные deps, network:none,1ГиБ/2CPU. Bundle989218B/SHA6d6fdb139b9bad1870bd0c8d07532a929e8d0c350f556f6818be5ad3a3118b8e,52inputs, без external imports |
| Первый framework |1тест/2.087с FAIL404 до handler: ошибочный основной URLConf без editor routes. framework-first.txt сохранён. Исправлены только QA ROOT_URLCONF/middleware, продуктовые маршруты не включались |
| Второй framework |2теста/8.091с,1ERROR TemplateDoesNotExist: price-only сохранение/normalization/revoke уже PASS, следующий GET достиг renderer, но QA не добавил каталог шаблонов. Отказ сохранён в framework-wiring-fixed.txt; добавлен прежний изолированный TEST_TEMPLATES pattern из test_media_http.py, базовые настройки не менялись |
| Framework после профиля |4PASS21.355с, framework-template-profile.txt. Genuine initial values/price-only grant/выбранные current-draft-stage/employee privacy, real child/PG Save/decimal normalization/late revoke, sparse+отказ по scalar bounds. Framework reader seam явно унаследован от test_check_http, это не socket proof; итоговый повтор после UUID ниже |
| Первый native preflight |EXACT_FROZEN_APP_PROFILE_REQUIRED до overlay/seed: guard ошибочно требовал candidate782f ещё от базового094333. native-first.txt сохранён, product/data не исполнялись. Coordinator теперь сверяет base/restore с python-runtime утверждённого lock, временный профиль с прежним candidate; остальные guards прежние |
| Первый native UI |fixed-runtime прошёл реальные Check/Save200, точные LF/PG/reload, но группа не засчитана: composite invariant PRICE_CSP_STORAGE_INLINE. Cleanup0live подтверждён, исходный отказ сохранён |
| Native diagnostic |fixed-csp-diagnostic сохранил тот же zero guard и добавил безопасные наблюдения. До screenshot CSP0/storage0/inline0; после CSP0/storage0/inline9. Playwright defaultcaret оставлял style-атрибуты полей. Это вмешательство инструмента снимка, не нарушение CSP продукта. Diagnostic остаётся FAIL и не считается приёмкой |
| Native после screenshot fix |fixed-caret: UI001 PASS с нулевыми before/after guards, затем UI003 FAIL PRICE_PAGE20. Причина product UUID описана ниже; это не финальный PASS |

После исправления screenshot UI001 действительно PASS (before/after CSP/storage/inline0). Следующая UI003 нашла product TP1-REV002: создание строк/колонок использовало crypto.randomUUID, недоступный на согласованном HTTP origin host.docker.internal. Отдельная readonly browser probe подтвердила secureContext:false/randomUUID:undefined/getRandomValues:function. Defaultfactory заменён на прежний криптографический getRandomValues/v4 helper; origin/CSP не ослаблялись. Добавлен model defaultfactory test без injected IDs, с actual RNG и отсутствующим randomUUID. Теперь6model PASS в model-uuid-fixed.txt, source price-editor SHAa033513ede0be944ae7adaad8da86a0a69a6bdc56b5086ebd5c18c0d1333cc44; новая сборка989562B/SHA5a9d19bd6bd178b0266eb04058a808156ae5a65583eee6d273823e6c063d06e2/52inputs. Прежние native failures сохранены.

### Итоговый снимок и реальные действия

226app файлов/run050c5459-b030-49e7-aba9-4605c94a9c79/manifestaa54ba3f39dbe33a9b3ba1d6f38967c9b0dc02589e112938e813540a78b8aa36: framework-uuid-fixed.txt **4PASS20.513с**, native-fixed-uuid/host-report.json **5/5PASS**. Модельные6групп отдельно прошли на том же product source; их нельзя суммировать с HTTP/native как уникальные AC.

TP1-UI-001: owner controls→настоящий Check/Save→actual PG→reload сохраняют empty/text/zero/from и LF/буквальный script-текст, остальные payload-поля прежние. TP1-UI-003: null→2колонки/21строка, page20 и скрытая последняя строка с LF проходят Save/reload; перестановка сохраняет UUID, удаление меняет только нужную структуру; удаление всего прайса до Save остаётся RAM-only. TP1-UI-002: price-only сотрудник сохраняет прайс, default-off/late revoke отказаны, protected поля прежние. TP1-UI-004: invalid amount/501codepoints доходят до сервера и остаются в UI без усечения, normalization review принят явно, максимальная сумма exact вPG; задержанный настоящий Check не затирает новую9.99, Save делает свежий Check и связывает новую квитанцию. TP1-UI-008: смена пользователя очищает DOM, прежний price не отправляется.

CSP/storage/inline/pageErrors/external requests/stderr0. Два PNG с синтетическими данными относятся к этому локальному компоненту. Применены прежние Playwright1.64.1/pinned47b510dd…/candidate782f…/base094333…; caps/сети/ingress не повышались. Own cleanup подтвердил users/pages/versions0 и единственный системный Route; постоянные identity/receipt/audit ledgers сохранены. Логи/синтетические секреты остаются в ignored work.

## Независимое ревью и пределы

Контракт проверен до кода. TP1-REV001/textinputLF и TP1-REV002/defaultUUID исправлены и подтверждены native. TP1-R01/R02/R03 проверяют whole matrix/epoch/atomicaccept, invalidate-before-mutation/caps и права/очистку. TP1-QA002 добавил настоящий поздний Check response; TP1-QA003 уточняет oracle согласно прежнему поведению Save→freshCheck при отсутствии proof. Ошибочные проверки не исправляются изменением принятого поведения продукта. Промежуточные226app файлов/run6472d22f…/manifest572c2e95… относятся к4PASS21.355с и найденной native UUID-ошибке; финальный cohort отличается ровно price-editor.mjs и производным bundle. [Запись независимого ревью](dev07-review.md).

Native small corpus и10k model — разные свидетельства. Новый полный10k GUI→Check→Save/resource run не выполнен, исторические серверные MAX не переименовываются в него. HTML-table GUI/заголовки/padding D-051/057/069, полная legacy матрица, остальные браузеры/все140AC и production остаются отдельно. Старый сайт/VPS не затронуты; push не выполнялся. Локальные свидетельства: work/dev07-price-20261101/, вне Git.

## Завершение

Независимый рецензент лично подтвердил6model/4HTTP-PG/5native и226host/frozen SHA без drift. Подтверждённых открытых блокеров этого ограниченного компонента нет; DEV07-TP1 выполнен в указанной области. После тестов manifest active:false, работающих foundation-test/own browser контейнеров0; тома сохранены. Final checks: из прежних223app файлов изменены ровно editor.mjs/editor.css/производный bundle, добавлены price-editor.mjs и2QA-файла. Модели, миграции0001–0005 shared_content, local writer profile, численные лимиты и main URLConf не менялись. Whitespace check с прежним исключением generated bundle прошёл. Новых зависимостей/ресурсов/установок Windows нет.

Точка продолжения — этап8/DEV-07, HTML-table GUI и отступы, затем оставшиеся legacy/browser/lifecycle/resource матрицы. Этап9 не начат. Свидетельства before.json/model-uuid-fixed.txt/build-uuid-fixed.txt/cohort-uuid-fixed.json/framework-uuid-fixed.txt/native-fixed-uuid/host-report.json/source-delta.json/stop-final.txt/final-checks.json сохранены в указанной локальной папке; первоначальные отказы и диагностические snapshots не удалялись.
