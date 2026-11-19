# RB4 rich editor browser-native gate

Дата: 2026-11-19. ID: `RB4-EDITOR-BROWSER-001`. Статус: **completed by D-1566; functional run2 PASS8/8 and independent result ACCEPTED 0/0/0; repeat unnecessary**.

## Purpose and claim boundary

This gate closes only the browser-native part of `RB4-EDHTTP-007` for the already implemented dependency-free rich adapter. It proves the real `Selection`, `Range`, `beforeinput`, `input`, paste and submit behavior of current `src/modules/pages/static/pages/editor.js` in the pinned real Chromium. The accepted Django/PostgreSQL exact40 remains authoritative for HTTP, roles, multipart parsing, PageCAS, database mutation and server validation; those tests are not repeated or simulated here.

The browser page is synthetic in-memory HTML containing only the literal data attributes consumed by the adapter. It is not presented as an application end-to-end test or a rendering claim for the Django template. The production script itself is mounted as one exact readonly file and executed unmodified. Network is `none`; there is no Django, PostgreSQL, Nginx, HTTP origin, login, real page, imported content, media or user data. Responsive/visual acceptance, structured fields, prices and media `001B` remain separate.

## Reused runner and files

Reuse the existing approved acceptance stack instead of installing host Node/npm or creating another runner:

- existing official image `mcr.microsoft.com/playwright@sha256:47b510dd9230bf0b9bfc9b20102241e577ea7a99334ab4c3ca19f19770e9b8ea`;
- existing pinned `@playwright/test==1.64.1`, `pnpm-lock.yaml`, bundled approved pnpm11.25.0 and `acceptance/run-container.ps1`;
- one new `acceptance/rich-editor-native.spec.js`;
- one project/report/mode named `rich-editor-native` added to the existing `playwright.config.js` and `run-container.ps1`;
- one command entry added to `acceptance/README.md`.

No host/global install, PATH/registry/WSL change, npm registry access, package/lock update, browser download, new image, CLI wrapper, second runner, application driver, fixture bridge or persistent service is allowed. For this mode only, `run-container.ps1` uses a separate mode-specific directory beneath its existing ignored scratch root. It clears/recreates that exact directory and copies only the literal allowlist `package.json`, `pnpm-lock.yaml`, `playwright.config.js` and `rich-editor-native.spec.js`. It does not execute the shared all-spec copy loop, optional/private binding staging or any fixture/migration staging, and does not mount docs. Other modes retain their current path unchanged.

Before recursive replacement of the fixed rich-mode staging directory, the runner verifies component-by-component that existing `work`, `work/acceptance-container` and `work/acceptance-container/rich-editor-native` are exact regular non-reparse directories with their expected immediate parents; any mismatch refuses deletion. Before either container, exact `docker image inspect` must prove the pinned digest is already local. Both rich-mode `docker run` calls use `--pull=never`; absence stops before container creation. Dependency preparation uses the existing frozen lock and local store with `pnpm install --offline --frozen-lockfile --ignore-scripts`; preparation and test containers both use network `none`. The local store, pnpm package and production `editor.js` mounts are readonly. If the store is incomplete or the pinned image cannot run the suite, stop instead of switching to network, installing or pulling.

The existing ignored scratch and result roots remain the only writes: the isolated rich-mode directory under `work/acceptance-container` and `test-results/acceptance`. Containers are one-shot `--rm` with the existing caps/resource boundaries. Trace, video and screenshots remain off; the bounded list/JSON reporter is sufficient. Other acceptance specs, optional/private bindings, application drivers, source tree, docs, Docker socket, secrets, database and media are not exposed to either rich-mode container; the only production input is exact readonly `editor.js`.

## Exact acceptance matrix

The spec uses a small literal fixture factory and test-only helpers only to place a browser selection, dispatch a browser event or intercept form navigation. It must import no production serializer logic and must never reimplement `validHref` or canonicalization as an oracle.

