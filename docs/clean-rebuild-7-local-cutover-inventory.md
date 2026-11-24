# R7C-INV-001 — read-only local topology inventory

Дата: 23 ноября 2026 года. Статус: `FAIL-CLOSED / SELECTOR ABSENT`, evidence approved. Первое independent release-gate review: `CHANGES_REQUIRED P0=0/P1=1/P2=2`; исправлены DB control-plane claim, stale gate table и неполная верхняя сводка. Repeat review: `APPROVED P0=0/P1=0/P2=0`.

## Граница выполнения

Выполнены только `docker ps/inspect`, `docker image inspect`, `docker network inspect`, SHA-256 локальных конфигураций и один read-only PostgreSQL metadata query с `default_transaction_read_only=on`. Контейнеры, сети, volumes и host bindings не создавались, не запускались, не останавливались и не переключались. Строки приложения и содержимое media не читались. Transfer, external copy, rehearsal, cutover, rollback, live/production и cleanup отсутствовали.

## Exact topology

| Компонент | Container ID | Image ID | Состояние | Host binding |
|---|---|---|---|---|
| foundation DB | `07558e4e011eb12b51e5586728dbf8cd2fc6752b973086e42295224fa843fd8a` | `sha256:de3d5ee43e308309e10730caead7dd880539d53f0275d977cd2f8c3f62b6eef7` | running | отсутствует |
| foundation app | `168e63ac0a485ae6472a748d6af59d921d47a60c15155cb90995ed5e0f7c7676` | `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986` | exited | отсутствует |
| foundation media-worker | `69ad87e827b463f3c61c10463d458dca8c7649c5286e4faff497aa78405d8497` | `sha256:6105f968d577220973fb9ed8e0caf3ba48a3e028d23d4d324059b4b4b3739f9c` | exited | отсутствует |
| foundation ingress | `006b1584fb11275fadc6ffc9e900ebe6faddc157e1011ad5604b3b09d5233c06` | `sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646` | exited | configured `127.0.0.1:8767`, inactive |
| RB5 preview app | `97e4acd16621174049f2b2d62c0ec4d4f90cd8b9e2d6af5208430f75c49e04cd` | `sha256:782f53c4a5e9473c5b93441adaac8da1ccbdcb93bc961a8d958c3b55c6e39986` | exited | отсутствует |
| RB5 preview ingress | `426c369b671ea4461dd67686f7caa57f560e673853a7fe45c72bdf8981d78f4c` | `sha256:a3b293bbab17bfd78d82d2392240d3d351501fba538ab82de1595b1d28d0d646` | exited | configured `127.0.0.1:18085`, inactive |

Все четыре image IDs имеют matching local repo digest. Все выбранные containers имеют `restart=no`; root filesystem у них read-only. Foundation DB присоединён только к internal network `639980a11e20f0a6a17e0da6610b2ebe19e02d26a748f8069816322de52d9eec`; web networks пусты, ingress networks не имеют attached containers. Public/production host binding не обнаружен.

Foundation compose config hashes: DB `c51b1ab164ebfde486388321d49b580eac8e8448ac8312162372e51d5f615f4c`, app `a06c70da3dec4b49d98cc97502e30da91dcc7ba61b8af0a3f40e2576a33b1213`, media-worker `d0dab17f1b2a3103ccbaea413a30035adc2d0f33c5e8aab655c4981d74053d7d`, ingress `e05c1a4a03346d19bcf846a6db9c606d5361bbbf1fbff6afc1fb9a5b84419f15`.

## Safe storage and configuration authority

- PostgreSQL metadata returned four non-template database/owner pairs; only their SHA-256 tokens were retained: `c5783cec182b59b090a8e0ff17a029b9b3c1a635299292ade746ada461ff0c27`, `27ac8ec917fd377a586e4a118330479b00f1646e01be9c27ec93a7f411598b1c`, `a1f9bdede3fb8ff75bb0deeba799fc3f449f260b880082290a8ca70b99b43716`, `df3660386f12638dfd2639bb68eebc0348b6d0e121dd9db25a24cf8159b11e24`.
- Foundation DB volume mount token: `656b31693026f469663d496fbc76484c67ac9f6cb06db4cb2e73822d71366c0d`.
- Foundation state and exchange mount tokens: `4be12c0a1d957aacbcf69925222b3ead3ce3135018cdc322daf961152ad92167`, `a985ddb945db2580de6bf349f2454fab9da142c9a4653390b632cfd754190c70`.
- RB5 preview media-facing read-only mount tokens: `/preview` = `a749617c70a4076f86ca078d3a54bbda5863f0259ebbca24c273fd69553b30e8`, `/srv/public-media` = `81b8e68f6852a58c72549b8e4ed4877cc31360334bde38b3acef4fb653895ed1`. Contents were not opened.
- Tracked config SHA-256: foundation compose `e1015cd4c8ff1ceadd2a04fffbb1f49c8aade1621a6dd6363938e014c4df785a`; foundation Nginx `900102c6579df7ff2c33ccbd4d62bc73798797e24509e9c1f6aa974d7805351e`; RB5 preview Nginx `eb12141e24120c19d869850fef4c656a5abee3a48390fa924bcced19686b29ad`.

## Selector и mutation bitmap

Оба Nginx config используют прямой upstream `app`; durable selector generation, pointer file, CAS precondition/token и отдельный observed-generation marker отсутствуют. Оба ingress остановлены, поэтому observed serving target = `NONE`. Ни foundation, ни RB5 preview нельзя честно объявить current local target; exact old rollback target также не назначен. Fresh `SEALED` new candidate отсутствует.

Фактический reachability bitmap на момент обоих Docker snapshots:

| Write path | Состояние | Основание |
|---|---|---|
| admin/editor | CLOSED | app и ingress exited |
| upload/media-worker | CLOSED | app и media-worker exited |
| request POST | CLOSED | app и ingress exited; candidate restore settings содержат `SERVICE_REQUESTS_ENABLED=False` |
| scheduler | CLOSED/ABSENT | отдельный service/container отсутствует |
| cleanup | CLOSED/ABSENT | отдельный service/container отсутствует |
| direct DB TCP host binding | CLOSED | host binding отсутствует; DB network internal и имеет только DB container |
| Docker exec/control-plane | AVAILABLE, вне application-writer bitmap | этим привилегированным путём выполнен разрешённый read-only metadata query; его доступность не позволяет заявлять полный direct DB access CLOSED |

Это reachability evidence, а не утверждение о вечной immutability: запуск app или присоединение нового container к DB network изменит bitmap и аннулирует inventory.

## Результат по acceptance

- `R7C-AC-002`: **PARTIAL PASS** — exact container/image/network/config/storage-token/bitmap identities получены без секретов и mutation; exact old/new/selector identities отсутствуют в самой топологии.
- `R7C-AC-004`, `R7C-AC-006`, `R7C-AC-008`: не запускались и остаются CLOSED.
- `R7C-INV-001`: **FAIL-CLOSED / BLOCKED FOR REHEARSAL**. Unknown не угадывался: current selector отсутствует, old rollback authority не определён, fresh new candidate отсутствует.

Перед `R7C-FREEZE-001` или rehearsal нужен отдельный reviewed source-only selector/observed-target design, который вводит минимальный durable selector CAS и exact old-target designation без controller daemon. Сам inventory не разрешает его реализацию или runtime-проверку.
