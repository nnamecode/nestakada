# TEST-10A — minimal registry amendment plan

Status D-1073, 2026-11-14: independently `APPROVED`, P1/P2/P3=0/0/0. Basis: independently approved D-1072 semantic table. This plan changes no product, fixture, database, browser flow or evidence files. It proposes an in-place v2 amendment of exactly four existing files:

1. `acceptance/test10a-bindings.json`;
2. `acceptance/test10a-payloads.json`;
3. `acceptance/test10a-observers.json`;
4. `scripts/test10-registries.ps1`.

No writer, launcher, browser driver, endpoint, receipt service, schema migration, dependency or additional validator is added. `registryReady=false`, all bindings/observers remain `unbound`, and `TEST10-Q003` remains closed after the amendment.

## 1. Binding registry v2

The file moves in place to `test10a-binding-registry-v2`. Existing acceptance/scenario IDs and the 40 stable binding IDs remain unchanged. Scenario `actions` remain trace groups, not temporal execution order. A new `executionBindingOrder` contains the exact 40 binding IDs in D-1072 order:

`1–5, 12, 13, 6, 7, 9, 10, 8, 11, 14, 15, 18–28, 32–40, 29, 30, 31, 16, 17`.

The validator expands those row numbers through the canonical 40-ID array and proves count40, unique40, missing0, extra0. It also proves rows12/13 precede6, row10 precedes8, row32 precedes29–31, row30 is the sole revoke request, row31 is the first request after30, and rows16/17 close the tail.

Every binding record has `id`, `executionKind`, `steps`, `oracle`, `implementationStatus`; all40 remain `unbound`. `steps` is an ordered closed tagged union and every step carries its own actor/context:

- `request`: exactly `type,id,actor,sessionSource,csrfSource,method,route,body,content,expected`; `sessionSource` is one approved fixture/runtime actor session, `csrfSource=none|rendered`, GET requires `csrfSource=none` and `body=null`, POST body references only a payload ID;
- `ui-local`: exactly `type,id,actor,sessionSource,action,content,expected`; closed actions are `open-editor`, `enter-tab-value`, `navigate`, `cancel-navigation`, `switch-actor`; it cannot claim server mutation;
- `state-transition`: exactly `type,id,actor,transition,sourceContext,targetContext,expected`; closed transitions are `expire-idle`, `expire-absolute`, `advance-current-separate-session`, `apply-password-reset`, `apply-grant-revoke`;
- `observation`: exactly `type,id,actor,observer,expected`; it invokes only an approved derived observer and no mutation;
- `binding-reference`: exactly `type,id,bindingRef,expected`; no request/evidence artifact is created;
- `evidence-reference`: exactly `type,id,evidenceRef,expected`; no request is performed.

`executionKind=request|ui-sequence|binding-reference|evidence-reference` must agree with its step variants. The validator rejects unknown variants/properties, illegal actor/session/CSRF combinations and mutation claims from local/reference/observation steps.

The exact per-row route/method/sequence/oracle is D-1072 table rows1–40. Mechanical transformation rules are closed:

- old single valid GET rows become one request step with the same exact route;
- old editor POST rows become `EDITOR-CHECK` only for negative rows2/36, normalisation/boundary row33 and validation row38; positive rows5/18/34/35/37 use `EDITOR-CHECK` then `EDITOR-SAVE`; conflict row40 uses check, a separately observed current mutation, then stale save; expiry row39 opens while valid and attempts check only after expiry;
- row33 expands deterministically to `P013-SAFE`, then `P104-1M.exact`, `P104-1M.plusOne`, `P104-TEXT200K.exact`, `P104-TEXT200K.plusOne`, `P104-NODES20K.exact`, `P104-NODES20K.plusOne`, `P104-DEPTH32.exact`, `P104-DEPTH32.plusOne`. Every member uses a fresh `EDITOR-CHECK` request step with current context; `P013-SAFE` and each `.exact` expect accepted normalisation with zero revision/current mutation, each `.plusOne` expects refusal with zero mutation, and no row33 step performs `EDITOR-SAVE`;
- rows23/29 use `.../{version}/compare/`;
- rows25/27/28/31/32 use the reviewed `RESTORE-PREPARE`/`RESTORE-APPLY` sequence and never `restore/stage/`; row31 stops after denied prepare; row28 records its actual fail-closed stop point;
- row16 is `evidence-reference` to `REV-E1`; row26 is `binding-reference` with exact `bindingRef=UI-022-STAGE` and creates no new evidence artifact or second save;
- row30 is the sole `GRANT-REVOKE` request and canonical source of `REV-E1`.

