from collections import Counter
from urllib.parse import urlencode
from uuid import UUID
from pathlib import Path
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.middleware.csrf import get_token
from django.views.decorators.http import require_GET, require_POST
from accounts.views import gate, fields
from audit.constants import Result
from content.models import Page
from .models import Asset, AssetFile, MediaFolder, PageMediaHome
from .paths import relative_path
from .storage import MediaStorage
from . import services, uploads
from .worker_client import WorkerClient, UploadRejected, UploadPending, WorkerUnavailable, MAX_INPUT


def _generation(request,data):
    try:given=int(data.get('generation',''))
    except (ValueError,TypeError):raise ValidationError('MEDIA_GENERATION_REQUIRED') from None
    if given!=request.auth_generation:raise PermissionDenied('AUTH_GENERATION_CHANGED')
    return given


def _error(request,message,status=400):
    return render(request,'media_library/error.html',{'owner':True,'message':message},status=status)


def _inside(path,selected):
    return not selected or path==selected or path.startswith(selected+'/')


@require_GET
@gate(owner=True)
def catalog(request):
    if len(request.META.get('QUERY_STRING','').encode('utf-8'))>16384:
        return _error(request,'Не удалось открыть медиатеку. Уточните запрос.')
    try:
        if any(key not in {'folder','q','page','asset'} or len(request.GET.getlist(key))!=1 for key in request.GET):raise ValidationError('MEDIA_INVALID_QUERY')
        selected=request.GET.get('folder','')
        if selected:relative_path(selected)
        current_page=get_object_or_404(Page,pk=UUID(request.GET['page'])) if request.GET.get('page') else None
    except (ValueError,ValidationError):raise Http404 from None
    homes={home.folder_id:home for home in PageMediaHome.objects.select_related('page','folder')}
    if current_page and not selected:
        home=next((home for home in homes.values() if home.page_id==current_page.pk),None)
        selected=home.folder.path if home else ''
    folders=list(MediaFolder.objects.order_by('path'))
    if selected and not any(_inside(folder.path,selected) for folder in folders):raise Http404
    query=request.GET.get('q','').strip();prefix=selected+'/' if selected else ''
    children={}
    for folder in folders:
        if folder.path.startswith(prefix) and folder.path!=selected:
            child=prefix+folder.path[len(prefix):].split('/')[0]
            children[child]=homes[folder.pk].page.name if child==folder.path and folder.pk in homes else child.rsplit('/',1)[-1]
    rows=[]
    assets=Asset.objects.filter(status=Asset.Status.READY).select_related('folder').prefetch_related('files').order_by('id')
    for asset in assets:
        if not _inside(asset.folder.path,selected):continue
        title=homes[asset.folder_id].page.name if asset.folder_id in homes else asset.folder.path
        if query and query.casefold() not in (title+' '+asset.folder.path+' '+str(asset.pk)).casefold():continue
        if not query and asset.folder.path!=selected:continue
        file_rows=list(asset.files.all());main=next((file for file in file_rows if file.kind in (AssetFile.Kind.MAIN,AssetFile.Kind.LEGACY_PUBLIC)),None)
        thumbnail=next((file for file in file_rows if file.kind==AssetFile.Kind.PREVIEW),main)
        rows.append({'asset':asset,'title':title,'main':main,'thumbnail':thumbnail,'file_count':len(file_rows)})
    uploaded=None
    if request.GET.get('asset'):
        try:uploaded=Asset.objects.filter(pk=UUID(request.GET['asset']),status=Asset.Status.READY).first()
        except ValueError:raise Http404 from None
    selected_label=next((homes[folder.pk].page.name for folder in folders if folder.path==selected and folder.pk in homes),selected.rsplit('/',1)[-1])
    return render(request,'media_library/catalog.html',{'owner':True,'rows':rows,'children':sorted(children.items()),'selected':selected,'selected_label':selected_label,
        'parent':selected.rsplit('/',1)[0] if '/' in selected else '', 'query':query,'current_page':current_page,
        'pages':Page.objects.order_by('name'),'generation':request.auth_generation,'uploaded':uploaded,'pending':WorkerClient().pending()})


