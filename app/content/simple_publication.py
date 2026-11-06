"""Receipt-free owner publish/hide command for the light version."""
import re
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.expressions import RawSQL

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions import schema
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  PageContentState)

from .models import Page, Route
from .simple_tree_commands import _enter, _outside, _page, _uid
from .tree_commands import TreeFault

SALT = 'estakada.simple-publication.v1'
ACTIONS = {'publish': True, 'hide': False}


def _operation(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise TreeFault('PUBLICATION_INVALID_INPUT', 400) from None


def _basis(page):
    routes = list(
        Route.objects.select_for_update()
        .filter(page=page, kind=Route.Kind.PRIMARY)
        .annotate(row_version=RawSQL('"content_route"."xmin"::text', [])))
    if len(routes) != 1:
        raise TreeFault('PUBLICATION_PRIMARY_REQUIRED')
    route = routes[0]
    try:
        state = (PageContentState.objects.select_for_update()
                 .select_related('current_revision')
                 .annotate(row_version=RawSQL(
                     '"page_versions_pagecontentstate"."xmin"::text', []))
                 .get(page=page))
    except PageContentState.DoesNotExist:
        raise TreeFault('PUBLICATION_CONTENT_REQUIRED') from None
    revision = state.current_revision
    if revision.page_id != page.pk:
        raise TreeFault('PUBLICATION_CONTENT_REQUIRED')
    if schema.digest(revision.payload) != revision.payload_hash:
        raise TreeFault('PUBLICATION_CONTENT_DAMAGED', 503)
    stamp = schema.digest({
        'page': {
            'id': str(page.pk), 'row_version': str(page.row_version),
            'name': page.name, 'kind': page.kind,
            'parent': str(page.parent_id) if page.parent_id else None,
            'position': page.position, 'published': page.is_published,
        },
        'primary': {
            'id': str(route.pk), 'row_version': str(route.row_version),
            'target': route.target, 'kind': route.kind,
            'page': str(route.page_id), 'legacy': route.is_legacy,
        },
        'current': {
            'state': str(state.pk),
            'row_version': str(state.row_version),
            'revision': str(revision.pk),
            'payload_hash': revision.payload_hash,
        },
    })
    return route, revision, stamp


def _ticket(value, *, actor, generation, page_id, operation_id, action):
    try:
        if type(value) is not str or len(value) > 4096:
            raise ValueError()
        data = signing.loads(value, salt=SALT)
        if (type(data) is not dict
                or set(data) != {'actor', 'generation', 'page',
                                 'operation', 'action', 'stamp'}
                or type(data['actor']) is not int
                or type(data['generation']) is not int
                or data['actor'] != actor.pk
                or data['generation'] != generation
                or data['page'] != str(page_id)
                or data['operation'] != str(operation_id)
                or data['action'] != action
                or type(data['stamp']) is not str
                or re.fullmatch('[a-f0-9]{64}', data['stamp']) is None):
            raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError):
        raise TreeFault('PUBLICATION_INVALID_CONFIRMATION', 400) from None


def prepare(*, actor, page_id, action, generation, session_key):
    _outside()
    if action not in ACTIONS:
        raise TreeFault('PUBLICATION_INVALID_INPUT', 400)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        route, revision, stamp = _basis(page)
        operation = uuid4()
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'action': action, 'stamp': stamp,
        }
        return {
            'page': page, 'route': route, 'revision': revision,
            'action': action, 'operation_id': str(operation),
            'token': signing.dumps(data, salt=SALT, compress=True),
        }


def apply(*, actor, page_id, action, generation, session_key, token,
          operation_id):
    _outside()
    if action not in ACTIONS:
        raise TreeFault('PUBLICATION_INVALID_INPUT', 400)
    page_id, operation_id = _uid(page_id), _operation(operation_id)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        data = _ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id, action=action)
        page = _page(page_id)
        _route, _revision, stamp = _basis(page)
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(
                    pk=operation_id).exists()):
            raise TreeFault('PUBLICATION_OPERATION_CONFLICT')
        if data['stamp'] != stamp:
            raise TreeFault('PUBLICATION_BASIS_CHANGED')
        desired = ACTIONS[action]
        if page.is_published == desired:
            raise TreeFault('PUBLICATION_UNCHANGED')
        page.is_published = desired
        page.save()
        record_event(
            category=Category.PAGES_LINKS,
            event_code=('TREE_PUBLISH' if desired else 'TREE_HIDE'),
            level=Level.INFO, source=Source.APPLICATION,
            result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=page.pk)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'publication_applied',
            'parent_id': str(page.parent_id) if page.parent_id else None,
        }
