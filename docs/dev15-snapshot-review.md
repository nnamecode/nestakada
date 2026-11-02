# DEV-15 — независимое ревью полного снимка и стартового клиента

2026-11-02, D-377. Автор product/probe unit: shared_contract; координатор: docs/infra/native host/probe; независимый readonly-рецензент: combined_review. Рецензент не меняет артефакты и не исполняет среду.

Precode gate SS15-001–009 положительный; reader-only manifest/client входят в принятый D-374 протокол, новых ресурсов/зависимостей/внешнего подключения нет. Дополнительного owner architecture gate не требуется.

Уточнение ревью до реализации: socket interread timeout не доказывает абсолютный deadline. Принят stdlib subprocess в прежних caps с общим communicate/kill/reap и absolute remaining30. Actual slow-output child по тому же production path плюс native fixed TLS worker дают достаточное свидетельство; отдельный TLS-drip сервер не требуется.

Code/QA gate положительный на один Start disabled →97unit→finallyStop. Проверены fixed argv/no shell/no external command override, reader secret только stdin, bounded child output до write, kill/reap и single child на запрос; схемы/counts/cursors/дубли/полный digest/cohort, отсутствие HTML authority. До запуска уточнён regression: continuous byte/flush50мс вместо одиночного byte→stall, timeout0.3с/elapsed<2/reap unchanged. ТестSHA413bed…; consumer5e89ca8a….

Actual97 PASS85.901с на source3319caa3… независимо прочитан, все36source/config SHA в native gate пересчитаны — drift0. Unitbudget295397234B, DBpeak287252480B/512МиБ, OOM0. Условный native gate после actual97/currentSHA/inactive/disabled/`{}` выполнен; один readonly native прогон затем завершился PASS. Host a397b891…, probe b03e2a65…, local_trust1262a205… проверены отдельно. Внешний finallyStop независимо от результата harness выполнен.

Нативный срез фактически PASS:3фазы/7экземпляровгрупп(3+1+3)/19HTTPSзапросов на том же source3319caa3…; настоящий ingress outage и API PID restart не изменили MAIN full-state/head/snapshot digest. Прежний archive report после прогона совпал целиком, finallyStop PASS. Общий writer profile не открыт, MAIN записей не добавлено, сайт не развёрнут.

Итоговый result/doc gate положительный. Рецензент лично сверил actual97/native/resource/archive, все36reviewSHA повторноdrift0, manifestinactive/disabled. Подтвердил корректные границы RAM последнихcgroup-периодов, наблюдаемого budget и ограниченного reader/startup-среза. Мелкие уточнения исторического времени и повторяющихся групп внесены; материальных блокеров нет.

DEV-15 остаётся в работе, около95%; этап8 около28%. Следом — сверка оставшихся локальных условий перед DEV-29. Полный MAX/capacity/general writer admission, APP/gate и физический ARC-10/production этим результатом не закрыты. Рецензент ничего не менял и не запускал; все прежние данные/ключи/архив и unrelated source сохранены.
