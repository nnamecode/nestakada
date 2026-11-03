# DEV-15: локальный run lease и проверки сбоев

## Итог D-392, 2026-11-03 — принят независимым ревью

Ограниченный RL15-инкремент выполнен: восемь lifecycle-фаз и девять реальных native-проверок PASS. Независимое итоговое result-review — **APPROVED**. После испытаний разрешение отозвано, собственных контейнеров 0; старый сайт/VPS/APP/DEV-29/production не затронуты. DEV-15 остаётся в работе, около 97%; этап 8 около 28%.

| Область | Фактический результат |
| --- | --- |
| Prepare/Enable/Check | Disabled и empty/stale lease отвергнуты корректным HTTP503; валидный lease принят на том же final CID с неизменными host/guest inode и данными. |
| Unbind/повторный Enable | После отзыва реальный 503; повторная выдача не добавила policy и не изменила Head10. |
| Restart/новый Enable | Новый run `74683647-f33e-4298-823c-fcca0cf9cca2`, final CID `0d81377f929b46a4448351cd8edff5c0d10b7b6e6dffef96b89c18d1c704de84`. Прежний lease не подошёл новому runtime; новый принят при той же policy1. |
| UNKNOWN/committed lost response | Полный POST и headers без чтения response body; независимые SQL/status подтвердили MAIN_RESULT_UNKNOWN и FINAL_RESTRICTION. Точные повторы вернули те же phaseReceipt без изменения полного состояния. Это потеря чтения body, не kernel packet loss. |
| Частичный другой prepare | Подтверждена неполная клиентская отправка и ограниченное окно отсутствия изменений. Создания operation не произошло; серверные slow/body границы и SQL-injection этим не доказаны. |
| Данные/bytes | Добавлены только одна synthetic operation и один route; все прежние persistent rows/pin/policy сохранены. Prepare charge4597 и reserve8362 проверены отдельно; после completion legacy reserve16708 сохранён. Head10→11→12→13, writer epoch2, policy1. |
| Финальный Inspect/Stop | Оба исходных архива OID16387/32563, raw rows/v2 и закрытое состояние совпали. Свежий SQL-v2 `b42ec332cfcd39f3952210eedbfc9722b0302dd9e94fa76b3b3f03aa6f13599a` совпал с native evidence. Файл permit пуст, 0 контейнеров; source30/config/EV63 без drift, исходные env/manifest прежние. |
| Приватность | FinalACL WinPS5.1 PASS689 объектов/1378 правил, только владелец/SYSTEM, reparse0. Raw inputs/captures/keys остались в игнорируемых private/work, в Git не добавлялись. |

Итоговый индекс `work/dev15-lease-20261102/final-result.json`, SHA `48621879539e8b52b049b8577bd45936794c07a3891cd7be4369a8ba233b1136`. Native report SHA `434a87bfe4e68bf60057c734079540ce2dd775b17d7546939718e39bc8ed8a10`: 9 checks/16 transport-файлов, точный planSHA и сохранённые тела до send. Последующий Inspect SHA `20a1da5d1b8db4c3fa281226989730c21e5bbb95b323720edf534742ab3e45fb`, archive proof a041996b… совпал с прежним. Collector независимо пересчитал три Head-digest перехода и bytes; root и рецензент сверили HMAC/raw links. Полный RP15/DEV-15 этим не закрыт.

Остались отдельные controls принятого плана: SQL/disk-error injection и оставшиеся transport UNKNOWN/503 (RP15-015), active/rate gate (016), TLS negatives (017), body/header/slow/privacy и логовые canary (018), оставшиеся отказные окна/recovery (007/019). Следующая серия должна использовать новый подписанный контекст от принятой текущей точки Head13/v2 b42ec…: конечный launcher этого инкремента привязан к исходной Head10/60e…, повторять его Prepare с прежней baseline или сбрасывать данные нельзя. Это обновление проверенной операционной точки, не увеличение caps или новая policy.

### Ход принятого исполнения

Владелец снял DEV15-RL-RESUME-001. Именованный preflight подтвердил все 189 SHA, 0 контейнеров, локальный Docker Desktop и пустой permit до начала исполнения. По технически принятому пакету и quality16/AST5 созданы exact code-gates; исходные файлы/архивы не сбрасываются.

