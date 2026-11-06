"""Small current-source page commits without the legacy operation ledger."""
import copy
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from . import engine as E, schema as S
from .models import (IdentityReservation, OwnerDraft, PageContentState,
                     PageRevision, RevisionMetadata, RevisionProtection,
                     VersionBasePin)


def _fingerprint(value):
    if (type(value) is not str
            or re.fullmatch(r'[a-f0-9]{64}', value) is None):
        raise ValidationError('VERSIONS_INVALID_EDITOR_FINGERPRINT')
    return value


def _candidate(page, fields, owner, state, *, patch=None, snapshot=None):
    if owner:
        return E._snapshot(snapshot, page)
    if type(patch) is not S.TextPricePatch:
        raise ValidationError('VERSIONS_TYPED_PATCH_REQUIRED')
    changes = patch.changes()
    if not set(changes).issubset(set(fields)) or not set(fields) & S.EMPLOYEE_FIELDS:
        raise PermissionDenied('VERSIONS_FIELD_DENIED')
    payload = copy.deepcopy(E.revision(page, state.current_revision_id).payload)
    payload.update(copy.deepcopy(changes))
    return S.validate(payload, page.kind)


def _commit(*, actor, page_id, base_revision, expected_generation, operation_id,
            editor_request_fingerprint, editor_session_key, owner, patch=None,
            snapshot=None):
    E.outside()
    operation = E.uid(operation_id)
    _fingerprint(editor_request_fingerprint)

    def inspect():
        page, profile, fields, actual_owner, state = E.enter(
            actor, page_id, expected_generation, owner=owner)
        E.check_editor_session(
            actor, expected_generation, editor_session_key)
        E._assert_base(state, base_revision)
        if actual_owner != owner:
            raise PermissionDenied('VERSIONS_PAGE_DENIED')
        return page, state, _candidate(
            page, fields, owner, state, patch=patch, snapshot=snapshot)

    with transaction.atomic():
        _page, _state, payload = inspect()
    evidence = E.preflight(payload)
    with transaction.atomic():
        page, state, checked = inspect()
        if checked != payload:
            raise ValidationError('VERSIONS_CURRENT_CONFLICT')
        E.check_evidence(payload, evidence)
        row = E.new_revision(
            page, state, payload, 'automatic', actor,
            source=base_revision)
        if row.page_id != page.pk:
            raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')
        E.raw(PageContentState).filter(pk=state.pk).update(
            current_revision_id=row.pk)
        E.sync_usage('current_page', page.pk, payload)
        E.prune(page, row.pk, actor, operation)
        action = 'commit_owner' if owner else 'commit_employee'
        E.event('VERSION_' + action.upper(), actor, row.pk)
        return {
            'operation_id': str(operation), 'action': action,
            'result_id': str(row.pk), 'result_code': 'applied',
            'gone': False, 'replay': False,
        }


def commit_owner(*, actor, page_id, base_revision, snapshot,
                 expected_generation, operation_id,
                 editor_request_fingerprint, editor_session_key):
    if type(snapshot) is not S.Snapshot:
        raise ValidationError('VERSIONS_TYPED_PRODUCER_REQUIRED')
    return _commit(
        actor=actor, page_id=page_id, base_revision=base_revision,
        expected_generation=expected_generation, operation_id=operation_id,
        editor_request_fingerprint=editor_request_fingerprint,
        editor_session_key=editor_session_key, owner=True,
        snapshot=snapshot)


def commit_employee(*, actor, page_id, base_revision, patch,
                    expected_generation, operation_id,
                    editor_request_fingerprint, editor_session_key):
    return _commit(
        actor=actor, page_id=page_id, base_revision=base_revision,
        expected_generation=expected_generation, operation_id=operation_id,
        editor_request_fingerprint=editor_request_fingerprint,
        editor_session_key=editor_session_key, owner=False, patch=patch)


