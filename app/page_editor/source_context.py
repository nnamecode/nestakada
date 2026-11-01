"""Small closed source selectors. No editor input is decoded in the parent."""
from urllib.parse import parse_qsl
from django.core.exceptions import ValidationError, PermissionDenied
from page_versions import engine as E, schema as S
from page_versions.restoration import candidate_for_stage


def current_selector():
    return {'editingFrom': 'current', 'draftBasis': None, 'stageId': None,
            'rebase': False, 'targetCurrentId': None}


def selector_for(request):
    raw = request.META.get('QUERY_STRING', '')
    try:
        if not raw.isascii() or len(raw) > 256:
            raise ValueError()
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        if len({key for key, _ in pairs}) != len(pairs):
            raise ValueError()
        values = dict(pairs)
        if not values:
            return current_selector()
        from .input_policy import identifier
        if values.get('source') == 'owner-draft':
            keys = {'source', 'draftId', 'draftRevision'}
            rebase = 'rebase' in values or 'targetCurrentId' in values
            if set(values) != keys | ({'rebase', 'targetCurrentId'} if rebase else set()):
                raise ValueError()
            revision = values['draftRevision']
            if not revision.isascii() or not revision.isdecimal() or revision.startswith('0'):
                raise ValueError()
            if rebase and values['rebase'] != '1':
                raise ValueError()
            return {'editingFrom': 'owner-draft',
                'draftBasis': {'id': identifier(values['draftId']), 'revision': int(revision)},
                'stageId': None, 'rebase': rebase,
                'targetCurrentId': identifier(values['targetCurrentId']) if rebase else None}
        if values.get('source') == 'restore-stage' and set(values) == {'source', 'stageId'}:
            return {**current_selector(), 'editingFrom': 'restore-stage',
                    'stageId': identifier(values['stageId'])}
        raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        raise ValidationError('EDITOR_INPUT_REJECTED') from None


def selected_source(page, profile, fields, owner, state, selector):
    mode = selector['editingFrom']
    if mode == 'owner-draft':
        if not owner:
            raise PermissionDenied('EDITOR_FIELDS_FORBIDDEN')
        draft = E.draft_for(page)
        basis = selector['draftBasis']
        if (draft is None or str(draft.pk) != basis['id'] or draft.revision != basis['revision']
                or S.digest(draft.payload) != draft.payload_hash):
            raise ValidationError('EDITOR_BASE_UNAVAILABLE')
        if selector['rebase'] and selector['targetCurrentId'] != str(state.current_revision_id):
            raise ValidationError('EDITOR_BASE_CONFLICT')
        return draft.payload, str(draft.base_revision_id), {'draftHash': draft.payload_hash}
    if mode == 'restore-stage':
        candidate = candidate_for_stage(page, profile, fields, E.uid(selector['stageId']), state)
        return candidate['payload'], str(state.current_revision_id), {'candidateHash': S.digest(candidate['payload'])}
    row = E.revision(page, state.current_revision_id)
    return row.payload, str(row.pk), {'payloadHash': row.payload_hash}
