"""Owner-only escaped comparison data; no renderer or content mutation."""
import json
from urllib.parse import urlencode
from django.core.exceptions import PermissionDenied
from django.db import transaction
from page_versions import engine as E
from .checks import CheckFault

LABELS = {'intro_text': 'Вводный текст', 'main_text': 'Основной текст', 'price': 'Прайс',
          'h1': 'Заголовок H1', 'title': 'Название для поиска', 'description': 'Описание для поиска',
          'indexing_allowed': 'Индексация', 'main_image': 'Основное изображение',
          'preview_image': 'Изображение для списка'}


def editor_metadata(request, page_id, context):
    if not context.child['owner']:
        return {'draft_navigation': None, 'draft_comparison': None}
    with transaction.atomic():
        page, profile, fields, owner, state = E.enter(request.user, page_id, request.auth_generation, owner=True)
        if str(state.current_revision_id) != context.child['current_revision_id']:
            raise CheckFault('EDITOR_CONTEXT_CHANGED')
        draft = E.draft_for(page)
        navigation = None
        if draft is not None:
            prefix = f'/manage/pages/{page.pk}/edit/'
            query = {'source': 'owner-draft', 'draftId': str(draft.pk), 'draftRevision': draft.revision}
            navigation = {'id': str(draft.pk), 'revision': draft.revision,
                'baseRevisionId': str(draft.base_revision_id), 'edit_url': prefix + '?' + urlencode(query),
                'rebase_url': prefix + '?' + urlencode({**query, 'rebase': '1',
                    'targetCurrentId': str(state.current_revision_id)})}
        comparison = None
        current = None
        if context.child['source']['editingFrom'] == 'owner-draft':
            basis = context.child['source']['draftBasis']
            if (draft is None or str(draft.pk) != basis['id'] or draft.revision != basis['revision']
                    or draft.payload != context.payload):
                raise CheckFault('EDITOR_CONTEXT_CHANGED')
            current = E.revision(page, state.current_revision_id).payload
            comparison = {'draftBaseRevisionId': str(draft.base_revision_id),
                          'currentRevisionId': str(state.current_revision_id)}
    # Formatting large price/text representations holds no domain locks.
    if comparison is not None:
        def display(value):
            return value if type(value) is str else json.dumps(value, ensure_ascii=False, indent=2)
        comparison['fields'] = [{'name': name, 'label': LABELS[name], 'draft': display(context.payload[name]),
                                 'current': display(current[name])} for name in context.child['fields']]
    return {'draft_navigation': navigation, 'draft_comparison': comparison}
