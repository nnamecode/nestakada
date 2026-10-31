# DEV-06 — локальная медиатека и подтверждаемая очистка

Основание D-326, D-324/325, IMG-001..013 и UI-S021/022. План записан до HTTP-кода. Worker/модели уже проверены отдельно; этот пакет не объявляет завершёнными настоящие Stable/версии/HTML-потребители или перенос214оригиналов.

До реализации выбраны сценарии: MH01 — реальный owner multipart+CSRF JPEG/PNG/WebP через проверенный worker (позитивные критические e2e выполняет координатор, без insert-ready/fake decoder); MH02 — visitor401/employee403, CSRF403, private/no-store+Vary:Cookie на закрытых ответах; MH03 — ровно1 файл≤1000000байт, body≤11МиБ, закрытые MIME/extension, поле формы≤16КиБ, неправильный формат/2файла/байты не создают READY; MH04 — поколение владельца проверяется до и после decoder, во время него нет DB/content/auth locks; MH05 — неизменённый private-source не выдаётся даже owner-preview endpoint, производные только owner с nosniff; MH06 — DB logical folder picker/search ограничивает полный сегмент, rename Page не двигает home; MH07 — фактические cleanup candidates/bytes, preview→подписанное подтверждение→повтор refs/owner generation, late reference и реальные physical failure/retry; MH08 — socket/receipt/hash/source mismatch не дают ложного успеха, неопределённый writer оставляет quarantine; MH09 — аудит содержит только постоянные коды и внутренние UUID/ID, без filename/path/text/body.

HTTP unit/integration — Django Client(enforce_csrf_checks=True), реальный PostgreSQL и TemporaryDirectory. Допустимый внутренний ledger fixture не изображает настоящий Stable/HTML. Dummy worker применяется только в явно отрицательных fault/recheck сценариях; положительная codec/HTTP-приёмка требует настоящего Unix daemon и фактических байтов.

Консервативная граница согласована координатором: после socket timeout/плохой receipt не доказывается остановка child. Job остаётся в exchange с quarantine-marker; без автосрока, повторного запуска или HTTP Docker-команд. Явный безопасный reset exchange выполняет локальный операторский wrapper после остановки собственных worker и app. Нормальный проверенный terminal reply допускает очистку только точных известных имён своего UUID job. При неопределённом исходе DB commit предлагается проверить актуальную медиатеку, а не повторять загрузку вслепую.

## Контракт интеграции

Root включает `media_library.urls` на `/manage/media/`, namespace `media_library`, каталог `catalog`. URL: GET `/manage/media/`; POST `/manage/media/pages/<pageUUID>/upload/`; GET `/manage/media/files/<fileUUID>/`; GET `/manage/media/cleanup/`; POST `cleanup/prepare/`, `cleanup/confirm/`, `cleanup/<assetUUID>/retry/`. Никакой публичной выдачи `/img/` или source download этот пакет не добавляет. Все варианты доступны сейчас только owner-preview; private-source возвращает404 даже владельцу.

Настройки: default `MEDIA_LIBRARY_ROOT=/var/lib/estakada/media`, `MEDIA_EXCHANGE_ROOT=/exchange`; MediaBodyLimitMiddleware должен отработать __call__ после PrivateAccess и до фактического CSRF/multipart parsing. Root задаёт DATA_UPLOAD_MAX_MEMORY_SIZE=11MiB, FILE_UPLOAD_MAX_MEMORY_SIZE=1000000, DATA_UPLOAD_MAX_NUMBER_FILES=1. Обычные поля и подготовленный confirmation POST ограничены уже принятым16KiB-профилем. Socket client использует общий20с communication deadline (worker processing15с плюс завершение/доставка); timeout не переисполняется. App UID10001/GID10001, worker10002/GID10001, exchange/jobs каталоги0770, input/выход0640. Новых моделей/миграций/dependencies не добавлено.

Поля upload: csrfmiddlewaretoken, generation, image. Успех303 → catalog?page=UUID&asset=UUID; marker data-uploaded-asset-id появляется только для существующего READY. Некорректные файл/формат400, размер413, права403/visitor401, неопределённый результат503. Каталог без q показывает непосредственные файлы и подпапки; q ищет имя материала, логический folder path и UUID в текущем поддереве, граница — '/' вместо строкового префикса. Переименование Page сохраняет PageMediaHome. Нет замены PageContent или фиктивного attach.

Cleanup: checkbox asset_ids (повторяемый), generation; prepare показывает фактические files/total и form[data-media-confirmation] с opaque confirmation. Отмена — обычная ссылка без POST. Confirm/retry показывают data-media-cleanup-result, data-state, data-released-bytes и data-pending-files с фактическими исходами. Ошибки чтения явно исключены из известной суммы, а не спрятаны за нулём. Аудит использует MEDIA_UPLOAD_*/MEDIA_CLEANUP_* с константными кодами, actor ID и optional Asset UUID; filename/path/body в audit не передаются.

Добавлен `app/media_library/test_http.py`:17 HTTP/PG/realFS и отрицательных client-fault проверок. Unit запуск координатором — обычная media_library discovery (включает прежние22). Положительные JPEG/PNG/WebP/точный1MB и closed-preview/cleanup выполняются отдельным настоящим HTTP/browser probe, не dummy. 40MP/EXIF/alpha и ресурсный предел проверены отдельным Unix-socket worker probe предыдущей когорты; положительные40MP именно через админский HTTP этим набором не объявляются. Исполнитель Docker/установку/живой сайт/VPS не запускал; фактический результат координатора приведён ниже.

