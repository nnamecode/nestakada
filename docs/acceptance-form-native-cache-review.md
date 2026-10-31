# Форма без JavaScript, CSRF и кэш: этап7

2026-10-30. Основания D-301–303/305/308 и прямое поручение владельца. Прежние изменения сохранены; только тесты/оснастка/документы. Старый сайт/VPS/БД/файлы/ОС/настройки не трогали; код нового сайта не писали.

## Подготовлено

| Поднабор | Экземпляров | Частичная область |
|---|---:|---|
| form-native.spec.js |8 | home/contacts: реальный браузер с JSfalse, native submit, GET без receipt/DBsession, missing/corruptCSRF, CSRF раньше acceptedreceipt, no-store отказа, положительная отправка после отказа |
| form-cache.spec.js |22 | optional304 или200 в том же действующем контексте; смена context/CSRF/consent/интервала/cookie/data/template/policy; IMS-only200, private/no-cache/VaryCookie, явная отправка именно пригодного представления |
| DRIVER-SAFE-028–031 |4 новых | строгий JSboolean, inlineJS отключён/nativePOST работает на синтетическом HTML, узкий conditionalGET304, реальный пустой HTTP304 без добавления DOMwrapper |

Транспорт: параметр openApplicationDriver({javaScriptEnabled:false}) применяется к фактическим actor contexts; response parser отдельный. Добавлена read-only проекция Vary. Outcome not-modified допускается только для HTTP GET с If-None-Match и единственным статусом304; не заменяет бизнес-маркер accepted200. Нет новых эндпоинтов продукта/контроллера, фиктивного приложения или реальных интеграций.

[Native контракты](acceptance-form-native.md), [cache контракты](acceptance-form-cache.md), [транспорт](local-test-adapter.md). 30 сценариев приложения **не исполнялись**: отсутствуют приложение, fixture bridge и bindings. Новые проверки не являются пройденными AC.

## Независимое ревью

Автор cache — form_cache; native/оснастки/интеграции — координатор. form_native_cache_review проверял read-only, не исправлял результат.

| ID | Приоритет | Замечание | Исправление/результат |
|---|---|---|---|
| TEST-R052 | P1 | Парсер пустого304 добавлял HTMLwrapper и делал ветку304 непроходимой | responseReportBody сохраняет пустойraw304; SAFE031 проверяет настоящий локальный HTTP304 и негативный nonemptyraw; независимо закрыто |
| TEST-R053 | P2 | Тест требовал отдельное hidden-поле версии согласия, хотя PR01 допускает версию внутри signedintent | Дополнительная структура полей не требуется; actual-db Consent version связана с той же принятой request; независимо закрыто |

После исправлений существенных замечаний в целевой партии нет. Это не полное TEST-07 и не проверка ещё отсутствующих concretebindings/framework/условных ответов настоящего приложения.

## Фактические проверки

- **78 driver-safety passed**, skipped/unexpected/flaky=0,6,576с. JSON `test-results/acceptance/driver-form-native-cache-results.json`, журнал `work/acceptance-driver-form-native-cache-final.txt`. Рецензент отдельно сверил JSON. Предыдущие77/74 не суммируются с этим пересекающимся набором.
- **933 tests in 30 files**, контейнерное перечисление exit0, `work/acceptance-stage7-list-form-native-cache.txt`. Это количество собранных экземпляров, не пройденных проверок сайта.
- Синтаксис JS/PowerShell и git diff --check без ошибок. После синхронизации **4 документные/изоляционные проверки passed**, skipped/unexpected/flaky=0,2,985с; `test-results/acceptance/documents-form-native-cache-results.json`, `work/acceptance-documents-form-native-cache.txt`.

Матрица140AT: **33 text_only /7 partial_http /100 assertions_waiting_driver**. AT401/402 впервые получили частичные assertions, AT404 дополнен. 140AC/63REQ/115MAP/RTE не перенумерованы; ни один полный AC не объявлен пройденным.

## Остаток

Конкретные поля/селекторы/PRG/CSRFmiddleware и cookie-привязки требуют независимой проверки с приложением. Полные границы времени/HEAD/ETag non-disclosure, отображение ошибок и ротация защиты в открытом DOM, исключение токенов из всего резерва, реальные cookies/privacy/LEGAL и аналитика не закрыты этой партией. Все source/clock/evidence декларации требуют подтверждения реальным подключением. Итоговая приёмка и восемь семейств браузеров отдельно.

Этап7 продолжается; полные UX-07/физический ARC-10/TEST-07 открыты. Этап8 и production требуют отдельного разрешения владельца.
