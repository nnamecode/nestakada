# DEV-29: Q018 — сохранённый STOP_UI из-за неверного selector

2026-11-04, D-444. Владелец поручил «Продолжай» после Q018. Fresh `sky.list_apps()`23:27:35.284Z вернул Docker Desktop running=true и единственное окно2033928 с заголовком **`Containers - Docker Desktop`**. Главное окно действительно открыто. Согласованный selector ожидал exact `Docker Desktop`; кандидатов по нему0. Причина остановки — слишком узкий критерий, предложенный координатором, а не отсутствие приложения или неправильное действие владельца.

Новых activation/click/navigation/state captures/settings/Docker CLI/SQL не выполнялось. Status STOP_UI/dispatched=false. По истечении UI60с действия не продолжались; срок не продлевался. Report002 записан один раз штатным `exec_command require_escalated`, wx, примерно на95953мс внутри total120с. RawSHA `64902f2f1b394840b2f70ddd6d67232e5cc30e9b82fd3c8d3cb5b0ed112cdc21`,846bytes. Report001 отсутствует и не восстанавливался.

**Q018 ACTUAL-RESULT APPROVED**: независимый рецензент `/root/dev29_publication_review` проверил report002,16 closed fields, planned command/45000, UI_UNAVAILABLE/null surface, null CLI outcomes/count, empty incomplete output hashes, STOP_UI/raw0 и elapsed<120. Это не самостоятельное повторное UI наблюдение и не diagnostic PASS.

Попытка завершена, report002 неизменяем. Действующий Scope не расширялся под фактический title, одноразовый deadline не перезапускался. Runtime R016/Run/SQL остаются приостановленными. Для исправления admission selector без скрытого расширения подготовлен [минимальный Q019](dev29-docker-diagnostic-resume-003.md). Никаких дальнейших UI/CLI до решения владельца.
