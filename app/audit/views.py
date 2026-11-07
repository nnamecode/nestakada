import re
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.views.decorators.http import require_GET

from accounts.views import gate

from .constants import Category, Level, Result
from .models import AuditEvent


PAGE_SIZE = 50
CURSOR = re.compile(r'^[1-9][0-9]{0,18}\Z')
MAX_CURSOR = 9223372036854775807
FILTERS = {
    'category': set(Category.values),
    'level': set(Level.values),
    'result': set(Result.values),
}


def _parameters(query):
    allowed = set(FILTERS) | {'before'}
    if any(key not in allowed or len(query.getlist(key)) != 1
           for key in query):
        raise ValidationError('AUDIT_INVALID_QUERY')
    values = {}
    for key, choices in FILTERS.items():
        if key in query:
            value = query[key]
            if value not in choices:
                raise ValidationError('AUDIT_INVALID_QUERY')
            values[key] = value
    before = None
    if 'before' in query:
        raw = query['before']
        if not CURSOR.fullmatch(raw):
            raise ValidationError('AUDIT_INVALID_QUERY')
        before = int(raw)
        if before > MAX_CURSOR:
            raise ValidationError('AUDIT_INVALID_QUERY')
    return values, before


def _events(filters, before):
    rows = AuditEvent.objects.filter(**filters)
    if before is not None:
        rows = rows.filter(id__lt=before)
    return list(rows.order_by('-id')[:PAGE_SIZE])


@gate(owner=True)
@require_GET
def events(request):
    try:
        filters, before = _parameters(request.GET)
    except (ValidationError, ValueError, TypeError):
        return render(request, 'accounts/error.html', status=400)

    rows = _events(filters, before)
    actor_ids = {row.actor_id for row in rows if row.actor_id is not None}
    actors = dict(get_user_model().objects.filter(pk__in=actor_ids)
                  .values_list('pk', 'username'))
    for row in rows:
        row.actor_label = actors.get(row.actor_id, str(row.actor_id or ''))

    next_url = ''
    if len(rows) == PAGE_SIZE:
        next_url = '?' + urlencode({**filters, 'before': rows[-1].id})
    return render(request, 'audit/events.html', {
        'owner': True,
        'events': rows,
        'filters': filters,
        'next_url': next_url,
        'categories': Category.choices,
        'levels': Level.choices,
        'results': Result.choices,
    })