def save_owner_draft(*, actor, page_id, base_revision, snapshot,
                     expected_generation, operation_id, draft_revision=None,
                     rebase=False, draft_id=None, expected_draft_hash=None,
                     expected_draft_base=None, editor_request_fingerprint,
                     editor_session_key):
    E.outside()
    operation = E.uid(operation_id)
    _fingerprint(editor_request_fingerprint)
    if type(snapshot) is not S.Snapshot or type(rebase) is not bool:
        raise ValidationError('VERSIONS_TYPED_PRODUCER_REQUIRED')

    def inspect():
        page, _profile, _fields, _owner, state = E.enter(
            actor, page_id, expected_generation, owner=True)
        E.check_editor_session(actor, expected_generation, editor_session_key)
        payload = E._snapshot(snapshot, page)
        base = E.revision(page, base_revision)
        draft = E.draft_for(page)
        if draft is None:
            if (draft_revision is not None or draft_id is not None or rebase
                    or base.pk != state.current_revision_id):
                raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        else:
            if (draft_id is None or draft.pk != E.uid(draft_id)
                    or draft.revision != draft_revision
                    or expected_draft_hash is None
                    or draft.payload_hash != expected_draft_hash
                    or S.digest(draft.payload) != expected_draft_hash
                    or expected_draft_base is None
                    or draft.base_revision_id != E.uid(expected_draft_base)):
                raise ValidationError('VERSIONS_DRAFT_CONFLICT')
            if rebase:
                if base.pk != state.current_revision_id:
                    raise ValidationError('VERSIONS_DRAFT_CONFLICT')
            elif base.pk != draft.base_revision_id:
                raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        return page, base, draft, payload

    with transaction.atomic():
        _page, _base, _draft, payload = inspect()
    evidence = E.preflight(payload)
    with transaction.atomic():
        page, base, draft, checked = inspect()
        if checked != payload:
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        E.check_evidence(payload, evidence)
        instant = E.now()
        if draft is None:
            draft = OwnerDraft.objects.create(
                page=page, base_revision=base, payload=payload,
                payload_hash=S.digest(payload), author_id=actor.pk,
                created_at=instant, updated_at=instant)
        else:
            E.raw(VersionBasePin).filter(
                holder_kind='owner_draft', holder_id=draft.pk).delete()
            E.raw(OwnerDraft).filter(pk=draft.pk).update(
                base_revision=base, payload=payload,
                payload_hash=S.digest(payload), author_id=actor.pk,
                updated_at=instant, revision=draft.revision + 1)
            draft.revision += 1
            draft.base_revision = base
        E.sync_usage('draft', draft.pk, payload)
        action = 'rebase_draft' if rebase else 'save_draft'
        E.event('VERSION_' + action.upper(), actor, draft.pk, 'page_draft')
        return {
            'operation_id': str(operation), 'action': action,
            'result_id': str(draft.pk), 'result_code': 'applied',
            'gone': False, 'replay': False,
            'draftBasis': {'id': str(draft.pk), 'revision': draft.revision},
            'baseRevisionId': str(base.pk),
        }


def cancel_owner_draft(*, actor, page_id, draft_id, draft_revision,
                       expected_generation, operation_id,
                       editor_request_fingerprint, editor_session_key):
    operation = E.uid(operation_id)
    _fingerprint(editor_request_fingerprint)
    params = {'draft': str(E.uid(draft_id)), 'draft_revision': draft_revision}
    with transaction.atomic():
        page, _profile, _fields, _owner, _state = E.enter(
            actor, page_id, expected_generation, owner=True)
        E.check_editor_session(actor, expected_generation, editor_session_key)
        previous = E.replay(
            operation, 'cancel_draft', actor, page, expected_generation,
            params, editor_request_fingerprint=editor_request_fingerprint)
        if previous:
            return previous
        draft = E.draft_for(page)
        if (draft is None or draft.pk != E.uid(draft_id)
                or draft.revision != draft_revision):
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        E.remove_usage('draft', draft.pk)
        E.raw(VersionBasePin).filter(
            holder_kind='owner_draft', holder_id=draft.pk).delete()
        E.raw(OwnerDraft).filter(pk=draft.pk).delete()
        E.event('VERSION_CANCEL_DRAFT', actor, draft.pk, 'page_draft')
        return {
            'operation_id': str(operation), 'action': 'cancel_draft',
            'result_id': str(draft.pk), 'result_code': 'released',
            'gone': True, 'replay': False,
        }


