"""Small transactional Header/Footer commands for the v0.7 architecture.

The public HTTP boundary must normalise and validate HTML before calling this
module.  These commands deliberately do not use the legacy reservation,
receipt, filesystem-journal, quota or restore-stage machinery.
"""
import hashlib
from uuid import UUID, uuid4

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import connection, models, transaction
from django.db.models import Max
from django.utils import timezone

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions.engine import check_editor_session

from .commands import sync_assets
from .content import descriptor_for
from .models import (SharedBasePin, SharedBlock, SharedDraft,
                     SharedIdentityReservation, SharedRevision)
from .services import owner_locked


MAX_HTML_BYTES = 1024 * 1024


def _raw(model):
    """Bypass legacy immutable managers inside this command's transaction."""
    return models.QuerySet(model=model, using='default')


def _outside_transaction():
    if connection.in_atomic_block:
        raise ValidationError('SHARED_SIMPLE_CALL_FROM_AUTOCOMMIT')


def _kind(value):
    if value not in ('header', 'footer'):
        raise ObjectDoesNotExist()
    return value


def _current_id(value):
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        raise ValidationError('SHARED_SIMPLE_CURRENT_INVALID') from None


def _normalised_html(value):
    if type(value) is not str or len(value.encode('utf-8')) > MAX_HTML_BYTES:
        raise ValidationError('SHARED_SIMPLE_HTML_INVALID')
    return value


def _bindings(value):
    if type(value) not in (list, tuple) or len(value) > 4:
        raise ValidationError('SHARED_SIMPLE_BINDINGS_INVALID')
    result, slots = [], set()
    for item in value:
        if type(item) is not dict or set(item) != {'assetId', 'slot'}:
            raise ValidationError('SHARED_SIMPLE_BINDINGS_INVALID')
        try:
            asset_id = str(UUID(str(item['assetId'])))
        except (TypeError, ValueError, AttributeError):
            raise ValidationError('SHARED_SIMPLE_BINDINGS_INVALID') from None
        slot = item['slot']
        if type(slot) is not str or not slot or len(slot) > 100 or slot in slots:
            raise ValidationError('SHARED_SIMPLE_BINDINGS_INVALID')
        slots.add(slot)
        result.append({'assetId': asset_id, 'slot': slot})
    return result


def _insert_revision(*, block, actor, kind, html, bindings, source_revision_id=None):
    sequence = (SharedRevision.objects.filter(block=block).aggregate(value=Max('sequence'))['value'] or 0) + 1
    payload_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()
    row = SharedRevision(
        id=uuid4(), block=block, sequence=sequence, schema_version=kind + '-v1',
        html=html, storage_kind='inline', file_key='', byte_size=None,
        file_sha256='', payload_hash=payload_hash, author_id=actor.pk,
        source_revision_id=source_revision_id,
    )
    row.full_clean(validate_unique=False, validate_constraints=False)
    # Transition only: legacy draft/restore receipts still have permanent-
    # identity FKs.  Keep this one compatibility row until those two paths are
    # switched, then remove it together with the legacy tables under REF-Q004.
    SharedIdentityReservation.objects.create(
        id=row.pk, kind='sharedrevision', block=block)
    _raw(SharedRevision).bulk_create([row])
    sync_assets('shared_block', row.pk, bindings)
    updated = _raw(SharedBlock).filter(pk=block.pk, current_revision_id=block.current_revision_id).update(
        current_revision_id=row.pk, generation=models.F('generation') + 1)
    if updated != 1:
        raise ValidationError('SHARED_SIMPLE_CURRENT_CHANGED')
    record_event(
        category=Category.USER_ACTIONS,
        event_code='SHARED_RESTORE' if source_revision_id else 'SHARED_APPLY',
        level=Level.INFO,
        source=Source.APPLICATION,
        result=Result.SUCCESS,
        actor_id=actor.pk,
        object_kind='shared_block',
        object_ref=block.pk,
    )
    return row


def commit_normalized_current(*, actor, kind, expected_generation, session_key,
                              expected_current_id, html, bindings=()):
    """Atomically append one inline revision and make it current.

    ``html`` is the output of the existing closed server-side normaliser, not
    raw browser input.  A stale current, revoked session, invalid media usage
    or audit failure rolls the whole transaction back.
    """
    _outside_transaction()
    kind = _kind(kind)
    html = _normalised_html(html)
    bindings = _bindings(bindings)
    expected_current_id = _current_id(expected_current_id)
    with transaction.atomic():
        owner_locked(actor, expected_generation)
        check_editor_session(actor, expected_generation, session_key)
        block = SharedBlock.objects.select_for_update().get(kind=kind)
        if block.current_revision_id != expected_current_id:
            raise ValidationError('SHARED_SIMPLE_CURRENT_CHANGED')
        return _insert_revision(
            block=block, actor=actor, kind=kind, html=html, bindings=bindings)


