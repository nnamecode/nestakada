# DEV-15: восстановление доступа с сохранением запретов — результат

2026-11-03, D-400, RF15-001–008 / RP15-007/019. **PASS; независимое result-review APPROVED в ограниченной UNIT-области.** DEV-15 около98%, этап8 около28%.

| Проверка | Результат |
| --- | --- |
| RF15-001 | Отдельные UNKNOWN-операция с2адресами и PENDING-отметка удаления заявки сохранены с полными persistent rows и резервами. Без точного подписанного допуска fence отклонён, состояние прежнее. |
| RF15-002 | После отзыва writer и INSERT receipt введён ENOSPC exception. Полный откат сохранил прежний доступ и записи. Повтор того же actionID успешен один раз; exact replay не меняет состояние. |
| RF15-003 | Старый ключ со свежим epoch отклонён. Старый envelope после смены runtime/config отклонён до SQL. Система остаётся FROZEN. |
| RF15-004 | Структурно валидные подписанные proof с неверным v2 digest либо previous runtime получают RECOVERY_PRECONDITION_FAILED. Полное состояние и запреты прежние. |
| RF15-005 | После создания нового credential и receipt настоящий PostgreSQL SELECT1/0 дал SQLSTATE22012. Восстановлены FROZEN/старые ключи/receipts. Повтор того же actionID и exact replay успешны. |
| RF15-006 | Новый writer реально выполнил prepare; старый ключ отклонён. Исходные запреты, полные строки и резервы не изменились. |
| RF15-007 | Два цикла создали ровно4recovery receipts. Следующий валидный fence отклонён с RECOVERY_COUNT_CAP без изменений; точный replay последней активации и новая writer-операция работают. Policy1, credentials5: пределы16/20 здесь не насыщались. |
| RF15-008 | Внешний rollback и reconnect восстановили UNIT-baseline. Отдельный readonly witness подтвердил полные строки/счётчики/sequence, OID52766/marker/роль/TLS. MAIN Head13/v2 и оба архива неизменны. |

Run: `ce8f3582-d68b-491c-88cb-6be64b257284`; native report: `work/dev15-recovery-20261103/recovery-ce8f3582-d68b-491c-88cb-6be64b257284-report.json`, SHA `8fada6722c8c9ae1ae3bab9491e4c41e81887ff80bd5453f3c2727c0f73e848e`. Collector: `work/dev15-recovery-20261103/final-result.json`, SHA `5b0619d0e7e7ef1d1f46cad00687c550aa7ec75adae37598740ae0c4b4771af2`. Независимое заключение: `work/dev15-recovery-20261103/independent-result-review.json`.

Прежние ресурсы: БД512МиБ/0,5CPU и один последовательный helper256МиБ/0,5CPU/PIDs64. Сверены7helper input/output/HMAC/CID/cgroup, source30/config24/EV63. Private ACL: 975объектов/1950правил до, 1060/2120после; только владелец/SYSTEM, reparse0. После Stop контейнеров0, manifest inactive, write permit пустой. До реализации сохранены113 изменённых файлов, перед native116.

Это настоящие транзакции PostgreSQL на точной UNIT с synthetic credentials/policy/runtime и внешним rollback. Диск физически не заполнялся. MAIN читалась только readonly; MAIN lease/activation/HTTP, APP/DEV-29, внешний провайдер, production и полный DEV-15 этим не подтверждаются. Runner/flush/teardown/миграции/reset не выполнялись. Прежние доказательства и отказы сохранены.

Следующий шаг — единая сверка RP15-001–020 с принятыми доказательствами и точное выделение оставшихся обязательных интеграционных проверок. Для новых MAIN-записей требуется актуальный signed context от Head13/b42ec…, старый Head10 Prepare не повторять. Старый сайт/VPS не затронуты, push не выполнялся.
