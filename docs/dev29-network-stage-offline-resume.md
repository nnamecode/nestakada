# Q025-OFFLINE-RESUME-001: штатный запуск offline harness

2026-11-04. Статус: возобновлено владельцем D-485; прежняя пауза D-484 сохранена ниже как история. DEV29-Q025/D-481 и ограниченное чтение D-483 сохраняются; архитектуру повторно не согласовывать.

## Факты

Новая public COW resume005 содержит36 source inputs и36 исходных inputs в baseline-checkpoint, без старых run/private. Внесены stage-aware spec/controller, новые AC и unchanged normalized Q024 fixture. Before COW36/36 baseline hashes совпали. Старые файлы не менялись.

Первый offline syntax harness не смог dispatch child processes в sandbox:26entries с status!=0/без полезного stderr; это не26 доказанных syntax ошибок. После сообщения исполнитель проверил node --version при том же sandbox, получив точный spawnSync node.exe EPERM. Консервативно признан второй equivalent launch failure. Координатор на первой доступной границе предупредил не повторять child в sandbox, но непрозрачный diagnostic call уже завершился; мгновенное прерывание внутри инструмента не обещается. Agent STOP/interrupt, третьего запуска нет. AC/existing suites ещё не запускались; syntax не PASS. Prepare/private/Docker/SQL/native0.

## Конкретное возобновление

1. После явного ответа владельца возобновить того же исполнителя. Контекст читать по одному известному файлу, вывод≤2000символов; широкие rg/полные listings запрещены по прежнему read-resume. Сохранённые partial code inputs не переписывать вслепую.
2. Все offline harness, требующие штатного child Node/Python, сразу выполнять через exec_command require_escalated в назначенной workspace, с точными известными командами/аргументами. Это стандартный профиль доступа, не ACL change/обход защиты runner. Не проверять permission повторным child --version/другим payload в прежнем sandbox. No install/settings/network/Docker/SQL.
3. До child dispatch исходник harness проверяется на fixed allowlist и отсутствие native Docker. На первом spawn error/error.code/status!=0 остановить harness: никаких26автоматических повторов launch после одного EPERM. Выводить только bounded summary/counts/enum errors, не raw stdout/stderr/Env/credentials.
4. Syntax/static → новые AC → полный existing offline безskip, каждый зависимый шаг только после PASS предыдущего. При настоящем syntax/test failure исправлять конкретный выявленный дефект по Q025 и новым свидетельствам; не blind retry. Затем frozen manifest/delta/source preservation и независимое code review.
5. Prepare только после CODE APPROVED и отдельного координаторского допуска. Далее все prepared/dispatch/actual-phase/result reviews и единственный conditional INIT/C/T строго D-481. Resume не добавляет Run/TTL/budget, не расширяет guard policy/SQL/source31/worker/runner. Existing reviewed ancestry hashes/stat — только назначенные nonsecret receipts; keys/credentials не читать вручную и не печатать.
6. При первой новой ошибке сообщить тип и точное новое условие любого повтора; второй equivalent — STOP, третьего нет. Если даже штатная escalation отклонена, не менять ACL/инструмент обхода, сохранить паузу и причину.

Старый сайт/VPS/корпус/история не меняются. DEV-29≈35%, этап8≈31%. **Q025-OFFLINE-RESUME-001:** разрешить возобновление с этим штатным способом запуска offline harness в рамках уже согласованного Q025? Альтернатива — сохранить техническую паузу.