@require_GET
@gate(owner=True,touch=False)
def stylesheet(request):
    response=FileResponse((Path(__file__).parent/'assets/media.css').open('rb'),content_type='text/css; charset=utf-8')
    response['X-Content-Type-Options']='nosniff'
    return response


@require_POST
@gate(owner=True)
def upload_view(request,page_id):
    get_object_or_404(Page,pk=page_id)
    try:
        if request.content_type!='multipart/form-data':raise ValidationError('MEDIA_MULTIPART_REQUIRED')
        length=int(request.META.get('CONTENT_LENGTH') or 0)
        if not 0<length<=11*1024*1024:return _error(request,'Файл не принят: размер запроса превышает допустимый.',413)
        if any(key not in {'generation','csrfmiddlewaretoken'} or len(request.POST.getlist(key))!=1 for key in request.POST):raise ValidationError('MEDIA_INVALID_FIELDS')
        if len(urlencode(list(request.POST.items())).encode())>16384:raise ValidationError('MEDIA_INVALID_FIELDS')
        generation=_generation(request,request.POST)
        if set(request.FILES)!={'image'} or len(request.FILES.getlist('image'))!=1:raise ValidationError('MEDIA_ONE_IMAGE_REQUIRED')
        image=request.FILES['image']
        if image.size>MAX_INPUT:return _error(request,'Файл не принят: максимальный размер — 1 МБ (1 000 000 байт).',413)
        asset=uploads.upload(actor=request.user,page_id=page_id,upload=image,expected_generation=generation)
    except PermissionDenied:return _error(request,'Доступ изменился. Войдите снова и проверьте актуальные права.',403)
    except UploadRejected:return _error(request,'Файл не принят: проверьте формат JPEG, PNG или WebP, размер и отсутствие анимации.')
    except UploadPending:return _error(request,'Загрузка не завершена. Проверьте актуальную медиатеку и состояние обработчика перед повтором.',503)
    except WorkerUnavailable:return _error(request,'Обработчик изображений недоступен. Загрузка не выполнена.',503)
    except (ValidationError,ValueError,TypeError):return _error(request,'Файл не принят: выберите один JPEG, PNG или WebP размером до 1 МБ.')
    response=HttpResponse(status=303)
    response['Location']=reverse('media_library:catalog')+'?'+urlencode({'page':str(page_id),'asset':str(asset.pk)})
    return response


@require_GET
@gate(owner=True)
def preview(request,file_id):
    file=get_object_or_404(AssetFile.objects.select_related('asset'),pk=file_id,asset__status=Asset.Status.READY)
    if file.kind==AssetFile.Kind.PRIVATE_SOURCE:raise Http404
    source=None
    try:
        source=MediaStorage().open_verified(file.key,{'sha256':file.sha256,'byte_size':file.byte_size})
        prefix=source.read(12);source.seek(0)
        mime='image/webp' if prefix[:4]==b'RIFF' and prefix[8:12]==b'WEBP' else None
        if file.kind==AssetFile.Kind.LEGACY_PUBLIC:
            mime='image/jpeg' if prefix.startswith(b'\xff\xd8\xff') else 'image/png' if prefix.startswith(b'\x89PNG\r\n\x1a\n') else mime
        if mime is None:raise ValidationError('MEDIA_INVALID_PREVIEW')
        response=FileResponse(source,content_type=mime)
        response['Content-Disposition']='inline'
        response['X-Content-Type-Options']='nosniff'
        return response
    except (OSError,ValidationError):
        if source is not None:source.close()
        raise Http404 from None


