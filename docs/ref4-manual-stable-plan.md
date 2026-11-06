# REF-4 — manual, Stable и отдельное удаление ordinary revision

Дата: 2026-11-05. Статус: завершено по D-615; повторное независимое review `APPROVED`.
Связанные требования: D-044–D-048, D-260, REF-AC-003–005, REF-AC-012, REF-AC-032, D-614.

## Граница

- Переключить создание manual revision и изменение только её metadata на простые PostgreSQL-транзакции без нового `OperationReceipt`.
- Переключить назначение и снятие Stable на простые транзакции без нового receipt; при снятии сохранить повторную проверку текущего пароля.
- Переключить отдельное подтверждённое удаление ordinary revision на простую транзакцию без нового receipt.
- Существующие receipts этих действий до нового маршрута продолжают точный replay с прежним результатом.
- Не менять просмотр/сравнение истории, direct restore, удаление всей страницы, schema, таблицы или данные. Старый код не удалять до REF-Q004.

## Приёмочные сценарии до кода

| ID | Сценарий | Обязательный результат |
|---|---|---|
| REF4-MS-001 | Владелец создаёт manual checkpoint текущей revision | Создана ровно одна immutable manual revision с копией server-side current payload/media и metadata; current не меняется; новый receipt не создаётся |
| REF4-MS-002 | Повторить новый manual POST или изменить signed source/current/generation | Дубликат не создаётся; повтор безопасно конфликтует, stale/tampered запрос отклоняется без изменений |
| REF4-MS-003 | Владелец меняет name/comment/manual_date manual revision | Меняется только точная metadata с generation CAS; payload, author, created_at, current и Stable неизменны; повтор конфликтует; нового receipt нет |
| REF4-MS-004 | Владелец назначает просмотренную ordinary/manual revision Stable | Exact view stamp повторно проверен; создаётся одна protection, media usages ordinary→stable, лимит не удаляет Stable; current не меняется; нового receipt нет |
| REF4-MS-005 | Сотрудник или устаревший/tampered view пытается назначить Stable | Безопасный 403/409; protection, usages, history и audit business-событий не меняются кроме bounded denial audit |
| REF4-MS-006 | Владелец снимает Stable с актуальным подтверждением и текущим паролем | Password проверен до locks и его hash повторно сверён под lock; protection снимается, usages stable→ordinary, limit10 применяется по исходной дате; current защищён; нового receipt нет |
| REF4-MS-007 | Неверный пароль, изменённая composition/stamp/session или сотрудник снимает Stable | Операция целиком отклонена; protection/media/history неизменны; пароль/confirmation не попадают в audit/receipt |
| REF4-MS-008 | Владелец удаляет подтверждённую ordinary revision | Только не-current, не-Stable, не-pinned и не-draft-base revision удаляется атомарно вместе с её usages/metadata; физические media files не удаляются; нового receipt нет |
| REF4-MS-009 | Audit/DB fault или replay старого receipt для любого действия | Новый путь полностью откатывается; старый fingerprinted receipt возвращает прежний результат без новой записи и без повторной mutation |

## Реализационный контур

- Простые команды располагаются рядом с уже принятыми `page_versions.simple_commands` и используют те же `enter`, row locks, signed stamps, media helpers, pruning и bounded audit.
- Для защиты manual double-submit operation UUID становится server-validated идентификатором новой revision; повтор не может создать вторую строку даже при гонке. Остальные операции имеют естественный CAS: metadata generation, protection/stamp/composition или существование target.
- HTTP сначала распознаёт существующий legacy receipt и только для него вызывает старую реализацию. Новый operation UUID никогда не создаёт receipt.

## Проверка

Сначала узкие command/HTTP/fault тесты REF4-MS-001–009, затем существующие page_versions history/concurrency, media/embedded/cleanup и transition наборы. После — независимое review, read-only main DB, login smoke и остановка `foundation-test`. Production, VPS и старый сайт не затрагивать.