def publish_owner_draft(*, actor, page_id, base_revision, snapshot,
                        expected_generation, operation_id, draft_id,
                        draft_revision, expected_draft_hash,
                        editor_request_fingerprint, editor_session_key):
    """Publish the exact selected draft without the legacy receipt ledger."""
    E.outside()
    operation = E.uid(operation_id)
    _fingerprint(editor_request_fingerprint)
    if type(snapshot) is not S.Snapshot:
        raise ValidationError('VERSIONS_TYPED_PRODUCER_REQUIRED')

    def inspect():
        page, _profile, _fields, _owner, state = E.enter(
            actor, page_id, expected_generation, owner=True)
        E.check_editor_session(actor, expected_generation, editor_session_key)
        E._assert_base(state, base_revision)
        payload = E._snapshot(snapshot, page)
        draft = E.draft_for(page)
        if (draft is None or draft.pk != E.uid(draft_id)
                or draft.revision != draft_revision
                or draft.base_revision_id != state.current_revision_id
                or expected_draft_hash is None
                or draft.payload_hash != expected_draft_hash
                or S.digest(draft.payload) != expected_draft_hash):
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        return page, state, draft, payload

    with transaction.atomic():
        _page, _state, _draft, payload = inspect()
    evidence = E.preflight(payload)
    with transaction.atomic():
        page, state, draft, checked = inspect()
        if checked != payload:
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        E.check_evidence(payload, evidence)
        row = E.new_revision(
            page, state, payload, 'automatic', actor,
            source=state.current_revision_id)
        if row.page_id != page.pk:
            raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')
        E.raw(PageContentState).filter(pk=state.pk).update(
            current_revision_id=row.pk)
        E.sync_usage('current_page', page.pk, payload)
        E.remove_usage('draft', draft.pk)
        E.raw(VersionBasePin).filter(
            holder_kind='owner_draft', holder_id=draft.pk).delete()
        deleted, _ = E.raw(OwnerDraft).filter(
            pk=draft.pk, revision=draft.revision).delete()
        if deleted != 1:
            raise ValidationError('VERSIONS_DRAFT_CONFLICT')
        E.prune(page, row.pk, actor, operation)
        E.event('VERSION_COMMIT_OWNER', actor, row.pk)
        return {
            'operation_id': str(operation), 'action': 'commit_owner',
            'result_id': str(row.pk), 'result_code': 'applied',
            'gone': False, 'replay': False,
        }


