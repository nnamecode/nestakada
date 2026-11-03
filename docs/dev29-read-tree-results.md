# DEV-29: просмотр дерева владельцем — результат

2026-11-03, D-403, TREE29-001–007 / DEV29-READ-01. **Ограниченный участок PASS; независимое code/result-review APPROVED.** Полный DEV-29 около5%, этап8 около31%.

Добавлен закрытый owner экран /manage/pages/: корень, переход в непосредственные дочерние разделы, хлебные крошки, точный PRIMARY URL, публикация и сохранённый публичный порядок. В интерфейсе порядок показывается с единицы: position+1; в БД position не меняется. Порядок списка админки отдельно по name/id, alias не подменяет primary. Внутренняя страница без primary показана без выдуманного адреса.

| Проверка | Результат |
| --- | --- |
| Доступ/приватность | Настоящие owner/employee sessions; анонимный и отозванная сессия401, employee403 доprojection. Private,no-store/VaryCookie на успехе/отказах. |
| Контент/целостность | Скрытый родитель и опубликованный ребёнок читаются владельцем; после GET Page/Route/версии прежние. HTML названий и точные queryURL экранируются. |
| Ошибки | Неизвестныйparent404; malformed/duplicate/лишниеquery400 без отраженияввода; POST405 безмутации; DBexception/corruptancestry503. Цикл вводился в чтение fixture, DBguards не отключались. |
| PostgreSQL/Django | Штатный foundationнабор160PASS за147.969с, skipped0, включая10новых TREE29проверок. Это реальный DjangoHTTP/middleware+PostgreSQL, не браузерные e2e. |
| Nginx | Два настоящих localHTTP GET: anonymous/manage/pages/401 и новыйCSS200, private,no-store/VaryCookie. Авторизованный owner browser/полныйdesktop/mobilevisual этим не подтверждены. |
| Сохранность | Host/frozen242sourcefiles совпали, sourceManifestSHA 7560574ef398e70068f8503c48869a712aebca093499912f4f555e87241c0dc7. Миграций нет; прежние124Git-изменения сохранены/внеразрешённыхdocsнеизменны. Foundation/trustконтейнеров0, тома/ключи сохранены; APP↔TRUST не подключался. |

APP run `726c3e87-6b0b-411d-b58b-7268a2afb910`. Сырой stdout/stderr Start/UnitTests/Stop и точные SHA9reviewedfiles — в `work/dev29-20261103/result.json`, SHA `449540e33164f54839d3ccbfa2e50d37fc47c04d5e9901b25b5492dca192438d`; независимое заключение `work/dev29-20261103/result-review.json`. AST4/whitespacePASS, tests/source присвоены только этому frozenrun, старый PASS не подменял новый.

Не реализованы create/rename/move/reorder/publication/changeURL/301/delete. Stable/история/медиа и главная не менялись; D-300/PR-07/08 сохраняются. Реальная запись потребует конкретной схемы durableintent/receipt/CAS и реальной gate/TRUST-интеграции для отзыва, а не подставного ACK. Новые таблицы/квоты/соединения согласуются отдельно по AGENTS.md до их реализации. Следующий участок — конкретизация безопасных команд дерева, затем их код/проверки после соответствующего согласования. Старый сайт/VPS/production/push не затронуты.
