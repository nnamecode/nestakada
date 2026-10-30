# Приёмочные проверки — этап 7

Разрешены D-302/D-303. Здесь только тестовый пакет и его запуск; приложения/его миграций/production-конфигурации нет. **Это частичный исполняемый набор, этап 7 ещё не завершён.**

## Состав

- 140 текстовых AT по 140 AC/63 REQ: [каталог](../docs/acceptance-cases.csv), [данные/варианты](../docs/acceptance-scenarios.md).
- 4 harness-проверки: целостность CSV/точные связи требований, карта маршрутов, запрет внешних адресов и переходов.
- По две browser-harness проверки Chromium/Firefox/WebKit на синтетическом HTML в памяти: запуск/assertions и инертный DOMParser при отключённом JavaScript. Вместе с4служебными —10самопроверок. Это проверка инструмента, не сайта и не восьми реальных семейств браузеров.
- 117 public-HTTP тестов: узкий smoke изолированного origin, 115 точных маршрутов, неизвестный путь404. Они покрывают лишь часть AT-001/AT-002/AT-501; сравнение текста/таблиц/альбомов/файлов и остальные критерии не заменяются HTTP200.
- 252 дополнительных публичных проверки:22canonical/115viewport+no-refresh/115no-cache. [Состав и ограничения](../docs/acceptance-public-contracts.md).
- 27 проверок прав/версий/статусов,74 проверок полей/телефона/повторов форм и33 проверки дерева/редактора/сессий/ручных операций содержат конкретные утверждения. [Транспорт локального адаптера](../docs/local-test-adapter.md) подготовлен, но конкретные bindings/fixture bridge ещё отсутствуют. Fake приложения нет; [контракт](../docs/acceptance-application-driver.md) не является API сайта или готовыми e2e.
- 61 самопроверка драйвера: ограничения/stdio/подготовка UI/control, multipart/File API, ресурсный бюджет/raw-redaction/pending и разделение допусков fallback/backup/html-build. Они и4документные/изоляционные проверки прошли в текущем проходе;6проверок трёх браузеров — отдельный прежний результат. Это оснастка, не AC сайта.
- 29 частичных [media-проверок](../docs/acceptance-media-contracts.md) и25 [logging/scanner-проверок](../docs/acceptance-logging-contracts.md) ждут конкретного приложения/привязок. [Ревью и результаты](../docs/acceptance-media-logs-review.md): пакет650экземпляров/11файлов; новые форматы/лимиты сайта не назначены.
- Добавлены26 [SEO-проверок](../docs/acceptance-seo-contracts.md) и22 [request lifecycle](../docs/acceptance-request-lifecycle.md). [Текущий отчёт](../docs/acceptance-seo-request-review.md): **698экземпляров/13файлов**, TEST-R020–023 независимо закрыты;4документных проверки повторены, AC сайта не пройдены.
- Последнее продолжение:20 [окон формы](../docs/acceptance-form-windows.md),18 [общих блоков](../docs/acceptance-shared-blocks.md), исправлены прежние74form assertions и добавлен pending guard. [Актуальный отчёт](../docs/acceptance-form-blocks-review.md): **737экземпляров/15файлов**, TEST-R024–028 независимо закрыты; конкретных bindings/приложения нет.
- Текущий набор:23 [backup](../docs/acceptance-backup-contracts.md) и12 [ночных сборок](../docs/acceptance-html-build-contracts.md). [Отчёт](../docs/acceptance-backup-html-review.md): **775экземпляров/17файлов**, R029–032 независимо закрыты. Это partial assertions до настоящих jobs/крипто-инструмента/стенда; реальный restore и Яндекс Диск не запускались.
- 26 частичных [fallback-проверок](../docs/acceptance-fallback-contracts.md) ждут конкретного инфраструктурного адаптера и окончательного ARC-10. Отдельный тестовый control-канал не реализует production-контроллер.
- [Статус всех AT](../docs/acceptance-automation-status.csv) и [текущие числа/доказательства](../docs/acceptance-test07-continuation.md) разделяют текст, частичный HTTP и утверждения, ожидающие конкретного драйвера. Ни один полный AC не объявлен закрытым.

Узкий smoke ENV-HTTP-001 не является допуском приложения. Будущий положительный прогон обязан иметь отдельное доказательство изолированного приложения/контрольной fixture, согласованную схему и результаты сценариев. Статический прототип может пройти часть HTTP-проверок и всё равно не считается приложением/полным AC.

## Версии и запуск

@playwright/test 1.64.1 и транзитивные зависимости закреплены в pnpm-lock.yaml с integrity. Пакетный менеджер — согласованно использованный pnpm 11.25.0 из runtime; глобальная установка не нужна. Контейнер — официальный mcr.microsoft.com/playwright:v1.64.1-noble, зафиксированный digest sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea. По фактическому запуску Linux/Node 24.22.1.

Из PowerShell в этой папке:

