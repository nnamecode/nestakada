"""Owner confirmation form for simple publish/hide."""
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from accounts.views import fields, gate

from . import simple_publication as publication
from .models import Page
from .tree_commands import TreeFault

LABELS = {'publish': 'Опубликовать страницу', 'hide': 'Скрыть страницу'}
MESSAGES = {
    'PUBLICATION_BASIS_CHANGED': 'Страница, адрес или текущее содержимое изменились. Откройте актуальную форму и проверьте состояние.',
    'PUBLICATION_OPERATION_CONFLICT': 'Это подтверждение уже относится к другой команде. Изменения не применены.',
    'PUBLICATION_PRIMARY_REQUIRED': 'У страницы должен быть ровно один основной адрес.',
    'PUBLICATION_CONTENT_REQUIRED': 'У страницы нет готовой текущей версии содержимого.',
    'PUBLICATION_CONTENT_DAMAGED': 'Целостность текущей версии не подтверждена. Публикация остановлена.',
    'PUBLICATION_UNCHANGED': 'Страница уже находится в выбранном состоянии.',
}


def _failed(request, page_id, action, data, status, message, *, retry=False):
    return render(request, 'accounts/page_publication.html', {
        'owner': True, 'page_id': page_id, 'action': action,
        'label': LABELS[action], 'values': data, 'error_mode': True,
        'message': message, 'retry': retry,
    }, status=status)


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def page_publication(request, page_id, action):
    if action not in LABELS:
        raise Http404()
    data = {}
    try:
        if request.method == 'GET':
            if request.GET:
                raise TreeFault('PUBLICATION_INVALID_INPUT', 400)
            prepared = publication.prepare(
                actor=request.user, page_id=page_id, action=action,
                generation=request.auth_generation,
                session_key=request.session.session_key)
            values = {
                'operation_id': prepared['operation_id'],
                'token': prepared['token'],
            }
            return render(request, 'accounts/page_publication.html', {
                'owner': True, 'page_id': page_id, 'action': action,
                'label': LABELS[action], 'prepared': prepared,
                'values': values,
            })
        if request.GET:
            raise TreeFault('PUBLICATION_INVALID_INPUT', 400)
        data = fields(request, ['operation_id', 'token'])
        if any(key not in data for key in ('operation_id', 'token')):
            raise TreeFault('PUBLICATION_INVALID_INPUT', 400)
        result = publication.apply(
            actor=request.user, page_id=page_id, action=action,
            generation=request.auth_generation,
            session_key=request.session.session_key,
            operation_id=data['operation_id'], token=data['token'])
        response = HttpResponse(status=303)
        response['Location'] = reverse('accounts:page-tree') + (
            '?' + urlencode({'parent': result['parent_id']})
            if result['parent_id'] else '')
        response['X-Tree-Result'] = 'applied'
        return response
    except PermissionDenied:
        return render(request, 'accounts/forbidden.html', status=403)
    except Page.DoesNotExist:
        return _failed(request, page_id, action, data, 404,
                       'Эта страница больше недоступна.')
    except TreeFault as error:
        if error.status == 401:
            return render(request, 'accounts/denied.html', status=401)
        return _failed(
            request, page_id, action, data, error.status,
            MESSAGES.get(error.code,
                         'Не удалось проверить подтверждение. Откройте актуальную форму.'))
    except ValidationError:
        return _failed(request, page_id, action, data, 400,
                       'Проверьте поля формы. Изменения не применены.')
    except (DatabaseError, OSError):
        return _failed(
            request, page_id, action, data, 503,
            'Результат пока не подтверждён. Повторите ту же команду: система безопасно проверит, было ли изменение применено.',
            retry=True)
