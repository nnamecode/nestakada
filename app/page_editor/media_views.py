"""Freshly authorized external image picker/bytes; no uploads or public paths."""
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_GET
from accounts.views import gate
from accounts.services import require_session, note_denial
from editor_runtime.guards import EditorSlot, EditorFault
from page_versions import engine as E
from media_library.models import Asset, AssetFile, MediaFolder
from media_library.paths import relative_path
from .checks import inspect_admission, _inspect_context_locked, CheckFault
from .input_policy import identifier
from .views import request_context
from . import media


def _fresh_owner(request, page_id):
    actor = require_session(request, touch=False)
    with transaction.atomic():
        E.enter(actor, page_id, request.auth_generation, owner=True)
        E.check_editor_session(actor, request.auth_generation, request.session.session_key)
    return actor


@require_GET
@gate(owner=True)
def picker(request, page_id):
    try:
        _fresh_owner(request, page_id)
        if len(request.META.get('QUERY_STRING', '').encode('utf-8')) > 16384:
            raise CheckFault('EDITOR_MEDIA_INVALID')
        if any(key not in {'folder', 'q', 'after'} or len(request.GET.getlist(key)) != 1 for key in request.GET):
            raise CheckFault('EDITOR_MEDIA_INVALID')
        folder, query, after = request.GET.get('folder', ''), request.GET.get('q', ''), request.GET.get('after')
        if folder:
            relative_path(folder)
        if after is not None:
            identifier(after)
        with EditorSlot():
            if folder and not MediaFolder.objects.filter(path=folder).exists():
                raise CheckFault('EDITOR_MEDIA_INVALID')
            rows = Asset.objects.filter(status=Asset.Status.READY).annotate(
                main_count=Count('files', filter=Q(files__kind=AssetFile.Kind.MAIN)),
                preview_count=Count('files', filter=Q(files__kind=AssetFile.Kind.PREVIEW))).filter(main_count=1, preview_count=1)
            if folder:
                rows = rows.filter(Q(folder__path=folder) | Q(folder__path__startswith=folder + '/'))
            if after is not None:
                rows = rows.filter(pk__gt=after)
            matches = []
            for row in rows.order_by('pk').values('id', 'folder__path').iterator(chunk_size=128):
                label = row['folder__path'] + ' · ' + str(row['id'])
                if query.casefold() not in label.casefold():
                    continue
                matches.append((row, label))
                if len(matches) == 51:
                    break
            items = []
            prefix = f'/manage/pages/{page_id}/edit/media/picker-files/'
            for row, label in matches[:50]:
                files = media.derivatives(row['id'])
                items.append({'assetId': str(row['id']), 'label': label, 'folder': row['folder__path'],
                    'mainFileId': str(files['main'].pk), 'previewFileId': str(files['preview'].pk),
                    'mainUrl': prefix + str(files['main'].pk) + '/',
                    'previewUrl': prefix + str(files['preview'].pk) + '/'})
            _fresh_owner(request, page_id)
            return JsonResponse({'items': items, 'nextAfter': items[-1]['assetId'] if len(matches) > 50 else None})
    except PermissionDenied:
        note_denial(request, 'owner')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except (ValidationError, ValueError, TypeError):
        return JsonResponse({'ok': False, 'code': 'EDITOR_MEDIA_INVALID'}, status=400)
    except ObjectDoesNotExist:
        return JsonResponse({'ok': False, 'code': 'EDITOR_MEDIA_UNAVAILABLE'}, status=409)
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)


def _file(file_id):
    row = AssetFile.objects.select_related('asset').filter(pk=file_id, asset__status=Asset.Status.READY,
        kind__in=(AssetFile.Kind.MAIN, AssetFile.Kind.PREVIEW)).first()
    if row is None or row.pk not in {file.pk for file in media.derivatives(row.asset_id).values()}:
        raise Http404()
    return row


@require_GET
@gate()
def contextual_file(request, page_id, file_id):
    return _bytes(request, page_id, file_id, picker_mode=False)


@require_GET
@gate(owner=True)
def picker_file(request, page_id, file_id):
    return _bytes(request, page_id, file_id, picker_mode=True)


def _bytes(request, page_id, file_id, *, picker_mode):
    source = response = None
    delivered = False
    try:
        actor = require_session(request, touch=False)
        generation, session_key = request.auth_generation, request.session.session_key
        admission = inspect_admission(actor=actor, page_id=page_id, generation=generation)
        if picker_mode and (not admission['owner'] or request.META.get('QUERY_STRING')):
            raise PermissionDenied()
        with EditorSlot():
            before = None if picker_mode else request_context(request, page_id)
            file = _file(file_id)
            if before is not None and not media.member(before, file):
                raise Http404()
            source = media.open_derivative(file)
            with transaction.atomic():
                if picker_mode:
                    E.enter(actor, page_id, generation, owner=True)
                else:
                    after = _inspect_context_locked(actor=actor, page_id=page_id, generation=generation,
                        origin=request.build_absolute_uri('/').rstrip('/'), selector=before.child['source'])
                    if before.stamp != after.stamp:
                        raise Http404()
                E.check_editor_session(actor, generation, session_key)
                actual = _file(file_id)
                if media.file_facts(actual) != media.file_facts(file) or (not picker_mode and not media.member(after, actual)):
                    raise Http404()
            response = FileResponse(source, content_type='image/webp')
            response['Content-Disposition'] = 'inline'
            response['X-Content-Type-Options'] = 'nosniff'
            response['Cache-Control'] = 'private, no-store'
            source = None
        delivered = True
        return response
    except PermissionDenied:
        note_denial(request, 'owner' if picker_mode else 'page')
        return JsonResponse({'ok': False, 'code': 'EDITOR_FIELDS_FORBIDDEN'}, status=403)
    except ValidationError as exc:
        if 'EDITOR_SESSION_ENDED' in str(exc):
            return JsonResponse({'ok': False, 'code': 'EDITOR_SESSION_ENDED'}, status=401)
        raise Http404() from None
    except (ObjectDoesNotExist, OSError):
        raise Http404() from None
    except EditorFault as exc:
        return JsonResponse({'ok': False, 'code': exc.code}, status=exc.status)
    finally:
        if source is not None:
            source.close()
        if response is not None and not delivered:
            response.close()
