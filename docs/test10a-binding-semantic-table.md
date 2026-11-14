# TEST-10A — semantic table for all 40 bindings

Status D-1072, 2026-11-14: independently `APPROVED`, P1/P2/P3=0/0/0. This is a read-only reconciliation of the existing unbound registry with current product routes and D-1071. It does not amend JSON, prepare a fixture, execute HTTP/browser/Docker, promote acceptance, or open `TEST10-Q003`.

## Exact reusable request contracts

- `EDITOR-CHECK`: `POST /manage/pages/{page}/edit/check/`, `application/json`, CSRF and the actor session. The JSON object has exactly `protocol`, `generation`, `baseRevisionId`, `editingFrom`, `draftBasis`, `stageId`, `changes`; `protocol="page-editor-v1"`, `editingFrom="current"`, `draftBasis=null`, `stageId=null`. `changes` contains only fields allowed to the actor. The response supplies exact `normalisedChanges` and a signed `checkReceipt`.
- `EDITOR-SAVE`: `POST /manage/pages/{page}/edit/save/`, `application/json`, CSRF and the same actor session. Its object is the exact `EDITOR-CHECK` object with `changes` replaced by returned `normalisedChanges` plus fresh UUID `operationId` and returned `checkReceipt`. A form body, a literal registry reference or client-invented normalisation is invalid. The signed receipt is not inherently single-use: it remains valid only while its bound actor/session/generation/page/basis/source/changes and server context remain exact. Current advancement, changed context and operation conflict are evaluated by separate save/idempotence rules.
- `LOGIN`: `POST /manage/login/`, `application/x-www-form-urlencoded`, CSRF, exactly `username` and literal synthetic `password`. `passwordRef` is registry metadata and is never sent.
- `PASSWORD-BODY`: `POST /manage/employees/{employee}/password/`, form with exactly literal synthetic `password`. Employee ID exists only in the route; `employee` and `passwordRef` are not body fields. Each row separately fixes actor/session/CSRF expectations for owner success or employee denial.
- `GRANT-REVOKE`: `POST /manage/employees/{employee}/grants/`, owner session and CSRF, form `page={page}&action=revoke`; optional capability fields are absent. Employee ID exists only in the route.
- `RESTORE-PREPARE`: `POST /manage/pages/{page}/versions/{version}/restore/prepare/`, actor session and CSRF, form with exactly current integer `generation`. It is read-only and returns a signed `preparation`, displayed allowed fields and a fresh rendered `operation_id`.
- `RESTORE-APPLY`: `POST /manage/pages/{page}/versions/{version}/restore/apply/`, same actor session and CSRF, form with exactly current `generation`, fresh rendered `operation_id`, returned `preparation`, and `confirm_input_replacement=yes`. It revalidates source/current/rights and atomically creates one current revision. No new `restore/stage/` call is allowed.
- Read routes have no request body. Version comparison is `GET /manage/pages/{page}/versions/{version}/compare/`; version read is `.../{version}/`; history is `.../versions/`. UI cancel is local navigation/no mutation, not a POST endpoint.

Dynamic values come only from the signed fixture summary/private handoff and current rendered responses: page/revision/user IDs, session cookies, CSRF tokens, auth generation, check receipt, restore preparation and operation UUID. They are never copied from guessed CLI values or persisted in evidence. All private responses must remain `private, no-store`; evidence stores only approved derived fields.

## One-Prepare isolation and order

The single fixture Prepare remains mandatory. To avoid regrant, a second Prepare and a new isolation subsystem, all employee-dependent checks run before one shared destructive tail. Exact superseding global action order by row number: `1–5, 12, 13, 6, 7, 9, 10, 8, 11, 14, 15, 18–28, 32–40, 29, 30, 31, 16, 17`. Aged sessions are therefore observed before password generation changes; new-password login precedes the valid non-owner password denial; every normal employee/editor check precedes revoke; AC-023 compare is immediately before revoke.

Row30 is the only revoke request. Its proposed non-secret evidence event is `REV-E1` with exact fields `evidenceId=REV-E1`, `canonicalActionId=UI-023-OWNER-REVOKE`, `method=POST`, `routeTemplate=/manage/employees/{employee}/grants/`, `responseStatus=303`, `grantAbsent=true`, `generationAdvanced=true`, `mutationCount=1`. The 303 supplies only `responseStatus`. The other fields remain **BLOCKED** until a reviewed read-only `OBS-REV-E1` is added to the observer registry. Its exact candidate authorities are: `accounts.models.PageGrant` count for fixture `(editUser,page)` changes `1→0`; `accounts.models.UserProfile.generation` for `editUser` changes `g→g+1`; and `audit.models.AuditEvent` delta between observer-owned before/after PK cursors contains exactly one row with `category=access`, `level=INFO`, `code=AUTH_GRANT_REVOKED`, `source=application`, `result=SUCCESS`, `actor_id={identifiers.ownerUser}`, `object_kind=user`, `object_ref=id:{identifiers.editUser}`, `occurrence_count=1`, `count_is_lower_bound=false`. The isolated run admits no concurrent fixture mutation between the two cursors. No raw rows, secrets, cookies or IDs beyond approved fixture identifiers enter evidence. Row16 performs no request and may record only `evidenceRef=REV-E1` after that observer is approved. The future registry/run manifest must explicitly supersede the current case-local order; until then rows16/30 and `REV-E1` remain blocked.

