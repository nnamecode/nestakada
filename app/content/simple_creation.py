"""Owner-only local page creation without the legacy tree operation ledger."""
import re
from uuid import uuid4

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction

from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from page_versions import schema
from page_versions.creation import initial_aggregate, initial_snapshot
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  PageContentState, PageRevision)

from .models import Page, Route
from .tree_commands import TreeFault
from .validators import new_target
from . import simple_tree_commands as tree

KINDS = ('service_detail', 'article', 'service_catalog',
         'service_section_overview', 'articles_catalog')
SALT = 'estakada.simple-create.v1'


def _enabled():
    if (getattr(settings, 'DEV29_LOCAL_CREATE_ENABLED', False) is not True
            or settings.ENVIRONMENT != 'test'):
        raise TreeFault('CREATE_DISABLED', 503)
    tree._outside()


def _selection(parent_id, kind):
    if kind not in KINDS:
        raise TreeFault('CREATE_INVALID_SELECTION', 400)
    return tree._optional_uid(parent_id)


def _parent_stamp(parent):
    return schema.digest(None if parent is None else {
        'id': str(parent.pk), 'row_version': str(parent.row_version),
        'name': parent.name, 'kind': parent.kind,
        'parent': (str(parent.parent_id)
                   if parent.parent_id is not None else None),
        'published': parent.is_published,
        'primary': Route.objects.filter(
            page=parent, kind=Route.Kind.PRIMARY).values_list(
                'target', flat=True).first(),
    })


def _ticket(value, *, actor, generation, page_id, operation_id,
            parent_id, kind):
    try:
        if type(value) is not str or len(value) > 4096:
            raise ValueError()
        data = signing.loads(value, salt=SALT)
        if (type(data) is not dict
                or set(data) != {'actor', 'generation', 'page', 'operation',
                                 'parent', 'kind', 'parent_stamp',
                                 'siblings_stamp'}
                or type(data['actor']) is not int
                or type(data['generation']) is not int
                or data['actor'] != actor.pk
                or data['generation'] != generation
                or data['page'] != str(page_id)
                or data['operation'] != str(operation_id)
                or data['parent'] != (str(parent_id)
                                      if parent_id is not None else None)
                or data['kind'] != kind
                or type(data['parent_stamp']) is not str
                or type(data['siblings_stamp']) is not str
                or re.fullmatch('[a-f0-9]{64}',
                                data['parent_stamp']) is None
                or re.fullmatch('[a-f0-9]{64}',
                                data['siblings_stamp']) is None):
            raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError):
        raise TreeFault('CREATE_INVALID_CONFIRMATION', 400) from None


def prepare(*, actor, generation, session_key, parent_id=None,
            kind='article', operation_id=None, page_id=None):
    _enabled()
    operation = (tree._uid(operation_id)
                 if operation_id is not None else uuid4())
    identifier = tree._uid(page_id) if page_id is not None else uuid4()
    if operation == identifier:
        raise TreeFault('CREATE_ID_CONFLICT', 400)
    with transaction.atomic():
        tree._enter(actor, generation, session_key)
        parent_id = _selection(parent_id, kind)
        parent = tree._page(parent_id) if parent_id is not None else None
        siblings = tree._siblings(parent_id)
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(identifier), 'operation': str(operation),
            'parent': str(parent_id) if parent_id is not None else None,
            'kind': kind, 'parent_stamp': _parent_stamp(parent),
            'siblings_stamp': tree._order_stamp(siblings),
        }
        return {
            'token': signing.dumps(data, salt=SALT, compress=True),
            'operation_id': str(operation), 'page_id': str(identifier),
            'parent_id': (str(parent_id)
                          if parent_id is not None else None),
            'kind': kind,
            'parents': list(Page.objects.order_by('name', 'id')),
            'kinds': KINDS,
        }


def _metadata(name, h1, title, url, kind):
    schema.text(name, 200)
    schema.text(h1, 255)
    schema.text(title, 255)
    if (not name.strip()
            or any(ord(character) == 127
                   for character in name + h1 + title)):
        raise TreeFault('CREATE_INVALID_METADATA', 400)
    new_target(url)
    return initial_snapshot(kind, h1=h1, title=title)


def _is_exact_result(*, page, name, kind, parent_id, url, snapshot):
    if (page.name != name or page.kind != kind
            or page.parent_id != parent_id or page.is_published):
        return False
    if Route.objects.filter(
            page=page, kind=Route.Kind.PRIMARY, target=url).count() != 1:
        return False
    payload = snapshot.data(kind)
    revision = PageRevision.objects.filter(
        page=page, kind=PageRevision.Kind.INITIAL, sequence=1,
        payload=payload, payload_hash=schema.digest(payload)).first()
    if revision is None:
        return False
    if not PageContentState.objects.filter(page=page).exists():
        return False
    return AuditEvent.objects.filter(
        code='TREE_CREATE', object_ref='uuid:' + str(page.pk)).exists()


def apply(*, actor, generation, session_key, token, operation_id, page_id,
          parent_id, kind, name, url, h1, title):
    _enabled()
    identifier, operation = tree._uid(page_id), tree._uid(operation_id)
    if identifier == operation:
        raise TreeFault('CREATE_ID_CONFLICT', 400)
    with transaction.atomic():
        tree._enter(actor, generation, session_key)
        parent_id = _selection(parent_id, kind)
        data = _ticket(
            token, actor=actor, generation=generation,
            page_id=identifier, operation_id=operation,
            parent_id=parent_id, kind=kind)
        snapshot = _metadata(name, h1, title, url, kind)
        if (OperationReceipt.objects.filter(pk=operation).exists()
                or IdentityReservation.objects.filter(pk=operation).exists()):
            raise TreeFault('CREATE_OPERATION_CONFLICT')

        existing = Page.objects.select_for_update().filter(
            pk=identifier).first()
        if existing is not None:
            if not _is_exact_result(
                    page=existing, name=name, kind=kind,
                    parent_id=parent_id, url=url, snapshot=snapshot):
                raise TreeFault('CREATE_ID_CONFLICT')
            return {
                'operation_id': str(operation),
                'page_id': str(identifier), 'replayed': True,
                'replay': True, 'exists': True,
                'result_code': 'created_hidden',
            }
        if (IdentityReservation.objects.filter(pk=identifier).exists()
                or Route.objects.filter(pk=identifier).exists()):
            raise TreeFault('CREATE_ID_CONFLICT')

        parent = tree._page(parent_id) if parent_id is not None else None
        siblings = tree._siblings(parent_id)
        if (data['parent_stamp'] != _parent_stamp(parent)
                or data['siblings_stamp'] != tree._order_stamp(siblings)):
            raise TreeFault('CREATE_BASIS_CHANGED')
        if Route.objects.filter(target=url).exists():
            raise TreeFault('CREATE_URL_CONFLICT')
        candidate = Route(
            target=url, kind=Route.Kind.PRIMARY, page_id=identifier)
        candidate.clean()
        page = Page.objects.create(
            id=identifier, name=name, kind=kind,
            parent_id=parent_id, is_published=False)
        candidate.page = page
        candidate.save()
        initial_aggregate(page=page, actor=actor, snapshot=snapshot)
        record_event(
            category=Category.PAGES_LINKS, event_code='TREE_CREATE',
            level=Level.INFO, source=Source.APPLICATION,
            result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=identifier)
        return {
            'operation_id': str(operation), 'page_id': str(identifier),
            'replayed': False, 'replay': False, 'exists': True,
            'result_code': 'created_hidden',
        }
