"""Closed escaped history/confirmations; no raw snapshot save/publication handler."""
from functools import wraps
from pathlib import Path
from uuid import uuid4
from django.core.exceptions import PermissionDenied,ValidationError,ObjectDoesNotExist
from django.db import DatabaseError, transaction
from django.http import HttpResponse,FileResponse,Http404
from django.shortcuts import render
from django.views.decorators.http import require_GET,require_POST,require_http_methods
from django.utils.html import strip_tags
from accounts.views import gate
from accounts.services import note_denial
from media_library.models import AssetFile,AssetUsage
from media_library.storage import MediaStorage
from . import services as V,engine as E,schema as S,simple_commands as C
from .models import PageRevision,RevisionMetadata,RevisionProtection,VersionBasePin,OwnerDraft,RestoreStage
from .reads import timestamp


def error(request,page_id,message,status=409):
    return render(request,'page_versions/error.html',{'page_id':page_id,'message':message},status=status)


def protected(view):
    @wraps(view)
    @gate()
    def guarded(request,page_id,*args,**kwargs):
        try:return view(request,page_id,*args,**kwargs)
        except PermissionDenied:
            note_denial(request,'page')
            return error(request,page_id,'Действие недоступно. Проверьте актуальную сессию и права.',403)
        except ObjectDoesNotExist:return error(request,page_id,'Сохранённый объект недоступен.',404)
        except ValidationError as exc:
            codes=str(exc)
            incompatible=any(code in codes for code in ['INCOMPATIBLE','INVALID_SNAPSHOT','COMPONENT_','BLOCK_REMOVED','PROTECTED_MEDIA','MEDIA_UNAVAILABLE'])
            return error(request,page_id,'Версия несовместима. Ничего не применено; проверьте схему, защищённые блоки и доступность изображений.' if incompatible else 'Действие не выполнено. Обновите показанные данные и проверьте ввод.',409)
        except DatabaseError:return error(request,page_id,'Ошибка хранения. Ничего не применено.',503)
        except (ValueError,TypeError,KeyError):return error(request,page_id,'Некорректные поля запроса. Ничего не применено.',400)
        except OSError:return error(request,page_id,'Не удалось проверить файл. Ничего не применено.',409)
    return guarded


def form(request,allowed):
    if request.content_type!='application/x-www-form-urlencoded':raise ValidationError('VERSIONS_FORM_REQUIRED')
    if any(key not in set(allowed)|{'csrfmiddlewaretoken'} or len(request.POST.getlist(key))!=1 for key in request.POST):raise ValueError()
    return request.POST


def generation(request,data):
    value=int(data.get('generation',''))
    if value!=request.auth_generation:raise PermissionDenied('VERSIONS_SESSION_CHANGED')
    return value


def operation(data):return E.uid(data.get('operation_id'))


FIELD_LABELS={'intro_text':'Вводный текст','main_text':'Основной текст','price':'Прайс','h1':'Заголовок страницы','title':'Заголовок для поиска','description':'Описание для поиска','indexing_allowed':'Индексация','main_image':'Основное изображение','preview_image':'Изображение превью','embedded_images':'Изображения в тексте','layout':'Порядок блоков'}


def display_fields(prepared):
    return [{'name':field,'label':FIELD_LABELS.get(field,'Сохранённые данные'),'value':S.canonical(prepared['payload'][field])} for field in prepared['fields']]


def result_page(request,page_id,result):
    return render(request,'page_versions/result.html',{'page_id':page_id,'result':result})


def read_context(request,page_id,version_id):
    context=V.view_version(actor=request.user,page_id=page_id,version_id=version_id,expected_generation=request.auth_generation)
    row=context['revision'];payload=row.payload
    kind='stable_version' if context['stable'] else 'ordinary_version'
    assets=AssetUsage.objects.filter(kind=kind,consumer_id=row.pk).values_list('asset_id',flat=True)
    images=AssetFile.objects.filter(asset_id__in=assets,asset__status='ready',kind__in=['main','preview']).order_by('asset_id','kind','id')
    text=[]
    if type(payload) is dict:
        for field,label in [('intro_text','Вводный текст'),('main_text','Основной текст')]:
            if type(payload.get(field)) is str:text.append({'field':field,'label':label,'value':strip_tags(payload[field])})
    context.update(page_id=page_id,payload_json=S.canonical(payload),texts=text,images=images,time=timestamp(row.created_at),
        manual_time=timestamp(context['metadata'].manual_date) if context['metadata'].manual_date else None,
        generation=request.auth_generation,operation_id=uuid4())
    return context


