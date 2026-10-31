# DEV-07 — таблицы, URL-контекст и проверка содержимого через HTTP

2026-10-31. Продолжение D-332, возобновление отдельной QA-правки D-333. DEV-07 остаётся **В работе**. Завершены ограниченные области pure table/URL policy и изолированного current-only check. Это не весь редактор и не разрешение подключения к основной конфигурации.

## Реализовано

- `tables.py`: проверка геометрии по реальным строкам/ячейкам с AVL intervals/gap augmentation/expiry. Память не выделяется по объявленным rowspan/colspan; большие числа разбираются без изменения глобального integer limit. Caption/thead/tbody/scope и вложенное содержимое сохраняются. Совокупный GUI budget20000 — derived capability, не лимит сохраняемой таблицы; крупные/вложенные получают opaque facts. Сам визуальный adapter ещё отсутствует.
- `URLContext`: доверенные actual public Page route/origin/private roots. Проверяются relative/root/same-origin absolute пути, выход за корень и закрытые маршруты; внешние literal URL не загружаются. Неоднозначный IDNA mapping пока получает явный ControlledUnsupported, без угадывания.
- `input_policy.py`/`normalizer_child.py`: закрытый PageInput, строгие типы/duplicate keys/UTF8, права полей из серверного context, base/generation, HTML/price/plain normalization. Две HTML области расходуют единый table GUI budget. Реальная semantic policy связана с контекстом и результатом. Однострочные H1/title проходят NFC и trim до canonical codepoint limit; description сохраняет крайние пробелы и нормализует переносы.
- `checks.py`/`views.py`/`http_urls.py`: только POST `/manage/pages/<uuid>/edit/check/`, без content commit. Короткий context snapshot, затем nonblocking slot/body reader/статический child без удержания SQL domain locks; после него повторные session/context/permission/base проверки. Возвращается подписанная stateless checkReceipt, привязанная к actor/generation/Page/base/permissions/semantic policy/raw+normalised fingerprints. Нового TTL нет. Это proof проверки, не OperationReceipt успешного сохранения.
- `EditorAdmissionMiddleware`: exact-path JSON/session/Page admission до настоящего CSRF process_view, чтобы multipart не начал разбор до проверки прав. CSRF не отключён. Позднее прекращение сессии даёт401; Page/field denial403 идёт в прежний bounded audit.

## Фактические проверки

Образ кандидата прежний `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`. Pure контейнеры без сети, HTTP/PG test container только во внутренней test DB сети,768МиБ/1CPU. Старый сайт/VPS не использованы; ресурсы не повышались.

| Набор | Фактический результат | Свидетельство в ignored work/dev07-cont-20261031/ |
|---|---|---|
| Runtime/price/HTML + новые tables/URL |64tests PASS6.054с, включая12 новых методов и160 seeded small dense-oracle fixtures | pure-b-first.txt |
| Read-only check через Django Client, настоящие PG/session/CSRF/static child |19tests PASS40.675с | check-http-first.txt |
| Отдельно добавленная по D-333 audit regression |1test PASS1.946с: три403 увеличивают actual session counter1/2/3 при одной первой SEC_PERMISSION_DENIED записи; content неизменен | check-http-audit.txt |
| После адресного добавления trim H1/title — закрытый DTO и настоящий static child |8tests PASS5.343с | input-policy-first.txt |

Это **отдельные прогоны**, не combined latest-source full suite. HTTP19+1 использовали immutable app snapshot run `e79cca02-fbc2-4ebc-9777-c2e855266a51`, audit-only test overlay SHA256 `566aeba640daa0f78a55bd5e663f596baece0bb30ebb0959eba02d36378999b0`. Последующее изменение касается trim однострочных plain fields, проверено адресными8 child tests; parent HTTP code не менялся.

HTTP Client не имеет настоящего WSGI socket: в этих тестах заменён **только body reader seam**, положительные normalized results не подменены. Проверены real CSRF/middleware chain, неподходящий multipart до read, реальные права/сессии/child, подписанные claims, конфликты при смене current/grants, поздний session expiry401, отсутствие content/draft/history/refs/commit receipt изменений. Во время reader/child отдельное PG соединение получало domain advisory locks; parent не держал atomic block.

Итоговые25source hashes и provenance отдельных прогонов: `work/dev07-cont-20261031/cohort-manifest.json`, SHA256 `678a6af404e5b7ce5ce2a181ce8c430f62501f5ea1f8d9053814934cb2a46fcb`. testEnvironmentActive=false/productAdmission=false. Git diff-check PASS; push не выполнялся.

Сценарии и границы: [H07](dev07-http-checks.md), [N07/B07](dev07-normalizer-checks.md). Независимый рецензент прочитал source, оба QA набора и actual logs; четыре HTTP замечания закрыты. [Ревью](dev07-review.md).

## Что не подключено и остаётся

Основные `estakada.urls`, middleware settings и Nginx body/config **не изменены**; тестовые URL/order задавались исключительно test settings. Образ кандидата не заменил main app. Локальный стенд остановлен, manifest.active=false, тома/секреты/результаты сохранены.

Нужны реальные Nginx/socket early denial/framing/slow/abort/parallel slot и полный Django64МиБ peak, source/config admission guards; semantic Tiptap/CSP adapter и UI принятия normalization; сохранение/owner draft/restore stage; protected media; inherited style resets; общие Header/Footer и фактические квоты; публичный renderer. Ragged table rich facts доказывают bounded geometry, но не отсутствие автоматического заполнения ячеек ProseMirror — до GUI требуется faithful mapping либо opaque fallback с полным source.

Три conditional native vendor advisory остаются в dev07-package-security.md. Полные AC и матрица140AC не объявляются пройденными. Production и переход к DEV-08 не разрешены этим результатом.