```powershell
.\run-container.ps1 -Mode list
.\run-container.ps1 -Mode harness
.\run-container.ps1 -Mode documents
.\run-container.ps1 -Mode driver-safety
.\run-container.ps1 -Mode public-http
.\run-container.ps1 -Mode public-contracts
.\run-container.ps1 -Mode application-contracts
.\run-container.ps1 -Mode form-contracts
.\run-container.ps1 -Mode form-windows
.\run-container.ps1 -Mode shared-blocks
.\run-container.ps1 -Mode backup-contracts
.\run-container.ps1 -Mode html-build
.\run-container.ps1 -Mode content-lifecycle
.\run-container.ps1 -Mode fallback-contracts
.\run-container.ps1 -Mode media-contracts
.\run-container.ps1 -Mode logging-contracts
.\run-container.ps1 -Mode request-lifecycle
.\run-container.ps1 -Mode seo-contracts
```

Docker Desktop должен работать. Подготовка зависимостей читает официальный npm registry для metadata/проверок supply-chain, использует frozen lock и ignore-scripts, не выключает проверки pnpm. Последующий harness/list/первоначальный public без target запускается отдельным контейнером с network=none. Это две временные команды, не фоновый сервис. Подготовка не запускает тесты сайта с доступом в сеть.

Все крупные локальные данные — T:\nestakada\work\pnpm-store, work\acceptance-container, test-results\acceptance, существующий Docker storage на T:. Проектные документы и bundled pnpm монтируются readonly; в контейнер не передаются Docker socket, профиль пользователя, пароли/токены и файлы приложения. Образ не меняется, privileged/дополнительные capabilities/production-порты не используются. Скрипт не меняет PATH/WSL/реестр/автоматизации.

На другой машине указать ESTAKADA_PNPM_PACKAGE на каталог pnpm 11.25.0 и подготовить те же зависимости по lock. Нет автоматической установки произвольной версии pnpm. Первичная локальная команда на этой машине:

```powershell
& 'C:\Users\nname\.cache\codex-runtimes\codex-primary-runtime\dependencies\bin\fallback\pnpm.cmd' install --store-dir 'T:\nestakada\work\pnpm-store' --ignore-scripts --frozen-lockfile
```

## Отсутствие приложения и будущая конфигурация

Сейчас ESTAKADA_TEST_BASE_URL не задан: public-suite намеренно даёт один отказ TEST_TARGET_UNCONFIGURED и 116 «не выполнено». Это ожидаемый первоначальный красный результат, не дефект будущего сайта и не 116 пройденных тестов. Автоматического запуска сервера/подмены Django макетом нет.

Режим public-contracts включает и public-http: при отсутствующем target — тот же красный guard и невыполненные новые проверки, без ложного зелёного агрегата из одних skip. Публичные metadata/cache/canonical-пробы требуют подтверждённой обычной опубликованной fixture; они не относятся к скрытому/аварийному/private режиму.

application-contracts исторически был однократно запущен:1отказ APPLICATION_DRIVER_NOT_IMPLEMENTED,26не запущены. Теперь модуль транспорта есть, но без target/bindings/bridge работа по-прежнему явно отказывает; повторные ожидаемые отказы не запускались. form-contracts/content-lifecycle собираются, но против приложения не исполнялись. Runner уже копирует фиксированные тестовые файлы и необязательные local-bindings.json/local-fixture-bridge.mjs/local-fixture-settings.json; последние ещё не создавались. Перед настоящими действиями обязательны изоляция и независимое ревью конкретных привязок. Без этого этап7 не завершён.

После отдельного разрешения на код и подготовки изолированного приложения установить ESTAKADA_TEST_BASE_URL на его HTTP-origin с явным портом. Разрешены только 127.0.0.1/localhost/::1/host.docker.internal. Для контейнера loopback указывает внутрь него; локальное приложение Windows доступно через host.docker.internal при явном тестовом порте. Public-режим с target использует bridge, HTTP-клиент не следует внешним Location. Внешний/живой сайт запрещён. По умолчанию никаких запросов к preview:8765 или production нет.

Результаты — test-results/acceptance/*-results.json вне Git. Контейнерные отчёты разделены по Mode; traces/video/screenshots отключены, чтобы не собирать лишние данные. Синтетический harness и HTTP-части отдельно от будущего полного приёмочного отчёта. Никакой green public-suite сам по себе не завершает TEST-01/TEST-07.

UX-08 принят по D-307. До полного набора нужны оставшийся UX-07 и конкретный ARC-10 по назначению, настоящие fixture/наблюдаемые SQL и outbox/контроль времени/fault barriers, реальные операции и отрицательные ветви остальных AT, затем независимое ревью всего исполняемого кода. Не добавлять скрытые production endpoints ради тестов. Реальные восемь браузеров/три версии проверяются позднее по [матрице](../docs/acceptance-browser-matrix.csv), Safari/iPhone отдельно.
