# KEY27 — приёмка разрешённого Q027

Трассировка утверждённого плана 1c41207483be3972741f43b60140af55fb6558b2738e90d9598d4486bb5164eb и D-504. Это идентификаторы уже согласованных критериев, без расширения архитектуры.

| ID | Сценарий и ожидаемый результат |
| --- | --- |
| KEY27-A01 | Только exact original source regular/nonreparse и ограниченная Windows ACL; любое несоответствие до create — fail closed. |
| KEY27-A02 | Exact endpoint/engine/pinned image и чистый уникальный runlabel; несоответствие — без нового helper. |
| KEY27-A03 | CREATED inspect подтверждает UID999:999, один RO filebind, networknone, caps/ресурсы/отсутствие extra mounts и ports до start. |
| KEY27-A04 | Helper отдаёт только согласованный JSON, без байтов ключа/Env/traceback; uid/gid999, regular/nonsymlink. |
| KEY27-A05 | Read-open successful: fstat identity/type/size совпадают со stat, fd закрыт; open failure: только разрешённый errno и identity=null. Отказ — диагностический результат, не повтор. |
| KEY27-A06 | Неизвестные поля/невалидные значения/ошибка identity/source drift — fail closed, без staging/исправлений. |
| KEY27-A07 | Readiness/command/helper/output/global лимиты соблюдены; превышение — отказ и ограниченный cleanup, без renewal/retry. |
| KEY27-A08 | Удаляется только exact owned immutable container на том же engine; чужой id/label/engine не допускает mutation. |
| KEY27-A09 | После штатного/ошибочного результата доказаны absence helper/new owned networks/volumes и source metadata/ACL unchanged. При неполном proof честный UNPROVEN. |
| KEY27-A10 | Один native attempt: повторный запуск запрещён; SQL/PG/staging/keycopy/ACL/pull запрещены. |
| KEY27-A11 | Code hash freeze и независимое review до native; после — отдельный result audit. Offline fixtures не выдаются за native evidence. |

Offline проверки покрывают опасные отказы и границы. Фактический Q027 даёт только один разрешённый исход (read-open success либо отказ) и настоящий cleanup; обе ветви на реальном ключе повторными запусками не проверяются.
