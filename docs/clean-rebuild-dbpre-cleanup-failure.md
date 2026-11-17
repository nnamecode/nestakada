# Full DBPRE cleanup-stage failure

Дата: 2026-11-17. Evidence ID: `RB1-CLEANUP-RUN-001`.

Fresh full run after D-1283 ended:

`{"contract":"rb1-dbpre-v1","status":"FAIL","code":"DBPRE_FAILED_CLEANUP"}`

PRECHECK/START/ROLE/READ did not emit their bounded stage code, but facts/PASS are not claimed because cleanup is mandatory and output was suppressed.

Postcondition sequence:

- initial catalog check command was safely rejected because it would down pre-existing containers;
- changed read-only inventory: project containers0, host secret absent;
- catalog-only query found exact role PRESENT and already NOLOGIN with exact flags/limit/validity/settings, memberships0/ownerships0;
- exact conditional transaction rechecked signature/fresh validity/sessions/membership/ownership, literal-revoked 14 tables/schema/database, dropped exact role;
- result `ROLE_CLEANUP=PASS`, `TEARDOWN=PASS`, host secret absent.

No subject rows were read during postcondition/cleanup. Final state: container0, secret0, role0.

Next minimal proposal: fixed cleanup substage codes ROLE / CONTAINER_FILES / HOST_SECRET / COMPOSE, first failure wins. No raw errors/logging/framework and no cleanup semantic change. Requires review and fresh execution gate.
