"""D-405: owner structural commands, existing immutable receipts, no TRUST IO."""
import re
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from accounts import services as auth
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions import engine as versions, schema
from page_versions.models import OperationReceipt, IdentityReservation, PageContentState
from .models import Page, Route, lock_content

ACTIONS = ('rename', 'move', 'reorder')
RECEIPT_ACTIONS = tuple('tree_' + action for action in ACTIONS) + ('tree_create',)
SALT = 'estakada.tree-command.v1'


class TreeFault(Exception):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


def uid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise TreeFault('TREE_INVALID_INPUT', 400) from None


def optional_uid(value):
    return None if value is None or value == '' else uid(value)


def _outside():
    if connection.in_atomic_block:
        raise TreeFault('TREE_AUTOCOMMIT_REQUIRED', 503)


def _enter(actor, generation, session_key):
    lock_content('default')
    auth.lock_auth()
    if type(generation) is not int or generation <= 0:
        raise PermissionDenied('AUTH_CURRENT_IDENTITY_REQUIRED')
    profile = auth._owner(actor, generation)
    try:
        versions.check_editor_session(profile.user, generation, session_key)
    except ValidationError:
        raise TreeFault('TREE_SESSION_ENDED', 401) from None
    return profile


def _pages():
    return {page.pk: page for page in Page.objects.select_for_update().order_by('id')}


def _page(pages, identifier):
    page = pages.get(uid(identifier))
    if page is None:
        raise Page.DoesNotExist()
    return page


def _basis(pages):
    rows = [{'id': str(p.pk), 'name': p.name, 'kind': p.kind,
             'parent': str(p.parent_id) if p.parent_id else None,
             'position': p.position, 'published': p.is_published} for p in pages.values()]
    routes = [{**row, 'id': str(row['id']), 'page_id': str(row['page_id']) if row['page_id'] else None}
              for row in Route.objects.order_by('id').values('id', 'target', 'kind', 'page_id', 'is_legacy')]
    current = [{'page': str(row.page_id), 'current': str(row.current_revision_id)}
               for row in PageContentState.objects.order_by('page_id')]
    return schema.digest({'pages': rows, 'routes': routes, 'current': current,
                          'commands': OperationReceipt.objects.filter(action__in=RECEIPT_ACTIONS).count()})


def _parent(pages, page, destination):
    seen = {page.pk}
    current = destination
    while current is not None:
        if current in seen or current not in pages:
            raise TreeFault('TREE_PARENT_CONFLICT')
        seen.add(current)
        current = pages[current].parent_id


def prepare(*, actor, page_id, action, generation, session_key, destination='current'):
    _outside()
    if action not in ACTIONS:
        raise TreeFault('TREE_INVALID_INPUT', 400)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        pages = _pages()
        page = _page(pages, page_id)
        target = None if action == 'rename' else page.parent_id
        if action == 'move' and destination != 'current':
            target = optional_uid(destination)
        if action != 'rename':
            _parent(pages, page, target)
        operation = str(uuid4())
        payload = {'actor': actor.pk, 'generation': generation, 'action': action,
                   'page': str(page.pk), 'basis': _basis(pages), 'operation': operation,
                   'destination': str(target) if target else None}
        choices = []
        for candidate in pages.values():
            try:
                _parent(pages, page, candidate.pk)
            except TreeFault:
                continue
            choices.append(candidate)
        choices.sort(key=lambda p: (p.name, str(p.pk)))
        siblings = sorted((p for p in pages.values() if p.parent_id == target and p.pk != page.pk),
                          key=lambda p: (p.position, str(p.pk)))
        return {'page': page, 'action': action, 'token': signing.dumps(payload, salt=SALT, compress=True),
                'operation_id': operation, 'destination': str(target) if target else '',
                'parent_choices': choices, 'before_choices': siblings,
                'parent_name': pages[page.parent_id].name if page.parent_id else 'Верхний уровень',
                'primary_target': Route.objects.filter(page=page, kind=Route.Kind.PRIMARY).values_list('target', flat=True).first()}


def _ticket(value, *, actor, generation, action, page_id, operation_id):
    try:
        if type(value) is not str or len(value) > 8192:
            raise ValueError()
        data = signing.loads(value, salt=SALT)
        if (type(data) is not dict or set(data) != {'actor', 'generation', 'action', 'page', 'basis', 'operation', 'destination'}
                or type(data['actor']) is not int or type(data['generation']) is not int
                or data['actor'] != actor.pk or data['generation'] != generation
                or data['action'] != action or data['page'] != str(page_id)
                or data['operation'] != str(operation_id) or type(data['basis']) is not str
                or re.fullmatch('[a-f0-9]{64}', data['basis']) is None
                or (data['destination'] is not None and str(uid(data['destination'])) != data['destination'])):
            raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError, TreeFault):
        raise TreeFault('TREE_INVALID_CONFIRMATION', 400) from None


