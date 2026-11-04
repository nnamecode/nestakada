# DEV-29: предложение допуска Docker после холодного старта

2026-11-04. DIAG29-READINESS-PROPOSAL-001, не утверждённое изменение архитектуры/кода и не разрешение Run. Основание — независимо установленная [причина R021](dev29-docker-timeout-cause.md): readyчерез19,09с противnative8,999с.

Минимальный вариант дляследующегосогласования: только самый первый read-only inventory в preflight получает явный cold-start readiness budget nominal≤45с/native≤44с с существующим1с trace reserve. Это всё ещё ровноодин запрос, неpolling/retry/второйRun. Его успешный завершённый ответ, а неUI/кэшированныйinfo, допускает дальнейшийpreflight. Остальные runtime/cleanup/SQL/admission/TTL/owner/source/budget gates и per-call timeouts неизменны; новаяизолированнаяcopy/root/once понадобятся, прежниеRunисчерпаны.

Сохранить exact expectedengine/endpoint/filter/sourcepins/raw0/failuretrace и noSQL приошибке. Timeout/exiterror/partial/invalidoutput => терминальныйFAIL/разрешённыйboundedcleanup, без второго readinessquery и продления. Coldstartphase проходит доSTART/INIT/admission clocks, не съедаетTTL уже начатойфазы. Проверитьприcode review, чтоnominal45 вписываетсявсуществующиепредфазовыебюджеты и не ослабляет общиеграницы; еслинет — пересмотретьпланвместо обхода.

До реализации согласоватьэту единственную budgetexception, критерии и весь новый one-shot lifecycle. Затем COW/delta/code review, тесты mockclock19.1сsuccess вновомreadinessbudget и failureвстаром8999; >44с/engine drift/partialoutput/readonlyfailure не допускаютследующийшаг; runtime cleanup по-прежнему прежний9с. Prepare/result/dispatch/start/payload reviews и сохранность всегоretainedкорпуса обязательны; noimages/install/settings/ACL/перезапусков/стороннихконтейнеров. P29-A ещё не завершён.

Альтернатива — внешняя one-shot readiness-проверка передRun, но она требует отдельного source/hash/once-binding и гарантии отсутствия idle-gap между ней иRun. Пока не выбрана. ОтключатьResourceSaver, менятьWSL/.wslconfig илиувеличиватьвсеtimeouts основанийнет. Никакойвариант вэтойсмене не реализован/незапущен. Это материалследующегосогласования, не готовыйновыйruntimeplan.

При следующем preparedbudget включить новый diagnosticnamespace work/dev29-docker-lifecycle-20261104-001/ (source/tests/summary/failedqualification) в retainedroots; ничего из него/старого корпуса не удалять для прохождения gate. Observer остаётся NOT_RUNTIME_QUALIFIED и не используется как readiness/admission proof.
