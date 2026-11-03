# DEV-15: отрицательные TLS-проверки

2026-11-03, D-393/D-394, RP15-017 / TN15-001–006. Локальный TLS-набор и завершённое независимое result-review — **APPROVED в ограниченной synthetic transport области**. Пауза DEV15-TN-RESUME-001 снята владельцем;128SHA/копий сверены. Certificate-only DER collector проверил отдельно CA, затем valid/wrong/expired с остановкой при первой ошибке. Повтор native и запуск БД не понадобились. DEV-15 около97%, этап8 около28%.

Проверены неизменные Nginx/config и fixed worker на существующих Python/Nginx images. Использованы два прежних слота256/128МиБ и0.5/0.25CPU, только согласованная внутренняя API-сеть; после неё осталось0контейнеров, созданная этим запуском пустая сеть удалена. PostgreSQL не запускалась, MAIN lease не выдавался, настоящие ключи не монтировались. Публичных портов, нового софта или постоянных настроек Windows нет. Старый сайт/VPS не затронуты.

| ID | Фактическое наблюдение |
| --- | --- |
| TN15-001 | TLS1.2 иTLS1.3 handshake PASS, fixed worker через штатный isolated subprocess получил точный synthetic head. После всех отрицательных вариантов positive повторён успешно. |
| TN15-002 | Wrong CA: direct verify code20 и fixed worker `SNAPSHOT_TRANSPORT_REJECTED`. |
| TN15-003 | Wrong SAN: verify code62. С тем же сертификатом и правильным именем `wrong.invalid` TLS1.3 PASS. |
| TN15-004 | Истёкший leaf с правильными CA/name: verify code10, notAfter2021-01-01. Системное время не менялось. |
| TN15-005 | TLS1.0/1.1: реально сгенерированы и отправлены ClientHello154/157байт, версии0301/0302. Получены server fatal alerts `15030100020246` / `15030200020246`, description70 protocol_version. TLS1.2 после них PASS. Это server rejection, не локальное отсутствие cipher/protocol. |
| TN15-006 | Source30 host/frozen, config24, EV63, исходные manifest/env/cert/key и прежний MAIN final-result SHA без изменений. Final0контейнеров/пустой permit/созданная сеть удалена; ACL до ключей2объекта/4правила, после23/46, owner/SYSTEM, reparse0. |

Реальный успешный run: `85b53dbd-0cf4-4d7d-87b1-100ad4727f21`. Native report `work/dev15-tls-negative-20261103/result-85b53dbd-0cf4-4d7d-87b1-100ad4727f21.json`, SHA `c3f001248ccc25065226da871ad427566aa44b0a277cf299ca4216ef4ca52075`: шесть native groups, включая восстановленный positive. Collector `final-result.json` SHA `eab2a07c8d0f6101e75ab4336c5016880a223eac7a31a2b001036726420e39f1` отдельно проверил кейсы, hashes/HMAC synthetic intent и фактический Stop. Ключ synthetic intent обеспечивает целостность тестового пакета, не полномочия записи MAIN. Raw fixtures/keys/transport metadata находятся только в ignored private/work.

До успеха сохранены реальные отказы: preflight на отсутствующей после Stop сети, два ранних вызова WinPS5.1 (ExecutionPolicy; затем унаследованный PS7 Security module) и первый TLS-positive на тестовой CA безkeyUsage (строгая проверка verify92). Причины диагностированы отдельно; исправления прошли независимый review и целевую проверку. В WinPS5.1 изменяется только окружение дочернего процесса. В CA добавленыkeyCertSign/cRLSign и строгая проверка до ingress; настройки TLS-клиента прежние. Ни один FAIL не переименован в PASS, данные/архивы не сбрасывались.

## Границы и продолжение

Это RP15-017 для настоящего TLS-транспорта с synthetic responder. Django/auth/SQL0, нагрузка и новый полный снимок этим не проверялись. БД не открывалась: последний принятый MAIN Head13/epoch2/policy1 и v2b42ec… остаётся последним SQL-свидетельством D-392, не новым наблюдением. Не запускать старый lease Prepare с baselineHead10.

Остаются RP15-015 SQL/disk-error injection и серверная partial-body граница; RP15-016 active/rate gates; RP15-018 body/header/slow/privacy/log-canaries; остатки recovery/отказных окон RP15-007/019. Потребуется актуальный подписанный контекст от Head13 для работы с MAIN, без сброса данных и новой policy. Весь DEV-15/APP/DEV-29/production не объявлены завершёнными.
