# Приёмочные проверки — этап 7

**DEV-03 / D-320–322,31.10.2026:** исходные12AUTH сценариев исполнены против настоящего входа/CSRF идвух реальных IP,12PASS; финальные75unit,11FOUNDATION и96harness PASS. [Итог](../docs/dev03-auth.md), [ревью](../docs/dev03-review.md). Auth test budget120с — ресурс инструмента, не бизнес-лимит. Полные AC/editor/requests/production этим не закрыты.

**DEV-04 / D-318:** 20 model/integration проверок страниц/дерева/маршрутов прошли на PostgreSQL, общий unit-набор 41 PASS и регрессионные 11 FOUNDATION PASS; независимое ревью завершено. [Итог](../docs/dev04-models.md). Полные LIFE/URL HTTP/UI e2e ожидают свои DEV-модули, это не прохождение всех AC.

**Актуально D-316/D-317, 2026-10-30:** локальные DEV-02/DEV-28 выполнены; 11 FOUNDATION прошли против настоящей основы и независимого ревью, 21 unit/integration прошли. [Результат](../docs/dev02-dev28-progress.md). Полные AT-053/055/312, 140 AC и остальные бизнес-сценарии этим не закрыты. Для FOUNDATION использовать scripts/test-foundation.ps1: host guard до/после обязателен.

Ниже — исходные спецификации и история подготовки до реализации; прежние заявления «не исполнялись»/«код запрещён» относятся к моменту их записи и заменены для этой ограниченной очереди D-316/317.

**Текущий D-315:** локальные base-image исправления и независимое ревью завершены; [результаты](../docs/base-image-security-remediation.md). Каталог1056/40, приложение/11FOUNDATIONнеисполнены; vendorостатокнеобнулён. Только следующий явный допуск владельца разрешает ограниченную DEV-02/28.

**Обновление D-313:** TEST-Q008 принят; локальный вход через Nginx проверен с компьютера и из Docker, изоляция/ограничения подтверждены независимо. [Итог](../docs/local-foundation-proxy-check.md). Базовые образы имеют открытый остаток безопасности; код сайта запрещён. Старые упоминания запрета подготовки/неработающего HTTP относятся к истории до D-312/313.

**Текущее состояние 30.10.2026:** TEST-Q006 принят D-310. [Единый пакет TEST-Q007](../docs/local-foundation-package.md) согласован D-311; независимое ревью R064/065 закрыто. Установки и код не разрешены. Каталог: 1056 экземпляров / 40 файлов; матрица 17 text_only / 7 partial_http / 116 assertions_waiting_driver. Это частичное авторство, не прохождение AC. 85 самопроверок драйвера прошли. Следующие абзацы с TEST-Q006 «на согласовании» и прежними числами — история до D-310; действующие зависимости в tasks.md. Код и установки по-прежнему запрещены.

Разрешены D-302/D-303. Здесь только тестовый пакет и его запуск; приложения/его миграций/production-конфигурации нет. **Это частичный исполняемый набор, этап 7 ещё не завершён.**

## Заключительный аудит — на согласование

[TEST-EXIT-20261030-01 / TEST-Q006](../docs/stage7-exit-review.md) рекомендует ограниченный поэтапный порядок, а не полное завершение TEST-01/07. [20-rowregister](../docs/stage7-exit-register.csv) сохраняет исходные статусы и условия до соответствующего кода. R061–063 закрыты к предложению; до ответа действуют прежние зависимости/запрет кода. Приложение/bindings не требуются до его реализации только ради зелёногоe2e; изоляция и проверенные bindings обязательны перед настоящими прогонами.

## Состав

