"""D-408 closed local creation form. No public writer or publication action."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from urllib.parse import urlencode
from accounts.views import gate, fields
from .models import Page
from . import creation
from .tree_commands import TreeFault
from page_versions.models import OwnerDraft

INPUTS = ('step', 'operation_id', 'page_id', 'token', 'name', 'kind', 'parent_id', 'url', 'h1', 'title')
KIND_LABELS = {'service_detail': 'Услуга', 'article': 'Статья', 'service_catalog': 'Каталог услуг',
               'service_section_overview': 'Обзор раздела услуг', 'articles_catalog': 'Каталог статей'}
MESSAGES = {
    'CREATE_DISABLED': 'Создание ещё не включено в этом локальном профиле.',
    'CREATE_URL_CONFLICT': 'Адрес уже занят. Укажите другой адрес и проверьте форму.',
    'CREATE_INVALID_URL': 'Проверьте адрес. Нужен допустимый локальный путь.',
    'CREATE_BASIS_CHANGED': 'Дерево изменилось. Ввод сохранён; явно проверьте форму ещё раз.',
    'TREE_BASIS_CHANGED': 'Дерево изменилось. Ввод сохранён; явно проверьте форму ещё раз.',
}


def form(request, values, prepared=None, message=None, status=200):
    # Error rendering never prepares a new token or queries an unavailable DB.
    return render(request, 'accounts/page_create.html', {'owner': True, 'values': values,
        'prepared': prepared, 'message': message,
        'metadata_ready': 'h1' in values and 'title' in values,
        'kind_choices': [(value, KIND_LABELS[value]) for value in creation.KINDS]}, status=status)


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def create_page(request):
    data = {}
    try:
        if settings.DEV29_LOCAL_CREATE_ENABLED is not True or settings.ENVIRONMENT != 'test':
            raise TreeFault('CREATE_DISABLED', 503)
        common = {'actor': request.user, 'generation': request.auth_generation,
                  'session_key': request.session.session_key}
        if request.method == 'GET':
            if set(request.GET) - {'parent', 'kind'} or any(len(request.GET.getlist(k)) != 1 for k in request.GET):
                raise TreeFault('CREATE_INVALID_INPUT', 400)
            prepared = creation.prepare(**common, parent_id=request.GET.get('parent') or None,
                                        kind=request.GET.get('kind', 'article'))
            data = {key: prepared[key] for key in ('operation_id', 'page_id', 'token', 'parent_id', 'kind')}
            data.update(name='', url='')
            return form(request, data, prepared)
        if request.GET:
            raise TreeFault('CREATE_INVALID_INPUT', 400)
        data = fields(request, INPUTS)
        required = {'step','operation_id','page_id','token','name','kind','parent_id','url'}
        if not required <= set(data) or data['step'] not in ('preview', 'save'):
            raise TreeFault('CREATE_INVALID_INPUT', 400)
        if ('h1' in data) != ('title' in data):
            raise TreeFault('CREATE_INVALID_INPUT', 400)
        if data['step'] == 'preview':
            prepared = creation.prepare(**common, parent_id=data['parent_id'] or None, kind=data['kind'],
                                         operation_id=data['operation_id'], page_id=data['page_id'])
            suggested = creation.preview(name=data['name'], parent_id=data['parent_id'] or None)
            values = data.dict()
            values['token'] = prepared['token']
            if not values['url']:
                values['url'] = suggested['url'] or ''
            if 'h1' not in values:
                values.update(h1=suggested['h1'], title=suggested['title'])
            return form(request, values, prepared,
                'Проверьте постоянный адрес до сохранения.' if values['url'] else
                'Автоматический адрес недоступен для этого названия или родителя. Введите полный путь вручную.')
        if not {'h1','title'} <= set(data):
            raise TreeFault('CREATE_INVALID_INPUT', 400)
        result = creation.apply(**common, **{key:data[key] for key in
            ('token','operation_id','page_id','parent_id','kind','name','url','h1','title')})
        if not result['exists']:
            return form(request, data, message='Команда выполнена ранее; созданная страница больше недоступна.', status=410)
        response = HttpResponse(status=303)
        location = reverse('page_editor:editor', kwargs={'page_id': result['page_id']})
        # Resolve the live draft, including on replay. Never reopen a historical
        # draft revision or implicitly rebase it onto a later current version.
        draft = OwnerDraft.objects.filter(page_id=result['page_id']).values('id','revision').first()
        if draft is not None:
            location += '?' + urlencode({'source':'owner-draft','draftId':str(draft['id']),
                                         'draftRevision':draft['revision']})
        response['Location'] = location
        response['X-Tree-Result'] = 'replay' if result['replayed'] else 'applied'
        return response
    except PermissionDenied:
        return render(request, 'accounts/forbidden.html', status=403)
    except Page.DoesNotExist:
        return form(request, data, message='Выбранный родитель больше недоступен. Ввод сохранён.', status=409)
    except TreeFault as error:
        if error.status == 401:
            return render(request, 'accounts/denied.html', status=401)
        return form(request, data, message=MESSAGES.get(error.code,
            'Не удалось проверить поля или подтверждение. Ввод сохранён; проверьте форму явно.'), status=error.status)
    except ValidationError:
        return form(request, data, message='Проверьте поля формы. Изменения не применены.', status=400)
    except (DatabaseError, OSError):
        return form(request, data, message='Результат пока не подтверждён. Повторите ту же команду с теми же полями; не создавайте новую до проверки результата.', status=503)
