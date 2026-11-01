# DEV07-SID — selected-source identity и повторный вход

2026-11-01, D-362. [SID-001–004](dev07-selected-identity-checks.md) выполнены в ограниченной локальной области: **4/4 браузерные группы PASS с первого запуска**, независимое ревью кода QA и фактических результатов положительное. Код сайта не менялся. DEV-07 около 98%, этап 8 около 20%.

## Фактический результат

| ID | Что подтверждено через настоящий Chromium/Nginx/PG |
|---|---|
| SID-001 | Owner selected draft с проверенным собственным вводом → настоящий logout/login employee в том же BrowserContext → явный Check. Старый editor payload не отправляется; исходная вкладка получает terminal identity lock, inputs/initial JSON очищены, контролы выключены. Реальные textarea/pre/script handles, сохранённые до смены actor, также пусты после очистки, даже если detached. Domain/receipts/VERSION audit неизменны |
| SID-002 | Employee selected stage с proof → logout/login owner → явный Save. Owner-права не обходят смену actor и привязку stage: editor POST=0, доступные старые копии очищены, held stage/pins/current сохранены |
| SID-003 | Реальный выбранный owner draft UPDATE проходит route.fetch до commit200; ответ обрывается. В PG тот же draft UUID/revision+1, одна новая owner save_draft receipt, current/history неизменны. После другого actor manual retry не отправляет второй POST и переводит исходную вкладку в terminal lock. Первоначальный commit и receipt не откатываются |
| SID-004 | Настоящий logout/login того же owner, прежняя generation, новая конкретная estakada_test_session cookie. Вкладка сохраняет собственный RAM-ввод и выбранную основу draft. Login/явная reauth ничего не отправляют автоматически. Только новые отдельные Check и Save с текущим CSRF публикуют retained input; одна новая ordinary/current и одна owner commit receipt |

Наблюдатель учитывает все POST под editor prefix, не только Save. Auth logout/login — настоящие запросы с cookies/CSRF; identity не подменяется фиктивным ответом. В SID-003 route.fetch/abort применяется только для потери настоящего ответа после доказанного commit. До/после сравниваются actual receipt-inclusive domainHash и VERSION audit. Иные auth-аудит/session изменения не объявляются domain mutations.

Новый CSRF проверен против конкретного ответа текущего bridge state GET той же Check/Save операции. Маски get_token на разных GET не сравниваются как доказательство ротации session. Рецензент до запуска потребовал SID-QA001: прежняя проверка «изменилась любая cookie» усилена до точного old/new estakada_test_session, nonempty+разные значения. Все cookies/proof/private input остаются в RAM runner, не выводятся в отчёт.

## Воспроизводимость и очистка

Run `fa5fe187-b9d1-4c4a-94dc-50a6c9fec8a3`, source manifest `96551e0705171bad80c36b336d57ab324650528121106f655be5cdc4cf6a2796`, 230 файлов. Все host/frozen SHA совпадают; app manifest побайтно идентичен предыдущему RUI. Прежние 20 серверных PASS/59.663с относятся к отдельному RUI run3e015682… на том же app manifest и здесь **не запускались заново**. Новых framework-тестов или продуктовых исправлений для SID нет.

Финальные native inputs: неизменная fixture713b5b4be3a6369ac6d394cacdc40914b1bafb432b8cf0f44f240d7f09a8cd5b; probe c0b5ba0dba3c3cbd14fe7047e08955320a4930da93b9b57b57766dd996016a20; host53dd2d4a130c4c3f342de14239ec691c73d1422ad426839729eba438f6c125db. Node --check PASS, независимый execution gate до первого run. Прежний approved профиль runtime094333…/test782f…/Playwright1.64.1, read-only source/private DB/loopback ingress и caps сохранены; новые зависимости/ресурсы/миграции/маршруты не вводились.

Actual host-report: status PASS/failed=null/stderrBytes=0. Cleanup users/pages/versions/drafts/stages/pins=0, сохранён один system Route и постоянные 673 version identity tombstones, 172 media identity tombstones, 350 operation receipts, 822 append-only audit events. Стенд остановлен с сохранением томов; final-checks.json подтверждает active=false/foundation[]/browser[] и230 SHA без расхождений.

Оба PNG просмотрены после SID-001 terminal lock, без private canary. Известный общий overflow редактора остаётся: mobile full-page PNG406x4364 при viewport390. Это не закрытие общей адаптивности и не причина ослаблять identity assertions.

## Границы и следующий шаг

Подтверждены наблюдаемые DOM/initial JSON/активные доступные ElementHandles, блокировка контролов/retry и запрет передачи старого payload. Это не инспекция всех JavaScript closures, не физическое обнуление heap и не доказательство очистки всех возможных носителей. Same-user сценарий имеет прежнюю generation; новое правило обязательного нажатия именно reauth-кнопки не вводится — существующий явный Check также может сам перепроверять session.

Полная новая generation/current/grant/late-body/child/FS/race матрица, media/price/сложный legacy/MAX/другие браузеры и общая responsive-проверка остаются отдельно. Четыре группы не закрывают все D07/AC. Следующий шаг — сверить конечные оставшиеся блокеры DEV-07 с implementation-plan.md, отделив обязательную готовность функций от итоговых TEST-09/10. Итоговые проверки сохраняют принятый объём и постоянные ID. Полный DEV-07 и этап8 не объявлены завершёнными, этап9 не начинается.

Свидетельства в ignored work/dev07-selected-identity-20261101/: before-2b043…/manifest.json, cohort-first.json, source-checks.json, http-freeze.json, probe-before-session-cookie.mjs, native-first/host-report.json и screenshots, stop-final.txt, final-checks.json. Всё сохранено локально; push не выполнялся. Старый сайт/VPS не затронуты.