- 140 текстовых AT по 140 AC/63 REQ: [каталог](../docs/acceptance-cases.csv), [данные/варианты](../docs/acceptance-scenarios.md).
- 4 harness-проверки: целостность CSV/точные связи требований, карта маршрутов, запрет внешних адресов и переходов.
- По две browser-harness проверки Chromium/Firefox/WebKit на синтетическом HTML в памяти: запуск/assertions и инертный DOMParser при отключённом JavaScript. Вместе с4служебными —10самопроверок. Это проверка инструмента, не сайта и не восьми реальных семейств браузеров.
- 117 public-HTTP тестов: узкий smoke изолированного origin, 115 точных маршрутов, неизвестный путь404. Они покрывают лишь часть AT-001/AT-002/AT-501; сравнение текста/таблиц/альбомов/файлов и остальные критерии не заменяются HTTP200.
- 252 дополнительных публичных проверки:22canonical/115viewport+no-refresh/115no-cache. [Состав и ограничения](../docs/acceptance-public-contracts.md).
- 27 проверок прав/версий/статусов,74 проверок полей/телефона/повторов форм и33 проверки дерева/редактора/сессий/ручных операций содержат конкретные утверждения. [Транспорт локального адаптера](../docs/local-test-adapter.md) подготовлен, но конкретные bindings/fixture bridge ещё отсутствуют. Fake приложения нет; [контракт](../docs/acceptance-application-driver.md) не является API сайта или готовыми e2e.
- 83 самопроверки драйвера:ограничения транспорта/изоляции/control permits/UI/HTTP/multipart/browser-memory/restore session/JSfalse/пустой304/URLfaults и отдельные service-quota/content-storage caps. Текущий проход83passed, исторические80/78/74/71 не суммируются. Это оснастка, не AC сайта.
- 29 частичных [media-проверок](../docs/acceptance-media-contracts.md) и24 актуальных [logging/scanner-проверки](../docs/acceptance-logging-contracts.md) ждут конкретного приложения/привязок. [Ревью и результаты](../docs/acceptance-media-logs-review.md): пакет650экземпляров/11файлов; новые форматы/лимиты сайта не назначены.
- Добавлены26 [SEO-проверок](../docs/acceptance-seo-contracts.md) и22 [request lifecycle](../docs/acceptance-request-lifecycle.md). [Текущий отчёт](../docs/acceptance-seo-request-review.md): **698экземпляров/13файлов**, TEST-R020–023 независимо закрыты;4документных проверки повторены, AC сайта не пройдены.
- Последнее продолжение:20 [окон формы](../docs/acceptance-form-windows.md),18 [общих блоков](../docs/acceptance-shared-blocks.md), исправлены прежние74form assertions и добавлен pending guard. [Актуальный отчёт](../docs/acceptance-form-blocks-review.md): **737экземпляров/15файлов**, TEST-R024–028 независимо закрыты; конкретных bindings/приложения нет.
- Текущий набор:23 [backup](../docs/acceptance-backup-contracts.md) и12 [ночных сборок](../docs/acceptance-html-build-contracts.md). [Отчёт](../docs/acceptance-backup-html-review.md): **775экземпляров/17файлов**, R029–032 независимо закрыты. Это partial assertions до настоящих jobs/крипто-инструмента/стенда; реальный restore и Яндекс Диск не запускались.
- Последний набор:14 [editor-boundaries](../docs/acceptance-editor-boundaries.md),14 [migration](../docs/acceptance-migration-contracts.md) и1source-only на16HTML. **804экземпляра/20файлов**; R033–035 независимо закрыты, source-only прошёл. [Актуальный отчёт](../docs/acceptance-migration-editor-review.md). Утренние71самопроверка также прошли; это оснастка, не AC сайта.
- Актуальное продолжение:30 [editor-safety](../docs/acceptance-editor-safety.md) и4 [version-time](../docs/acceptance-version-time.md). **838экземпляров/22файла**, TEST-R036–038 независимо закрыты; новые бизнес-сценарии ещё не исполнены. [Отчёт](../docs/acceptance-editor-time-review.md).
- Последний поднабор:12 [auth-login](../docs/acceptance-auth-login.md),10 [unsaved-editor](../docs/acceptance-unsaved-editor.md) и2memory selfchecks. **862экземпляра/24файла**, TEST-R039 независимо закрыт,63driver-safety прошли. Входы/сохранения приложения пока не исполнялись. [Актуальный отчёт](../docs/acceptance-auth-memory-review.md).
- Актуальный поднабор:9 [log-quota](../docs/acceptance-log-quota.md),6 [background-jobs](../docs/acceptance-background-jobs.md),4 selfchecks. **881 экземпляр/26 файлов**, R040–045 независимо закрыты,67 driver-safety прошли. Квоты/worker faults пока не исполнялись. [Отчёт](../docs/acceptance-quota-jobs-review.md).
- Актуальное продолжение:10 [restore](../docs/acceptance-restore-contracts.md),2 [partial log deletion](../docs/acceptance-log-delete-failures.md),7selfchecks. **899экземпляров/28файлов**, R046–051 независимо закрыты,74driver-safety прошли. Старый logging уточнён25→24 без неутверждённого passwordcase. Restore/удаления не исполнялись. [Отчёт](../docs/acceptance-restore-log-review.md).
- Актуальный поднабор:8 [native/CSRF](../docs/acceptance-form-native.md),22 [cache](../docs/acceptance-form-cache.md),4selfchecks. **933 экземпляра/30 файлов**, R052–053 независимо закрыты,78driver-safety прошли. 30 новых сценариев сайта не исполнялись. [Отчёт](../docs/acceptance-form-native-cache-review.md). Режимы runner:form-native/form-cache, только изолированное приложение после readiness.
- Актуальный поднабор:7 [главная/источник цены](../docs/acceptance-home-source.md),4 [общие компоненты](../docs/acceptance-shared-component-restore.md). **944 экземпляра/32 файла**, TEST-R054 независимо закрыт.11 новых сценариев сайта не исполнялись; транспорт и прежние78selfchecks не менялись. [Отчёт](../docs/acceptance-home-blocks-review.md). Режимы runner:home-source/shared-component-restore.
- Актуальный поднабор:12 [URL/reserve/SEO](../docs/acceptance-url-reserve.md),16 [URLreuse](../docs/acceptance-url-reuse.md). **972 экземпляра/34 файла**, TEST-R055 независимо закрыт.28новых сценариев сайта не исполнялись; транспорт/прежние78selfchecks не менялись. [Отчёт](../docs/acceptance-url-reserve-review.md). Режимы runner:url-reserve/url-reuse.
- Актуальный поднабор:11 [URL-transition](../docs/acceptance-url-transition.md),2самопроверки. **985 экземпляров/35 файлов**, TEST-R056–058 независимо закрыты,80driver-safety прошли.11новых сценариев сайта не исполнялись. [Отчёт](../docs/acceptance-url-transition-review.md). Режим runner:url-transition.
- Актуальный поднабор:4 [servicequota](../docs/acceptance-service-quota.md),15 [versionstorage](../docs/acceptance-version-storage.md),3selfchecks. **1007 экземпляров/37 файлов**, TEST-R059 независимо закрыт,83driver-safety прошли.19новых сценариев сайта не исполнялись. [Отчёт](../docs/acceptance-service-version-review.md). Режимы runner:service-quota/version-storage.
- Актуальный поднабор:25 [price-editor](../docs/acceptance-price-editor.md),11 [price-home](../docs/acceptance-price-home.md). **1043 экземпляра/39 файлов**, TEST-R060 независимо закрыт.36новых сценариев сайта не исполнялись. Транспорт/прежние83selfchecks не менялись. [Отчёт](../docs/acceptance-prices-review.md). Режимы runner:price-editor/price-home.
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
.\run-container.ps1 -Mode editor-boundaries
.\run-container.ps1 -Mode editor-safety
.\run-container.ps1 -Mode version-time
.\run-container.ps1 -Mode auth-login
.\run-container.ps1 -Mode unsaved-editor
.\run-container.ps1 -Mode log-quota
.\run-container.ps1 -Mode background-jobs
.\run-container.ps1 -Mode restore-contracts
.\run-container.ps1 -Mode log-delete-failures
.\run-container.ps1 -Mode migration-contracts
.\run-container.ps1 -Mode migration-source
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

