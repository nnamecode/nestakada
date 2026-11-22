# REBUILD-4 — Page Reorder TLS/RNG static environment investigation plan

Дата: 2026-11-21. ID: `RB4-PAGE-REORDER-TLS-RNG-ENV-001`. Статус: **D-1836 sole collector run `ACCEPTED_PASS / BASELINE_PARTIAL / ROOT CAUSE INCONCLUSIVE`, collector P0/P1/P2=0/0/0 and privacy PASS; one-shot gate consumed, no rerun/fallback/alternate query authorized**.

## 1. Purpose and evidence boundary

D-1833 локализовал единственный owner-authorized run до exact Windows/.NET boundary `[System.Security.Cryptography.RandomNumberGenerator]::Fill($serial)`: `SERVER_SERIAL_ALLOC` завершён, затем closed `SERVER_SERIAL_RNG`, а `SERVER_CERT`, certificate/leaves/PostgreSQL/app/tests не достигнуты. Cleanup и post-audit дали containers0/networks0/TLS leaves0/runner leaves0. Independent terminal review зафиксировал coordinator P1, product0 и exact196 `UNDETERMINED`.

Цель будущего исследования — только сопоставить эту уже полученную evidence с bounded metadata локального Windows PowerShell/.NET/crypto-policy окружения. План не предполагает повтор failure, не вызывает RNG/RSA/certificate APIs и не обещает установить root cause. Если read-only metadata не доказывает конкретный механизм, обязательный результат — `INCONCLUSIVE`, TLS branch остаётся owner-paused.

## 2. Exact future read-only facts

После отдельного разрешения один диагностический сбор может прочитать только следующие exact facts:

1. Windows product/build/architecture из `System.Environment.OSVersion`, `HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion` exact values `ProductName`, `CurrentBuildNumber`, `UBR` и process/OS architecture. Другие registry branches не перечисляются.
2. PowerShell engine metadata: `PSEdition`, semantic `PSVersion`, process bitness and language mode. Module list, command history, profiles and transcript files не читаются.
3. Loaded CLR/.NET Framework identity: `System.Environment.Version`, closed core-assembly family token `CORELIB|MSCORLIB|OTHER`, normalized assembly simple name/version selected by the active process, and `HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full` exact `Release`/`Version` values. Assembly location/path is neither read nor emitted; `OTHER` does not trigger enumeration. Assembly contents and broad GAC enumeration are excluded.
4. Exact machine crypto policy value `HKLM:\SYSTEM\CurrentControlSet\Control\Lsa\FipsAlgorithmPolicy\Enabled`; absent is reported only as `ABSENT`. No policy mutation, export or recursive registry listing.
5. Exact service metadata for `CryptSvc` and `KeyIso`: service exists/absent, status and start type only. Dependencies, credentials, binary command line, recovery configuration and service control actions are excluded.
6. Exact `Microsoft-Windows-CAPI2/Operational` log metadata: exists/enabled/record-count/last-write time only. Trustworthy literal UTC endpoints for D-1833 were not retained in approved evidence, so event records are unconditionally `WINDOW_UNAVAILABLE` and are not queried. Counts by level, provider/event-ID pairs, raw message, XML, payload, subject/SAN, paths, process command line, user/SID and certificate/key fields are forbidden; no wider time search occurs.
7. Existing project evidence only: coordinator SHA `86FBCEF8E4E241BBA5D0399542D7B01A93E4FD40EFCB89AB8DC670B06876DACA`, literal stage placement and D-1833 terminal markers. Coordinator/source files are read-only; no new instrumentation or application change.

The future collector must use fixed literal queries, emit only a closed fact-name/value allowlist and never print exception messages. It builds the complete at-most-32-fact output in memory, validates unique names, closed value shapes and a 4,096-character maximum before emitting any fact. If cardinality, uniqueness, shape or character cap fails, it emits only `RB4_TLSENV_OUTPUT=UNAVAILABLE`; partial/truncated output is forbidden. A failed individual query records only `<FACT>=UNAVAILABLE`; it does not retry through another API or broaden scope.

## 3. Explicit exclusions

The plan authorizes none of the following:

