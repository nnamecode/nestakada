"""Private owner forms; the service performs the authoritative locked checks."""
from urllib.parse import urlencode
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from accounts.views import gate, fields
from .models import Page
from . import tree_commands as commands

LABELS = {'rename': 'Изменить название', 'move': 'Переместить страницу', 'reorder': 'Изменить порядок'}
MESSAGES = {
    'TREE_BASIS_CHANGED': 'Дерево или содержимое страниц изменилось. Ваши данные не применены. Откройте актуальную форму и проверьте изменения.',
    'TREE_OPERATION_CONFLICT': 'Это подтверждение уже относится к другой команде. Изменения не применены.',
    'TREE_INVALID_NAME': 'Введите непустое название до 200 символов, без управляющих символов.',
    'TREE_PARENT_CONFLICT': 'Проверьте выбранный раздел. Страницу нельзя переместить в саму себя или в её дочерний раздел.',
    'TREE_NEIGHBOUR_CONFLICT': 'Выбранная соседняя страница не относится к нужному разделу. Обновите форму.',
}


def failed(request, page_id, action, data, status, message):
    return render(request, 'accounts/tree_command.html', {'owner': True, 'action': action,
        'label': LABELS[action], 'page_id': page_id, 'values': data, 'error_mode': True,
        'message': message}, status=status)


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def command(request, page_id, action):
    if action not in LABELS:
        raise Http404()
    data = {}
    try:
        if request.method == 'GET':
            if (set(request.GET) - ({'parent'} if action == 'move' else set())
                    or any(len(request.GET.getlist(key)) != 1 for key in request.GET)):
                raise commands.TreeFault('TREE_INVALID_INPUT', 400)
            prepared = commands.prepare(actor=request.user, page_id=page_id, action=action,
                generation=request.auth_generation, session_key=request.session.session_key,
                destination=request.GET.get('parent', 'current'))
            values = {'operation_id': prepared['operation_id'], 'token': prepared['token'],
                      'name': prepared['page'].name, 'parent_id': prepared['destination'], 'before_id': ''}
            return render(request, 'accounts/tree_command.html', {'owner': True, 'action': action,
                'label': LABELS[action], 'page_id': page_id, 'prepared': prepared, 'values': values})
        if request.GET:
            raise commands.TreeFault('TREE_INVALID_INPUT', 400)
        allowed = ['operation_id', 'token'] + (['name'] if action == 'rename' else ['parent_id', 'before_id'])
        data = fields(request, allowed)
        if any(key not in data for key in allowed):
            raise commands.TreeFault('TREE_INVALID_INPUT', 400)
        result = commands.apply(actor=request.user, page_id=page_id, action=action,
            generation=request.auth_generation, session_key=request.session.session_key,
            token=data['token'], operation_id=data['operation_id'], name=data.get('name'),
            parent_id=data.get('parent_id'), before_id=data.get('before_id'))
        response = HttpResponse(status=303)
        response['Location'] = reverse('accounts:page-tree') + (
            '?' + urlencode({'parent': result['parent_id']}) if result['parent_id'] else '')
        response['X-Tree-Result'] = 'replay' if result['replay'] else 'applied'
        return response
    except PermissionDenied:
        return render(request, 'accounts/forbidden.html', status=403)
    except Page.DoesNotExist:
        return failed(request, page_id, action, data, 404, 'Эта страница больше недоступна. Вернитесь к дереву страниц.')
    except commands.TreeFault as error:
        if error.status == 401:
            return render(request, 'accounts/denied.html', status=401)
        return failed(request, page_id, action, data, error.status,
            MESSAGES.get(error.code, 'Не удалось проверить поля или подтверждение. Проверьте ввод и откройте актуальную форму.'))
    except ValidationError:
        return failed(request, page_id, action, data, 400, 'Проверьте поля формы. Изменения не применены.')
    except (DatabaseError, OSError):
        return failed(request, page_id, action, data, 503,
            'Результат пока не подтверждён. Повторите ту же команду без изменения полей; не начинайте новое действие до проверки результата.')