If a row's exact response class or fail-closed stop point is still unknown in D-1072, `expected` is `BLOCKED:<reason-code>` rather than a guessed status. Such a row remains unbound and cannot contribute PASS.

## 2. Payload registry v2

The file moves in place to `test10a-payload-registry-v2`. The eight content payloads and all existing literal/boundary hashes remain byte-for-byte unchanged. The nine obsolete `PBODY-*` form templates are retired and replaced by this closed request-template set:

| ID | Content type | Exact semantic body |
|---|---|---|
| `REQ-PASSWORD-NEW` | form | `password={private.NEW-SYNTHETIC-SECRET}` |
| `REQ-LOGIN-OLD` | form | `username=test10-s-edit&password={private.OLD-SYNTHETIC-SECRET}` |
| `REQ-LOGIN-NEW` | form | `username=test10-s-edit&password={private.NEW-SYNTHETIC-SECRET}` |
| `REQ-GRANT-REVOKE` | form | `page={identifiers.page}&action=revoke` |
| `REQ-EDITOR-CHECK` | JSON | exact `page-editor-v1` check object from D-1072 with runtime generation/current basis and selected canonical content |
| `REQ-EDITOR-SAVE` | JSON | exact check object with returned normalised changes plus runtime operation UUID and signed check receipt |
| `REQ-RESTORE-PREPARE` | form | `generation={runtime.generation}` |
| `REQ-RESTORE-APPLY` | form | `generation={runtime.generation}&operation_id={runtime.operationId}&preparation={runtime.preparation}&confirm_input_replacement=yes` |

`form` means `application/x-www-form-urlencoded`; `JSON` means `application/json`. Templates store placeholders, never resolved secrets/tokens. Each template has SHA-256 of its canonical template bytes. Runtime evidence may store only the approved template ID/hash and a boolean `resolved=true`; it never stores the resolved body.

Closed placeholder bindings are extended in place with:

- safe fixture: page/current/historical/incompatible/editUser/ownerUser;
- private: old/new synthetic password and `TEST10-SYNTHETIC-CANARY` from `private.canary`; these values are resolved only in memory and never enter evidence;
- runtime-only: generation, operationId, checkReceipt, preparation, normalisedChanges;
- content registry: selected literal/set member and its canonical hash.

Closed content projections define the exact `changes` JSON before it enters `REQ-EDITOR-CHECK`:

- `P013-SAFE`, every expanded `P104-*` exact/plusOne member and active member: `{"main_text":<canonical JSON string of selected content>}`; boundary member IDs are exactly `<payloadId>.exact|plusOne` and their generated bytes/hashes remain those stored in each boundary-pair record;
- every `P106-SAFE-LINKS`/`P106-UNSAFE-SET` member: `{"main_text":"<p><a href=\"{attribute-escaped selected value}\">EDITOR-LINK-CANARY</a></p>"}` with fixed label/field; the sole attribute projection replaces `&` with `&amp;`, `"` with `&quot;`, `<` with `&lt;`, and `>` with `&gt;` in that order, then canonical JSON escaping is applied; each projected member SHA-256 is stored in the registry;
- tab canary save/conflict: `{"main_text":<canonical JSON string of private TEST10-SYNTHETIC-CANARY>}`;
- validation denial row38: `{"h1":<canonical JSON string of private TEST10-SYNTHETIC-CANARY>}` submitted by S-EDIT, so the owner-only field is refused;
- save always replaces this input with the exact returned `normalisedChanges` object.