@require_GET
@protected
def history(request,page_id):
    if any(key!='p' or len(request.GET.getlist(key))!=1 for key in request.GET):raise ValueError()
    page_number=int(request.GET.get('p','1'))
    if page_number<1:raise ValueError()
    context=V.history(actor=request.user,page_id=page_id,expected_generation=request.auth_generation,page_number=page_number)
    context['page_id']=page_id
    if context['owner']:
        for row in context['rows']:
            row['pinned']=VersionBasePin.objects.filter(revision=row['revision']).exists() or OwnerDraft.objects.filter(base_revision=row['revision']).exists()
    return render(request,'page_versions/history.html',context)


@require_GET
@protected
def read(request,page_id,version_id):
    return render(request,'page_versions/read.html',read_context(request,page_id,version_id))


@require_GET
@protected
def stylesheet(request,page_id):
    with transaction.atomic():E.enter(request.user,page_id,request.auth_generation,optional=True)
    response=FileResponse((Path(__file__).parent/'assets/versions.css').open('rb'),content_type='text/css; charset=utf-8')
    response['X-Content-Type-Options']='nosniff';return response


@require_GET
@protected
def compare(request,page_id,version_id):
    if any(key!='other' or len(request.GET.getlist(key))!=1 for key in request.GET):raise ValueError()
    context=read_context(request,page_id,version_id)
    with transaction.atomic():page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation)
    other=request.GET.get('other') or state.current_revision_id
    context['other']=read_context(request,page_id,other)
    return render(request,'page_versions/compare.html',context)


@require_GET
@protected
def version_file(request,page_id,version_id,file_id):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation)
        row=E.revision(page,version_id)
        kind='stable_version' if RevisionProtection.objects.filter(revision=row).exists() else 'ordinary_version'
        file=AssetFile.objects.filter(pk=file_id,kind__in=['main','preview'],asset__status='ready').first()
        if file is None or not AssetUsage.objects.filter(kind=kind,consumer_id=row.pk,asset_id=file.asset_id).exists():raise Http404
    source=None
    try:
        source=MediaStorage().open_verified(file.key,{'sha256':file.sha256,'byte_size':file.byte_size})
        header=source.read(12);source.seek(0)
        if header[:4]!=b'RIFF' or header[8:12]!=b'WEBP':raise Http404
        response=FileResponse(source,content_type='image/webp');response['Content-Disposition']='inline';response['X-Content-Type-Options']='nosniff'
        return response
    except BaseException:
        if source is not None:source.close()
        raise


@require_GET
@protected
def manual_prepare(request,page_id):
    prepared=V.prepare_manual(actor=request.user,page_id=page_id,expected_generation=request.auth_generation)
    return render(request,'page_versions/manual.html',{'page_id':page_id,'prepared':prepared,'time':timestamp(prepared['source'].created_at),
        'generation':request.auth_generation,'operation_id':uuid4()})


@require_POST
@protected
def manual_create(request,page_id):
    data=form(request,['generation','operation_id','confirmation','name','comment','manual_date'])
    operation_id=operation(data)
    from .models import OperationReceipt
    service=V.create_manual if OperationReceipt.objects.filter(pk=operation_id).exists() else C.create_manual
    result=service(actor=request.user,page_id=page_id,confirmation=data.get('confirmation',''),expected_generation=generation(request,data),
        operation_id=operation_id,name=data.get('name',''),comment=data.get('comment',''),manual_date=data.get('manual_date') or None)
    return result_page(request,page_id,result)


@require_http_methods(['GET','POST'])
@protected
def metadata_edit(request,page_id,version_id):
    if request.method=='GET':
        context=read_context(request,page_id,version_id)
        if not context['owner']:raise PermissionDenied()
        if context['revision'].kind!='manual':raise ValidationError('VERSIONS_MANUAL_REQUIRED')
        context['manual_date_value']=context['metadata'].manual_date.isoformat() if context['metadata'].manual_date else ''
        return render(request,'page_versions/metadata.html',context)
    data=form(request,['generation','operation_id','metadata_generation','name','comment','manual_date'])
    operation_id=operation(data)
    from .models import OperationReceipt
    service=V.edit_manual_metadata if OperationReceipt.objects.filter(pk=operation_id).exists() else C.edit_manual_metadata
    result=service(actor=request.user,page_id=page_id,version_id=version_id,metadata_generation=int(data.get('metadata_generation','')),
        expected_generation=generation(request,data),operation_id=operation_id,name=data.get('name',''),comment=data.get('comment',''),manual_date=data.get('manual_date') or None)
    return result_page(request,page_id,result)


@require_POST
@protected
def stable_set(request,page_id,version_id):
    data=form(request,['generation','operation_id','view_receipt'])
    operation_id=operation(data)
    from .models import OperationReceipt
    service=V.set_stable if OperationReceipt.objects.filter(pk=operation_id).exists() else C.set_stable
    return result_page(request,page_id,service(actor=request.user,page_id=page_id,version_id=version_id,view_receipt=data.get('view_receipt',''),
        expected_generation=generation(request,data),operation_id=operation_id))


