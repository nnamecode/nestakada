# Q031 — исправления первого независимого code review

D-540 R1–R7, D-541 revision002. Исполнитель заявил устранение семи замечаний, независимое повторное review PENDING. Это offline evidence, не approval и не runtime acceptance.

COW work/dev29-bounded-20261104-resume007, runId35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1. Новый frozen package55 14bbe843bdbeafec4f6e337ce0ea3ff78d96f052b1a018b3bda4fda66f71e45b, изменены7 source files. Первый frozen checkpoint55+26 metadata manifest3ce282c312c7d9cadc1088f76f1b91b73ae18d67f3386442caddbe4393242759 сохранён. Первый report byte-identical docs/dev29-key-pg-integration-code-review-001.md SHA41d900d4bc17c193f39f41fda6b7f325d57a009a6d845fadec57477982601ba0. Старые root manifest/evidence исторические и не являются текущим package authority.

| Замечание | Заявленное исправление, ожидает независимого подтверждения |
| --- | --- |
| R1 | Нет EOF extra read, предел total8192/32, pinned FD after metadata checks сохранены. |
| R2 | Actual Original-after adapter использует cleanup lease budget для verify/rawDocker/capture и whitelist инспектора; FULL keyState.verify и post-await/final guards сохранены. |
| R3 | Production stageCallAdapter разделяет full work verification и узкую owned safety stop/remove/RO proofs с role/nonce intent/code/owner/host-key authority; safety create/start запрещены. |
| R4 | Composite связывается с фактически сохранённым signed result raw ledger hash после authenticated metadata/identity readback. |
| R5 | Actual bindQualifiedFlowIO содержит qualification; missing/failed/repeated qualification закрывает PG до mint; same8 sources/receipt проверяются. |
| R6 | Общая exclusive lifecycle claim RUN/CANCEL до tag effects, marker/readback и crash failclosed. |
| R7 | Actual cleanDirectoryWithIo сравнивает pinned copy identity перед unlink. Qualified missing/null pin → UNPROVEN до FS; retained stageDirectory выставлен до потенциальной ошибки host metadata. |

203 distinct PASS, skip0: текущие Node148 (focused37, stage19, review25, host33, guard10, trace10, failure-host14), переиспользованные Python55 из предыдущего исполнения с exact previous/current source hashes в evidence. Target11 входят focused37, повторные исполнения не суммируются. Changed syntax7 и последний changed syntax4 PASS, затронутые suites после исправлений PASS. Protected24 и baseline50 сохранены. Ошибок инструментов/проверок при этом correction phase не было. Координатор отдельно проверил55 current source hashes и9 public artifact hashes.

| Артефакт относительно COW | SHA256 |
| --- | --- |
| revision002/package-manifest.json | 123e1d0e9aee6e4085eb96cf078dcabad10c8d2ac3618de9e90b39530f019e40 |
| revision002/delta-proof.json | 0d9e434422db319ffc816c3259faa573b6872fc81076762d1df5a75fabd8865c |
| revision002/static-protected-equivalence.json | 08f8f6c41bc3dd398e096b794997ba04370644f84805ee1714383e3e25128a04 |
| revision002/offline-evidence.json | 0c21ccf9074b3fa167bcc83e2d2a35c27100cd16ccca835759e7dec14b94c59b |
| revision002/freeze-record.json | bba206ebb96d282de621e48fb13cf6f7742a1d409738b8fbcbe4e1d47f4f981b |

OPERATOR-COMMANDS.md и real-host/review-handoff.json byte-identical; revision002/OPERATOR-ADDENDUM.md закреплён freeze-record. Current runtime package admission и все R1–R7 должен проверить q026_result_auditor. До APPROVED нет rehearsal/Prepare/native. Private/key reads/Prepare/Docker/SQL/native0, единственный условный Run не использован. Старый сайт/VPS и ACL не изменялись. Этап8 «Код», DEV-29 около35%, этап8 около31%.
