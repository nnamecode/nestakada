"""Owner confirmation UI for deleting one leaf Page and all history."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.views import fields, gate

from . import simple_page_delete as page_delete
from .models import Page
from .tree_commands import TreeFault

MESSAGES = {
    'PAGE_DELETE_HAS_CHILDREN': 'Сначала отдельно разберите дочерние страницы. Поддерево не удаляется.',
    'PAGE_DELETE_PRIMARY_REQUIRED': 'У страницы должен быть ровно один основной адрес.',
    'PAGE_DELETE_HISTORY_REQUIRED': 'История страницы неполна. Удаление остановлено.',
    'PAGE_DELETE_BASIS_CHANGED': 'Страница, маршруты или история изменились. Откройте актуальное подтверждение.',
    'PAGE_DELETE_OPERATION_CONFLICT': 'Это подтверждение уже относится к другой команде.',
    'PAGE_DELETE_EXACT_CONFIRMATION_REQUIRED': 'Введите точные название и основной адрес, показанные в актуальной форме.',
}


def _form(request, page_id, values, *, prepared=None, message=None,
          status=200, retry=False):
    return render(request, 'accounts/page_delete.html', {
        'owner': True, 'page_id': page_id, 'values': values,
        'prepared': prepared, 'message': message,
        'error_mode': status != 200, 'retry': retry,
    }, status=status)


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def delete_page(request, page_id):
    data = {}
    try:
        common = {
            'actor': request.user, 'page_id': page_id,
            'generation': request.auth_generation,
            'session_key': request.session.session_key,
        }
        if request.method == 'GET':
            if request.GET:
                raise TreeFault('PAGE_DELETE_INVALID_INPUT', 400)
            prepared = page_delete.prepare(**common)
            data = {
                'operation_id': prepared['operation_id'],
                'token': prepared['token'],
                'confirm_name': '', 'confirm_url': '',
            }
            return _form(request, page_id, data, prepared=prepared)
        if request.GET:
            raise TreeFault('PAGE_DELETE_INVALID_INPUT', 400)
        posted = fields(request, [
            'operation_id', 'token', 'confirm_name',
            'confirm_url', 'password'])
        required = ('operation_id', 'token', 'confirm_name',
                    'confirm_url', 'password')
        if any(key not in posted for key in required):
            raise TreeFault('PAGE_DELETE_INVALID_INPUT', 400)
        data = {key: posted[key] for key in required if key != 'password'}
        result = page_delete.apply(
            **common, operation_id=posted['operation_id'],
            token=posted['token'], confirm_name=posted['confirm_name'],
            confirm_url=posted['confirm_url'], password=posted['password'])
        response = HttpResponse(status=303)
        response['Location'] = reverse('accounts:page-tree')
        response['X-Tree-Result'] = (
            'replay' if result['replay'] else 'applied')
        return response
    except PermissionDenied:
        return _form(
            request, page_id, data,
            message='Текущий пароль владельца не подтверждён.', status=403)
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
                'Не удалось проверить подтверждение. Откройте актуальную форму.'),
            status=error.status)
    except ValidationError:
        return _form(request, page_id, data,
                     message='Удаление остановлено проверкой целостности.',
                     status=409)
    except (DatabaseError, OSError):
        return _form(
            request, page_id, data,
            message=('Результат пока не подтверждён. Повторите ту же '
                     'команду и заново введите текущий пароль.'),
            status=503, retry=True)
