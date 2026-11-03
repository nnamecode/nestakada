# DEV-29: фактический допуск восстановления continuation-стенда

2026-11-03. **CONTINUATION-ACTUAL-START-REVIEW-001 APPROVED** для одного немедленного неизменного DB-only compose up по Q009/Q010/Q011/D-425. Review не является fixture/Run-допуском: после старта обязательны fresh Baseline/Authorize и отдельное actual payload review.

Независимо подтверждены Verify/runtimeAdmitted=false, exact plan/checkpoint/source/protected/package/ancestry/full frozen focused/saved-first/report/review/owner bindings. Before HMAC/validateBudget PASS, VerifyStart PASS с full Verify/подписями/повторным inventory/images/retained volume и отсутствием exact named/labelled ресурсов.

| Артефакт | SHA256 |
|---|---|
| Plan canonical | a7959d12560ff085b0e333357d9b6d16565e4678149582530e43e540497c30e2 |
| Plan raw | 3b3817de5c392a0e3011df5e918e434fdb099ccb71350e7824f67cef6d151937 |
| Checkpoint raw | c62d86d81ab4f8b95a2392faffe3ca1e0c404f759c1f8b3309f81d8643d16e0d |
| Budget-before raw | 8b4da5646b9e39ec22cf21d963d6983acfd48e26b3a45305da90eadab56d75d2 |
| Code-review raw | 132b56718f1ff48f47c4f9d7f8c2ce5899b9e61ca3b43defe4d7d33336544a7b |
| Accepted saved report raw | 18737e3022ddd8d35b721ac790fa1172e00826462d4f0c6c4bc49a5e0aaa0787 |

Budget340,295,283<2,147,483,648байт, age при review около50,6с<15мин. Рецензент файлов не менял, Docker start/SQL не выполнял.

Первый Before остановился STORAGE_DOCKER около10с, helper/receipt отсутствовали. Последующие отдельные readonly inventory/volume PASS; инструментированный Node→Docker volume inspect202ms/status0/errornull. Единственный повтор Before7,4с PASS и VerifyStart5,5с PASS после нового свидетельства работоспособности. Caps/timeout/profile/code не изменялись; ошибки не выданы за успешный первый запуск.

После APPROVED координатор выполнил только прежний DB-only compose `--no-deps --no-build --pull never db`: DB8f25760397f53d38a940d1ce49c494169dcf672c03ff6f18b4c3aa96ccc742d4, network194a3f327258d89080a070b442583c2cc770dc20f18f4f45b09885adad7ea2ed. Baseline PASS, receipt577c7ca18093d594df45dd7842e6b3ff317f56425205219a06ffe731bfc44f57; Authorize PASS четырёх групп. Init/migrate/API/pull/build не выполнялись. Старый сайт/VPS не затронуты.
