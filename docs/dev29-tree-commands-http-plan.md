# DEV29-CMD: конечная HTTP-проверка через локальный Nginx

2026-11-03, D-405, CMD29-008. План до запуска; отдельная synthetic fixture, не product create/delete API. Код команд/26tests прошёл независимое code-review. Используются только прежние foundation-test app/DB/Nginx/media-worker images/caps/сети/тома, текущий ROOT_URLCONF; новых служб/портов/пакетов нет. TRUST не запускается.

Перед fixture — ownership/source/image/runtime/actualDBrole guards и приватный сохранённый request сrunUUID; пароль/сессии/CSRF/токены только в уже закрытом foundation/test/private. Seed разрешён лишь при пустых User/Page/current versions/sessions и только прежних system routes. В одной транзакции создаются ровно2syntheticusers/6pages/3routes; владельцу nesadmin задаётся случайный тестовый пароль, всеfixtureusers помеченыrunUUID, страницы префиксомCMD TEST/run. Существующие live-данные не очищаются ради теста; непустота — отказ.

Через 127.0.0.1:8767 и обычные страницы login/structure проверяются:

1. Ownerlogin с настоящими cookies/CSRF, GET формы без durable tree receipt.
2. RenamePOST303/applied, тот жеPOST303/replay; отдельная устаревшая форма409 со своим сохранённым вводом. InvalidCSRF403 не меняет результат.
3. MoveGETпредпросмотр в hidden-раздел, POST сявнымbefore; reorderPOST. Точные исходные primary/alias/redirect и собственнаяпубликация/childPageID не меняются.
4. EmployeeGET/POST403. На всех новых ответах private,no-store/VaryCookie. Protected ownerконтент не выдаётся в запрещённом ответе.
5. НезависимоеCLI SQLнаблюдение подтверждает окончательные parents/positions/name, ровно3tree receipts/UUIDreservations/успешныхtreeaudits, отсутствие повтора/CSRF/stale-вставок. Это HTTPworkflow без браузерногоvisual acceptance; injectedlostcommitboundary отдельно вUNIT, не выдумывать реальнуюпотерюпакета.
6. Scoped cleanup вfinally: проверяются точные user/Page/route IDs, ownershiptag, неизменность всех прочих моделей и прежних строк постоянного журнала. Только собственные fixture routes/leaf-to-root pages/users/sessions удаляются внутренним test helper; product delete этим не подтверждается. Новые immutable operation receipts/UUIDreservations/audit сохраняются; исходные ledgers/systemroutes/media/shared полностью сохранны. При несовпадении cleanup отказывает и данные сохраняются.
7. APP/DB/Nginx cgroup measurements снимаются доStop с отдельными периодами. После rootStop —0контейнеров, source/codeSHA прежние; публикация/private data/VPS не затрагиваются. Ресурсы автоматически не повышаются; приFAIL разборсохранённогоотчёта, неслепойповтор.

Fixture/host-helper проходят отдельное независимое review до seed/HTTP. Публичный отчёт не содержит паролей/cookies/tokens; raw private outputs не добавляются вGit. Физическийrollback/powerloss/APP↔TRUST/HTMLadmission/production вне области.

Уточнение сохранностиauth: readonlypreflight обнаружил2истёкшие пустые LoginThrottle безошибок/блокировок ировно2AuthResourceState(full=False). Seed проверяет все счётчики/массивы/флаги/blocked_until/сроки и сохраняет полные исходные строки только приватно. Fixture их не удаляет и не восстанавливает: при настоящемlogin выполняется уже согласованная обычная auth.cleanup. В наблюдении допустимы только свежие пустые throttle с last_request_id из точных X-Request-ID двух успешныхHTTPвходов; NULL/неизвестныйID/ошибка/блокировка/старыйсрок запрещены. Возможен новыйrecord на томжеIP. Эти2временныестроки явно учитываются как штатно очищенные, а не сохранённые. ОбаResourceState и прежние постоянные журналы строго прежние. НовогоTTL/политикиочистки/сырогоудалениянет.