def _cleanup_state(request):
    storage=MediaStorage();candidates=[];retained=[];pending=[];unavailable=[]
    with transaction.atomic():
        services._owner_locked(request.user,request.auth_generation)
        for asset in Asset.objects.select_related('folder').prefetch_related('usages','files').order_by('id'):
            references=list(asset.usages.all())
            if references:
                labels={'current_page':'Страница','shared_block':'Общий блок','ordinary_version':'Версия','stable_version':'Stable','draft':'Черновик','retained_html':'HTML-копия'}
                retained.append({'asset':asset,'references':[(labels[kind],count) for kind,count in sorted(Counter(row.kind for row in references).items())]});continue
            if asset.status in (Asset.Status.DELETING,Asset.Status.DELETE_FAILED):pending.append(asset);continue
            if asset.status!=Asset.Status.READY:continue
            try:manifest=services._manifest(asset,storage)
            except (OSError,ValidationError):unavailable.append(asset);continue
            main=next((file for file in asset.files.all() if file.kind in (AssetFile.Kind.PREVIEW,AssetFile.Kind.MAIN,AssetFile.Kind.LEGACY_PUBLIC)),None)
            candidates.append({'asset':asset,'files':manifest['files'],'bytes':sum(file['byte_size'] for file in manifest['files']),'preview':main})
    return {'owner':True,'candidates':candidates,'retained':retained,'pending':pending,'unavailable':unavailable,
            'total_bytes':sum(row['bytes'] for row in candidates),'generation':request.auth_generation}


@require_GET
@gate(owner=True)
def cleanup_catalog(request):
    return render(request,'media_library/cleanup.html',_cleanup_state(request))


@require_POST
@gate(owner=True)
def cleanup_prepare(request):
    try:
        data=fields(request,['generation','asset_ids'])
        # Checkbox values intentionally repeat; fields() rejects duplicates, so parse with the same byte bound here.
    except ValidationError:
        if request.content_type!='application/x-www-form-urlencoded' or len(request.body)>16384:return _error(request,'Не удалось проверить выбор файлов.')
        if any(key not in {'generation','asset_ids','csrfmiddlewaretoken'} or (key!='asset_ids' and len(request.POST.getlist(key))!=1) for key in request.POST):return _error(request,'Не удалось проверить выбор файлов.')
        data=request.POST
    try:
        generation=_generation(request,data)
        preview=services.prepare_cleanup(actor=request.user,asset_ids=data.getlist('asset_ids'),expected_generation=generation)
        if len(urlencode({'confirmation':preview['confirmation'],'generation':generation,'csrfmiddlewaretoken':get_token(request)}).encode())>16384:
            return _error(request,'Выберите меньше файлов для одного подтверждения.')
        for item in preview['candidates']:uploads.media_event('MEDIA_CLEANUP_PREPARED',request.user,item['asset_id'])
    except PermissionDenied:return _error(request,'Доступ изменился. Проверьте актуальные права.',403)
    except (ValidationError,ValueError,TypeError,OSError):return _error(request,'Не удалось подтвердить отсутствие использования. Обновите проверку.')
    return render(request,'media_library/confirm.html',{'owner':True,'preview':preview,'generation':generation})


@require_POST
@gate(owner=True)
def cleanup_confirm(request):
    try:
        data=fields(request,['generation','confirmation']);generation=_generation(request,data)
        results=services.confirm_cleanup(actor=request.user,confirmation=data.get('confirmation',''),expected_generation=generation)
        _record_cleanup(request,results)
    except PermissionDenied:return _error(request,'Доступ изменился. Проверьте актуальные права.',403)
    except (ValidationError,ValueError,TypeError,OSError,ObjectDoesNotExist):return _error(request,'Очистка не подтверждена. Проверьте актуальный список и использование файлов.')
    return render(request,'media_library/result.html',{'owner':True,'results':results})


def _record_cleanup(request,results):
    for result in results:
        uploads.media_event('MEDIA_CLEANUP_PENDING' if result['state']=='delete_failed' else 'MEDIA_CLEANUP_DELETED',request.user,result['asset_id'],
                            Result.PENDING if result['state']=='delete_failed' else Result.SUCCESS)


@require_POST
@gate(owner=True)
def cleanup_retry(request,asset_id):
    try:
        data=fields(request,['generation']);generation=_generation(request,data)
        result=services.retry_cleanup(actor=request.user,asset_id=asset_id,expected_generation=generation)
        _record_cleanup(request,[result])
    except PermissionDenied:return _error(request,'Доступ изменился. Проверьте актуальные права.',403)
    except (ValidationError,ValueError,TypeError,OSError,ObjectDoesNotExist):return _error(request,'Удаление не завершено. Проверьте актуальное состояние и повторите проверку.')
    return render(request,'media_library/result.html',{'owner':True,'results':[result]})
