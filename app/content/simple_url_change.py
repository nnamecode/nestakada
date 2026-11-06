"""Receipt-free owner URL change for non-legacy pages."""
import re
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.expressions import RawSQL

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions import schema
from page_versions.models import IdentityReservation, OperationReceipt

from .models import Route
from .simple_tree_commands import _enter, _outside, _page, _uid
from .tree_commands import TreeFault

SALT = 'estakada.simple-url-change.v1'


def _operation(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise TreeFault('URL_CHANGE_INVALID_INPUT', 400) from None


def _primary(page):
    routes = list(
        Route.objects.select_for_update()
        .filter(page=page, kind=Route.Kind.PRIMARY)
        .annotate(row_version=RawSQL('"content_route"."xmin"::text', [])))
    if len(routes) != 1:
        raise TreeFault('URL_CHANGE_PRIMARY_REQUIRED')
    route = routes[0]
    if route.is_legacy:
        raise TreeFault('URL_CHANGE_LEGACY_PROTECTED', 403)
    return route


def _stamp(page, route):
    return schema.digest({
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
    })


def _target(value, page):
    if type(value) is not str:
        raise TreeFault('URL_CHANGE_INVALID_TARGET', 400)
    try:
        Route(target=value, kind=Route.Kind.PRIMARY,
              page=page, is_legacy=False).clean()
    except ValidationError:
        raise TreeFault('URL_CHANGE_INVALID_TARGET', 400) from None
    return value


def _ticket(value, *, actor, generation, page_id, operation_id):
    try:
        if type(value) is not str or len(value) > 4096:
            raise ValueError()
        data = signing.loads(value, salt=SALT)
        if (type(data) is not dict
                or set(data) != {'actor', 'generation', 'page',
                                 'operation', 'stamp'}
                or type(data['actor']) is not int
                or type(data['generation']) is not int
                or data['actor'] != actor.pk
                or data['generation'] != generation
                or data['page'] != str(page_id)
                or data['operation'] != str(operation_id)
                or type(data['stamp']) is not str
                or re.fullmatch('[a-f0-9]{64}', data['stamp']) is None):
            raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError):
        raise TreeFault('URL_CHANGE_INVALID_CONFIRMATION', 400) from None


def prepare(*, actor, page_id, generation, session_key):
    _outside()
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        route = _primary(page)
        operation = uuid4()
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'stamp': _stamp(page, route),
        }
        return {
            'page': page, 'route': route,
            'operation_id': str(operation),
            'token': signing.dumps(data, salt=SALT, compress=True),
        }


def apply(*, actor, page_id, generation, session_key, token,
          operation_id, target):
    _outside()
    page_id, operation_id = _uid(page_id), _operation(operation_id)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        data = _ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id)
        page = _page(page_id)
        primary = _primary(page)
        target = _target(target, page)
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(
                    pk=operation_id).exists()):
            raise TreeFault('URL_CHANGE_OPERATION_CONFLICT')
        if data['stamp'] != _stamp(page, primary):
            raise TreeFault('URL_CHANGE_BASIS_CHANGED')
        if target == primary.target:
            raise TreeFault('URL_CHANGE_UNCHANGED')
        if Route.objects.select_for_update().filter(target=target).exists():
            raise TreeFault('URL_CHANGE_TARGET_CONFLICT')
        old_target = primary.target
        primary.target = target
        primary.save()
        redirect = Route.objects.create(
            target=old_target, kind=Route.Kind.REDIRECT,
            page=page, is_legacy=False)
        record_event(
            category=Category.PAGES_LINKS,
            event_code='TREE_URL_CHANGE', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=actor.pk, object_kind='page', object_ref=page.pk)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'url_changed',
            'old_target': old_target, 'target': target,
            'redirect_id': str(redirect.pk),
            'parent_id': str(page.parent_id) if page.parent_id else None,
        }
