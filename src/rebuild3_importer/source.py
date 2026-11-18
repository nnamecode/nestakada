from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, Protocol, Sequence

from rebuild3_importer.errors import SourceReadError


SHA256 = re.compile(r"^[0-9a-f]{64}$")
SNAPSHOT_ID = re.compile(r"^[0-9]+:[0-9]+:[0-9,]*$")
MAX_STAFF = 64
MAX_PAGES = 115
MAX_GRANTS = MAX_STAFF * MAX_PAGES
MAX_PROVENANCE = MAX_PAGES * 2

# These are deliberately literal queries.  The one-shot importer has no query
# builder and accepts no table, column or predicate input.
PREFLIGHT_SQL = """
WITH
selected_current AS (
  SELECT s.page_id, r.id, r.sequence, r.author_id
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r
    ON r.id = s.current_revision_id AND r.page_id = s.page_id
  WHERE r.kind IN ('initial', 'automatic')
),
selected_previous AS (
  SELECT c.page_id, p.id, p.author_id
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id, r.author_id
    FROM app.page_versions_pagerevision r
    WHERE r.page_id = c.page_id AND r.sequence < c.sequence
      AND r.kind IN ('initial', 'automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
),
request_count AS (
  SELECT count(id) AS value FROM app.service_requests_servicerequest
),
staff_candidate AS (
  SELECT user_id AS id FROM app.accounts_userprofile
  UNION SELECT user_id FROM app.accounts_pagegrant
  UNION SELECT id FROM app.auth_user WHERE is_staff OR is_superuser
  UNION SELECT author_id FROM selected_current
  UNION SELECT author_id FROM selected_previous WHERE id IS NOT NULL
),
valid_staff AS (
  SELECT c.id
  FROM staff_candidate c
  JOIN app.auth_user u ON u.id = c.id
  JOIN app.accounts_userprofile p
    ON p.user_id = u.id AND p.role IN ('owner', 'employee')
  GROUP BY c.id HAVING count(*) = 1
)
SELECT
  pg_backend_pid(),
  txid_current(),
  CASE WHEN current_user = 'estakada_rebuild_reader'
         AND current_database() = 'estakada_foundation'
         AND current_setting('transaction_read_only') = 'on'
         AND current_setting('transaction_isolation') = 'repeatable read'
         AND COALESCE((SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()), false)
       THEN txid_current_snapshot()::text END,
  count(*) FILTER (WHERE f.code = 'active-requests'),
  count(*) FILTER (WHERE f.code = 'current-author'),
  count(*) FILTER (WHERE f.code = 'previous-author'),
  count(*) FILTER (WHERE f.code = 'invalid-staff'),
  count(*) FILTER (WHERE f.code = 'staff-shape'),
  count(*) FILTER (WHERE f.code = 'owner-count'),
  count(*) FILTER (WHERE f.code = 'grant-user'),
  count(*) FILTER (WHERE f.code = 'grant-page'),
  count(*) FILTER (WHERE f.code = 'grant-groups'),
  (SELECT count(*) FROM app.accounts_userprofile),
  (SELECT count(*) FROM app.accounts_pagegrant),
  (SELECT count(*) FROM selected_current),
  (SELECT count(*) FROM selected_previous WHERE id IS NOT NULL)
FROM (
  SELECT 'active-requests' AS code FROM request_count WHERE value <> 0
  UNION ALL SELECT 'current-author' FROM selected_current c
    LEFT JOIN valid_staff v ON v.id = c.author_id
    WHERE c.author_id IS NULL OR c.author_id <= 0 OR v.id IS NULL
  UNION ALL SELECT 'previous-author' FROM selected_previous p
    LEFT JOIN valid_staff v ON v.id = p.author_id
    WHERE p.id IS NOT NULL AND (p.author_id IS NULL OR p.author_id <= 0 OR v.id IS NULL)
  UNION ALL SELECT 'invalid-staff' FROM staff_candidate c
    LEFT JOIN valid_staff v ON v.id = c.id WHERE v.id IS NULL
  UNION ALL SELECT 'staff-shape' FROM app.auth_user u
    JOIN app.accounts_userprofile p ON p.user_id = u.id
    WHERE (p.role = 'owner' AND (u.username <> 'nesadmin' OR NOT u.is_active OR NOT u.is_staff OR NOT u.is_superuser))
       OR (p.role = 'employee' AND (u.username = 'nesadmin' OR NOT u.is_staff OR u.is_superuser))
  UNION ALL SELECT 'owner-count'
    WHERE (SELECT count(*) FROM app.accounts_userprofile WHERE role = 'owner') <> 1
  UNION ALL SELECT 'grant-user' FROM app.accounts_pagegrant g
    LEFT JOIN valid_staff v ON v.id = g.user_id
    LEFT JOIN app.accounts_userprofile p ON p.user_id = g.user_id
    LEFT JOIN app.auth_user u ON u.id = g.user_id
    WHERE v.id IS NULL OR p.role <> 'employee' OR NOT u.is_active
  UNION ALL SELECT 'grant-page' FROM app.accounts_pagegrant g
    LEFT JOIN app.content_page p ON p.id = g.page_id WHERE p.id IS NULL
  UNION ALL SELECT 'grant-groups' FROM app.accounts_pagegrant g
    JOIN app.content_page p ON p.id = g.page_id
    WHERE NOT (g.intro_text OR g.main_text OR g.price)
       OR ((g.intro_text OR g.main_text) AND p.kind NOT IN (
             'service_section_overview', 'service_detail', 'article',
             'legacy_news_article', 'service_wash_legacy_alias'))
       OR (g.price AND p.kind NOT IN ('service_detail', 'service_wash_legacy_alias'))
) f
""".strip()

