# DEV-06 — исполнение реальных HTTP/UI-проверок

2026-10-31, D-326. Независимый oracle — dev06-http-checks.md и IMG-001–013; этот документ не объявляет проверки выполненными. Запуск — только координатором после готовности неизменяемого snapshot приложения и действующего test-пакета foundation.

Команда из T:\nestakada: `powershell -ExecutionPolicy Bypass -File scripts/test-media.ps1`. Wrapper ничего не устанавливает/не собирает/не запускает окружение и не повторяет сбойный набор. Требует уже работающие test app/SQL/ingress/реальный media-worker и пустую по пользователям/страницам/Asset изолированную fixture-БД.

Host `tools/test-media-http.mjs` сначала вызывает collect-foundation-evidence.mjs без параметров, сохраняет SHA guard.json в памяти и проверяет `--verify <sha256>` до/после набора/очистки. Защищаются реальные source/images/контейнеры и worker. Подмена нового guard вместе со snapshot не заменяет первоначальный якорь.

Этот foundation guard не охватывает QA-скрипты и синтетические входы. Для них wrapper отдельно фиксирует SHA-256 до/после: fixture, probe, собственный координатор, PowerShell wrapper, inputs.json и девять входных файлов. Набор имён закрыт, разрешены только проверенные basename без symlink/junction/выхода за репозиторий; байты сверяются с synthetic manifest. Несекретные {path,sha256} попадают в qaProvenance отчёта; drift даёт FAIL. Перед каждым host-exec fixture дополнительно проверяется SHA именно исполняемых байтов.

Случайные actor-пароли fixture передаются Playwright только через stdin процесса. Отдельного password-файла, HTTP fixture endpoint, Docker socket/DB-паролей в browser container нет. Контейнер получает read-only node_modules уже подготовленного Playwright 1.64.1, один probe, девять синтетических входов и отдельную папку результатов. Используется только утверждённый digest образа; `--pull=never`, без новых зависимостей.

`tools/media_http_probe.mjs` использует настоящее Chromium-окно headless: login/CSRF/формы/кнопки/отрисовка img, а отрицательные мутации выполняет реальными HTTP-запросами того же обработчика. Фиксированный origin — http://host.docker.internal:8767; нет VPS/живого сайта. Положительная загрузка не заменяется insert-ready/mock decoder.

Host-only observer читает фактические Asset/AssetFile и ФС. Allowlist бывших файлов накапливается только из прежних наблюдений БД; browser-сообщение содержит лишь ID запроса observe и не может задать путь/команду. После UI-удаления проверяется и отсутствие Asset, и фактическое отсутствие каждого ранее наблюдённого leaf-файла. Непроверяемый/недоступный родитель не считается отсутствующим файлом.

Покрытие: owner JPEG/PNG/WebP/ровно1000000байт; over/multi/SVG/HTML/MIME/extension/truncated/pixels; employee/visitor/CSRF deny; source private и закрытые WebP/nosniff/no-store; real browser img; logical folder traversal и parent-child/similar-prefix search; cleanup prepare/подписанный ticket/role/CSRF/tamper/реальные байты; desktop1280/mobile390. Три страницы/папки — только metadata-fixture; изображения в каждой загружаются настоящим HTTP через worker.

MH-008 физические partial-failure и MH-009 worker-down/неизвестный receipt этим успешным путём не закрываются: root запускает адресные fault-проверки отдельно. Ledger-модели не выдаются за настоящие будущие Stable/HTML/current consumers; полный прежний MEDIA-набор и214оригиналов также не объявляются пройденными.

Результат — безопасный JSON и desktop/mobile PNG в work/foundation/test/media-http/<runId>. Пароли/токены/полные HTTP headers/trace не сохраняются; снимки делаются после входа без password-полей. API-запросы не следуют redirect; browser route допускает только фиксированный origin. Первый сбой прекращает набор, без retries. У runner собственное имя nestakada-media-http-<runId>, scope/run labels и проверенный image ID. Finally до удаления fixture проверяет, что именно этот контейнер остановлен: завершение Docker CLI само по себе недостаточно. При неподтверждённой остановке fixture сохраняется. Удаляются только собственные опознанные fixture-данные; чужие данные, pending/quarantine и незавершённая физическая очистка сохраняются для отдельного расследования и дают FAIL, а не разрушительный reset.

На подготовке выполнены только Node syntax checks, PowerShell parser и diff-check. Фактический сетевой результат фиксируется координатором после запуска.