- `RB4-EDB-001 init-nojs-unchanged`: before script execution Save is disabled and the surface is not editable; a separate JS-disabled context retains that state. After current script loads, the exact marked surface becomes contenteditable and Save becomes enabled. Submitting an unchanged control retains `changed=0`, disabled value carrier and no serialized replacement.
- `RB4-EDB-002 input-ime-and-multiple-controls`: native typing/input and a separate composition/IME input path each mark only the affected control dirty. On submit only that control enables and fills its value carrier; an unchanged sibling retains `changed=0` and disabled carrier.
- `RB4-EDB-003 paragraph-linebreak-paste`: browser `beforeinput` for paragraph and line break uses the active in-editor range, mutates the expected DOM and marks dirty. Plain-text paste with multiple lines creates only text and `<br>`; HTML clipboard content is never inserted. A missing/outside range causes no mutation.
- `RB4-EDB-004 toolbar-inline-block-list`: each literal toolbar action `strong`, `em`, `u`, `s`, `p`, `h2`, `h3`, `blockquote`, `ul` and `ol` uses the selected range, changes only its control and marks dirty even without a browser-generated `input` event.
- `RB4-EDB-005 link-unlink`: valid internal and HTTPS links are created through the prompt and serialized; unlink removes only the anchor while preserving children. Unsafe credentials, port, fragment, backslash, scheme-relative, dot-segment, non-HTTPS, invalid percent escape, percent-decoded whitespace/control, and any query other than empty/`page=1`/`page=2` show the safe error state and do not enable a changed carrier. Cases use literal input/outcome tables and do not duplicate `validHref` logic.
- `RB4-EDB-006 deterministic-serializer`: changed allowed content serializes exact escaped text/attributes with fixed `href,title`, `colspan,rowspan,scope` ordering and expected canonical tags, including existing table/sub/sup content. DOM attribute insertion order must not change output.
- `RB4-EDB-007 fail-closed-dom`: unsupported element, comment/other node, unknown attribute, unsafe href, invalid table span or scope prevents submission, keeps the carrier disabled and exposes the single safe error message; content is not silently stripped.
- `RB4-EDB-008 submit-boundary`: a valid changed control enables its carrier immediately before submit and emits the exact serialized value. On serializer failure the same observed submit event has `defaultPrevented=true`, navigation/HTTP remains0, the carrier stays disabled and the safe error is visible. Test interception observes the browser event only and performs no HTTP request.

Every top-level case is independent and uses fresh in-memory HTML; loops are bounded subcases within that case. The exact expected discoverable count is **8** before the first browser run. The existing runner receives one optional `-ListOnly` switch accepted only with `-Mode rich-editor-native`; other modes reject it and retain their behavior. The switch reuses the identical isolated staging, image/store/source guards and test container, changes only the Playwright argument to `--project=rich-editor-native --list`, and redirects combined output to one exact regular file inside the isolated rich staging. It preserves the process exit code, refuses to read or print a file over64KiB, then reads at most200 lines and requires exit0 plus exactly one full CRLF-normalized pinned-CLI summary `Total: 8 tests in 1 file`. Mismatch exits nonzero. It does not launch a browser and claims only dependency/CLI/config/spec discovery and exact project/count readiness. The later separately authorized functional run omits the switch and is the only browser-behavior claim. A second mode, script or runner is forbidden.

## Review, execution and stop rules

Plan review precedes code. Code review and a network-none list/capability plan precede any Docker/browser execution. Browser execution requires separate owner authorization. A failed capability or functional run gets one diagnosis and materially changed condition review; no automatic retry.

Stop and return to the owner if closure requires host Node/npm, registry/network access, a new dependency/image, jsdom, a Python/JS mirror of the serializer, an application server, database, generic fixture framework, screenshots as the behavior oracle, production hooks, raw HTML mode or any `001B` control. The light compromise is to leave the affected claim open, not broaden the harness.

## List run1 result and changed condition

The owner-authorized list run1 stopped before the first Docker/image/pnpm/discovery call because PowerShell `New-Item` has no `-LiteralPath` parameter. Containers, browser, network and source execution were0. The single changed condition restores supported `New-Item -Path` for the already component-validated, coordinator-constructed fixed package/results paths; neither value comes from user input or contains wildcard syntax. All recursive-delete guards and runtime boundaries remain unchanged. Run1 is not accepted; independent review and fresh owner authorization precede any run2.

## List run2 result and candidate changed condition

Owner-authorized run2 passed the PowerShell boundary and started only the one-shot offline preparation container. Node24.22.1 started, then pinned pnpm11.25.0 failed before dependency staging/discovery because its default `StoreIndex` opens `/store/v11/index.db` writable while the approved store mount is readonly. Test container, Playwright discovery, Chromium, network and production source execution were0; the preparation container used `--rm`.

Pinned pnpm already provides the exact supported solution: `--frozen-store` selects `ReadOnlyStoreIndex`, opens the existing SQLite index through its immutable URI, rejects missing store content instead of writing, and is supported by Node24.22.1. The candidate changes only the rich preparation command by adding that one flag while retaining `--offline`, frozen lock, ignore-scripts, readonly store, network none and pull-never. Store write/copy/network fallback remain forbidden. Run2 is not accepted; independent review and fresh authorization precede run3.

## List run3 result and candidate changed condition

Owner-authorized run3 proved Node24 and frozen-store operation: pinned pnpm reused3/downloaded0 and copied all three locked packages from the readonly content-addressable store into isolated staging. It then failed before discovery because the default minimum-release-age supply-chain recheck requires full registry metadata under the ephemeral cache, while network none is mandatory and only older abbreviated local metadata exists. Test container, Playwright discovery, Chromium and production source execution were0; preparation was one-shot `--rm`.