Реальный Prepare run `de95408f-1a27-425c-89cf-8d87befe76d4` — PASS: disabled intermediate API и затем final bounded API без действительного lease дали правильные аутентифицированные HTTP503 (`WRITE_PROFILE_DISABLED` / `BOUNDED_ADMISSION_REJECTED`). Подписанные creation/final-creation/final-container intents сохранены до соответствующих команд. Конечный CID `7214c14a21676ab1c57dc6373727a69086092de4bcbc5baa7cd8f26f7e85263f`; intermediate `3123604fd4126ce92c9d8b3c1ac5bf15e09bb369733fea8124df2dcb1c76c49e` и previous MAIN a4e2… исключены. Состояние policy1/Head10/epoch2/full-v2 60e067…0bc1 и reserve16708 неизменно. PreparedACL471/942 PASS. Независимое result-review Prepare принято.

Enable `8b1810a5-2da8-42bb-a63a-c011eeb564af` и Check `996b8d08-147e-4b91-9638-793803c0cc49` — PASS, принято независимым ревью. Envelope SHA `6d486c3c3b0c723958a6afe13bea7fe54f70d8dfd72763df7a949a9a098c959d` опубликован при stopped API в тот же host inode; запущен тот же UUID/CID, guest inode и реально прочитанные байты совпали. Admission с Head lock проверен с rollback без мутации; snapshot, source/config/EV63 неизменны. На этом раннем этапе положительных HTTP-операций ещё не было; последующие успешные Unbind/Enable/Restart/Enable/native/Stop отражены в итоговом блоке выше.

DEV-15 около 97%, этап 8 около 28%; старый сайт/VPS не затронуты. Ниже — историческая пауза до D-392, а не текущий статус.

2026-11-03, продолжение D-391, RL15-001–010. DEV-15 около 96%, этап 8 около 28%. Статус — **Приостановлено владельцу, DEV15-RL-RESUME-001**.

Подготовлены controller конкретного запуска, API-side observer/transport probe, 16 VM-проверок и конечный native fault-controller. Политика, применённая D-390, не менялась: последний принятый фактический SQL-итог — policy1/Head10/epoch2/full-v2 60e067…0bc1. В D-391 свежий SQL-снимок, API lifecycle, выдача lease и HTTP-мутации **NOT_RUN**.

Выполнено:

- Сохранены 84 существовавших Git-изменения и 170 SHA, включая неизменяемые env/manifest/source/EV63. После первой неподтверждённой Docker-status проверки отдельная диагностика подтвердила локальный Engine, завершённая сверка — 0 контейнеров/disabled/пустой permit.
- Подтверждена HMAC-связанная история previous MAIN CID/runtime; hostFAIL LG не переименован в PASS.
- Независимое ревью плана и кода выявило/закрыло NF-REV-001/002 и LEASE-REV-001. Подробности — dev15-runtime-lease-review.md.
- Финальный кандидат: controller579e37… / probefdd92… / guard29e567… / fault-controller3881… / прежний fault-probe2fa27…; полные SHA — work/dev15-lease-20261102/resume-plan.md.
- Финальный quality-9fa7662d… PASS: Node syntax, 16 VM-кейсов фактических функций с подставными FS/Docker и AST пяти Python-блоков. Docker для AST был без сети, ключей, БД и mounts; пакетный image/лимиты прежние. Это не проверка настоящего lifecycle, SQL rollback или native HTTP.

Пауза вызвана повтором ошибки PowerShell quoting в необязательной информационной Node -e проверке исполнителя. Ошибочный вызов не исполнился; готовый код, VM-результаты и исходные данные сохранены. Координатор остановил исполнителя; независимый рецензент подтвердил признак цикла AGENTS.md. Новое runtime-исполнение до решения владельца запрещено.

Именованный inspect-sources.mjs заменяет сложный inline Node для SHA/информационных проверок без PowerShell quoting. План возобновления — work/dev15-lease-20261102/resume-plan.md. Техническая готовность исправления принята, но runtime code-gates пока не опубликованы и полный DEV-15 не завершён. Старый сайт и VPS не затронуты; push не выполнялся.