## All 40 rows

| # | Binding | Exact target contract | Pre-state and dynamic inputs | Expected post-state / oracle | Isolation / current disposition |
|---:|---|---|---|---|---|
| 1 | `UI-013-SAFE` | visitor `GET /test10/assigned/` | published fixture route | 200 ordinary page contains real shared Header and Footer; no mutation | independent; route-ready |
| 2 | `HTTP-013-ACTIVE` | `EDITOR-CHECK` only for each member of `P104-ACTIVE-SET`; `EDITOR-SAVE` is prohibited | fresh current basis per member | every member refused; zero revision/current mutation, execution or egress | current form body invalid; rewrite to negative JSON check |
| 3 | `HTTP-013-HEADER` | visitor `GET /header/` | none | not a standalone Page and no private/shared component body disclosure | exact response class still must be bound |
| 4 | `HTTP-013-FOOTER` | visitor `GET /footer/` | none | same as row3 | exact response class still must be bound |
| 5 | `UI-013-POSITIVE` | `EDITOR-CHECK` + `EDITOR-SAVE` with `P013-SAFE` | S-EDIT current session, fresh basis/receipt/op UUID | one new revision and published permitted content; shared/protected fields unchanged | generic `/edit/` POST invalid; rewrite sequence |
| 6 | `UI-014-OWNER-RESET` | `PASSWORD-BODY` with literal generated new synthetic password | owner session and CSRF; employee route ID | redirect/success; password generation advances; secret absent from evidence | body currently has two invalid fields |
| 7 | `HTTP-014-OLD-SESSIONS` | old S-EDIT session `GET /manage/pages/{page}/edit/` | session captured before reset | denied; no private canary/body and no mutation | after row6 |
| 8 | `HTTP-014-SELF-CHANGE` | S-EDIT `POST` with exact `PASSWORD-BODY` | valid non-owner session obtained by row10 and CSRF | owner gate denies before password mutation | body must be syntactically exact; current body invalid |
| 9 | `HTTP-014-SELF-RECOVERY` | `LOGIN` with literal old synthetic password | logged-out/fresh client | generic login denial; no recovery or auth mutation | current `passwordRef` invalid |
| 10 | `UI-014-NEW-LOGIN` | `LOGIN` with literal new synthetic password | fresh client | accepted session with current generation; secret not recorded | current `passwordRef` invalid |
| 11 | `UI-015-UNSAVED` | S-EDIT `GET /edit/`; enter canary locally without submit | valid new session | canary only in tab memory; server/site/history/storage unchanged | UI-only; no body |
| 12 | `HTTP-015-IDLE1801` | expired fixture session `GET /edit/` | exact idle-expired cookie at initial employee generation | denied specifically by idle boundary without mutation/private content | must run before row6; fixture clock/session binding required |
| 13 | `HTTP-015-ABS43201` | absolute-expired fixture session `GET /edit/` | exact absolute-expired cookie at initial employee generation | denied specifically by absolute boundary without mutation/private content | must run before row6; fixture clock/session binding required |
| 14 | `UI-015-RELOGIN` | `LOGIN` with literal new password | fresh client after expiry branch | accepted current session | may reuse semantic LOGIN contract, not secret bytes |
| 15 | `HTTP-015-OTHER-DENY` | S-OTHER `GET /edit/` | other employee session, assigned page ID | denied without closed page data | before destructive tail |
| 16 | `UI-015-OWNER-REVOKE` | no request; evidence reference `REV-E1` to canonical row30 revoke | `REV-E1` already recorded | proves AC-015 uses the same one revoke; no second mutation | destructive-tail reference, blocked until registry model review |
| 17 | `HTTP-015-REVOKED-DENY` | revoked employee `GET /edit/` | cookie after shared revoke | denied on the subsequent editor request; row31 is the first post-revoke request; no closed data/mutation | final destructive-tail observation |
| 18 | `UI-015-EXPLICIT-SAVE` | `EDITOR-CHECK` + `EDITOR-SAVE` with tab canary | valid S-EDIT session before revoke; fresh receipt/op UUID | exactly one revision only after explicit save | current form body invalid; must precede tail |
| 19 | `UI-021-HISTORY` | S-EDIT `GET /versions/` | valid grant before revoke | assigned page ordinary/manual/Stable labels visible | before tail |
| 20 | `UI-021-OWNER-CONTROL` | owner `GET /versions/` | owner session | same history plus owner controls | independent read |
| 21 | `HTTP-021-VISITOR` | visitor `GET /versions/` | no auth | denied/private content absent | response class binding required |
| 22 | `HTTP-021-S-OTHER` | S-OTHER `GET /versions/` | other employee session | denied/private history absent | before tail |
| 23 | `UI-022-COMPARE` | S-EDIT `GET /versions/{historical}/compare/` | granted session and historical ID | comparison visible; current/site/history unchanged | current generic read route wrong |
| 24 | `UI-022-CANCEL` | navigate away/back from comparison; no mutation request | snapshot before compare | no new revision, current unchanged | UI-only, not generic GET action |
| 25 | `UI-022-STAGE` | rename semantically to confirmed employee direct restore: `RESTORE-PREPARE` + `RESTORE-APPLY` | fresh granted branch; signed preparation/op UUID | one atomic current revision restoring only granted fields | action ID/oracle stale; no stage endpoint |
| 26 | `UI-022-SAVE` | retire as second save; evidence becomes the successful `RESTORE-APPLY` result from row25 | same branch | no additional editor save/revision | binding must be removed or converted to observation |
| 27 | `UI-022-OWNER-CONTROL` | owner compare, then owner `RESTORE-PREPARE` + `RESTORE-APPLY` on fresh branch | owner session and compatible historical ID | one revision restores full compatible Page content; URL/tree position/publication/grants/Stable/shared unchanged | role-aware positive control |
| 28 | `UI-023-INCOMPATIBLE` | S-EDIT `RESTORE-PREPARE` for incompatible version, or fail-closed prepare/apply sequence if prepare renders reasons | valid grant, incompatible ID | safe reasons; zero revision/current/media mutation | generic POST wrong; exact stop point must be bound |
| 29 | `UI-023-COMPARE-BEFORE-REVOKE` | S-EDIT `GET .../{historical}/compare/` | valid grant immediately before tail | comparison succeeds and does not mutate | compare route required |
| 30 | `UI-023-OWNER-REVOKE` | the only `GRANT-REVOKE` request; proposed evidence event `REV-E1` | owner session, CSRF, page/edit-user IDs; observer before cursor/state | 303 plus observer after state: grant absent, generation +1, exact one matching audit event | canonical mutation remains BLOCKED until `OBS-REV-E1` review |
| 31 | `UI-023-REVOKED` | revoked employee attempts `RESTORE-PREPARE` (and must never reach apply) | post-revoke cookie/generation | full denial, zero partial mutation | generic POST/body invalid; tail |
| 32 | `UI-023-COMPATIBLE-CONTROL` | granted employee `RESTORE-PREPARE` + `RESTORE-APPLY` | fresh compatible branch before revoke | one role-limited revision; protected/common fields follow D-1071 | must execute before rows29–31 |
| 33 | `UI-104-NORMALISE` | `EDITOR-CHECK` with `P013-SAFE`; inspect returned normalised bytes before save | valid grant/current basis | deterministic safe normalisation; check itself creates no revision | generic `/edit/` POST invalid |
| 34 | `UI-104-POSITIVE` | `EDITOR-CHECK` + `EDITOR-SAVE` using returned bytes | fresh receipt/op UUID | exactly one accepted revision | generic `/edit/` POST invalid |
| 35 | `UI-106-SAFE-LINKS` | for each `P106-SAFE-LINKS` value: fresh `EDITOR-CHECK` + `EDITOR-SAVE` | fresh basis/receipt for each value | allowed link preserved with required `noopener`; no extra network | generic `/edit/` POST invalid |
| 36 | `HTTP-106-PROTECTED-SET` | `EDITOR-CHECK` only using each `P106-UNSAFE-SET` in a granted link field; `EDITOR-SAVE` is prohibited | valid employee basis per member | every member refused; zero revision/current mutation, execution or egress | current save/form/content mapping is semantically wrong |
| 37 | `UI-106-POSITIVE` | independent fresh `EDITOR-CHECK` + `EDITOR-SAVE` with safe link | fresh basis/receipt/op UUID | positive accepted revision | generic `/edit/` POST invalid |
| 38 | `UI-118-VALIDATION` | `EDITOR-CHECK` with invalid synthetic change while tab holds canary | valid session | validation error; tab input retained locally; server/site/history unchanged | current generic POST/form invalid |
| 39 | `UI-118-EXPIRY` | open editor while valid, expire session, then attempted `EDITOR-CHECK` JSON | expired cookie; locally held canary | session denial; canary remains tab-only; no revision/storage leak | actor label alone insufficient; transition required |
| 40 | `UI-118-CONFLICT` | obtain check receipt, mutate current on separate reviewed branch, then `EDITOR-SAVE` with stale basis/receipt | two sessions/branches, fresh op UUID | conflict; tab input retained locally; no second/partial revision | current form body cannot create the intended conflict |

## Classification and next gate

- Route/body/UI amendment required: rows 2, 5–6, 8–10, 14, 16, 18, 23–40 (27 rows).
- Existing read route with missing exact response/session binding: rows 1, 3, 4, 7, 11–13, 15, 17, 19–22 (13 rows).
- Semantically ready registry rows: zero until the destructive-tail choice, `OBS-REV-E1`, role-aware observer schema, exact response classes and rewritten payload hashes receive independent review.

The next permitted step is independent review of this table and its 40-row completeness. JSON registry amendment, fixture execution, direct HTTP, browser, Docker, Foundation and `TEST10-Q003` remain closed.