Creating or mounting a new full-metadata cache, permitting registry network or disabling integrity/store checks is rejected. The bounded candidate uses pinned pnpm's documented `--trust-lockfile`, intended for CI against an already verified trusted-base lockfile. The canonical `acceptance/pnpm-lock.yaml` is Git-unchanged and still has exact size993/mtime matching the local `lockfile-verified.jsonl` record of a successful 2026-10-30 policy verification with minimumReleaseAge1440, registry routing, integrity and resolution checks.

Before staging, the runner requires canonical `package.json` and `pnpm-lock.yaml` to be exact regular non-reparse files with respective SHA-256 `4F67B18A01DEA58504AB72A98697514475423307D21BB5E42015DA14B6E2017B` and `51E5ADEF0356129F1415DA50C4913064EA9435342F5DE6B7988FE40B2E7C1264`. Immediately after copy it repeats the same regular-file and hash checks against staged files. Only then may `--trust-lockfile` execute; mismatch stops before Docker. The flag skips only re-fetch/reapplication of release-age/trust policy to those exact locked entries; `--frozen-lockfile`, content-addressable package integrity, `--frozen-store`, `--offline`, `--ignore-scripts`, readonly store, network none and pull-never remain. Any lock/store mismatch still fails. Independent repeat security review and fresh owner authorization are required before run4.

## List run4 result

Owner-authorized run4 passed canonical and staged trusted-base hash checks, local exact-image/pull-never guards and frozen readonly store preparation. Pinned Node24.22.1/pnpm11.25.0 reported lock up to date, packages3, reused3, downloaded0, added3 and exit0 in4.9s. The separate network-none `--list` container loaded the pinned config/spec and enumerated exactly the eight `RB4-EDB-001..008` cases under project `rich-editor-native`, finishing with the exact required `Total: 8 tests in 1 file` and overall exit0. Both containers were one-shot `--rm`. Chromium, production `editor.js`, HTTP, application, DB and behavior tests executed0. Independent result review precedes the separate owner gate for the functional run.

Independent result review ACCEPTED the discovery gate P1/P2/P3=0/0/0 with no-bloat PASS. It confirms only dependency/CLI/config/spec readiness; `RB4-EDHTTP-007` browser behavior remains open. One functional run uses the same command without `-ListOnly`, the same exact trusted-base/offline/network-none/pull-never/source-readonly boundaries, exact8 and one-shot containers. It requires separate owner authorization and independent result review; no automatic retry.

## Functional run1 result and candidate changed condition

Owner-authorized functional run1 passed exact trusted offline preparation and started real Chromium with worker1/retries0. `RB4-EDB-001` and `002` passed; fail-fast stopped at `003` with paragraph DOM unchanged, leaving five tests unrun. The failing positive path used Playwright locator `dispatchEvent('beforeinput', {inputType: ...})`, which did not provide the production handler a real browser `InputEvent.inputType`; the handler therefore correctly ignored it. Product DOM remained unchanged and product findings are0.

The bounded test-only changed condition uses actual Chromium keyboard input for positive editor behavior: focus+selection then `Enter` for paragraph and `Shift+Enter` for line break. The outside-range negative path constructs a real `InputEvent('beforeinput', ...)` in the browser while selection remains outside. The separate IME oracle is strengthened from generic dispatch to a real `InputEvent('input', {inputType:'insertCompositionText', isComposing:true})`. Production `editor.js`, runner, dependencies and exact8 remain unchanged. Independent triage/review and fresh owner authorization precede run2; no automatic retry.

## Functional run2 result

Owner-authorized run2 passed the exact trusted-base checks and frozen offline preparation with packages3/reused3/downloaded0/added3, then ran real network-none Chromium with worker1/retries0 against only readonly current `editor.js`. All exact eight cases passed in12.6s: init/no-JS/unchanged, native input+IME isolation, paragraph/line-break/paste range behavior, all literal toolbar actions, link/unlink policy, deterministic serializer, unsupported DOM fail-closed/no-strip, and submit enable/prevent/no-navigation boundary. Overall exit0; both containers were one-shot `--rm`. HTTP, Django template E2E, application, DB, responsive visual and 001B remain outside the claim. Independent result review is required before closing `RB4-EDHTTP-007` browser behavior.

Independent result review ACCEPTED P1/P2/P3=0/0/0, product findings0 and no-bloat PASS. `RB4-EDITOR-BROWSER-001` and the browser-native portion of `RB4-EDHTTP-007` are closed; together with the previously accepted Django/PostgreSQL exact40, the bounded `RB4-EDITOR-HTTP-001A` increment is closed. No repeat is needed. Template/HTTP browser E2E, responsive/visual acceptance, Nginx/live and structured/prices/media `001B` remain separate.
