# Production VPS: bounded resource budget for 2 vCPU / 4 GB / 60 GB

Статус: предложение D-1064 от 2026-11-14, не утверждение достаточности тарифа и не разрешение заказа, SSH, настройки или deployment. По указанию владельца этот документ и дальнейшая инфраструктурная проработка ведутся в отдельном VPS-чате; разработка продукта продолжается в чате «ворк2».

## Область расчёта

Расчёт относится только к минимальной уже согласованной схеме: один Nginx, один Django application container и один PostgreSQL container. В него не входят ISPmanager, Apache, PHP, MySQL, Prometheus/Grafana, собственный backup/monitoring server, очередь, CRM и другие новые сервисы.

Исходная арифметика использует ровно 4096 MiB RAM и не менее 54 GiB доступной ёмкости целевой Linux-файловой системы после установки ОС. Маркетинговые 60 GB дают около 55.88 GiB до разметки и служебных расходов, поэтому `54 GiB usable` — обязательный будущий admission check, а не предположение. Если фактический `MemTotal` меньше 4096 MiB или usable disk меньше 54 GiB, этот бюджет недействителен и deployment не начинается.

Текущие локальные ориентиры не являются production-замером: исходные media занимают 90,130,604 bytes (около 86 MiB), а `app/` — 4,861,400 bytes. Локальный Compose задаёт потолки PostgreSQL 1 GiB, Django 768 MiB и Nginx 128 MiB; production application server и production-данные ещё не измерены.

## RAM и пиковая одновременность

| Потребитель | Жёсткая граница, MiB | Условие |
| --- | ---: | --- |
| Хост: kernel, systemd, Docker daemon, SSH, security update | 896 | Не отдаётся контейнерам |
| PostgreSQL container | 1024 | Включает процессную память и его tmpfs |
| Django application container | 768 | Один ограниченный application contour; число workers выбирается только после замера |
| Nginx container | 128 | Один worker для стартового профиля |
| Обычный максимум | 2816 | Хостовый резерв включён |
| Один временный job: migrate, backup, restore-check или deploy preflight | 512 | Строго один; restore выполняется при остановленном обычном приложении |
| Пиковый максимум | 3328 | 2816 + 512 |
| Неприкосновенный запас до 4096 MiB | 768 | Для кратких всплесков и предотвращения OOM |

Tmpfs не прибавляется второй раз поверх container memory limit. Media worker, если он вообще понадобится в production-процедуре, считается временным job внутри тех же 512 MiB, а не четвёртым постоянным сервисом.

Предлагаемый swap: один 2048 MiB swapfile, `vm.swappiness=10`. Swap нужен как аварийный амортизатор, но не считается RAM и не разрешает превышать таблицу. Любой OOM, устойчивый swap-in/swap-out либо peak RSS выше границы означает `FAIL` и повторный выбор ресурсов/настроек.

## CPU и пик операций

Для двух vCPU стартовый ceiling контейнеров предлагается таким: PostgreSQL `0.70`, Django `0.70`, Nginx `0.20` CPU; обычная сумма `1.60 vCPU`. Один live-safe backup job может получить не более `0.20 vCPU`, оставляя около `0.20 vCPU` хосту. Миграция, restore, image cleanup и переключение release не совмещаются с backup и друг с другом. Restore выполняется в maintenance/rollback режиме, не параллельно с обслуживающим запросы Django.

Это стартовый предел, а не обещание производительности. До признания тарифа достаточным нужны измеренные smoke/load results на production-like образах: отсутствие OOM, timeout и устойчивого swap, плюс приемлемое время backup, migration и rollback при указанных ceiling.

## Диск: полный бюджет 54 GiB