def save_normalized_draft(*, actor, kind, expected_generation, session_key,
                          expected_current_id, draft_id=None, draft_revision=None,
                          html, bindings=()):
    """Create or update the owner's single inline draft without publishing it."""
    _outside_transaction()
    kind = _kind(kind)
    html = _normalised_html(html)
    bindings = _bindings(bindings)
    expected_current_id = _current_id(expected_current_id)
    supplied_draft_id = _current_id(draft_id)
    if (supplied_draft_id is None) != (draft_revision is None):
        raise ValidationError('SHARED_SIMPLE_DRAFT_BASIS_INVALID')
    if draft_revision is not None and (type(draft_revision) is not int or draft_revision < 1):
        raise ValidationError('SHARED_SIMPLE_DRAFT_BASIS_INVALID')

    with transaction.atomic():
        owner_locked(actor, expected_generation)
        check_editor_session(actor, expected_generation, session_key)
        block = SharedBlock.objects.select_for_update().get(kind=kind)
        if block.current_revision_id != expected_current_id:
            raise ValidationError('SHARED_SIMPLE_CURRENT_CHANGED')
        existing = SharedDraft.objects.select_for_update().filter(block=block).first()
        payload_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()
        instant = timezone.now()
        if existing is None:
            if supplied_draft_id is not None:
                raise ValidationError('SHARED_SIMPLE_DRAFT_CHANGED')
            row = SharedDraft(
                id=uuid4(), block=block, revision=1,
                base_revision_id=expected_current_id, html=html,
                storage_kind='inline', file_key='', byte_size=None,
                file_sha256='', payload_hash=payload_hash,
                author_id=actor.pk, created_at=instant, updated_at=instant,
            )
            row.full_clean(validate_unique=False, validate_constraints=False)
            # Transition only: the still-available legacy restore-stage quota
            # inventory expects every shared record to have an identity row.
            # Remove this when the stage path is retired under REF-Q004.
            SharedIdentityReservation.objects.create(
                id=row.pk, kind='shareddraft', block=block)
            _raw(SharedDraft).bulk_create([row])
        else:
            if (existing.pk != supplied_draft_id or existing.revision != draft_revision
                    or existing.base_revision_id != expected_current_id
                    or existing.storage_kind != 'inline'):
                raise ValidationError('SHARED_SIMPLE_DRAFT_CHANGED')
            next_revision = existing.revision + 1
            candidate = SharedDraft(
                id=existing.pk, block=block, revision=next_revision,
                base_revision_id=existing.base_revision_id, html=html,
                storage_kind='inline', file_key='', byte_size=None,
                file_sha256='', payload_hash=payload_hash,
                author_id=actor.pk, created_at=existing.created_at, updated_at=instant,
            )
            candidate.full_clean(validate_unique=False, validate_constraints=False)
            updated = _raw(SharedDraft).filter(
                pk=existing.pk, revision=existing.revision).update(
                    revision=next_revision, html=html, storage_kind='inline',
                    file_key='', byte_size=None, file_sha256='',
                    payload_hash=payload_hash, author_id=actor.pk, updated_at=instant)
            if updated != 1:
                raise ValidationError('SHARED_SIMPLE_DRAFT_CHANGED')
            row = candidate
        sync_assets('draft', row.pk, bindings)
        record_event(
            category=Category.USER_ACTIONS, event_code='SHARED_DRAFT',
            level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=actor.pk, object_kind='shared_block', object_ref=block.pk)
        return row


def commit_normalized_draft(*, actor, kind, expected_generation, session_key,
                            expected_current_id, draft_id, draft_revision,
                            html, bindings=()):
    """Publish an owner draft and consume it in the same transaction."""
    _outside_transaction()
    kind = _kind(kind)
    html = _normalised_html(html)
    bindings = _bindings(bindings)
    expected_current_id = _current_id(expected_current_id)
    draft_id = _current_id(draft_id)
    if draft_id is None or type(draft_revision) is not int or draft_revision < 1:
        raise ValidationError('SHARED_SIMPLE_DRAFT_BASIS_INVALID')
    with transaction.atomic():
        owner_locked(actor, expected_generation)
        check_editor_session(actor, expected_generation, session_key)
        block = SharedBlock.objects.select_for_update().get(kind=kind)
        if block.current_revision_id != expected_current_id:
            raise ValidationError('SHARED_SIMPLE_CURRENT_CHANGED')
        draft = SharedDraft.objects.select_for_update().get(
            pk=draft_id, block=block, revision=draft_revision,
            base_revision_id=expected_current_id)
        row = _insert_revision(
            block=block, actor=actor, kind=kind, html=html, bindings=bindings)
        sync_assets('draft', draft.pk, [])
        _raw(SharedBasePin).filter(holder_kind='draft', holder_id=draft.pk).delete()
        deleted, _ = _raw(SharedDraft).filter(
            pk=draft.pk, revision=draft.revision).delete()
        if deleted != 1:
            raise ValidationError('SHARED_SIMPLE_DRAFT_CHANGED')
        return row


def restore_normalized_current(*, actor, kind, expected_generation, session_key,
                               expected_current_id, source_revision_id,
                               source_descriptor, html, bindings):
    """Commit a source already checked by the current isolated normalizer."""
    _outside_transaction()
    kind = _kind(kind)
    expected_current_id = _current_id(expected_current_id)
    source_revision_id = _current_id(source_revision_id)
    if source_revision_id is None:
        raise ValidationError('SHARED_SIMPLE_SOURCE_INVALID')
    if type(source_descriptor) is not dict:
        raise ValidationError('SHARED_SIMPLE_SOURCE_INVALID')
    html = _normalised_html(html)
    bindings = _bindings(bindings)

    with transaction.atomic():
        owner_locked(actor, expected_generation)
        check_editor_session(actor, expected_generation, session_key)
        block = SharedBlock.objects.select_for_update().get(kind=kind)
        if block.current_revision_id != expected_current_id:
            raise ValidationError('SHARED_SIMPLE_CURRENT_CHANGED')
        locked_source = SharedRevision.objects.get(pk=source_revision_id, block=block)
        if (locked_source.schema_version != kind + '-v1'
                or descriptor_for(locked_source) != source_descriptor):
            raise ValidationError('SHARED_SIMPLE_SOURCE_CHANGED')
        return _insert_revision(
            block=block, actor=actor, kind=kind, html=html,
            bindings=bindings, source_revision_id=locked_source.pk)
