"""Closed metadata projections. Unsupported payloads stay escaped by the HTTP layer."""
from zoneinfo import ZoneInfo
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from . import engine as E
from .models import PageRevision,RevisionProtection


def timestamp(value):
    return {'utc':value.isoformat(),'moscow':timezone.localtime(value,ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'),
            'zone':'Europe/Moscow'}


def history(*,actor,page_id,expected_generation,page_number=1):
    with transaction.atomic():
        page,profile,fields,owner,state=E.enter(actor,page_id,expected_generation)
        query=PageRevision.objects.filter(page=page).defer('payload').select_related('metadata','stable_protection').order_by('-created_at','-sequence','-id')
        ordinary=query.filter(stable_protection__isnull=True).count();stable=query.filter(stable_protection__isnull=False).count()
        selected=Paginator(query,20).get_page(page_number)
        rows=[]
        for row in selected:
            protection=getattr(row,'stable_protection',None)
            rows.append({'revision':row,'metadata':row.metadata,'stable':protection is not None,'current':row.pk==state.current_revision_id,
                         'time':timestamp(row.created_at)})
        return {'page':page,'current_id':state.current_revision_id,'ordinary_count':ordinary,'stable_count':stable,
                'rows':rows,'pagination':selected,'owner':owner,'fields':fields}