- any call to `RandomNumberGenerator`, `RandomNumberGenerator.Fill`, `GetBytes`, `BCryptGenRandom`, `RtlGenRandom`, RSA, ECDSA, certificate request/create/export, OpenSSL or another entropy/crypto probe;
- Docker, PostgreSQL, app/tests, coordinator execution, network, browser, live/deploy or external installation;
- registry/service/config/event-log changes, service start/stop/restart, OS repair, policy refresh, reboot or administrator remediation;
- environment-variable names/values, process list, command line, PowerShell history/profile/transcript, credential stores, DPAPI, certificate stores, key containers or private files;
- raw event messages/XML, stack traces, exception type/message/HResult, serial/certificate/key bytes, paths or user identifiers;
- broad registry/event/filesystem search, WMI inventory, ETW tracing, ProcMon, debugger, dump, telemetry collector or persistent script/service;
- provider substitution, fixed/deterministic serial, fallback PRNG, cached entropy, relaxed TLS or any product/coordinator crypto workaround.

No new dependency, tool or machine setting is introduced. Built-in read-only APIs are the only proposed mechanism; any missing capability remains `UNAVAILABLE`.

## 4. Interpretation contract

Facts may support only these non-causal conclusions:

- `BASELINE_COMPLETE`: every exact non-event fact has a closed present/absent value and the atomic output validates;
- `BASELINE_PARTIAL`: at least one exact fact is `UNAVAILABLE` and the atomic output otherwise validates.

Both conclusions mean that D-1833 root cause remains `INCONCLUSIVE`. No value or combination is classified as conflicting/unsupported, and event correlation is impossible because event records are not queried.
If atomic validation itself fails, no baseline conclusion or fact is emitted; output is only `RB4_TLSENV_OUTPUT=UNAVAILABLE`.

None of these outcomes authorizes a retry or fix. A concrete remediation proposal requires a new documentation-only plan grounded in the returned closed facts and independent architecture/privacy review. If remediation would alter crypto generation, weaken randomness/TLS, install software, change policy/service/registry or run a probe, stop for a separate owner decision.

## 5. Acceptance before execution

| ID | Scenario | Required result |
|---|---|---|
| `RB4-TLSENV-001` | exact OS/PowerShell/CLR/.NET metadata | Fixed fields only; no module/profile/history/environment/process inventory |
| `RB4-TLSENV-002` | FIPS registry fact present/absent/unavailable | One exact value or closed state; recursive registry read and mutation0 |
| `RB4-TLSENV-003` | CryptSvc/KeyIso metadata | Exists/status/start-type only; service control/credentials/path/dependencies0 |
| `RB4-TLSENV-004` | CAPI2 log unavailable/disabled/window unavailable | Closed status only; no wider search, raw message/XML or alternate log0 |
| `RB4-TLSENV-005` | CAPI2 event records | Unconditionally `WINDOW_UNAVAILABLE`; record query/count/provider/event-ID/payload0 |
| `RB4-TLSENV-006` | any read/query error | One `UNAVAILABLE`, no exception text and no retry through another API |
| `RB4-TLSENV-007` | interpretation | Exactly `BASELINE_COMPLETE|BASELINE_PARTIAL`; root cause remains `INCONCLUSIVE`; no causation, retry or remediation claim |
| `RB4-TLSENV-008` | static scope/output inspection | RNG/RSA/certificate/Docker/network/write/install/change/probe/history/env/dump0; at most32 unique closed facts and4096 chars built before emission, otherwise only `RB4_TLSENV_OUTPUT=UNAVAILABLE` |

## 6. Gates and stop rules

This document must pass independent architecture/privacy/anti-loop review before it may be proposed for execution. The future collector/query implementation, if any is needed, requires its own exact-source review; a direct one-shot built-in command requires an exact command review instead. Actual metadata collection requires a fresh explicit owner permission and is limited to one execution.

The first query failure is recorded as `UNAVAILABLE`; there is no equivalent retry. Stop and return to the owner if correct collection needs elevation, a new tool, registry/service/event configuration change, broader logs/time window, raw messages, environment/history/process inventory, RNG/crypto invocation or any write outside documentation. Page Reorder and Page Move runtime remain owner-paused; product code, coordinator crypto logic and exact196 are unchanged.