STAFF_SQL = """
WITH guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::bigint, NULL::text, NULL::boolean, NULL::text, NULL::bigint
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       u.id, u.username, u.is_active, p.role, p.generation
FROM guard CROSS JOIN app.auth_user u
JOIN app.accounts_userprofile p ON p.user_id = u.id
WHERE p.role IN ('owner', 'employee')
ORDER BY 1, 5
""".strip()

PRIVATE_BINDINGS_SQL = """
WITH
guard AS (
  SELECT pg_backend_pid() AS backend_pid, txid_current() AS transaction_id,
         txid_current_snapshot()::text AS snapshot_id
),
selected_current AS (
  SELECT s.page_id, r.id, r.sequence, r.author_id
  FROM app.page_versions_pagecontentstate s
  JOIN app.page_versions_pagerevision r
    ON r.id = s.current_revision_id AND r.page_id = s.page_id
  WHERE r.kind IN ('initial', 'automatic')
),
selected_previous AS (
  SELECT c.page_id, p.id, p.author_id
  FROM selected_current c
  LEFT JOIN LATERAL (
    SELECT r.id, r.author_id
    FROM app.page_versions_pagerevision r
    WHERE r.page_id = c.page_id AND r.sequence < c.sequence
      AND r.kind IN ('initial', 'automatic')
    ORDER BY r.sequence DESC LIMIT 1
  ) p ON true
)
SELECT 0, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       NULL::text, NULL::uuid, NULL::bigint,
       NULL::boolean, NULL::boolean, NULL::boolean
FROM guard
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       'grant', g.page_id, g.user_id,
       g.intro_text, g.main_text, g.price
FROM guard CROSS JOIN app.accounts_pagegrant g
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       'current', c.page_id, c.author_id, false, false, false
FROM guard CROSS JOIN selected_current c
UNION ALL
SELECT 1, guard.backend_pid, guard.transaction_id, guard.snapshot_id,
       'previous', p.page_id, p.author_id, false, false, false
FROM guard CROSS JOIN selected_previous p WHERE p.id IS NOT NULL
ORDER BY 1, 5, 6, 7
""".strip()


class SourceExecutor(Protocol):
    def fetch_one(self, sql: str) -> Sequence[object]: ...

    def fetch_all(self, sql: str) -> Iterable[Sequence[object]]: ...


@dataclass(frozen=True, slots=True, repr=False)
class SourceSession:
    backend_pid: int
    transaction_id: int
    snapshot_id: str


@dataclass(frozen=True, slots=True, repr=False)
class VerifiedLedgerEvidence:
    identity: uuid.UUID
    generation: int
    digest: str
    row_count: int
    snapshot_id: str


