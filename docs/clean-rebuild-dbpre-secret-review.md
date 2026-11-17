# DBPRE exact-byte secret transport review

Дата: 2026-11-17. Review ID: `RB1-SECRET-REVIEW-001`.

Вердикт: **CHANGES_REQUESTED — P1=0, P2=2, P3=0**.

## Open findings

### `RB1-SECRET-P2-001` — timeout/lifecycle not fully bounded

После failed `WaitForExit(10000)` вызывается unlimited `WaitForExit()`. Результат `Process.Start()` игнорируется, а `$started=true` ставится безусловно; редкий false может нарушить cleanup/dispose.

Минимальная remediation: `$started=$process.Start()` + reject false; timeout → best-effort kill и immediate bounded throw без unlimited wait; HasExited/kill protected, Dispose in unconditional nested finally.

Статус D-1279: **remediation candidate prepared, repeat review pending**. Start false rejected; timeout has no unlimited WaitForExit; cleanup protected; Dispose unconditional. Parser/static PASS, runtime0.

### `RB1-SECRET-P2-002` — shell failures can be masked

`cat; chown; chmod` позволяет успешному chmod скрыть failed chown.

Минимальная remediation: `umask 077 && cat > fixed-path && chown 999:999 fixed-path && chmod 600 fixed-path`.

## Confirmed

- exact lowercase hex96 guard; direct docker ArgumentList; payload not command line;
- UTF8 no BOM, Write without newline, stdin close;
- stdout/stderr async drained/discarded; nonzero constant throw;
- caller clears payload; docker cp absent; positional binding PASS;
- other runner contracts unchanged; no launcher/logger/framework/secret subsystem.

Review edits0/runtime0/Docker0/DB0/network0, tool errors0/cycle0. Следующий этап: P2-002 only, затем repeat review; runtime closed.