@require_GET
@protected
def demote_prepare(request,page_id,version_id):
    prepared=V.prepare_demote(actor=request.user,page_id=page_id,version_id=version_id,expected_generation=request.auth_generation)
    return render(request,'page_versions/demote.html',{'page_id':page_id,'prepared':prepared,'time':timestamp(prepared['revision'].created_at),
        'generation':request.auth_generation,'operation_id':uuid4()})


@require_POST
@protected
def demote(request,page_id,version_id):
    data=form(request,['generation','operation_id','confirmation','password'])
    # Confirmation embeds the exact target; URL must match it too.
    from .operations import load_ticket
    if E.uid(load_ticket(data.get('confirmation',''),'demote')['target'])!=version_id:raise ValueError()
    operation_id=operation(data)
    from .models import OperationReceipt
    service=V.demote_stable if OperationReceipt.objects.filter(pk=operation_id).exists() else C.demote_stable
    return result_page(request,page_id,service(actor=request.user,page_id=page_id,confirmation=data.get('confirmation',''),password=data.get('password',''),
        expected_generation=generation(request,data),operation_id=operation_id))


@require_GET
@protected
def delete_prepare(request,page_id,version_id):
    prepared=V.prepare_delete(actor=request.user,page_id=page_id,version_id=version_id,expected_generation=request.auth_generation)
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation,owner=True)
        page_context=E.page_context(page)
    return render(request,'page_versions/delete.html',{'page_id':page_id,'prepared':prepared,'time':timestamp(prepared['revision'].created_at),
        'generation':request.auth_generation,'operation_id':uuid4(),'page_context':page_context})


@require_POST
@protected
def delete(request,page_id,version_id):
    data=form(request,['generation','operation_id','confirmation'])
    from .operations import load_ticket
    if E.uid(load_ticket(data.get('confirmation',''),'delete')['target'])!=version_id:raise ValueError()
    operation_id=operation(data)
    from .models import OperationReceipt
    service=V.delete_revision if OperationReceipt.objects.filter(pk=operation_id).exists() else C.delete_revision
    return result_page(request,page_id,service(actor=request.user,page_id=page_id,confirmation=data.get('confirmation',''),
        expected_generation=generation(request,data),operation_id=operation_id))


@require_GET
@protected
def owner_draft(request,page_id):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation,owner=True)
        draft=E.draft_for(page)
        if draft is None:raise Http404
    return render(request,'page_versions/draft.html',{'page_id':page_id,'draft':draft,'payload_json':S.canonical(draft.payload),'owner':True})


@require_POST
@protected
def restore_prepare(request,page_id,version_id):
    data=form(request,['generation'])
    prepared=V.prepare_restore(actor=request.user,page_id=page_id,version_id=version_id,expected_generation=generation(request,data))
    fields=display_fields(prepared)
    return render(request,'page_versions/restore.html',{'page_id':page_id,'version_id':version_id,'prepared':prepared,'fields':fields,
        'generation':request.auth_generation,'operation_id':uuid4()})


@require_POST
@protected
def restore_stage(request,page_id,version_id):
    data=form(request,['generation','operation_id','preparation','confirm_input_replacement'])
    from .operations import load_ticket
    if E.uid(load_ticket(data.get('preparation',''),'restore')['source'])!=version_id:raise ValueError()
    from .models import OperationReceipt
    if not OperationReceipt.objects.filter(pk=operation(data),action='stage_restore').exists():
        return error(request,page_id,'Создание новых промежуточных восстановлений отключено.',410)
    result=V.stage_restore(actor=request.user,page_id=page_id,preparation=data.get('preparation',''),confirm_input_replacement=data.get('confirm_input_replacement')=='yes',
        expected_generation=generation(request,data),operation_id=operation(data))
    try:context=stage_context(request,page_id,result['result_id'])
    except (ValidationError,ObjectDoesNotExist):
        # The mutation receipt remains true even if a later command consumed or
        # invalidated its stage before this request could render a projection.
        with transaction.atomic():
            page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation)
            stage=RestoreStage.objects.filter(pk=result['result_id'],page=page,actor_id=request.user.pk).first()
            terminal_status='gone' if stage is None else stage.status if stage.status!='held' else 'stale'
        return render(request,'page_versions/result.html',{'page_id':page_id,'result':result,'terminal_status':terminal_status})
    context['result']=result
    return render(request,'page_versions/stage.html',context)


