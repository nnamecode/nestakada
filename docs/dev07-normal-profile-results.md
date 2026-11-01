# DEV07-CLOSE-01 — результат обычной локальной интеграции

2026-11-01. Выполнено в границах D-330/331/364/365 и [NH07-001–008](dev07-normal-profile-checks.md). Независимое ревью кода, тестового инструмента и фактических результатов положительное. CLOSE-01 завершён; DEV-07 целиком остаётся в работе — около 95%, этап 8 около 20%.

## Изменение

Обычный локальный Start подключает основной URLConf редактора, закрытые assets, template discovery и admission перед CSRF. App/migrate/units используют проверенный editor artifact782, базовый094 и отдельный media worker сохранены. В wrapper добавлен закрытый admission receipt/recipe/tree/версий/слоёв образа. Новых зависимостей относительно D-330, портов, томов, лимитов ресурсов или ролей БД нет.

Три точных Page POST check/save/draft получили прежний согласованный transport64MiB/streaming/proxy_read_timeout150s; Shared outer11MiB, application reader4MiB и small actions16KiB сохраняют область. Локальный Django runserver --noreload работает с HTTP threads для немедленного BUSY; тяжёлая операция остаётся одна. Production WSGI этим не выбирается.

## Фактические проверки

Обычный Start прошёл с первого запуска, без QA settings/URLConf, image overlay или observer middleware. Источник: 230 файлов, manifest SHA256 `217492c9f16abdb5a515c89c3a5fc7cac07417338e8be816e171ab3b8aea7634`, source run `fe5d5ce3-5aa5-4c85-a509-9f01b0f277ea`. Actual nginx -T соответствует проверенному конфигу; host/frozen source drift0.

- 20 framework-регрессий: PASS, 57.774s, system check0. Шесть terminal UI, шесть restore terminal и восемь прежних versions HTTP; отдельная unit БД, тот же source manifest.
- NH07-001–004: обычные routes/templates/assets, нормализация→Check→Save→reload, назначенный текст и price-only права, запрет поддельных/чужих полей, selected draft и employee restore stage. Shared GET/реальный Check разрешены владельцу и запрещены сотруднику; Shared Apply в этот срез не входит.
- NH07-005: девять ранних отказов входа/прав/CSRF по всем трём большим действиям; отправлено0байт тела, ingress request temps отсутствуют.
- NH07-006: действительные превышения бюджетов/малые маршруты, content type и framing; exact411 EDITOR_LENGTH_REQUIRED,400 EDITOR_BODY_INVALID,415 EDITOR_JSON_REQUIRED и413. Allowlist не расширен.
- NH07-007: реальный удержанный slot, без advisory locks при чтении тела. Второй запрос получает503 EDITOR_BUSY за141мс до тела; FD4→8→4, slot освобождён, следующий Check успешен.
- NH07-008: тело передаётся каждые5секунд;25байт до настоящего deadline приложения120172мс. Exact408 EDITOR_BODY_TIMEOUT, без преждевременного proxy504. FD4→4, slot освобождён, следующий Check успешен.

Итог native отчёта PASS, failed=null, stderr0. Особенность схемы отчёта: NH07-008.status содержит HTTP408, перекрывая строковый статус группы; успех доказывается выполненными assertions и общим PASS. Это не восемь строк status="PASS" и не причина ослаблять тест или повторять успешный запуск.

До полного запуска независимое QA-ревью исправило один дефект сценария: вместо молчаливого ожидания120s добавлен drip5s, чтобы измерять абсолютный deadline приложения, а не inactivity Nginx. Отдельная предварительная диагностика подтвердила exact411/400 без тела/мутации; она не считается дополнительной NH-группой. Полный набор из8групп прошёл с первого запуска, продукт ради ожиданий теста не менялся.

## Воспроизводимость и сохранность

Runtime app `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986`, base `sha256:09433387bce7dd726eb2f76918287c04c1fbd340eed1db2aaa3397fbd0474951`. Receipt SHA256 `634b91630fac20a12aba9ce9f243038aab3c91c202bac0383c2db8ee7139d74b`: проверены85 package files,5точных версий,8base layers+1editor layer, UID10001:10001/linux-amd64. Это локальный проверенный кандидат, не production certification.

Локальные доказательства вне Git: work/dev07-normal-20261101/{runtime-validation.json,cohort-first.json,nginx-effective-first.txt,framework-first.txt,native-first/host-report.json,http-freeze.json,stop-final.txt,final-checks.json}. Native run `c5447ff2-63af-4af5-9e3c-37f325b56c81`; все config/QA hashes записаны в host-report.

Cleanup удалил только свои тестовые записи/asset: пользователей/страниц/версий/черновиков/stages/pins/assets осталось0. Системный route и Shared baseline/бюджет/история сохранены; постоянные identity tombstones699/180, operation receipts363 и append-only audit850 не очищались. Обычный Stop завершён, private files/named volumes сохранены. Старый сайт и VPS не затронуты; commit/push не выполнялись.

## Что ещё требуется

[Конечный аудит](dev07-completion-audit.md) сохраняет CLOSE-02 явную отмену shared stage, CLOSE-03 диагностику/исправление мобильного overflow и CLOSE-04 единый конечный normal cohort с Shared Apply, сложными таблицами, медиа и представительными MAX. Shared Apply здесь намеренно не выдаётся за проверенный; его бюджет/история не сбрасывались ради теста. Полные TEST09/10 и зависимые DEV остаются обязательными.

Старый неактивный compose.env до интеграции не содержал FOUNDATION_APP_IMAGE; восстановление Status/Stop активного legacy cohort не проверено. Новый обычный Start обновил неактивную среду, последующий обычный Stop проверен. Production/runtime выбор и этап9 не начинаются.