application-contracts исторически был однократно запущен:1отказ APPLICATION_DRIVER_NOT_IMPLEMENTED,26не запущены. Теперь модуль транспорта есть, но без target/bindings/bridge работа по-прежнему явно отказывает; повторные ожидаемые отказы не запускались. form-contracts/content-lifecycle собираются, но против приложения не исполнялись. Runner уже копирует фиксированные тестовые файлы и необязательные local-bindings.json/local-fixture-bridge.mjs/local-fixture-settings.json; последние ещё не создавались. Перед настоящими действиями обязательны изоляция и независимое ревью конкретных привязок. Это условие реального прогона после создания приложения, а не требование написать приложение до этапа8. Полнота авторства сценариев/ревью и текущий допуск оцениваются отдельно: [итоговый аудит на согласование](../docs/stage7-exit-review.md). НепройденныеAC не становятсяpass.

После отдельного разрешения на код и подготовки изолированного приложения установить ESTAKADA_TEST_BASE_URL на его HTTP-origin с явным портом. Разрешены только 127.0.0.1/localhost/::1/host.docker.internal. Для контейнера loopback указывает внутрь него; локальное приложение Windows доступно через host.docker.internal при явном тестовом порте. Public-режим с target использует bridge, HTTP-клиент не следует внешним Location. Внешний/живой сайт запрещён. По умолчанию никаких запросов к preview:8765 или production нет.

Результаты — test-results/acceptance/*-results.json вне Git. Контейнерные отчёты разделены по Mode; traces/video/screenshots отключены, чтобы не собирать лишние данные. Синтетический harness и HTTP-части отдельно от будущего полного приёмочного отчёта. Никакой green public-suite сам по себе не завершает TEST-01/TEST-07.

UX-08 принят по D-307. До полного набора нужны оставшийся UX-07 и конкретный ARC-10 по назначению, настоящие fixture/наблюдаемые SQL и outbox/контроль времени/fault barriers, реальные операции и отрицательные ветви остальных AT, затем независимое ревью всего исполняемого кода. Не добавлять скрытые production endpoints ради тестов. Реальные восемь браузеров/три версии проверяются позднее по [матрице](../docs/acceptance-browser-matrix.csv), Safari/iPhone отдельно.


DEV-06/D-326: локальная медиатека — scripts/test-media.ps1 после Start test через Windows PowerShell5.1. Это отдельный реальный Chromium/HTTP runner с host-only наблюдателем, не подмена29MEDIA assertions.114unit,11FOUNDATION и8MH-групп PASS; ownfixture очищается, runner не получает Docker socket/DB-пароли. Результат и границы — docs/dev06-http-implementation.md; тестовые PNG/JPEG/WebP генерируются tools/media_http_inputs.py только внутри согласованного Pillow image в ignored work/. Новых пакетов/автоустановок нет.
