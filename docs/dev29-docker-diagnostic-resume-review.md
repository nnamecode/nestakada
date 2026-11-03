# DEV-29: независимое ревью Q017

2026-11-04. **R016-DOCKER-DIAG-PROPOSAL APPROVED**, только для вопроса владельцу. [Предложение Q017](dev29-docker-diagnostic-resume.md), exact rawSHA `d84863fc7f77da4f643c551a82fd72ad81ca7b2cabfaccfdcdf2658043d8b518`. Рецензент `/root/dev29_publication_review` исходный документ/код не редактировал, UI/Docker не вызывал. R016 остаётся «Приостановлено владельцу», ответа Q017 ещё нет.

| ID | Исправление принято повторным review |
|---|---|
|Q017-REV-001/P1 | Единственный уже существующий native Docker Desktop window/status indicator, foreground/read без clicks/launch/settings. Closed state mapping; только exact RUNNING допускает CLI, все иные/неизвестные состояния STOP. Timestamp/opaque UI identity, screenshot persistence отсутствует. |
|Q017-REV-002/P2 | Один иной formatted query, stdout только complete unique64lowerhex IDs; CRLF-only normalization, bytes/hash/complete, count только для полного валидного ответа, raw persistence0, caps/clocks/wx/no retry. |
|Q017-REV-003/P2 | Явный dispatched и STOP_UI/PASS/FAIL; closed error/signal/exit/duration/null правила. При UI STOP CLI не запускается; произвольные Error.message не сохраняются. |

Два начальных snapshot6bc3ee…/4fd8bf… получили CHANGES REQUIRED; финальный d84863… одобрен, новых блокеров нет. Review не является диагностическим результатом и не разрешает выполнять даже read-only UI/CLI до решения владельца. После согласования — один bounded проход и независимое файловое result review; полный Run/SQL/code/новые roots этим не разрешаются.
