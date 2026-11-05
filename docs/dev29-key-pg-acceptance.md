# KEYPG — приёмка согласованной интеграции

D-528/Q031, finalplan df2c00f148f581c6f4113ccfe2febf4c76d385bfd2e36ccca87b3c44be184311. Ниже traceability уже утверждённых критериев, без расширения scope.

| ID | Сценарии и ожидаемое поведение |
| --- | --- |
| KEYPG-A01 | Prepare: source FD/core/ACL stable, origin tag32B exclusive/regular/nlink1/protected/readback, plan публикуется последним. Stage отсутствует, public key digest/tag/tagHash отсутствуют. Partial Prepare не даёт admission; unknown ownership не превращается в absence. |
| KEYPG-A02 | Run: writer10001:GID999/640 удалён до reader999; reader open квалифицирует SAME stage и все8 точных DB RO binds без byte read. Credential/identity failure закрывает INIT/network/DB, без ACL/UID/copy fallback. |
| KEYPG-A03 | host-key continuity до tag; tag-read ровно32/original+copy-read≤8192 через pinned FD. Original MAC проверяется при каждом прежнем verify от Prepare; staged MAC равен ТОМУ ЖЕ commitment после qual. Same-size/same-mtime byte drift любого key обнаруживается. |
| KEYPG-A04 | Подмена host-key/tag/ref/receipt/core, потеря RAM, wrong state и expired clock запрещают dependent PG. Persistent tag не позволяет resume/replay; PENDING/QUALIFYING не запускают DB. |
| KEYPG-A05 | Actual START/INIT/PAYLOAD-C/C/PAYLOAD-T/T: own reviewer source/direct publish, final monotonic check после validation/proof-write и перед action. Window120/parent wins, old admission expiry/minimums не продлеваются; NOAUTHORITY не admission. |
| KEYPG-A06 | Prepared validity900 signedUTC отдельно от copy3600/work3000/cleanup600 на одном Run clock. Unknown budget/недостаточный operation+next-dependency reserve закрывает dispatch; нет renew/retry, all-max success/crash cleanup не обещаются. |
| KEYPG-A07 | ALL create intents (stage/PG network/DB/helpers/inspectors) и holders закрыты перед stage/tag unlink. Empty inventory не закрывает incomplete create. Inner rollback/witnesses/original-after/sameengine owned0 идут до stage/tag удаления. Content failure не блокирует доказуемую safety cleanup; unknown identity→UNPROVEN без unsafe unlink. |
| KEYPG-A08 | Exact image/UID/mount/caps/private propagation/read-only policy; invalid API types/source/target/options запрещены. Fixed split projections≤4096, нет потерянных argv/security checks или extra mounts. Old SQL/workers/supervisor/capture/protocol functional equivalence сохраняется; только новые runId/pins отдельно доказаны. |
| KEYPG-A09 | Нет key bytes/private tag/tagHash/content-derived TLS digest в public output/ledger/Git/generic exports. Tag — special metadata-only private input, never mounted. Invalid secret streams/ошибки не раскрывают raw/hash. Source old corpus/MAIN/archives/history/checkpoints/late records сохранены. |
| KEYPG-A10 | Syntax/static/offline/code review→oneNOAUTHrehearsal≤80x6/global490/review→onePrepare→readiness≤10/reviews/dispatch→atmostoneRun INIT/C/T. Actual1000/1001 +139 без skip, rollback и2sequentialwitnesses/ROafter/terminal proofs; старые5+8 не повторяются. Это не завершение всех P29-A/leases/crash/APP. |
| KEYPG-A11 | Cancel/expired/unused Prepare: append cancel marker до owned tag unlink, Run закрыт; host-onlycancel≤30. No autoerase при dead coordinator, unknown/partial states честноUNPROVEN. Обычные старые inputs/corpus не удаляются. |

Offline данные только dummy/mocked, actual original/copy/tag не читать и не создавать до code APPROVED и предусмотренных допусков. Runtime acceptance запускается лишь root в пределах Q031, максимум один Run, включая отказ до SQL. Старый сайт/VPS/production/push исключены.