def restore_prepared(*, actor, page_id, preparation, snapshot,
                     expected_generation, operation_id, expected_fields,
                     editor_session_key):
    """Apply a confirmed, currently normalised restore in one transaction."""
    from . import restoration as R
    from .operations import load_ticket

    E.outside()
    operation = E.uid(operation_id)
    if type(snapshot) is not S.Snapshot or type(expected_fields) is not list:
        raise ValidationError('VERSIONS_TYPED_PRODUCER_REQUIRED')
    data = load_ticket(preparation, 'restore')

    def inspect():
        page, profile, fields, owner, state = E.enter(
            actor, page_id, expected_generation)
        E.check_editor_session(actor, expected_generation, editor_session_key)
        candidate = R._check_preparation(
            data, actor, page, profile, fields, owner, state)
        payload = E._snapshot(snapshot, page)
        if candidate['fields'] != expected_fields or candidate['payload'] != payload:
            raise ValidationError('VERSIONS_RESTORE_STALE')
        source = E.revision(page, data['source'])
        return page, state, source, payload

    with transaction.atomic():
        _page, _state, _source, payload = inspect()
    evidence = E.preflight(payload)
    with transaction.atomic():
        page, state, source, checked = inspect()
        if checked != payload:
            raise ValidationError('VERSIONS_RESTORE_STALE')
        E.check_evidence(payload, evidence)
        row = E.new_revision(
            page, state, payload, 'automatic', actor, source=source.pk)
        if row.page_id != page.pk:
            raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')
        E.raw(PageContentState).filter(pk=state.pk).update(
            current_revision_id=row.pk)
        E.sync_usage('current_page', page.pk, payload)
        E.prune(page, row.pk, actor, operation)
        E.event('VERSION_RESTORE', actor, row.pk)
        return {
            'operation_id': str(operation), 'action': 'restore_direct',
            'result_id': str(row.pk), 'result_code': 'restored',
            'gone': False, 'replay': False,
        }


def _result(operation, action, result_id, code='applied', gone=False):
    return {
        'operation_id': str(operation), 'action': action,
        'result_id': str(result_id) if result_id else None,
        'result_code': code, 'gone': gone, 'replay': False,
    }


def create_manual(*, actor, page_id, confirmation, expected_generation,
                  operation_id, name='', comment='', manual_date=None):
    """Copy the signed current revision without a new operation receipt."""
    from media_library import services as media
    from media_library.models import AssetUsage
    from .operations import _binding, load_ticket

    operation = E.uid(operation_id)
    data = load_ticket(confirmation, 'manual')
    metadata = E.metadata_values(name, comment, manual_date)
    with transaction.atomic():
        page, _profile, _fields, _owner, state = E.enter(
            actor, page_id, expected_generation, owner=True)
        if IdentityReservation.objects.filter(pk=operation).exists():
            raise ValidationError('VERSIONS_OPERATION_ID_CONSUMED')
        source = E.revision(page, data['source'])
        if (data['binding'] != _binding(actor, page, expected_generation)
                or state.current_revision_id != source.pk
                or data['stamp'] != E.stamp(page, source)):
            raise ValidationError('VERSIONS_CURRENT_CONFLICT')
        row = PageRevision.objects.create(
            id=operation, page=page, sequence=state.sequence + 1,
            schema_version=source.schema_version, payload=source.payload,
            payload_hash=source.payload_hash, kind='manual',
            created_at=E.now(), author_id=actor.pk,
            source_revision_id=source.pk)
        RevisionMetadata.objects.create(revision=row, **metadata)
        E.raw(PageContentState).filter(pk=state.pk).update(
            sequence=row.sequence)
        source_kind = ('stable_version' if RevisionProtection.objects.filter(
            revision=source).exists() else 'ordinary_version')
        for usage in AssetUsage.objects.filter(
                kind=source_kind, consumer_id=source.pk).order_by('slot'):
            media.attach(
                asset_id=usage.asset_id, kind='ordinary_version',
                consumer_id=row.pk, slot=usage.slot)
        E.prune(page, state.current_revision_id, actor, operation,
                retained_ids=(row.pk,))
        E.event('VERSION_CREATE_MANUAL', actor, row.pk)
        return _result(operation, 'create_manual', row.pk)


def edit_manual_metadata(*, actor, page_id, version_id,
                         metadata_generation, expected_generation,
                         operation_id, name='', comment='', manual_date=None):
    operation = E.uid(operation_id)
    metadata = E.metadata_values(name, comment, manual_date)
    with transaction.atomic():
        page, _profile, _fields, _owner, _state = E.enter(
            actor, page_id, expected_generation, owner=True)
        row = E.revision(page, version_id)
        meta = RevisionMetadata.objects.get(revision=row)
        if (row.kind != 'manual' or type(metadata_generation) is not int
                or meta.generation != metadata_generation):
            raise ValidationError('VERSIONS_METADATA_CONFLICT')
        E.raw(RevisionMetadata).filter(pk=meta.pk).update(
            **metadata, generation=meta.generation + 1)
        E.event('VERSION_EDIT_MANUAL', actor, row.pk)
        return _result(operation, 'edit_manual', row.pk)


