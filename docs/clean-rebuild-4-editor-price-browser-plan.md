# RB4 price editor browser-native gate

Дата: 2026-11-19. ID: `RB4-EDITOR-PRICE-BROWSER-001`. Статус: **completed by D-1584; discovery exact8 and functional Chromium8/8 independently ACCEPTED P1/P2/P3=0/0/0; repeat unnecessary**.

## Purpose and claim boundary

The accepted PostgreSQL exact47 closes server-side `001B-P`. This separate gate proves only current browser behavior of `src/modules/pages/static/pages/price-editor.js` together with the final readiness logic in current `editor.js`.

It uses synthetic literal HTML on an intercepted HTTPS origin and exact8 `RB4-EDP-001..008`: no-JS/final-adapter fail-closed; dual readiness+dirty; column add/remove cleanup; row/column add/remove/move order; absent/text/amount fixed-wire serialization; invalid amount/duplicate controls fail-closed; insecure/randomUUID failure; unsupported DOM/no-navigation/partial-carriers0. It does not claim Django template/HTTP, authorization, parser, PageCAS, PostgreSQL, responsive visual layout or real data.

## Reused exact runner

Reuse the already accepted native-editor branch of `acceptance/run-container.ps1`:

- pinned image digest `sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`, local-only and `--pull=never`;
- exact trusted package/lock SHA checks, pinned pnpm11.25.0, `--offline --frozen-lockfile --frozen-store --trust-lockfile --ignore-scripts`, readonly store and network none for preparation and test;
- one mode-specific guarded staging directory containing only package, lock, config and `price-editor-native.spec.js`;
- readonly mounts only for current `editor.js` and `price-editor.js`; docs, app tree, DB, private bindings, Docker socket and media0;
- worker1, retries0, traces/video/screenshots0, one-shot `--rm`, existing resource/cap boundaries and result directory.

No host install, browser download, registry access, new image/dependency/runner/fixture framework/application server or serializer/parser mirror is allowed.

## Discovery and functional sequence

One small runner amendment permits existing `-ListOnly` for either native editor mode. It selects the current mode's project and requires the same bounded evidence file≤64KiB/200 lines, exit0 and exactly one literal `Total: 8 tests in 1 file`. It does not launch Chromium. Other modes still reject `-ListOnly`; rich behavior and its exact8 summary remain unchanged.

After amendment review, one explicit owner authorization may cover this fixed conditional sequence:

1. one `price-editor-native -ListOnly` Docker preparation+discovery; require exact8/one file/exit0;
2. only if discovery passes, one functional `price-editor-native` Docker preparation+real Chromium run; require worker1/retries0, eight named PASS, failures/skips0 and exit0.

Any failure stops the sequence immediately; no retry or fallback. Independent result review closes the browser gate. The combined permission reduces a needless owner round-trip while still explicitly naming both Docker actions.

## Evidence and stop rules

Evidence is limited to trusted-base checks, packages/reused/downloaded counts, exact discovery summary, the eight named test outcomes, duration, exit code and one-shot cleanup. Network requests to the synthetic origins are intercepted in-browser; container network remains none. No screenshot is an oracle.

Stop and return to the owner if the gate requests host Node/npm, network/registry, another runner/project layer, jsdom, application/DB/template fixture, copied product logic, screenshot baseline, broader source mount or any `001B-S/M` behavior. The light compromise is to leave the browser claim open.

## Conditional sequence result

Owner-authorized ListOnly passed trusted-base checks and frozen offline preparation with packages3/reused3/downloaded0, then enumerated exact RB4-EDP-001..008 in one file and exit0. The permitted conditional functional phase repeated the same preparation and ran real network-none Chromium worker1/retries0: exact8/8 passed in11.4s, exit0. Both phases used readonly current two JS files, pull-never and one-shot `--rm`. Independent result acceptance precedes gate and `001B-P` closure.