def _normalised_restore(request,page_id,prepared):
    """Re-run a historical candidate through today's isolated editor policy."""
    import json
    from editor_runtime.guards import EditorSlot, EditorFault
    from editor_runtime.processing import normalize_input
    from page_editor.checks import (CheckFault, check_worker_result,
                                    inspect_context, restore_context)
    from page_editor.input_policy import OWNER_FIELDS
    from page_editor import embedded, media

    try:
        with EditorSlot():
            current = inspect_context(
                actor=request.user, page_id=page_id,
                generation=request.auth_generation,
                origin=request.build_absolute_uri('/').rstrip('/'))
            context = restore_context(
                current, prepared['payload'], prepared['source'].pk)
            changes = {
                field: prepared['payload'][field]
                for field in prepared['fields'] if field in OWNER_FIELDS
            }
            raw = json.dumps({
                'protocol': 'page-editor-v1',
                'generation': request.auth_generation,
                'baseRevisionId': str(prepared['current'].pk),
                'editingFrom': 'current', 'draftBasis': None,
                'stageId': None, 'changes': changes,
            }, ensure_ascii=False, allow_nan=False,
                separators=(',', ':')).encode('utf-8')
            result = check_worker_result(
                normalize_input(raw, context.child), raw=raw, context=context)
            if result['changed']:
                raise ValidationError('VERSIONS_RESTORE_NORMALIZATION_REQUIRED')
            if 'derived' in result:
                payload, _map_hash = embedded.validate_derived(
                    context, result, save=True)
            else:
                payload = {**context.payload, **result['changes']}
            if payload != prepared['payload']:
                raise ValidationError('VERSIONS_RESTORE_STALE')
            media.prepare(
                context, result['changes'], derived=result.get('derived'))
            return S.Snapshot.trusted(payload, payload['page_kind'])
    except (EditorFault, CheckFault) as exc:
        raise ValidationError(
            getattr(exc, 'code', 'VERSIONS_RESTORE_NORMALIZER_FAILED')) from None


@require_POST
@protected
def restore_apply(request,page_id,version_id):
    data=form(request,['generation','operation_id','preparation','confirm_input_replacement'])
    from .operations import load_ticket
    prepared_data=load_ticket(data.get('preparation',''),'restore')
    if E.uid(prepared_data['source'])!=version_id:raise ValueError()
    if data.get('confirm_input_replacement')!='yes':
        raise ValidationError('VERSIONS_CONFIRM_INPUT_REPLACEMENT')
    expected_generation=generation(request,data)
    prepared=V.get_prepared_restore(
        actor=request.user,page_id=page_id,preparation=data.get('preparation',''),
        expected_generation=expected_generation)
    snapshot=_normalised_restore(request,page_id,prepared)
    from . import simple_commands
    result=simple_commands.restore_prepared(
        actor=request.user,page_id=page_id,preparation=data.get('preparation',''),
        snapshot=snapshot,expected_generation=expected_generation,
        operation_id=operation(data),expected_fields=prepared['fields'],
        editor_session_key=request.session.session_key)
    return result_page(request,page_id,result)


def stage_context(request,page_id,stage_id):
    prepared=V.get_stage(actor=request.user,page_id=page_id,stage_id=stage_id,expected_generation=request.auth_generation)
    return {'page_id':page_id,'prepared':prepared,'fields':display_fields(prepared),
        'generation':request.auth_generation,'operation_id':uuid4()}


@require_GET
@protected
def stage_read(request,page_id,stage_id):
    try:
        context=stage_context(request,page_id,stage_id)
    except ValidationError as exc:
        if exc.messages!=['VERSIONS_STAGE_STALE']:raise
        # Only the currently authorised actor may see their own stage status.
        # Do not load a historical payload or manufacture an operation receipt.
        with transaction.atomic():
            page,profile,fields,owner,state=E.enter(request.user,page_id,request.auth_generation)
            status=RestoreStage.objects.filter(pk=stage_id,page=page,actor_id=request.user.pk).values_list('status',flat=True).first()
        messages={
            'released':'Подготовка восстановления отменена. Данные для подстановки не выдаются.',
            'consumed':'Подготовка восстановления уже применена. Повторная подстановка недоступна.',
            'invalidated':'Подготовка восстановления утратила актуальность. Подготовьте восстановление заново из истории.',
            'held':'Подготовка восстановления утратила актуальность. Подготовьте восстановление заново из истории.',
        }
        if status not in messages:raise
        return error(request,page_id,messages[status]+' Текущая версия страницы не изменена этим просмотром.')
    return render(request,'page_versions/stage.html',context)


@require_POST
@protected
def stage_cancel(request,page_id,stage_id):
    data=form(request,['generation','operation_id'])
    return result_page(request,page_id,V.cancel_stage(actor=request.user,page_id=page_id,stage_id=stage_id,
        expected_generation=generation(request,data),operation_id=operation(data)))
