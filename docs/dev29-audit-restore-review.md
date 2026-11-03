# Независимое ревью read-only preflight и уточнения Q008

2026-11-03. **READONLY-AUDIT-PREFLIGHT-REVIEW-001 APPROVED** для документа `dev29-audit-restore.md` и вынесения Q008 владельцу. Это не разрешение восстановления и не runtime-допуск.

Рецензент независимо подтвердил по исходникам корректность текущего STOP: Q007 A.2 прямо запрещает автоматически создавать отсутствующую сеть; audit-preflight и controller.dbBoundary требуют running DB и точную internal сеть. При обнаруженных0контейнеров/0сетей вызывать Observe/Audit нельзя — допустимых фактов нет, но появятся ошибочные lock/attempt артефакты.

Сверен реальный tools/local_trust.mjs: Stop использует compose down без -v, сохраняя том; Start вызывает init/migrate и поэтому не подходит Q007. Compose подтверждает named dbdata, три internal named networks, DB512МиБ и отсутствие host ports. Предложение разрешает только первоначальные temporary ресурсы, не новую архитектуру сайта.

Достаточные условия уточнения на уровне документа: RO-volume/network-none/bounded inspector до writable DB start; отказ при недоказанной инициализации/неверном volume/image/foreign object; прежний DB service без build/pull/init/migrate/API; фиксация полных IDs; fresh signed Observe/Audit/result-review; cleanup только своих ID+labels и пустых network endpoints; запрет down -v/удаления тома. WAL/recovery изменения обычного старта оговорены и не выдаются за побайтную неизменность файлов БД. Metadata тома не заменяет свежий SQL witness.

Новых замечаний P0–P3 нет. Рецензент Docker/SQL/Observe/IssueAudit не запускал, файлы не менял. Одна ошибка локализации local_trust.mjs сразу сообщена; затем прочитан точный tools/local_trust.mjs, повторной эквивалентной ошибки не было.

Инвентаризация координатора сохранена в ignored `work/dev29-publication-20261103/pg-check/host-preflight-inventory.json`, scope explicitly not-admission. Восстановление, volume mount, SQL и Audit не выполнялись. Следующий шаг требует ответа Q008 и code/QA-review конкретного inspector/recovery перед исполнением. Q007 повторно не согласовывается, Run/fixture writes закрыты. DEV-29 около35%, этап8 около31%.