@dataclass(frozen=True, slots=True, repr=False)
class SourcePreflight:
    ledger: VerifiedLedgerEvidence
    staff_count: int
    grant_count: int
    current_count: int
    previous_count: int


class LatestLedgerVerifier(Protocol):
    def latest_for(self, snapshot_id: str) -> VerifiedLedgerEvidence: ...


def valid_snapshot_id(value: object) -> bool:
    return isinstance(value, str) and SNAPSHOT_ID.fullmatch(value) is not None


def valid_ledger_evidence(value: object, expected_snapshot_id: str) -> bool:
    return (
        valid_snapshot_id(expected_snapshot_id)
        and isinstance(value, VerifiedLedgerEvidence)
        and isinstance(value.identity, uuid.UUID)
        and value.identity.int != 0
        and not isinstance(value.generation, bool)
        and isinstance(value.generation, int)
        and value.generation >= 1
        and isinstance(value.digest, str)
        and SHA256.fullmatch(value.digest) is not None
        and not isinstance(value.row_count, bool)
        and isinstance(value.row_count, int)
        and value.row_count == 0
        and value.snapshot_id == expected_snapshot_id
    )


@dataclass(frozen=True, slots=True, repr=False)
class TargetStaff:
    id: uuid.UUID
    username: str
    is_active: bool
    role: str
    generation: int


@dataclass(frozen=True, slots=True, repr=False)
class TargetPageRef:
    id: uuid.UUID
    kind: str


@dataclass(frozen=True, slots=True, repr=False)
class TargetGrant:
    staff_id: uuid.UUID
    page_id: uuid.UUID
    groups: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class TargetProvenance:
    page_id: uuid.UUID
    version: str
    staff_id: uuid.UUID


