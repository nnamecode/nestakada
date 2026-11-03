"""Internal empty aggregate for the locked owner-only page creation command."""
from django.core.exceptions import ValidationError
from django.db import connection
from . import engine, schema
from .models import PageContentState, OwnerDraft, VersionBasePin


def initial_snapshot(kind, *, h1, title):
    # Stable block identities make exact retries independent of fresh random IDs.
    return schema.snapshot_v1(kind, h1=h1, title=title, layout=[
        {'id': '71de8370-3105-5209-a189-82bb243b0051', 'kind': 'text',
         'field': 'intro_text', 'protected_nodes': []},
        {'id': '71de8370-3105-5209-a189-82bb243b0052', 'kind': 'text',
         'field': 'main_text', 'protected_nodes': []},
        {'id': '71de8370-3105-5209-a189-82bb243b0053', 'kind': 'price'}])


def initial_aggregate(*, page, actor, snapshot):
    """Caller holds content/auth locks and has just inserted this hidden Page."""
    if not connection.in_atomic_block or page.is_published:
        raise ValidationError('CREATE_INTERNAL_TRANSACTION_REQUIRED')
    payload = engine._snapshot(snapshot, page)
    if (payload != initial_snapshot(page.kind, h1=payload['h1'], title=payload['title']).data(page.kind)
            or PageContentState.objects.filter(page=page).exists()
            or page.content_revisions.exists() or OwnerDraft.objects.filter(page=page).exists()):
        raise ValidationError('CREATE_INTERNAL_EMPTY_AGGREGATE_REQUIRED')
    revision = engine.new_revision(page, None, payload, 'initial', actor)
    PageContentState.objects.create(page=page, current_revision=revision)
    instant = engine.now()
    draft = OwnerDraft.objects.create(page=page, base_revision=revision, payload=payload,
        payload_hash=schema.digest(payload), author_id=actor.pk, created_at=instant, updated_at=instant)
    VersionBasePin.objects.create(revision=revision, holder_kind='owner_draft', holder_id=draft.pk)
    return revision, draft
