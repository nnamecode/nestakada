# DEV-15: итог локального компонента

2026-11-03, D-402. FC15 PASS; **независимое итоговое result/completion-review APPROVED. DEV-15 готов в согласованной локальной области (100%), этап8 около31%.**

Конечная [матрицаRP15-001–020](dev15-final-coverage.md) сопоставляет требования с принятыми131регрессиями, ёмкостью, TLS, операторским допуском, run lease, нагрузкой, приватностью, rollback и recovery. Gap-review оставил только FC15-001–005; новый код самого компонента не менялся.

| Проверка | Фактический результат |
| --- | --- |
| FC15-001 | Созданы16policy rows. Точно подписанный запрос запрещённогоepoch17 отклонён с ADMISSION_INTENT_REJECTED; полный state до/после одинаков, история16 сохранна. |
| FC15-002 | После отказа работают read_head/operation_status/snapshot_manifest/snapshot. PENDING_DENY и резерв не изменились от чтения. Новая разрешённая операция и completion прежней успешны; точные повторы prepare/terminal вернули прежние receipts без изменения state и истории16. |
| FC15-003 | Внешнийrollback/reconnect и независимый readonlywitness: UNIT52766/marker/emptyrows/sequence прежние. MAIN Head13/epoch2/policy1/v2b42ec… и оба закрытых архива before/after совпали. |
| FC15-004 | DBdata directory 256253952байт; все24host roots 64271909байт; резерв Dockerlogs8МиБ и конечныхартефактов8МиБ. Итого337303077байт, около321.68МиБ <2ГиБ. WAL/temp/relations/index/TOAST уже внутриDBdirectory и повторно не складывались. |
| FC15-005 | Source30/config24/EV63/manifest/env/keys без drift; семьhelper HMAC/input/output/CID/cgroup совпали. ACL1060/2120до и1145/2290после, толькоowner/SYSTEM/reparse0. Контейнеров0, permit пустой. |

Native run `64f0a5b5-22cf-4f98-9bda-70d5aa840358`, отчёт `work/dev15-closeout-20261103/finalcontrols-64f0a5b5-22cf-4f98-9bda-70d5aa840358-report.json`, SHA `f0ecc7ce7c0517998451e255ca489222ae843372468f687e1cc28855da6a0896`. Collector `work/dev15-closeout-20261103/final-result.json`, SHA `9ac9375667abe40e356faf2ea63a114c961f9ec9c3ebde10f74b73a909521b36`. Gate15файлов; перед native сохранены122файла. Node/PythonAST2 PASS;4VMnegative/positive budget-parsercase не выдаются за реальные ресурсные измерения.

Измерение бюджета снято после helper/архивныхпроверок доStop; hostscan дополнен резервом конечныхфайлов. Это observedbudget, не hardquota или точное postshutdown allocatedsize. DBmemory peak335011840/536870912байт, OOM0; отдельныеhelper peaks записаны вnative report. Пики разных периодов не складываются.

Прежние исходные ошибки и отказы сохранены. В этом инкременте до запуска была исправлена статическая ошибка экранирования pathseparator в сборочном черновике; готовый controller прошёлsyntax/VM/независимоеcode-review. Проверки приложения наVPS, physicalpowerloss/внешнийTRUSTrollback, APP удаления/HTMLadmission и production не выполнялись. Код самого журнала не изменялся; полный131/TLSснимок повторно не запускались без причины.

Локальная область DEV-15 — независимый journal/head, долговечные запреты, signedboundedwriter, replay/recovery и проверяемый snapshot. Будущая интеграция APP и удаление страниц — DEV-29; внешнее размещение/стоимость/провайдер, DEV-16/23/26/27 и общие TEST/READY сохраняют свои открытые условия. Старыйсайт/VPS не затронуты, push не выполнялся.

Итоговое completion-review принято. DEV-15 отмечен готовым локально; следующая область для владельца — DEV-29. Автоматически её код и production не начинать. Для будущего MAINwriter потребуется актуальный signedcontext от Head13/b42ec…, старый Head10Prepare не повторять.
