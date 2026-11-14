"""Fixed TEST-10A data preparation for a fresh disposable database.

This module is test-only infrastructure.  It deliberately exposes no URL,
model, background process, or arbitrary fixture selector.
"""
from datetime import timedelta
from hashlib import sha256
import json
import re
from uuid import uuid4

from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.db import models
from django.utils import timezone

from accounts import services as auth
from accounts.models import UserProfile
from content.models import Page, Route
from page_versions import schema, services as versions
from page_versions.models import (PageContentState, PageRevision,
                                  RevisionMetadata, RevisionProtection)
from shared_content.models import SharedBlock
from shared_content.simple_commands import commit_normalized_current


SCHEMA = "test10a-fixture-v1"
DATABASE_PATTERN = re.compile(r"\Aestakada_test10_[a-f0-9]{32}\Z")
PROFILES = (
    "FX-IDENTITY",
    "FX-CONTENT",
    "assigned-page-with-owner-draft",
    "controlled-session-boundary",
    "page-history-restore",
)
CASE_IDS = (
    "AC-013", "AC-014", "AC-015", "AC-021", "AC-022", "AC-023",
    "AC-DTL-004", "AC-DTL-006", "AC-DTL-018",
)


def validate_database_name(value):
    if not isinstance(value, str) or DATABASE_PATTERN.fullmatch(value) is None:
        raise ValueError("T10_FIXTURE_DATABASE_REJECTED")
    return value


def _raw(model):
    return models.QuerySet(model=model, using="default")


def _session(user, *, instant, issued_age=0, seen_age=0):
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    store[HASH_SESSION_KEY] = user.get_session_auth_hash()
    store[auth.SESSION_GENERATION] = UserProfile.objects.get(user=user).generation
    store[auth.SESSION_ISSUED_AT] = (instant - timedelta(seconds=issued_age)).isoformat()
    store[auth.SESSION_LAST_SEEN] = (instant - timedelta(seconds=seen_age)).isoformat()
    store.set_expiry(int(auth.IDLE.total_seconds()))
    store.create()
    return store.session_key


def _shared(owner, owner_session, kind, html):
    block = SharedBlock(id=uuid4(), kind=kind, generation=1)
    _raw(SharedBlock).bulk_create([block])
    revision = commit_normalized_current(
        actor=owner, kind=kind, expected_generation=1,
        session_key=owner_session, expected_current_id=None,
        html=html, bindings=[])
    return block, revision


