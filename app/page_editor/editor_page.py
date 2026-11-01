"""Escaped private editor page; initial raw HTML never becomes a live template."""
import json
from pathlib import Path
from django.http import JsonResponse, FileResponse, Http404
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.middleware.csrf import get_token
from accounts.views import gate
from accounts.services import require_session, note_denial
from page_versions import engine as E
from content.models import Page
from editor_runtime.guards import EditorSlot, EditorFault
from editor_runtime.processing import normalize_input
from .checks import inspect_context, inspect_admission, check_worker_result, CheckFault
from .source_context import current_selector
from .comparison import editor_metadata
from .views import request_context, source_response
from .media import initial_media
from . import embedded


def context_for(request, page_id):
    return request_context(request, page_id)


@require_GET
@gate()
def state(request, page_id):
    try:
        if not request.META.get('QUERY_STRING'):
            admission = inspect_admission(actor=request.user, page_id=page_id, generation=request.auth_generation)
            return JsonResponse({'userId': str(request.user.pk), 'generation': request.auth_generation,
                'baseRevisionId': admission['current_revision_id'], 'fields': admission['fields'],
                'csrfToken': get_token(request), 'canReadSource': True,
                'sourceContext': {**current_selector(), 'baseRevisionId': admission['current_revision_id'],
                                  'currentRevisionId': admission['current_revision_id']}})
        with EditorSlot():
            context = context_for(request, page_id)
    except PermissionDenied:
        note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    response = {'userId': str(request.user.pk), 'generation': request.auth_generation,
        'baseRevisionId': context.child['base_revision_id'], 'fields': context.child['fields'],
        'csrfToken': get_token(request), 'sourceContext': source_response(context), 'canReadSource': True}
    if context.child['source']['editingFrom'] == 'owner-draft':
        response['comparison'] = {'draftBaseRevisionId': context.child['base_revision_id'],
            'currentRevisionId': context.child['current_revision_id'],
            'targetCurrentId': context.child['source']['targetCurrentId']}
    return JsonResponse(response)


@require_GET
@gate()
def editor(request, page_id):
    try:
        with EditorSlot():
            before = context_for(request, page_id)
            page = Page.objects.get(pk=page_id)
            payload = before.payload
            values = {field: payload[field] for field in before.child['fields']}
            basis = {'protocol': 'page-editor-v1', 'generation': request.auth_generation,
                'baseRevisionId': before.child['base_revision_id'],
                **{key: before.child['source'][key] for key in ('editingFrom', 'draftBasis', 'stageId')}}
            approved = None
            embedded_media = {'intro_text': [], 'main_text': []}
            try:
                raw = json.dumps({**basis, 'changes': values}, ensure_ascii=False, separators=(',', ':')).encode()
                result = check_worker_result(normalize_input(raw, before.child), raw=raw, context=before)
                if 'derived' in result:
                    embedded.validate_derived(before, result)
                    embedded_media = embedded.preview_mapping(before, None, result['intentBindings'])
                if not result['changed']:
                    approved = result['changes']
            except EditorFault:
                # Old/incompatible HTML remains escaped source, not a live DOM.
                pass
            metadata = editor_metadata(request, page_id, before)
            selected_media = initial_media(before)
            try:
                current_actor = require_session(request, touch=False)
            except PermissionDenied:
                raise CheckFault('EDITOR_SESSION_ENDED') from None
            after = context_for(request, page_id)
            if current_actor.pk != request.user.pk or before.stamp != after.stamp:
                raise CheckFault('EDITOR_CONTEXT_CHANGED')
            initial = {'owner': before.child['owner'], 'actorId': str(request.user.pk),
                'pageId': str(page_id), **basis, 'values': values,
                'fields': [{'name': field, 'rawHtml': values[field],
                            'approvedHtml': approved[field] if approved is not None else None}
                           for field in ('intro_text', 'main_text') if field in values],
                'checkReceipt': None, 'rebase': before.child['source']['rebase'],
                'targetCurrentId': before.child['source']['targetCurrentId'],
                'currentRevisionId': before.child['current_revision_id'], 'media': selected_media,
                'embeddedMedia': embedded_media}
            return render(request, 'page_editor/editor.html', {'page': page, 'page_id': page_id,
                'owner': before.child['owner'], 'initial_state': initial, 'fields': initial['fields'], **metadata})
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    except PermissionDenied:
        note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)


@require_GET
@gate()
def asset(request, name):
    known = {'editor.bundle.js': 'text/javascript', 'editor.css': 'text/css',
             'editor-bridge.mjs': 'text/javascript'}
    if name not in known:
        raise Http404()
    path = Path(__file__).parent / 'assets' / name
    if not path.is_file() or path.is_symlink():
        raise Http404()
    return FileResponse(path.open('rb'), content_type=known[name])
