# Независимое review PUBLIC OFFLINE ACL module proposal

Verdict: APPROVED в пределах неактивного public offline patch proposal. Findings: []. Reviewer: q026_result_auditor. Дата: 2026-11-05. Это не runtime code gate, activation или разрешение Prepare/Readiness/Run.

Bundle: work/dev29-acl-module-offline-20261105-001.
Source aggregate9 SHA256: 9dc1ac5693e0deda1aa30b049b8731f4d60bc5e6a412447b75fb3fd68aed8ade.
Proposal key-host SHA256: 56e1af9c4d8b00dc1be6b8c63d82b1443ecbe1bb2cec743ad2bcb1d7ceb68520.
Baseline key-host SHA256: 5e1cd8fa78e570f6e5996f2aebb05795e45a8ee89abca8877707cbcbfdf1d191.
Manifest raw SHA256: 7cd6a6046bfe52af46168655b23a67d7552b4b35e15215b99a7af5fcac1d660c.

## Source/diff review

Предлагаемый source создаёт отдельный child-env object из enumerable parent entries, исключает все имена с toUpperCase()==PSMODULEPATH и добавляет ровно один PSModulePath со штатным native WindowsPowerShell Modules path. Parent/global env не мутируется; остальные key/value сохраняются. Это важно для Windows: [официальная Node child_process документация](https://nodejs.org/api/child_process.html) описывает case-insensitive keys и выбор первого lexicographically sorted совпадения. Простая добавка canonical key при сохранённых aliases не давала бы той же гарантии.

Независимо проверена обратная whole-source transformation: три exact occurrences1/1/1 — добавленный env clone, env spawn option, split diagnostic guards — удаляются/возвращаются к прежней conjunction, и результат byte-identical baseline. Иных изменений module body нет; cap mutation negative не проходит ту же equivalence.

Executable/argv/Get-Acl script, owner/current-user+SYSTEM/Allow predicates, ACL schema, encoding/maxBuffer4096/windowsHide, remaining<=10с, captured own/current parent deadlines, FD/HMAC/tag/export/privacy поведение сохранены. Module lookup фиксируется только в параметрах этого child, без persistent environment/registry/profile/module install/ACL changes.

Одна старая conjunction разделена на те же четыре условия и в той же priority: child error/status/stderr/deadline. Новые codes фиксированные uppercase constants; raw error/stdout/stderr/env/SID не включаются в exception/public output. Существующий entry contract принимает их без controller source patch. Это diagnostics refinement, не ослабление rejection.

## Evidence review

Прочитаны actual proposal source, exact diff, VM loader/fixture, все11 tests, integration harness и summaries; тесты/PS reviewer не запускал.

VM действительно загружает copied proposed module через SourceTextModule и заменяет только зависимости PUBLIC dummy FS/process.env/spawn. Родительский dummy env frozen, содержимое реального env не сериализуется. Cases покрывают aliases/parent preservation/other options, missing/empty/untrusted paths, executable/argv/caps, all4 failures/priority, shorter/expired parent, rolling own budget, late-open close1/read0, malformed/invalid ACL/JSON/hardlink, public entry compatibility и exact authorized delta. Test-summary:11PASS, skip0; real PS/ACL actions в этих VM tests0. Syntax evidence также учтено как проверка, не как дополнительный test count.

Отдельный real integration уже был выполнен builder ровно один раз, только на retained PUBLIC dummy. Harness использует exact proposed module и реальные FS metadata/fixed WindowsPowerShell transport, но role paths ограничены public bundle; data-FD/read/write/unlink source callbacks запрещены. Reviewer его не повторял.

Recorded integration: childCount1, exe/nativePathMatch/one canonical module key/clone/unchanged parent/timeoutCap=true; childExit1, stderrEmpty=false, dataFdCalls0, aclEdits0; elapsed705.2441ms. Итог POLICY_DENIED, KEYPG_ACL_CHILD_STATUS, metadataGuardPassed=false. Это НЕ metadata PASS.

Recognition не выведена из одного exit1: pinned harness допускает policyException только по exact standalone ACL/OWNER либо exact FullyQualifiedErrorId ACL/OWNER. В неизменённом fixed script эти markers относятся к policy throws после Get-Acl. Поэтому limited command-resolution recognition согласуется с code/evidence; arbitrary error text/module error не принимаются как policy success. Raw stderr намеренно не сохранён/не перечитывался, поэтому auditor не заявляет независимый повтор regex над оригинальными bytes. Это ограниченное source-provenance evidence признанного marker, не successful metadata qualification dummy/private target, не доказательство пригодности runtime и не основание менять права ради PASS.

## Freeze/current-candidate closure

Совпали шесть переданных exact artifact pins, все9 source hashes/aggregate и все manifest evidence hashes. Runtime candidate55 повторно совпал с его прежним manifest; текущий key-host равен baseline, controller policy reference SHA2564450f20e9fdbda9b3c7270dbc9e5e56dd228628eeb62d249aa3e6842dd8f33b8 совпал. Active code-review document SHA256 f6b9a0b62b5ad5dab8b02fa3d5a63b7521415d55a8ba320d494ec16a680bc3a4 неизменён. Runtime proposal не применялся.

Ранее созданные ordinary6/808B остаются RETAIN/UNPROVEN по forensic outcome; в этом review private namespace не читался и не инвентаризировался повторно. Ничего не удалялось/не adopted.

## Scope и дальнейший допуск

Одобрен только этот изолированный offline proposal и его узкая semantic correction. Перенос в runtime COW, судьба partial inputs, новый frozen runtime package/code review и любой последующий Prepare требуют отдельного конкретного reviewed owner plan. Дополнительный Run или повтор Prepare из этого verdict не следуют.

Reviewer не менял source/candidate/ownerline/active code-review/ACL/settings; не запускал tests, PowerShell, Docker, SQL, private operations или runtime modes. Читались только public sources/evidence и официальная Node документация. Real tool/read ошибок не было. Записан только этот review-документ; runtime authority marker не создавался.