The JSON editor templates use fixed canonical key order and JSON-native types. `normalisedChanges` and projected `changes` are inserted as canonical JSON values, not free-form string interpolation. The validator checks the closed projection IDs/fields/wrapper/template hashes and rejects unknown placeholders, literal secret/canary values, noncanonical templates, form editor bodies and any restore-stage template.

## 3. Observer registry v2

The file moves in place to `test10a-observer-registry-v2`; `registryReady=false`. Existing observer IDs remain, and `OBS-REV-E1` is appended as the seventh observer. All seven stay `unbound`.

`OBS-022-PROTECTED-UNCHANGED` becomes role-aware:

- common unchanged: URL, parent, page position, publication, grants, Stable, shared Header/Footer;
- employee branch unchanged: current owner-only H1/SEO/block layout/protected media;
- owner branch: those compatible snapshot fields are restored per D-261.

Its v2 `inputBindings` becomes the exact array `[UI-022-STAGE, UI-022-OWNER-CONTROL]` for employee direct restore and owner control; row26 is only a reference. All observer records use `inputBindings` arrays in v2, including single-input observers.

Its exact v2 output is `status`, `complete`, `commonUnchangedByField`, `employeeOwnerFieldsUnchangedByField`, `ownerSnapshotFieldsRestoredByField`. The three maps contain only the closed field names above and boolean values, never raw content. PASS requires `complete=true`, every common boolean true, every employee-owner-field boolean true on the employee branch and every owner-snapshot-restored boolean true on the owner branch. Missing branch/field is BLOCKED; any complete false is FAIL. The validator pins all three field-name arrays and this branch semantics.

`OBS-REV-E1` has:

- `inputBindings=[UI-023-OWNER-REVOKE]`;
- source candidates `accounts.models.PageGrant`, `accounts.models.UserProfile`, `audit.models.AuditEvent`;
- exact output `status`, `grantCountBefore`, `grantCountAfter`, `generationBefore`, `generationAfter`, `matchingAuditEvents`, `complete`;
- PASS only for `1→0`, `g→g+1`, and exact-one cursor-bounded event tuple: `category=access`, `level=INFO`, `code=AUTH_GRANT_REVOKED`, `source=application`, `result=SUCCESS`, owner actor ID, `object_kind=user`, `object_ref=id:{editUser}`, `occurrence_count=1`, `count_is_lower_bound=false`;
- missing authority/drift/concurrency gives BLOCKED; any complete wrong mutation gives FAIL.

No raw DB row, cursor, cookie, response body, secret or unapproved identifier enters case evidence.

## 4. Existing offline validator only

`scripts/test10-registries.ps1` is amended, not replaced. It remains PowerShell 5 compatible and offline. It validates:

- exact v2 schemas and allowed property sets;
- stable case/scenario/binding/content IDs and exact 40 execution order;
- tagged step variants, per-step actors/session/CSRF sources, closed transitions/actions/routes/methods, POST body presence and zero-request reference bindings;
- request-template canonical bytes, SHA-256, content type and closed placeholders; every literal/set/boundary member is referenced by an actual execution step, not only by a trace-group action;
- negative rows2/36 and every row33 `.plusOne` branch contain no save step; row33 member order and exact-accept/plusOne-refuse zero-mutation expectations are exact;
- direct restore has no stage route and row26 is exactly `bindingRef=UI-022-STAGE` with no request/evidence artifact;
- exactly one revoke request; row16 references `REV-E1`;
- exact seven observers, the three-map role-aware OBS-022 output/semantics and blocked/unbound OBS-REV-E1;
- `registryReady=false`, unboundBindings40, unboundObservers7, `dockerCalled=false`.

The validator must still emit one compact JSON result and must not read private files, environment secrets, Docker, network, browser or database.

## 5. Amendment and review sequence

1. Independently review this plan.
2. Amend only the four named files in one bounded patch.
3. Run only `powershell -File scripts/test10-registries.ps1` offline; no regression suite is involved.
4. Independently review the four-file diff and validator output.
5. Keep registry/execution/Q003 closed. Any future binding implementation or TEST-10 run requires a separate owner gate.

No product test is required for this registry-only amendment. If a later regression is needed for product changes, it remains restricted to exact suites through `scripts/test-editor.ps1`, without wildcard or Playwright.