Адресное DEV06-HTTP-REV-003: адаптер media_event теперь передаёт настоящий UUID в строгий audit API, а не строковое `uuid:`-представление. Регрессия пишет настоящие MEDIA_UPLOAD_ACCEPTED и MEDIA_CLEANUP_PREPARED строки AuditEvent для Asset UUID, проверяет canonical persisted reference/actor/result без подмены writer. Это проверка аудита, не имитация положительного decoder.

Первый запуск координатора:114tests,102PASS/12setupFAIL за53.862с. Все12 новых HTTP случаев остановились до проверок: unit-container имеет только DB-сеть и не разрешает DNS имени ingress, а direct Django Client не является reverse proxy. Как в существующих accounts-тестах, только класс MediaHttpTests получает override AUTH_TRUSTED_PROXY_HOST=None. Продуктовые настройки и настоящий сетевой QA сохраняют доверенный ingress. Это новое условие для одного повторного запуска; до изменения повторов не выполнялось. Результаты HTTP проверок после исправления ещё не получены.

## Фактический результат D-326 — 2026-10-31

Реализационный модуль DEV-06 завершён в согласованной локальной области. В админку подключены настоящая загрузка JPEG/PNG/WebP владельцем, стабильная папка материала, каталог/поиск, закрытые превью и подтверждаемая очистка с честным частичным результатом и повтором. Исходники не выдаются HTTP даже через закрытый preview владельца. Добавление в медиатеку не меняет содержимое страницы: это соединение с редактором следующих модулей.

| Проверка | Фактический результат |
|---|---|
| Django/PostgreSQL/реальная ФС |114 PASS за86.093с:97прежних+17новых; check0ошибок/0silenced |
| Основа и изоляция worker |11 FOUNDATION PASS за7.3с; guard до/после без изменений |
| Настоящий Chromium/UI/HTTP/worker |8групп MH PASS,0повторов; JPEG/PNG/WebP,1МБ positive и8negativepayloads,права/CSRF/private-source/HTTP-file SHA,папки/traversal/поиск,отмена/подтверждённое удаление |
| Физическая очистка через браузер |Удалены3рабочих файла,916байт; отсутствие проверено ФС,не только строкой Asset. Отмена/сотрудник/посетитель/CSRF/tamper сохраняли данные |
| Качество наблюдения |14 QA-файлов с одинаковыми SHA до/после,исходники/контейнеры/worker защищены отдельным foundation guard |
| Визуальная проверка |Координатор просмотрел1280px и390px скриншоты; горизонтального переполнения/обрезанных элементов не обнаружено. Это не полная пиксельная UX-приёмка |
| После fixture |Пользователи/профили/сессии/Asset/AssetFile/папки/страницы и рабочие медиа-файлы:0; ordinary local_http,искусственные часы выключены. Служебные audit/tombstone/результаты сохранены |

Снимок приложения: run aca2bff4-8a0b-4fff-b980-e9aadbde3b5f, SHA256811b298b89d1b3c4d257a675f0364009c2175e8e165a437252e74776b59d16a2. Worker source manifest SHA2566b82b9f9f488e6f7ea60044eb41338ac0829393da471b9edfdb58bd34c0d9ef5. Browser run ec48cfcf-0fe0-4d8f-81c9-dbc4b18d6a4f.

Артефакты: work/dev06-http-20261031/{units-fixed-client.txt,foundation.txt,fixture-restored.json}; browser report/скриншоты — work/foundation/test/media-http/ec48cfcf-0fe0-4d8f-81c9-dbc4b18d6a4f/. Исправления независимого ревью и первая диагностическая неудача описаны в dev06-review.md. Первый browser-прогон прошёл целиком,без повторов/подмены worker.

## Сохраняющиеся границы

- Полные AC-025..029 и прежние29 MEDIA assertions не объявлены пройденными. Настоящие потребители версий/Stable/черновиков/общих блоков/HTML подключаются в DEV-05/07/25; полный перенос214 оригиналов и публичные изображения — DEV-09/10. Тестовый ledger не заменяет эти модули.
- Physical-failure/retry/late-ref проверены реальными PG/ФС/Django Client,а не сетевым браузерным fault injection. Отрицательные transport/client проверки и прежние21worker tests не названы выполненным HTTP worker-down/unknown-receipt сценарием.
- Native/base vendor-остаток и частичный RELRO остаются в dev06-worker-security.md. Полный усиленный hardening/нулевые CVE/готовность production не обещаются.
- При неизвестном commit/worker результате нет ложного успеха или очистки по таймеру; evidence сохраняется. После остановки последнего пользователя tmpfs не является долговременным журналом; восстановление/разбор исходных файлов при аварии остаётся эксплуатационным и выпускным условием.

Этап8 продолжается. Следующая задача DEV-05 — версии,Stable и восстановление страницы; её начало требует отдельного поручения владельца. Старый сайт/VPS/preview/production не затронуты. Push не выполнялся: смена не завершена владельцем.

Завершение контрольной точки: собственный test-стенд остановлен штатным Stop без удаления постоянных томов/секретов; manifest.active=false. Матрица140уникальных AT сохранена, изменённые026/027/029 отмечены partial_http. git diff --check PASS,237незакоммиченныхфайлов проверены на известные локальные секреты:0совпадений. Все прежние изменения сохранены; рабочая копия не отправлялась в GitHub.