def _safe_hash(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def prepare(*, database_name, secrets, reference_instant=None):
    """Prepare the only admitted TEST-10A fixture in an empty database."""
    validate_database_name(database_name)
    if set(secrets) != {"owner", "s_edit", "s_other", "canary"}:
        raise ValueError("T10_FIXTURE_SECRET_SET_REJECTED")
    if any(not isinstance(value, str) or len(value) < 32 for value in secrets.values()):
        raise ValueError("T10_FIXTURE_SECRET_VALUE_REJECTED")
    if (get_user_model().objects.exists() or Page.objects.exists()
            or SharedBlock.objects.exists()):
        raise RuntimeError("T10_FIXTURE_DATABASE_NOT_EMPTY")
    instant = reference_instant or timezone.now()
    if instant.tzinfo is None:
        raise ValueError("T10_FIXTURE_INSTANT_REJECTED")

    owner = auth.bootstrap_owner(secrets["owner"])
    s_edit = auth.create_employee(
        actor=owner, username="test10-s-edit", password=secrets["s_edit"])
    s_other = auth.create_employee(
        actor=owner, username="test10-s-other", password=secrets["s_other"])

    page = Page.objects.create(
        kind=Page.Kind.ARTICLE, name="TEST-10A assigned page",
        position=0, is_published=True)
    route = Route.objects.create(
        page=page, kind=Route.Kind.PRIMARY, target="/test10/assigned/")
    auth.set_grant(actor=owner, employee=s_edit, page=page,
                   intro_text=True, main_text=True)

    initial = versions.initialize(
        actor=owner, page_id=page.pk,
        snapshot=schema.snapshot_v1(
            page.kind, h1="TEST-10A heading", title="TEST-10A title",
            intro_text="<p>TEST10-INTRO</p>",
            main_text="<p>TEST10-HISTORICAL-ALLOWED</p>"),
        expected_generation=1, operation_id=uuid4())["result_id"]
    second = versions.commit_owner(
        actor=owner, page_id=page.pk, base_revision=initial,
        snapshot=schema.snapshot_v1(
            page.kind, h1="TEST-10A heading", title="TEST-10A title",
            intro_text="<p>TEST10-INTRO</p>",
            main_text="<p>TEST10-CURRENT</p>"),
        expected_generation=1, operation_id=uuid4())["result_id"]
    first_row = PageRevision.objects.get(pk=initial)
    RevisionProtection.objects.create(
        revision=first_row, marked_by_id=owner.pk, marked_at=timezone.now())

    current = PageRevision.objects.get(pk=second)
    incompatible = PageRevision.objects.create(
        page=page, sequence=3, schema_version="test10-incompatible-v0",
        payload=current.payload, payload_hash=current.payload_hash,
        kind=PageRevision.Kind.MANUAL, created_at=timezone.now(),
        author_id=owner.pk, source_revision_id=current.pk)
    RevisionMetadata.objects.create(
        revision=incompatible, name="TEST10 incompatible", comment="")
    _raw(PageContentState).filter(page=page).update(sequence=3)

    versions.save_owner_draft(
        actor=owner, page_id=page.pk, base_revision=second,
        snapshot=schema.snapshot_v1(
            page.kind, h1="TEST-10A heading", title="TEST-10A title",
            main_text="<p>TEST10-OWNER-DRAFT</p>"),
        expected_generation=1, operation_id=uuid4())

    owner_session = _session(owner, instant=instant)
    edit_session = _session(s_edit, instant=instant)
    other_session = _session(s_other, instant=instant)
    idle_session = _session(s_edit, instant=instant,
                            issued_age=1801, seen_age=1801)
    absolute_session = _session(s_edit, instant=instant,
                                issued_age=43201, seen_age=0)
    header, header_revision = _shared(
        owner, owner_session, "header", "<header>TEST10-HEADER</header>")
    footer, footer_revision = _shared(
        owner, owner_session, "footer", "<footer>TEST10-FOOTER</footer>")

    identifiers = {
        "page": str(page.pk), "route": str(route.pk),
        "currentRevision": str(second), "historicalRevision": str(initial),
        "incompatibleRevision": str(incompatible.pk),
        "headerBlock": str(header.pk), "headerRevision": str(header_revision.pk),
        "footerBlock": str(footer.pk), "footerRevision": str(footer_revision.pk),
        "ownerUser": owner.pk, "editUser": s_edit.pk, "otherUser": s_other.pk,
    }
    descriptor = {
        "routeTarget": route.target,
        "roles": {"OWNER": "owner", "S-EDIT": "employee",
                  "S-OTHER": "employee"},
        "grant": {"actor": "S-EDIT", "page": "P-ASSIGNED",
                  "introText": True, "mainText": True, "price": False},
        "page": {"published": page.is_published,
                 "currentPayloadHash": current.payload_hash,
                 "historicalPayloadHash": first_row.payload_hash,
                 "stableRevision": str(first_row.pk),
                 "incompatibleSchema": incompatible.schema_version,
                 "ownerDraftPayloadHash": page.owner_draft.payload_hash},
        "shared": {"headerCurrentHash": header_revision.payload_hash,
                   "footerCurrentHash": footer_revision.payload_hash},
        "sessionAges": {"active": {"issued": 0, "lastSeen": 0},
                        "idleExpired": {"issued": 1801, "lastSeen": 1801},
                        "absoluteExpired": {"issued": 43201, "lastSeen": 0}},
    }
    private = {
        "schema": SCHEMA, "passwords": {
            "OWNER": secrets["owner"], "S-EDIT": secrets["s_edit"],
            "S-OTHER": secrets["s_other"]},
        "sessions": {"OWNER": owner_session, "S-EDIT": edit_session,
                     "S-OTHER": other_session, "S-EDIT-IDLE-1801": idle_session,
                     "S-EDIT-ABSOLUTE-43201": absolute_session},
        "canary": secrets["canary"], "referenceInstant": instant.isoformat(),
    }
    summary = {
        "schema": SCHEMA, "profiles": list(PROFILES), "caseIds": list(CASE_IDS),
        "identifiers": identifiers, "descriptor": descriptor,
        "fixtureHash": _safe_hash({"profiles": PROFILES, "caseIds": CASE_IDS,
                                    "identifiers": identifiers,
                                    "descriptor": descriptor}),
        "containsSecrets": False,
    }
    return summary, private
