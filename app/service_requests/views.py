from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.core import signing
from django.db import DatabaseError, transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from accounts import services as account_services
from accounts.views import fields, gate, redirect_to
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from .models import RequestSettings, ServiceRequest
from . import deletion, ledger


PAGE_SIZE = 25
PAGE_MAX = 10_000
MOSCOW = ZoneInfo('Europe/Moscow')
DELETE_SALT = 'estakada.service-request.delete.v1'


def _page_number(request):
    if not request.GET:
        return 1
    if (set(request.GET) != {'page'} or len(request.GET.getlist('page')) != 1):
        raise ValidationError('REQUEST_LIST_QUERY_INVALID')
    raw = request.GET['page']
    if (not raw.isascii() or not raw.isdigit() or raw.startswith('0')
            or not 1 <= int(raw) <= PAGE_MAX):
        raise ValidationError('REQUEST_LIST_PAGE_INVALID')
    return int(raw)


def _created_at(row):
    return timezone.localtime(row.created_at, MOSCOW)


@require_GET
@gate()
def request_list(request):
    owner = account_services.is_owner(request.user)
    try:
        page = _page_number(request)
    except ValidationError:
        return render(request, 'service_requests/error.html', {
            'owner': owner, 'message': 'Неверный номер страницы.'}, status=400)
    start = (page - 1) * PAGE_SIZE
    rows = list(ServiceRequest.objects.only(
        'id', 'created_at', 'name', 'phone', 'source').order_by(
            '-created_at', '-id')[start:start + PAGE_SIZE + 1])
    has_next = len(rows) > PAGE_SIZE
    rows = rows[:PAGE_SIZE]
    return render(request, 'service_requests/list.html', {
        'owner': owner, 'rows': [
            {'row': row, 'created_at': _created_at(row)} for row in rows],
        'page': page, 'has_previous': page > 1, 'previous': page - 1,
        'has_next': has_next, 'next': page + 1,
    })


@require_GET
@gate()
def request_detail(request, request_id):
    owner = account_services.is_owner(request.user)
    row = get_object_or_404(ServiceRequest, pk=request_id)
    return render(request, 'service_requests/detail.html', {
        'owner': owner, 'row': row, 'created_at': _created_at(row),
    })


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def request_settings(request):
    row = RequestSettings.objects.filter(pk=1).first()
    error = None
    if request.method == 'POST':
        try:
            data = fields(request, ['recipient_email'])
            candidate = RequestSettings(
                id=1, recipient_email=data.get('recipient_email', '').strip())
            candidate.full_clean(validate_unique=False, validate_constraints=False)
            with transaction.atomic():
                RequestSettings.objects.update_or_create(
                    pk=1, defaults={'recipient_email': candidate.recipient_email})
                record_event(
                    category=Category.USER_ACTIONS,
                    event_code='REQUEST_SETTINGS_CHANGED', level=Level.INFO,
                    source=Source.APPLICATION, result=Result.SUCCESS,
                    actor_id=request.user.pk)
            return redirect_to('service_requests:settings')
        except (ValidationError, DatabaseError):
            error = 'Не удалось сохранить адрес. Проверьте его и повторите.'
        row = candidate if 'candidate' in locals() else row
    return render(request, 'service_requests/settings.html', {
        'owner': True, 'settings': row, 'error': error,
    })


def _delete_token(row):
    return signing.dumps({
        'schema': 'service-request-delete-v1',
        'request_id': str(row.pk),
        'created_at': row.created_at.isoformat(),
    }, salt=DELETE_SALT, compress=False)


def _verify_delete_token(value, request_id):
    try:
        payload = signing.loads(value, salt=DELETE_SALT, max_age=1800)
    except signing.BadSignature:
        raise ValidationError('REQUEST_DELETE_CONFIRMATION_INVALID') from None
    if (type(payload) is not dict
            or set(payload) != {'schema', 'request_id', 'created_at'}
            or payload['schema'] != 'service-request-delete-v1'
            or payload['request_id'] != str(request_id)
            or type(payload['created_at']) is not str):
        raise ValidationError('REQUEST_DELETE_CONFIRMATION_INVALID')
    return payload


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def request_delete(request, request_id):
    if request.method == 'GET':
        row = get_object_or_404(ServiceRequest, pk=request_id)
        return render(request, 'service_requests/delete.html', {
            'owner': True, 'row': row, 'confirmation': _delete_token(row),
        })
    try:
        data = fields(request, ['confirmation'])
        payload = _verify_delete_token(data.get('confirmation', ''), request_id)
        row = ServiceRequest.objects.filter(pk=request_id).only('created_at').first()
        if row is not None and row.created_at.isoformat() != payload['created_at']:
            raise ValidationError('REQUEST_DELETE_CONFIRMATION_STALE')
        deletion.delete(request_id=request_id, actor_id=request.user.pk)
        return redirect_to('service_requests:list')
    except ServiceRequest.DoesNotExist:
        return render(request, 'service_requests/error.html', {
            'owner': True, 'message': 'Заявка не найдена.'}, status=404)
    except ValidationError:
        return render(request, 'service_requests/error.html', {
            'owner': True, 'message': 'Подтверждение устарело.'}, status=400)
    except (ledger.LedgerError, DatabaseError):
        return render(request, 'service_requests/error.html', {
            'owner': True,
            'message': 'Удаление не выполнено. Заявка сохранена.'}, status=503)