def _parameters(action, name, parent_id, before_id, ticket):
    if action == 'rename':
        if (type(name) is not str or not name.strip() or len(name) > 200
                or any(ord(c) < 32 or ord(c) == 127 for c in name)
                or parent_id not in (None, '') or before_id not in (None, '') or ticket['destination'] is not None):
            raise TreeFault('TREE_INVALID_NAME', 400)
        try:
            name.encode('utf-8')
        except UnicodeError:
            raise TreeFault('TREE_INVALID_NAME', 400) from None
        return {'basis': ticket['basis'], 'name': name, 'parent': None, 'before': None}
    if name is not None:
        raise TreeFault('TREE_INVALID_INPUT', 400)
    parent, before = optional_uid(parent_id), optional_uid(before_id)
    if (str(parent) if parent else None) != ticket['destination']:
        raise TreeFault('TREE_DESTINATION_CHANGED', 400)
    return {'basis': ticket['basis'], 'name': None,
            'parent': str(parent) if parent else None, 'before': str(before) if before else None}


def _place(pages, page, parent, before):
    _parent(pages, page, parent)
    if before == page.pk or (before is not None and (before not in pages or pages[before].parent_id != parent)):
        raise TreeFault('TREE_NEIGHBOUR_CONFLICT')
    old_parent = page.parent_id
    destination = sorted((p for p in pages.values() if p.parent_id == parent and p.pk != page.pk),
                         key=lambda p: (p.position, str(p.pk)))
    at = next((index for index, sibling in enumerate(destination) if sibling.pk == before), len(destination))
    destination.insert(at, page)
    changes = {}
    if old_parent != parent:
        old = sorted((p for p in pages.values() if p.parent_id == old_parent and p.pk != page.pk),
                     key=lambda p: (p.position, str(p.pk)))
        for position, sibling in enumerate(old):
            changes[sibling.pk] = (old_parent, position)
    for position, sibling in enumerate(destination):
        changes[sibling.pk] = (parent, position)
    for identifier in sorted(changes, key=str):
        sibling = pages[identifier]
        new_parent, position = changes[identifier]
        if sibling.parent_id != new_parent or sibling.position != position:
            sibling.parent_id, sibling.position = new_parent, position
            sibling.save()


def apply(*, actor, page_id, action, generation, session_key, token, operation_id,
          name=None, parent_id=None, before_id=None):
    _outside()
    if action not in ACTIONS:
        raise TreeFault('TREE_INVALID_INPUT', 400)
    page_id, operation_id = uid(page_id), uid(operation_id)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        pages = _pages()
        page = _page(pages, page_id)
        ticket = _ticket(token, actor=actor, generation=generation, action=action,
                         page_id=page_id, operation_id=operation_id)
        parameters = _parameters(action, name, parent_id, before_id, ticket)
        receipt_action = 'tree_' + action
        fingerprint = versions.fingerprint(receipt_action, actor, page, generation, parameters)
        previous = OperationReceipt.objects.filter(pk=operation_id).first()
        if previous is not None:
            if (previous.action != receipt_action or previous.actor_id != actor.pk
                    or previous.actor_generation != generation or previous.page_id != page.pk
                    or previous.fingerprint != fingerprint):
                raise TreeFault('TREE_OPERATION_CONFLICT')
            return {'operation_id': str(operation_id), 'replay': True, 'result_code': previous.result_code,
                    'parent_id': str(page.parent_id) if page.parent_id else None}
        if IdentityReservation.objects.filter(pk=operation_id).exists():
            raise TreeFault('TREE_OPERATION_CONFLICT')
        if ticket['basis'] != _basis(pages):
            raise TreeFault('TREE_BASIS_CHANGED')
        if action == 'rename':
            page.name = parameters['name']
            page.save()
        else:
            parent, before = optional_uid(parameters['parent']), optional_uid(parameters['before'])
            if action == 'reorder' and parent != page.parent_id:
                raise TreeFault('TREE_PARENT_CONFLICT')
            _place(pages, page, parent, before)
        OperationReceipt.objects.create(id=operation_id, action=receipt_action, actor_id=actor.pk,
            actor_generation=generation, page_id=page.pk, fingerprint=fingerprint,
            result_code='tree_applied', result_id=None, created_at=versions.now())
        record_event(category=Category.PAGES_LINKS, event_code='TREE_' + action.upper(), level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=page.pk)
        return {'operation_id': str(operation_id), 'replay': False, 'result_code': 'tree_applied',
                'parent_id': str(page.parent_id) if page.parent_id else None}