@dataclass(frozen=True, slots=True, repr=False)
class PrivateSourceRows:
    staff: tuple[TargetStaff, ...]
    grants: tuple[TargetGrant, ...]
    provenance: tuple[TargetProvenance, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _PrivateCounts:
    staff: int
    grants: int
    current: int
    previous: int


class _PrivateStaffMap:
    __slots__ = ("_values", "_closed")

    def __init__(self) -> None:
        self._values: dict[int, uuid.UUID] = {}
        self._closed = False

    def __repr__(self) -> str:
        return "<PrivateStaffMap closed>" if self._closed else f"<PrivateStaffMap size={len(self._values)}>"

    def add(self, source_key: object, target_id: uuid.UUID) -> None:
        key = _positive_int(source_key, "staff-key")
        if self._closed:
            raise SourceReadError("staff-map-closed")
        if key in self._values or target_id in self._values.values():
            raise SourceReadError("staff-map-duplicate")
        if not isinstance(target_id, uuid.UUID) or target_id.version != 4 or target_id.variant != uuid.RFC_4122:
            raise SourceReadError("staff-uuid")
        self._values[key] = target_id

    def resolve(self, source_key: object) -> uuid.UUID:
        key = _positive_int(source_key, "staff-key")
        if self._closed:
            raise SourceReadError("staff-map-closed")
        try:
            return self._values[key]
        except KeyError:
            raise SourceReadError("staff-unmapped") from None

    def close(self) -> None:
        self._values.clear()
        self._closed = True


def _positive_int(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SourceReadError(code)
    return value


def _uuid4(factory: Callable[[], uuid.UUID]) -> uuid.UUID:
    value = factory()
    if not isinstance(value, uuid.UUID) or value.version != 4 or value.variant != uuid.RFC_4122:
        raise SourceReadError("staff-uuid")
    return value


def _target_page(resolver: Callable[[uuid.UUID], TargetPageRef], source_key: object) -> TargetPageRef:
    if not isinstance(source_key, uuid.UUID) or source_key.int == 0:
        raise SourceReadError("page-key")
    try:
        value = resolver(source_key)
    except (KeyError, LookupError):
        raise SourceReadError("page-unmapped") from None
    if (
        not isinstance(value, TargetPageRef)
        or not isinstance(value.id, uuid.UUID)
        or not isinstance(value.kind, str)
        or not value.kind
    ):
        raise SourceReadError("page-ref")
    return value


def _grant_groups(page_kind: str, intro: bool, main: bool, price: bool) -> tuple[str, ...]:
    groups = tuple(group for group, present in (("text", intro or main), ("prices", price)) if present)
    allowed = {
        "service_section_overview": frozenset({"text"}),
        "service_detail": frozenset({"text", "prices"}),
        "article": frozenset({"text"}),
        "legacy_news_article": frozenset({"text"}),
    }.get(page_kind, frozenset())
    if not groups or not set(groups) <= allowed:
        raise SourceReadError("grant-groups")
    return groups


def _guard(row: Sequence[object], session: SourceSession, width: int) -> bool:
    if len(row) != width or type(row[0]) is not int or row[0] not in (0, 1):
        raise SourceReadError("private-row")
    if (
        row[1] != session.backend_pid
        or row[2] != session.transaction_id
        or row[3] != session.snapshot_id
    ):
        raise SourceReadError("source-session-drift")
    return row[0] == 0


class SourceReader:
    """One-snapshot reader bound to the open repeatable-read read-only transaction."""

    __slots__ = ("_executor", "_session", "_ledger", "_page", "_uuid4", "_map", "_counts", "_ready", "_read", "_closed")

    def __init__(
        self,
        executor: SourceExecutor,
        source_session: SourceSession,
        ledger_verifier: LatestLedgerVerifier,
        page_resolver: Callable[[uuid.UUID], TargetPageRef],
        *,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._executor = executor
        self._session = source_session
        self._ledger = ledger_verifier
        self._page = page_resolver
        self._uuid4 = uuid_factory
        self._map = _PrivateStaffMap()
        self._counts: _PrivateCounts | None = None
        self._ready = False
        self._read = False
        self._closed = False

    def __repr__(self) -> str:
        state = "closed" if self._closed else ("ready" if self._ready else "new")
        return f"<SourceReader state={state}>"

    def preflight(self, expected_snapshot_id: str) -> SourcePreflight:
        try:
            if self._closed or self._ready:
                raise SourceReadError("source-state")
            if (
                not isinstance(self._session, SourceSession)
                or isinstance(self._session.backend_pid, bool)
                or not isinstance(self._session.backend_pid, int)
                or self._session.backend_pid <= 0
                or isinstance(self._session.transaction_id, bool)
                or not isinstance(self._session.transaction_id, int)
                or self._session.transaction_id <= 0
                or not valid_snapshot_id(self._session.snapshot_id)
                or expected_snapshot_id != self._session.snapshot_id
            ):
                raise SourceReadError("source-session")
            row = tuple(self._executor.fetch_one(PREFLIGHT_SQL))
            if (
                len(row) != 16
                or type(row[0]) is not int
                or type(row[1]) is not int
                or row[0] != self._session.backend_pid
                or row[1] != self._session.transaction_id
                or row[2] != expected_snapshot_id
            ):
                raise SourceReadError("source-session-drift")
            for value in row[3:12]:
                if isinstance(value, bool) or not isinstance(value, int) or value != 0:
                    raise SourceReadError("pretarget-gate")
            counts = row[12:16]
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
                raise SourceReadError("private-counts")
            staff_count, grant_count, current_count, previous_count = counts
            if (
                staff_count > MAX_STAFF
                or grant_count > MAX_GRANTS
                or current_count > MAX_PAGES
                or previous_count > MAX_PAGES
                or current_count + previous_count > MAX_PROVENANCE
            ):
                raise SourceReadError("private-cap")
            evidence = self._ledger.latest_for(expected_snapshot_id)
            if not valid_ledger_evidence(evidence, expected_snapshot_id):
                raise SourceReadError("ledger-evidence")
            self._counts = _PrivateCounts(*counts)
            self._ready = True
            return SourcePreflight(
                evidence,
                staff_count,
                grant_count,
                current_count,
                previous_count,
            )
        except SourceReadError:
            self.close()
            raise
        except Exception:
            self.close()
            raise SourceReadError("source-preflight") from None

    def read_private(self) -> PrivateSourceRows:
        if self._closed or not self._ready or self._read:
            raise SourceReadError("source-state")
        staff: list[TargetStaff] = []
        seen_names: set[str] = set()
        grantable_staff: set[uuid.UUID] = set()
        try:
            staff_guard = False
            for raw in self._executor.fetch_all(STAFF_SQL):
                row = tuple(raw)
                if _guard(row, self._session, 9):
                    if staff_guard or any(value is not None for value in row[4:]):
                        raise SourceReadError("staff-guard")
                    staff_guard = True
                    continue
                if not staff_guard:
                    raise SourceReadError("staff-guard")
                if self._counts is None or len(staff) >= self._counts.staff:
                    raise SourceReadError("staff-count")
                source_key, username, is_active, role, generation = row[4:]
                if (
                    not isinstance(username, str)
                    or not username
                    or username in seen_names
                    or type(is_active) is not bool
                    or role not in ("owner", "employee")
                ):
                    raise SourceReadError("staff-row")
                target_id = _uuid4(self._uuid4)
                self._map.add(source_key, target_id)
                seen_names.add(username)
                if role == "employee" and is_active:
                    grantable_staff.add(target_id)
                staff.append(TargetStaff(target_id, username, is_active, role.upper(), _positive_int(generation, "staff-generation")))
            if not staff_guard:
                raise SourceReadError("staff-guard")
            if self._counts is None or len(staff) != self._counts.staff:
                raise SourceReadError("staff-count")

            grants: list[TargetGrant] = []
            provenance: list[TargetProvenance] = []
            seen_grants: set[tuple[uuid.UUID, uuid.UUID]] = set()
            seen_provenance: set[tuple[uuid.UUID, str]] = set()
            current_count = 0
            previous_count = 0
            binding_guard = False
            for raw in self._executor.fetch_all(PRIVATE_BINDINGS_SQL):
                row = tuple(raw)
                if _guard(row, self._session, 10):
                    if binding_guard or any(value is not None for value in row[4:]):
                        raise SourceReadError("binding-guard")
                    binding_guard = True
                    continue
                if not binding_guard:
                    raise SourceReadError("binding-guard")
                kind, source_page, source_staff, intro, main, price = row[4:]
                page = _target_page(self._page, source_page)
                staff_id = self._map.resolve(source_staff)
                if kind == "grant":
                    if self._counts is None or len(grants) >= self._counts.grants:
                        raise SourceReadError("binding-count")
                    if staff_id not in grantable_staff or any(type(flag) is not bool for flag in (intro, main, price)):
                        raise SourceReadError("grant-row")
                    groups = _grant_groups(page.kind, intro, main, price)
                    key = (staff_id, page.id)
                    if key in seen_grants:
                        raise SourceReadError("grant-duplicate")
                    seen_grants.add(key)
                    grants.append(TargetGrant(staff_id, page.id, groups))
                elif kind in ("current", "previous"):
                    if self._counts is None:
                        raise SourceReadError("binding-count")
                    if kind == "current":
                        if current_count >= self._counts.current:
                            raise SourceReadError("binding-count")
                        current_count += 1
                    else:
                        if previous_count >= self._counts.previous:
                            raise SourceReadError("binding-count")
                        previous_count += 1
                    if (intro, main, price) != (False, False, False):
                        raise SourceReadError("provenance-row")
                    key = (page.id, kind)
                    if key in seen_provenance:
                        raise SourceReadError("provenance-row")
                    seen_provenance.add(key)
                    provenance.append(TargetProvenance(page.id, kind.upper(), staff_id))
                else:
                    raise SourceReadError("binding-kind")
            if not binding_guard:
                raise SourceReadError("binding-guard")
            if (
                self._counts is None
                or len(grants) != self._counts.grants
                or current_count != self._counts.current
                or previous_count != self._counts.previous
            ):
                raise SourceReadError("binding-count")
            result = PrivateSourceRows(tuple(staff), tuple(grants), tuple(provenance))
            self._read = True
            return result
        except SourceReadError:
            self.close()
            raise
        except Exception:
            self.close()
            raise SourceReadError("source-private-read") from None

    def close(self) -> None:
        self._map.close()
        self._closed = True
        self._ready = False
        self._read = False
        self._counts = None
