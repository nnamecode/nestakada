# Q031 — остаточное R2, revisions003–004

Текущая точка: D-546, revision004 independent APPROVED, residualR2 CLOSED; далее NOAUTH rehearsal/result review. Актуальные results/pins в последнем разделе; раздел revision003 ниже — сохранённая история.

D-542 → D-543. Исправление по новому конкретному post-await/parent-I/O boundary, без изменения согласованного контракта. Независимое подтверждение revision003 PENDING; это не approval.

Frozen package55 eb3970ae23ed7821d247113991139e7d83d9720053dcaff91155ac1be8d9bac6, COW work/dev29-bounded-20261104-resume007, прежний runId35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1. Checkpoint002 перед правкой source55+16 metadata: manifest SHA3ac464800bcf49c49e34f1eeb08330a9dbf801bae2443a4e67adb5d804130c48.

Заявленные изменения: clock check immediately after prove await до нового verify; actual hostOriginIO deadline=min(existing own/lease,current command parent), pre/post action guards, global verify precheck до host-key read. FULL keyState.verify не удалён и выполняется при validremaining. Уже начатое непрозрачное I/O не объявляется мгновенно прерываемым; после expiry новые ACL/FD/metadata actions запрещены, owned FD close остаётся safety cleanup.

Syntax5 PASS; target3 и focused40 PASS, skip0. Counter evidence: exact/late prove → postverify/ACL/FD0; valid remaining → полный actual originSession.verify с ненулевыми ACL/FD; firstACL overrun → nextFD0; late-return FD open → close1/read0. Target3 включены focused40. Затронутые stage19/review25/host33/guard10 PASS.

206distinctPASS: currentNode127 + reusedNode24(trace10/failurehost14) + reusedPython55. Reuse closure37 captured dependency/data files changed0/unknown0, previous/current hashes закреплены; независимые неизменённые наборы лишний раз не запускались. Ошибок correction-phase0. Root отдельно проверил55 source hashes и7 artifact hashes; код заморожен для q026_result_auditor.

| Артефакт относительно COW | SHA256 |
| --- | --- |
| revision003/package-manifest.json | 1139df4d2034ca868594a42d1de45bd5e38204c3c9c8238a4936edf87d5bce0d |
| revision003/delta-proof.json | f579bc8972f0c63094cfb89b255c17b39775ae105e94c82380fd6e5fa6035fb1 |
| revision003/static-protected-equivalence.json | 2310e70ab8bc8f81e4d80f798cb9394c3c5d8543927d6df8578c8dbb46b2c275 |
| revision003/offline-evidence.json | 5553bf5f14841232d525350c6f318ebbaa361d47b6e9de1f66e8e0120d88f83e |
| revision003/freeze-record.json | 1103cca7a55bbfceaa035b1a2184b90e8c5532b025d56f67bba58c84438538eb |
| residual-r2-reuse-003.json | 63198f73de884c962e6541aa4357c8b4d6560e79b848f2b5c781ddccc55a2a16 |

Operator addendum revision003/OPERATOR-ADDENDUM.md закреплён freeze-record, команды/handoff прежние. R1/R3–R7 CLOSED во втором review, не переоткрываются без нового свидетельства. Residual R2 должен независимо проверить reviewer на actual paths. До APPROVED никаких rehearsal/Prepare/native. Private/key reads/Prepare/Docker/SQL/native0, oneRun сохранён. Старый сайт/VPS/ACL не менялись. Этап8, DEV-29около35%, этап8около31%.


## Revision004 — запрет own10 renewal (2026-11-05)

D-545. Frozen package55 efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460, changed4 только own10/token fix/tests. Checkpoint003 manifest f8c9caf0d61e3362c2062691d038ab53d0a92bb70e1f8cea59ab529af163d93a. Исполнитель заявил captured preActionEnd, post min(capturedEnd,current shorter parent), actual Prepare/Run guardHostKeyRead с тем же token; FULL integrity verify сохранён. Независимое узкое rereview PENDING, это не approval.

Syntax4/rolling-provider target3/focused43/stage19/review25/host33/guard10 PASS. Targets: actual now+10s provider при parent90, t0→t15 отвергается без renewal; late open close1/read0, late fstat/read не запускает nextIO, manualhostkey overrun запрещает nextFD; earlierparent wins, valid<10 fullguard проходит. 209distinctPASS=currentNode130+reusedNode24+reusedPython55, skip0. Reuse37 dependency/data files changed0/unknown0. Target3 входят focused43, повторно не суммируются. Root55source/7artifacts independently hashes verified.

История коррекции: first HOSTKEY_PAIR_COUNT отказ после partial key-host save, controller untouched; exact known callback A1/B1 + SHA дали новое условие. Controller-only patch PASS, key-host mutation не повторялась. Prepare A имел guarded форму, Run B plain read; оба actual callbacks теперь guardHostKeyRead. После correction actualerrors0; вторых эквивалентных ошибок/STOP не было.

| Артефакт относительно COW | SHA256 |
| --- | --- |
| revision004/package-manifest.json | 0e3019819d46df35aa99edb4259b57a73c364467ffc656151866882cee7d367d |
| revision004/delta-proof.json | b67a9e40fb4ca95782be7fc7723925ccf600ceaa0221e6b78819852164733399 |
| revision004/static-protected-equivalence.json | 5043b330a86d9baad739ac1e68ae363ba096ff027e138493c4e45416bcfbb6ba |
| revision004/offline-evidence.json | d3399904bcc52f9534ada2b919b6c66132d0b36c6d051b90a63a681f1d915e91 |
| revision004/freeze-record.json | 0a377a8a58aa8d8db101aa55b28d67804cd3398f4a6bc2040d6999f903da07db |
| own10-reuse-004.json | 10f708dff5304207e7f34db85c92b127a0b70538e191f42cbcda9ecb8b016e11 |

Operator revision004/OPERATOR-ADDENDUM.md pinned freeze-record; основные commands/handoff неизменны. Старые artifacts/checkpoints/reports сохранены. Private/keyreads/Prepare/Docker/SQL/native0, oneRun unspent. Смена даты не сбрасывает разрешение, attempt/TTLs; будущая Prepare validity исчисляется по фактическим часам. До independent APPROVED нет rehearsal/Prepare/native.


## Независимый итог revision004 (D-546, 2026-11-05)

APPROVED, residualR2 CLOSED/findings[]. Независимый report SHAfa920c6517f4f7c3f9b53daff38ab6377cd3ff6030c0b4deaeb07a7e511c047e архивирован byte-identical code-review-004.md. Active code marker doc SHA f6b9a0b62b5ad5dab8b02fa3d5a63b7521415d55a8ba320d494ec16a680bc3a4, только current55 efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460. Все R1–R7 CLOSED. Code gate не заменяет NOAUTH rehearsal/result review и остальные runtime gates. Root status update first HEADER refusal не повторялось: decisionD546 был сохранён один раз, exact dated headers/count1 подтверждены до отдельных remaining docs writes. Recorder/private/Prepare/native0.
