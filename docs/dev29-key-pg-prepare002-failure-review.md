# DEV29-Q031/Q032 — forensic review failed Prepare002

Reviewer: q026_result_auditor. Дата: 2026-11-05. Итог: FAILED/NOT_PREPARED; обнаружена command/module-resolution проблема ACL adapter. ACL policy не опровергнута и не ослабляется. Повтор Prepare этим отчётом не разрешён.

Root: work/dev29-bounded-20261104-resume007. RunId: 35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1.
Frozen package55 SHA256: efc7d76f8b76e1966ba958eb7d174671650140f251a8de170a8481832cb05460.
Source55 hashes повторно совпали. Active code-review SHA256 f6b9a0b62b5ad5dab8b02fa3d5a63b7521415d55a8ba320d494ec16a680bc3a4 неизменён; public ART/inputs/code-review.md имеет тот же SHA.

## Исполнение и source-derived failure boundary

Root непосредственно наблюдал ровно одну дополнительную Prepare invocation по Q032: exit1 за3.468с, stdout65bytes, stderr0. Readiness/Run/actual gates не запускались. Public root-prepare-002.stdout: code KEYPG_ACL, scope BOUND29-REAL-HOST, statusFAIL. Raw stdout SHA256 77d42aa4eda7f6dbd7efb5452385ecb69de1f395a4634ee5337c5b2fb4220e06.

В controller.mjs:55 keyPolicyCore object вычисляет sourceMetadata:originIo.metadata('original'). Subject original однозначно resolve в <LOCAL_PRIVATE_ROOT>/database-server-key. Это выполняется ДО создания originSession и ДО try keySession.prepare в controller:56.

key-host.mjs:7 metadata делает nonlink/stat проверки, затем fixed WindowsPowerShell Get-Acl на ЭТОМ файле. KEYPG_ACL — объединённый execution guard: отсутствие spawn error, status0, пустой stderr и завершение до deadline. Он расположен до JSON parse/ACL-schema check. Policy checks owner/current-user+SYSTEM/Allow/count выполняются внутри child script; отдельные результаты не сохранены при отказе.

ART/prepare-partial.json отсутствует. Этот journal пишется только из более позднего keySession.prepare catch. В PRIV отсутствует origin-tag-intent.json. Совместно с source order это локализует отказ в первом policy-core original metadata query, до boundedFdRead data-open/MAC и до создания tag. ACL metadata access не является чтением TLS key bytes. Ветка application data FD оригинала не достигнута; HMAC/tag32B/staging не начинались. Это не утверждение нулевого private I/O всего старого Prepare: старые QA/private reference guards расположены раньше и отдельно не анализировались.

## Почему это не ACL denial

Source comparison:
- controller.mjs:13 legacy acl(dir) задаёт child env.PSModulePath=C:/Windows/System32/WindowsPowerShell/v1.0/Modules.
- key-stage/runner.mjs также задаёт этот native module path и передаёт env в processCall.
- key-host.mjs:7 запускает тот же fixed WindowsPowerShell executable без env override, наследуя caller module lookup context.

Выполнены только два разрешённых read-only metadata child diagnostics, без изменения current source/ACL/settings:

| Diagnostic | Условие | Closed result |
| --- | --- | --- |
| 1 | Exact original path; fixed WindowsPowerShell; inherited child environment | readSucceeded=false, category COMMAND_OR_MODULE; child exit0, stderrEmpty, within10s |
| 2 | Тот же path/executable/Get-Acl metadata logic; единственное изменение — child-only native PSModulePath из approved adapters | readSucceeded=true; ownerCurrent=true; allAllow=true; onlyCurrentSystem=true; rules2; inheritedRules2; protected=false; child exit0, stderrEmpty, within10s |

Первый child ловил ошибку и возвращал только closed category, не raw exception. Это failure команды/модуля, а не установленный отрицательный ACL predicate. При штатном native lookup Get-Acl прочитал ACL, и все исходные policy predicates прошли. Directory native Modules существует/isDirectory=true. Никакого третьего module/path child attempt не было.

Таким образом контролируемый contrast подтверждает зависимость failure от module-resolution context и отсутствие env pin в новом adapter. Точный исходный r.error/status/stderr conjunct отдельно не записан, конкретный module/DLL/parent Env value не выводился; его нельзя выдумывать из KEYPG_ACL. В аудите не утверждается, что исходный runtime child имел тот же exit0, что диагностические wrappers: они специально возвращали закрытый результат.

Никаких SID/account names/raw ACL/raw Env/key bytes/digests в выводе diagnostics нет. Global process environment/registry/profiles/settings не менялись; env override был только параметром одного child. Права не изменялись и predicates не ослаблялись.

## Owned partial state

До invocation root подтвердил ART/PRIV/STAGE absent. После failure metadata exact candidate paths показывают:

| Namespace/artifact | Состояние |
| --- | --- |
| ART=real-host/run | PRESENT; только inputs и пустые attempts/readiness/reviews/reviewer-outbox |
| ART/inputs | owner.txt и code-review.md; unsigned preparatory inputs, не signed plan |
| ART/plan.json | ABSENT |
| ART/prepare-partial.json | ABSENT |
| PRIV=private/bound29-35d97e6c-real | PRESENT;6 ordinary files,808bytes total |
| PRIV/tls-key-origin.tag | ABSENT |
| PRIV/origin-tag-intent.json | ABSENT |
| STAGE=private/key29-35d97e6c-8049-48c4-8ab2-0ea3bdce9ed1 | ABSENT; copy не создавалась |

Private inventory был только names/lstat, без contents/hash/ACL dumps:

| File | Size | Type/links |
| --- | ---: | --- |
| host-key | 32 | regular/nlink1/nonlink |
| bootstrap-password | 96 | regular/nlink1/nonlink |
| migrator-password | 96 | regular/nlink1/nonlink |
| django-secret | 96 | regular/nlink1/nonlink |
| identity-pin | 36 | regular/nlink1/nonlink |
| credentials.json | 452 | regular/nlink1/nonlink |

Эта форма согласуется с единственной recorded branch: mkdir/legacy strict acl(PRIV) → ordinary6 outputs → copied public inputs → first original metadata failure. Creation-time directory ACL guard был пройден, иначе исполнение не дошло бы сюда. Current ACL PRIV/files отдельным третьим child не перечитывалась. Signed ownership/plan/terminal cleanup proof для последующей destructive операции не создан; одних имён и размеров недостаточно для слепого удаления.

## Safety outcome: RETAIN / UNPROVEN

Все partial inputs сохраняются защищёнными; они НЕ PREPARED, не admission и не могут быть автоматически adopted/overwritten. Никакого unlink/rmdir/recursive/prune/CancelPrepared не выполнялось. CancelPrepared требует существующий signed plan, которого нет. Frozen Prepare также требует absent ART/PRIV; непосредственный повтор на partial namespace запрещён и технически не является продолжением предыдущего Prepare.

Q032 additional invocation израсходована, прежний oneRun не исполнялся. Ни corrected-context ACL metadata PASS, ни отсутствие tag не дают новой Prepare/Run authority.

Если впоследствии потребуется cleanup, нужен отдельный reviewed known-owned plan: source/root/run binding, current exact identities/nonreparse/nlink/ACL metadata, отсутствие holders/intents, проверка replacement непосредственно перед каждым действием, только явно перечисленные новые объекты/nonrecursive empty directory. Unknown identity или посторонний объект — RETAIN/UNPROVEN. Старые namespaces, original key, corpus и обычные archived inputs не затрагивать. Этот audit cleanup не одобряет.

## Конкретное следующее безопасное действие

Root уже поручил builder только неактивный PUBLIC offline patch proposal work/dev29-acl-module-offline-20261105-001, не current COW и не новый RunId. Минимальная correction: передать native WindowsPowerShell module path в child env key-host metadata по существующему controller/stage pattern. Не менять Get-Acl policy, owner/SYSTEM/Allow checks, paths, caps, captured deadlines/pre-post checks, nofollow/identity, HMAC/tag/export contracts. Не исправлять это изменением original ACL или persistent caller environment.

Offline tests должны использовать public fixtures/dummy env: contaminated parent module lookup не переходит в child; actual spawn options содержат fixed native path; все строгие ACL rejects/timeout/stderr/error и captured-parent boundaries сохранены. Никаких real key/creds/Env dumps. После freeze proposal требуется независимое diff/tests review. Перенос в runtime candidate, выбор судьбы partial state и новая Prepare invocation требуют отдельного конкретного reviewed owner plan; этот отчёт не разрешает source mutation или новый запуск.

Diagnostic gap: единый KEYPG_ACL не различает process/module/timeout/stderr/policy причины, а эта ранняя policy-core ошибка не попадает в prepare-partial journal. Возможное улучшение closed subcodes/journal — отдельный reviewed scope; raw stderr/SID/secret output не является допустимым решением. Для минимального module lookup fix weakening ACL не требуется.

## Scope аудита

Auditor не читал private file contents, key/credential bytes/digests и raw ACL/Env; только exact namespaces lstat/inventory и два closed Get-Acl metadata probes на одном source-derived path. Source55/current code review/ownerline не изменялись. Tests/retryPrepare/InspectPrepared/CancelPrepared/Readiness/Run/Docker/SQL/images не запускались. Source output и controlled metadata-query failure сообщались root; повтор был ровно один с подтверждённым changed condition, успешен, третьей попытки нет.

Записан только этот forensic report. RETAIN/UNPROVEN и offline correction proposal — не admission и не разрешение на новый Prepare.