| Область | Ceiling/reserve, GiB | Что входит |
| --- | ---: | --- |
| Разметка/filesystem/provider uncertainty | 2 | Разница raw и usable, служебные данные FS |
| Ubuntu host и packages | 6 | ОС, Docker/Compose plugin, SSH, firewall, unattended security updates |
| Swapfile | 2 | Ровно 2048 MiB |
| Docker images/layers | 8 | Текущий и предыдущий release, нужные base layers; build cache не бессрочный |
| PostgreSQL data + WAL | 2 | Одна production DB; рост выше порога останавливает release/backup rotation |
| Media | 2 | Оригиналы/производные в утверждённой модели, без Git-копий |
| HTML current/previous и operations data | 1 | Два fallback-поколения и малые manifests/ledger |
| Project technical logs | 1 | Утверждённый общий предел файловых логов проекта |
| Host/journald/security logs | 1 | Отдельно от project log quota |
| Local backup zone at peak | 12 | Retention current/previous плюс одно новое staging-поколение; worst case 4 GiB каждое (DB dump + media) |
| Release/rollback staging | 4 | Код/config artifacts и один подготовленный rollback release |
| Update/download temporary space | 3 | Параллельное получение нового образа/package без удаления last good |
| Неприкосновенный recovery reserve | 10 | Не занимать обычной работой; stop-gate для обновления, backup и deploy |
| **Итого** | **54** | Никакого двойного счёта за пределами строк |

Ceiling PostgreSQL 2 GiB и media 2 GiB — эксплуатационные лимиты первой версии, а не прогноз их фактического роста. При достижении 75% любой из этих двух квот требуется оценка; при 90% запрещаются необязательные записи/новый release до освобождения или расширения. Неприкосновенный общий reserve 10 GiB проверяется до image pull, backup и deployment; операция не начинается, если её рассчитанный peak нарушит reserve.

По D-593/D-598 действующий no-bloat contract — retention ровно двух поколений в локальном месте и двух зашифрованных поколений во внешнем месте; старые семь внешних точек заменены и не являются текущим требованием. Safe rotation peak в каждом месте равен трём поколениям: current+previous+candidate до checksum/readback verification, после которой кандидат продвигается, а старейшее поколение удаляется. External storage не считается частью 60 GB, но его quota/cost gate обязан вместить три encrypted generations вместе с ciphertext/format overhead.

54-GiB budget допустим только при потоковом client-side encryption/upload: проверенное локальное поколение читается один раз, ciphertext сразу передаётся внешнему хранилищу, а на VPS не создаются второй plaintext archive, полный ciphertext file, upload cache или retry spool. In-memory encryption/transfer buffer ограничен 128 MiB и входит в общий transient-job ceiling512MiB; сетевой ciphertext overhead хранится только во внешнем месте. Если выбранный инструмент требует materialized ciphertext/temp, этот budget автоматически `BLOCKED` до добавления измеренного disk ceiling или выбора большего тарифа. Rehearsal измеряет filesystem free-block high-water до, во время и после backup/encryption/upload, а не только размер конечного generation.

## Что ещё не доказано

Тариф нельзя признать достаточным до получения всех следующих результатов:

1. В новой VPS read-only подтверждены `MemTotal >= 4096 MiB`, usable filesystem `>= 54 GiB`, 2 vCPU и Ubuntu Server 26.04 LTS amd64.
2. Зафиксированы фактические размеры production images, PostgreSQL, media, fallback HTML и одного полного backup generation; каждый укладывается в свою строку.
3. Production-like Nginx + application server + Django + PostgreSQL проходят smoke/load с peak memory `<= 3328 MiB`, без OOM и устойчивого swap.
4. Один serialized backup и одна migration rehearsal по отдельности проходят CPU/RAM/disk ceilings; local backup peak сохраняет current+previous+candidate и 10 GiB recovery reserve. Encryption/upload rehearsal отдельно доказывает no-materialized-copy boundary, buffer<=128MiB и минимальный free-block high-water всего filesystem; external rehearsal доказывает quota для three-generation encrypted rotation peak, checksum/readback candidate verification, promotion и только затем retirement oldest при retention2.
5. Restore rehearsal и rollback доказаны на изолированной копии; время и временный диск измерены.
6. Проверены log rotation/quota, Docker layer cleanup без удаления running/rollback image и stop-gates 75%/90%/10 GiB.

До этих измерений итог — `CANDIDATE, SUFFICIENCY NOT PROVEN`. Если любой hard gate не проходит, варианты только два: уменьшить фактический объём/нагрузку без потери требований либо вернуться к тарифу с большим запасом. Поднимать лимиты на бумаге или считать swap дополнительной RAM нельзя.

## Следующий ограниченный этап

После утверждения владельцем этого бюджета можно подготовить provider-neutral минимальный список host packages и настроек: Docker/Compose, SSH, firewall с `DOCKER-USER`, security updates, quotas, TLS, secret files, external backup/restore, external monitoring и последовательность deploy/migration/rollback. Это будет проект конфигурации, не её применение.
