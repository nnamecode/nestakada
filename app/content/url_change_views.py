"""Owner confirmation form for changing a non-legacy PRIMARY URL."""
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.views import fields, gate

from . import simple_url_change as url_change
from .models import Page
from .tree_commands import TreeFault

MESSAGES = {
    'URL_CHANGE_LEGACY_PROTECTED': 'Перенесённый адрес защищён и не может быть изменён этой командой.',
    'URL_CHANGE_PRIMARY_REQUIRED': 'У страницы должен быть ровно один основной адрес.',
    'URL_CHANGE_BASIS_CHANGED': 'Страница или основной адрес изменились. Откройте актуальную форму.',
    'URL_CHANGE_OPERATION_CONFLICT': 'Это подтверждение уже относится к другой команде.',
    'URL_CHANGE_INVALID_TARGET': 'Введите допустимый новый локальный адрес без query, fragment и служебного пути.',
    'URL_CHANGE_TARGET_CONFLICT': 'Этот адрес уже занят страницей, alias, redirect или системным маршрутом.',
    'URL_CHANGE_UNCHANGED': 'Новый адрес совпадает с текущим.',
}


def _form(request, page_id, values, *, prepared=None, message=None,
          status=200, retry=False):
    return render(request, 'accounts/page_url_change.html', {
        'owner': True, 'page_id': page_id, 'values': values,
        'prepared': prepared, 'message': message,
        'error_mode': status != 200, 'retry': retry,
    }, status=status)


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def page_url_change(request, page_id):
    data = {}
    try:
        common = {
            'actor': request.user, 'page_id': page_id,
            'generation': request.auth_generation,
            'session_key': request.session.session_key,
        }
        if request.method == 'GET':
            if request.GET:
                raise TreeFault('URL_CHANGE_INVALID_INPUT', 400)
            prepared = url_change.prepare(**common)
            data = {
                'operation_id': prepared['operation_id'],
                'token': prepared['token'], 'target': '',
            }
            return _form(request, page_id, data, prepared=prepared)
        if request.GET:
            raise TreeFault('URL_CHANGE_INVALID_INPUT', 400)
        data = fields(request, ['operation_id', 'token', 'target'])
        if any(key not in data for key in
               ('operation_id', 'token', 'target')):
            raise TreeFault('URL_CHANGE_INVALID_INPUT', 400)
        result = url_change.apply(
            **common, operation_id=data['operation_id'],
            token=data['token'], target=data['target'])
        response = HttpResponse(status=303)
        response['Location'] = reverse('accounts:page-tree') + (
            '?' + urlencode({'parent': result['parent_id']})
            if result['parent_id'] else '')
        response['X-Tree-Result'] = 'applied'
        return response
    except PermissionDenied:
        return render(request, 'accounts/forbidden.html', status=403)
    except Page.DoesNotExist:
        return _form(request, page_id, data,
                     message='Эта страница больше недоступна.', status=404)
    except TreeFault as error:
        if error.status == 401:
            return render(request, 'accounts/denied.html', status=401)
        return _form(
            request, page_id, data,
            message=MESSAGES.get(
                error.code,
                'Не удалось проверить поля или подтверждение. Откройте актуальную форму.'),
            status=error.status)
    except ValidationError:
        return _form(request, page_id, data,
                     message='Проверьте поля формы. Изменения не применены.',
                     status=400)
    except (DatabaseError, OSError):
        return _form(
            request, page_id, data,
            message=('Результат пока не подтверждён. Повторите ту же '
                     'команду: система безопасно проверит состояние адреса.'),
            status=503, retry=True)
