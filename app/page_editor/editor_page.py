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
from .checks import inspect_context, check_worker_result, CheckFault


def context_for(request, page_id):
    return inspect_context(actor=request.user, page_id=page_id, generation=request.auth_generation,
                           origin=request.build_absolute_uri('/').rstrip('/'))


@require_GET
@gate()
def state(request, page_id):
    try:
        context = context_for(request, page_id)
    except PermissionDenied:
        note_denial(request, 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_PAGE_UNAVAILABLE'}, status=404)
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    return JsonResponse({'userId': str(request.user.pk), 'generation': request.auth_generation,
        'baseRevisionId': context.child['base_revision_id'], 'fields': context.child['fields'],
        'csrfToken': get_token(request)})


@require_GET
@gate()
def editor(request, page_id):
    try:
        before = context_for(request, page_id)
        with EditorSlot():
            page = Page.objects.get(pk=page_id)
            payload = E.revision(page, before.child['base_revision_id']).payload
            values = {field: payload[field] for field in before.child['fields']
                      if field not in ('main_image', 'preview_image')}
            basis = {'protocol': 'page-editor-v1', 'generation': request.auth_generation,
                'baseRevisionId': before.child['base_revision_id'], 'editingFrom': 'current',
                'draftBasis': None, 'stageId': None}
            approved = None
            try:
                raw = json.dumps({**basis, 'changes': values}, ensure_ascii=False, separators=(',', ':')).encode()
                result = check_worker_result(normalize_input(raw, before.child), raw=raw, context=before)
                if not result['changed']:
                    approved = result['changes']
            except EditorFault:
                # Old/incompatible HTML remains escaped source, not a live DOM.
                pass
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
            'checkReceipt': None}
        return render(request, 'page_editor/editor.html', {'page': page, 'page_id': page_id,
            'owner': before.child['owner'], 'initial_state': initial, 'fields': initial['fields']})
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
