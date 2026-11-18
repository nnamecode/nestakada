# REBUILD-1 media source offline harness repeat code review

Дата: 2026-11-17. Review ID: `RB1-MEDIA-SOURCE-OFFLINE-HARNESS-CODE-REVIEW-002`.

Вердикт: **CHANGES_REQUESTED — P1=2, P2=1, P3=0**.

- `P1-001`: verifier-fail oracle omitted the final outer-catch `Test-Path` boundary after known cleanup and rethrow.
- `P1-002`: one label fake conflated broad collision lookup `label=<key>` with exact cleanup evidence `label=<key>=<value>`; bounded-process payload was not required to equal the exact descriptor.
- `P2-001`: `--no-trunc` guard was scoped only to the function, not to the exact `Invoke-Docker ps` command.

D-1394 remediation remains local: add the one final boundary to the verifier-fail queue; split broad/exact label operations and compare the exact descriptor; bind the AST guard to the unique production `Invoke-Docker ps -aq --no-trunc --filter ...` command. Docker/DB/media/process/write remain zero; no module, dependency or production test mode is added.

## Review 003

Review ID: `RB1-MEDIA-SOURCE-OFFLINE-HARNESS-CODE-REVIEW-003`.

Вердикт: **CHANGES_REQUESTED — P1=0, P2=1, P3=0**.

Все предыдущие findings закрыты. `P2-002`: boundary fakes должны отклонять не только неверные обязательные значения, но и любые лишние common/unbound PowerShell arguments. D-1396 добавляет exact `$PSBoundParameters` key sets и `$args.Count==0` в том же файле без helper/framework/runtime.
