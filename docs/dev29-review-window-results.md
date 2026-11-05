# Q026 — фактический результат

Итог D-501 (2026-11-04): единственный Q026 Run завершён exit1/FAIL на INIT, HOST_CLEANUP_UNPROVEN; повтор не запускать. START фактически принят runner за59789.0573мс<120000. Result a7df3826…1d26,44ledgerSHA совпали, phases/witnesses пусты/fullP29A=false. Независимый result audit подтвердил: DB stopped/removed и сеть удалена, terminal owned containers/networks пусты; clean-stop proof DB отсутствует, поэтому cleanupProved=false. DB Exit1/санитизированная категория PERMISSION; точная причина исследуется по сохранённым файлам, SQL не подтверждён. Original before/after идентичны (2398 файлов/256516096bytes). Код/защиту/лимиты не обходить, старый сайт/VPS не затрагивать. DEV-29 около35%, этап8 около31%.

Result SHA256 a7df3826e52e8766b6ec0b7e9e5ea4282332a99a835c0c3fd0d6f0093c831d26. Accepted START SHA256 7a41e877483d83ea12048086faa4bf7f1eef5663304d5c32c8f0d57477ed8b65. Runtime window120000мс; accepted59789.0573мс, remaining60210.9328мс. OPINION_RECORDED отдельно от фактического admission.

Независимый /root/q026_result_auditor подтвердил44ledgerSHA, сохранность original и отсутствие owned ресурсов на том же engine. Cleanup также требует полного успешного DB-stream/systemIdentifier: proof не получен; HOST_DB_CLEAN_STOP → HOST_FINAL_CLEANUP → HOST_CLEANUP_UNPROVEN. Исходный DB ExitCode1/OOMfalse/State.Error отсутствует. Категория ошибки PERMISSION; точную операцию audit не установил. Phases/witnesses пусты; отсутствие любых SQL-действий не доказано, полное P29-A не выполнено.

Original:2398 файлов, allocated256516096bytes, shut down; systemIdentifier7703371248427204668; manifest637dcc8822560b10fce09b95eb173f764fe95cb74122df7e1295fff71eca7d2c; rawproofa996e57e8c8662516f2b4dccc179b55ba81b74374f1618c833ddf4b35b653993. Before/after идентичны.

Одна усечённая stdout-выдача terminal-result: повтор bulk не выполнялся, дальнейшее чтение только bounded проекциями. Ключи вручную не читались, независимый HMAC не заявляется. Новый Run/правки frozen package/публикация этим результатом не разрешены. Текущий этап8 «Код»; следующий этап9 «Unit-тесты» по pipeline, пока не начинается.

После Run все42 frozen package files совпали с manifest; package SHA256 2489595e6c86e7ea797af0e2276786ea46e7742a696412faa2bcbe592eba299e. Отдельный аудит текста результата и строки DEV-29 не обнаружил фактических ошибок.

## Уточнение D-502

Исполнитель классифицировал savedstream SHA256 e505733ac26de6a126613ef6a55a71d2a5d1d655690794a0193df08803da9471 без вывода raw: cp TLS key /run/secrets/database-server-key получил Permission denied, exit1; frame NOT_STARTED/FAIL/SUPERVISOR_INCOMPLETE. Независимый /root/q026_result_auditor подтвердил статически UID/GID999:999/readonly bind и порядок cp → chmod копии → INITDB → initdb. Сам rawstream аудитор повторно не читал. При верной классификации supervisor не дошёл до initdb/postmaster/SQL. Конкретный механизм запрета доступа пока не установлен.

Metadata/code план прошёл независимое ревью; реализация способа доступа и новый native Run не разрешены этим планом. Исходный ключ/ACL/frozen package не менялись.
