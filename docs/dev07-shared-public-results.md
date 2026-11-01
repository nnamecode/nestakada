# DEV07-SH-PUB — результаты локальной проверки

2026-11-01, D-356. Область: [контракт](dev07-shared-public-contract.md) и [PUB07-001–009](dev07-shared-public-checks.md). Общий DEV-07 остаётся в работе, около98%; этап8 около20%.

## Реализованная область

Добавлены публичный renderer текущих Header/Footer, типизированная граница доверенного меню, функции HTML/media/static response и собственные CSS/JS меню. Перед ответом200/304 проверяются канонический HTML, контрольные суммы файлов, реальные current-ссылки READY media и свежий согласованный контекст обоих блоков и host/nav. Повтор ограничен двумя попытками и допускается только при наблюдённом изменении контекста. Ошибка без изменения данных не скрывается старым304 или пустым200.

Обычный HTML/media требует revalidation; закрытые ошибки no-store. Private source/preview/history-only/draft-only/stage-only не становятся публичными. Anonymous чтение не создаёт сессий, квитанций, заданий, reader pins или файлов. Меню доступно без JavaScript, собственный скрипт поддерживает клавиатуру, Escape и фокус при строгой self CSP.

Доверенные ссылки меню и host stamp передаёт будущий host. QA-only URLConf использует реальные модели Page/PRIMARYRoute и синтетические страницы; это не production правило выбора пунктов меню. Основные URLConf, Nginx, модели/миграции, профиль записи, квоты, зависимости и ресурсы не менялись. Общий helper канонической сериализации вынесен из policy без изменения принимаемой грамматики.

## Фактические запуски

Первый запуск новых тестов:3теста/49.007с,1ERROR. Тест перестановки пунктов пытался занять позицию0, уже занятую другой fixture Page. Исправлен только тест: реальные собственные позиции10/20 меняются под блокировкой, чужие позиции отдельно сверяются. Первый отказ сохранён в public-first.txt.

Исправленный запуск:10PASS168.854с, public-qa-fixed.txt. Проверены реальные HTTP/PG/FS, конкурентные изменения через две PG connections,2×1МиБ блоков с большим меню и экранируемыми URL, пробельный nav, условные запросы, повреждение без ложного304, текущая доступность media и совместимое восстановление телефона. Это10методов, а не число отдельных assertions.

Исправленный frozen source:223файла, run87a93668-9ae1-4e78-8271-771c399b9cfb, manifest SHA256 87d57a04d503cdb468b101462d0aadb7f4a122058cecf5669bc0161b9fcffeaf. Из прежних216app файлов изменён только shared_content/policy.py;7новых файлов содержат5product и2QA. Хост и frozen SHA сверены без drift.

Общая shared регрессия на том же223-file source:108найдено/104выполнено PASS734.771с,4heavy calibration skip. Новые10 входят в104, не прибавляются как уникальные. Независимый рецензент лично подтвердил полный протокол и повторно сверил223host/frozen SHA без drift.

Первый native Chromium/Nginx:3группы PASS, PUB-UI-004 FAIL PUBLIC_FRESH_NAV_LABEL_MISSING. HTTP200/новыйETag после реального rename уже прошли; неверный oracle сравнивал rendered innerText с исходным mixedcase при CSS text-transform:uppercase. PUB-QA002 исправляет только probe: отдельно exact textContent и exact отображаемый uppercase. Href/ETag/private media/HEAD/readonly assertions сохранены; независимое ревью исправления положительное. Первый отказ и исходные3SHA сохранены; cleanup подтвердил0live и отсутствие ownRoot.

Исправленный native:4/4PASS, native-fixed-navcase.txt и native-fixed-navcase/host-report.json, тот же223-file app source. PUB-UI-001:actual DOM/READY media/точные ссылки/304/нет anonymous writes. PUB-UI-002:320/390/768/1024/1440 без overflow, клавиатура/Escape/focus/безJS, CSP violations0. PUB-UI-003:реальный owner Check/Apply меняет буквальный телефон и ETag в anonymous DOM, другой блок сохраняется. PUB-UI-004:реальный rename отражён в исходном/отображаемом тексте и ETag; private-source/preview denied даже If-None-Match:*; HEAD без body; лишних writes нет. PageErrors/externalDenied/stderr0. Cleanup closed:true, users/pages/versions/assets/ownroutes0, ownRootAbsent:true. Два анонимных PNG визуально проверены: это компонентный synthetic host с тестовыми растровыми placeholders, не принятый дизайн всей страницы.

Браузер использует согласованные Playwright1.64.1 и pinned image47b510dd… через прежний локальный Nginx. App/DB/ingress/worker и browser caps не повышались. Новые3tools frozen в http-freeze.json; после PUB-QA002 только probeSHA сталd8d7920e0aaeb1d40af4a197eabc1a354b81a472192441dbe470386b6234ff77. Исходная фиксация сохранена отдельно. Синтетические данные удалены ограниченным teardown; постоянные квитанции/идентичности не выдаются за удалённые.

## Замечания и границы

PUB-REV001: бюджет результата учитывает фактическое увеличение байтов при подстановке экранированных URL, включая повтор одного Asset. PUB-REV002: допустимый пробельный nav заполняется через проверенный AST. PUB-QA001: seed с запрещёнными шаблонными маркерами заменён допустимым; отдельные реальные Check400/неизменность сохранены. Независимый рецензент подтвердил исправления и фактические10PASS.

Полноценные публичные Page/маршрутизация/выбор production меню и согласованность всего body относятся к DEV-08/29. Last-Modified/IMS не выдумывается без достоверного timestamp всего host; весь AT-050 этим не закрыт. Импорт бренда, SVG/шрифтов, полное визуальное соответствие страниц, другие браузеры и прочие остатки редактора не объявляются выполненными. Ресурсный профиль writer и прежние отдельные heavy калибровки не переименовываются в новые испытания.

## Итог и продолжение

Независимый рецензент лично подтвердил actual104shared/4native и точные SHA: открытых блокеров проверенного локального компонента нет. [Запись ревью](dev07-review.md). Задача DEV07-SH-PUB выполнена в этой области; полный DEV-07 остаётся в работе. Далее оставшиеся table/price/legacy/browser/stage lifecycle матрицы редактора, затем зависимые задачи этапа8 по основному плану. Этап9 не начат.

После тестов стенд остановлен с сохранением томов: manifest active:false, работающих foundation-test и собственных browser контейнеров0. Final checks подтвердили223host/frozen SHA без drift, неизменность всех прежних app путей кроме вынесенного helper policy.py, отсутствие изменений миграций0001–0005. Локальный writer profile остаётся прежним exact LC: enabledTrue/schemaa4190d7e…/FSid16471834453763965976, без новой калибровки или повышения лимитов. Whitespace diff check прошёл с прежним исключением сгенерированного editor.bundle.js.

Локальные свидетельства: work/dev07-public-20261101/{before-index.json,cohort-first.json,public-first.txt,cohort-qa-fixed.json,public-qa-fixed.txt,shared-regression.txt,http-freeze-first.json,http-freeze.json,native-first/host-report.json,native-fixed-navcase/host-report.json,stop-final.txt,final-checks.json}. Старый сайт, VPS и production не затронуты; push не выполнялся. Логи/синтетическиеprivatefixtures остаются вне Git.
