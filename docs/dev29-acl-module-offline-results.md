# ACL module context — PUBLIC offline patch proposal

D-554,2026-11-05. Независимое review APPROVED (D-555), findings[]. Это не активный runtime candidate и не code admission/новая Prepare. Current efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460 source55/codedocf6b unchanged; частичный PRIV6files808B RETAIN/UNPROVEN не затронут.

Исходная причина/границы: docs/dev29-key-pg-prepare002-failure-review.md SHA4d20421a1143994e69c26583e2cb0d89bb7f07b16a34dc3c7c14a296cb1090ee. Прямой read-only contrast исходного пути подтвердил module-context issue: сnativechildPSModulePath ACLpolicy проходит без измененияправ. Точный original process conjunct не сохранён, поэтому нельзя выдумывать r.error/status/stderr/deadline исходного failed command.

Offline root work/dev29-acl-module-offline-20261105-001/, reported sourceaggregate9dc1ac5693e0deda1aa30b049b8731f4d60bc5e6a412447b75fb3fd68aed8ade. Public frozen source checkpoint5e1cd8fa78e570f6e5996f2aebb05795e45a8ee89abca8877707cbcbfdf1d191; controller policyreference4450f20e9fdbda9b3c7270dbc9e5e56dd228628eeb62d249aa3e6842dd8f33b8. Current candidate не изменялся и никакого нового RunId/COW/private authority не создавалось.

Delta: child-env clone удаляет только case-insensitive aliases PSModulePath и устанавливает один canonical native WindowsPS module path; остальные переменные сохраняются, parent/global env не меняется. Case-normalization соответствует [официальной документации Node.js child_process](https://nodejs.org/api/child_process.html): Windows не различает регистр env-имён, а duplicate case variants могут выбрать не тот entry. Это не ослабляетACL predicates. Fixedexe/argv/ACLscript/IOcaps/captureddeadline guards остаются прежними. Те же четыре transport failure conditions разделены на закрытые постоянные коды без raw stderr/messages/env/SID/private content. Existing public entry regex принимает эти codes; API failure object shape не меняется.

Syntax4+helper1 PASS, VM actual-source tests11/11 PASS/skip0. Injected только PUBLIC dummy env, никаких deepEqual/full realenv dumps. Одна real proposed-source WindowsPS metadata integration на публичном dummy: commandResolved/nativepath/exe match=true, childModuleKeyCount1, childEnvClone/parentModuleEnvUnchanged=true, within10s около705ms. Честный результат POLICY_DENIED/KEYPG_ACL_CHILD_STATUS, childExit1, metadataGuardPassed=false — НЕ metadata PASS. ИсточникGuard не ослаблялся, dummyACL не менялись, dataFDcalls0; no repeat. Независимый review должен проверить силу classification evidence, не выдавая command resolution за private ACL qualification.

| Артефакт относительно offline root | SHA256 |
| --- | --- |
| manifest.json | 7cd6a6046bfe52af46168655b23a67d7552b4b35e15215b99a7af5fcac1d660c |
| proposal.diff | 99cb9012d4a28ee672d490afff8a94c019fffbdd8e3d02e3791d285e531fa74b |
| proposal/key-host.mjs | 56e1af9c4d8b00dc1be6b8c63d82b1443ecbe1bb2cec743ad2bcb1d7ceb68520 |
| candidate-unchanged-proof.json | 8e5bd82a7f65515578ebd79bfdd7846017204c20ab8e20d1763d577727152df7 |
| integration-summary.json | a50d2a5e3b61911587fad0ba849cdeddb38a8514742d9a23f97c52de036b4236 |
| freeze-record.json | ac5706c6a0d3722f210e6206378a17bdf01a90a7a70a5dfbfaffcc6085e857fd |

Координатор отдельно проверил6 artifact hashes и55currentcandidate hashes. Proposal source STOP. q026_result_auditor независимо проверяет diff/tests/privacy/environment/unchangedguards; report docs/dev29-acl-module-offline-review.md. До verdict не считатьapproved и не применятьпатч. Любой новый bounded runtimecycle/freshCOW/Prepare требует concrete separately reviewed owner plan: текущие Prepare entries использованы, Run остаётся0, extraRun неразрешён. Старый сайт/VPS/corpus не менялись. Этап8около31%,DEV29около35%; current baseline209PASS не суммируется с11proposal tests как новыйcandidate результат.


## Независимый итог (D-555)

Proposal review APPROVED/findings[], SHA8c78127f73d8473c20d3de471638ec59a39811d9155b793525fe8fa24a72d201. Whole-source inverse delta точно восстанавливаетbaseline; source/artifacts aggregate9dc…8ade verified. Смыслrealprobe сохранён POLICY_DENIED/metadataGuardPassedfalse: exactstandaloneACL/OWNER либоFullyQualifiedErrorIdACL/OWNER recognition подтверждает достижение policythrowпослеGet-Acl, не простоexit1. No realprivatequalification/currentcandidateactivation/CODEmarker. Следующийшаг — independentreview Q033futurecycleplan, затем отдельныйownerreply.


## Future cycle proposal (D-556)

Root-authored Q033 planb018cfa75c3e9f5a1283a76bd09b91d39a92636e2f47c658e1a79bf65daf5f89 independently PLAN REVIEW APPROVED, review59fc1be7cb5ed3ccc70e0080ec19eb57cc91998941951f3e6524c9404ae4b798. Patch approval и plan review не являются ownergrant/CODEadmission новогоcandidate. Ждём явного DEV29-Q033; до него никакихactiveCOW/UUID/Prepare/Readiness/Run. Oldpartial808B RETAIN/current55immutable/Run0, extraRun0.
