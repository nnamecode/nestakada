from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError
from django.http import HttpResponse

from . import notifications, services


PUBLIC_CSP = ("default-src 'none'; style-src 'self'; base-uri 'none'; "
              "object-src 'none'; frame-ancestors 'none'; form-action 'self'")
FIELDS = frozenset(('name', 'phone', 'car', 'comment', 'consent', 'intent'))


def _response(message, status):
    response = HttpResponse(
        message, status=status, content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['Content-Security-Policy'] = PUBLIC_CSP
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def submit(request):
    if request.method != 'POST':
        response = _response('Метод не поддерживается.', 405)
        response['Allow'] = 'POST'
        return response
    if (settings.SERVICE_REQUEST_INTAKE_ENABLED is not True
            or settings.SERVICE_REQUEST_TRANSPORT_PROFILE != 'synthetic'):
        return _response('Запись через сайт временно недоступна.', 503)
    try:
        if (set(request.POST) - {'csrfmiddlewaretoken'} != FIELDS
                or any(len(request.POST.getlist(key)) != 1
                       for key in set(request.POST))):
            raise ValidationError('REQUEST_INVALID_FORM')
        result = services.accept(
            intent=request.POST['intent'], name=request.POST['name'],
            phone=request.POST['phone'], car=request.POST['car'],
            comment=request.POST['comment'], consent=request.POST['consent'])
        if result.inserted:
            notifications.deliver(result.request)
    except ValidationError:
        return _response('Проверьте заполнение формы.', 400)
    except (DatabaseError, IntegrityError):
        return _response('Не удалось принять заявку. Повторите позже.', 503)
    return _response('Заявка принята.', 200)