def set_stable(*, actor, page_id, version_id, view_receipt,
               expected_generation, operation_id):
    from .operations import _binding, load_ticket

    operation = E.uid(operation_id)
    data = load_ticket(view_receipt, 'view')
    with transaction.atomic():
        page, _profile, _fields, _owner, _state = E.enter(
            actor, page_id, expected_generation, owner=True)
        row = E.revision(page, version_id)
        expected = {
            'action': 'view',
            'binding': _binding(actor, page, expected_generation),
            'stamp': E.stamp(page, row),
        }
        if data != expected:
            raise ValidationError('VERSIONS_VIEW_CHANGED')
        if RevisionProtection.objects.filter(revision=row).exists():
            raise ValidationError('VERSIONS_ALREADY_STABLE')
        RevisionProtection.objects.create(
            revision=row, marked_by_id=actor.pk, marked_at=E.now())
        E.move_usage(row, 'ordinary_version', 'stable_version')
        E.event('VERSION_SET_STABLE', actor, row.pk)
        return _result(operation, 'set_stable', row.pk)


def demote_stable(*, actor, page_id, confirmation, password,
                   expected_generation, operation_id):
    from .operations import _binding, composition, load_ticket

    operation = E.uid(operation_id)
    data = load_ticket(confirmation, 'demote')
    user = get_user_model().objects.get(pk=actor.pk)
    if (type(password) is not str or not 0 < len(password) <= 4096
            or not check_password(password, user.password)):
        raise PermissionDenied('VERSIONS_CURRENT_PASSWORD_REQUIRED')
    verified_password_hash = user.password
    with transaction.atomic():
        page, profile, _fields, _owner, state = E.enter(
            actor, page_id, expected_generation, owner=True)
        if profile.user.password != verified_password_hash:
            raise PermissionDenied('VERSIONS_CURRENT_PASSWORD_CHANGED')
        row = E.revision(page, data['target'])
        if (data['binding'] != _binding(actor, page, expected_generation)
                or data['stamp'] != E.stamp(page, row)
                or data['composition'] != S.digest(composition(page, state))):
            raise ValidationError('VERSIONS_CONFIRMATION_CHANGED')
        if not RevisionProtection.objects.filter(revision=row).exists():
            raise ValidationError('VERSIONS_NOT_STABLE')
        E.move_usage(row, 'stable_version', 'ordinary_version')
        E.raw(RevisionProtection).filter(revision=row).delete()
        E.prune(page, state.current_revision_id, actor, operation)
        E.event('VERSION_DEMOTE_STABLE', actor, row.pk)
        return _result(
            operation, 'demote_stable', row.pk,
            gone=not PageRevision.objects.filter(pk=row.pk).exists())


def delete_revision(*, actor, page_id, confirmation,
                    expected_generation, operation_id):
    from .operations import _binding, _deletable, load_ticket

    operation = E.uid(operation_id)
    data = load_ticket(confirmation, 'delete')
    with transaction.atomic():
        page, _profile, _fields, _owner, state = E.enter(
            actor, page_id, expected_generation, owner=True)
        row = E.revision(page, data['target'])
        _deletable(page, row, state)
        if (data['binding'] != _binding(actor, page, expected_generation)
                or data['stamp'] != E.stamp(page, row)):
            raise ValidationError('VERSIONS_CONFIRMATION_CHANGED')
        E.remove_usage('ordinary_version', row.pk)
        E.raw(PageRevision).filter(pk=row.pk).delete()
        E.event('VERSION_DELETE_REVISION', actor, row.pk)
        return _result(
            operation, 'delete_revision', data['target'],
            code='deleted', gone=True)
