"""Small owner-only tree commands without the legacy operation ledger."""
import re
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models.expressions import RawSQL

from accounts import services as auth
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions import engine as versions, schema
from page_versions.models import IdentityReservation, OperationReceipt

from .models import Page, Route, lock_content
from .tree_commands import TreeFault

SALT = 'estakada.simple-rename.v1'
REORDER_SALT = 'estakada.simple-reorder.v1'
MOVE_SALT = 'estakada.simple-move.v1'


def _uid(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise TreeFault('TREE_INVALID_INPUT', 400) from None


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


def _page(page_id):
    return (Page.objects.select_for_update()
            .annotate(row_version=RawSQL('xmin::text', []))
            .get(pk=_uid(page_id)))


def _stamp(page):
    primary = Route.objects.filter(
        page=page, kind=Route.Kind.PRIMARY).values(
            'id', 'target', 'kind', 'page_id', 'is_legacy').first()
    if primary is not None:
        primary = {key: str(value) if key in ('id', 'page_id') else value
                   for key, value in primary.items()}
    return schema.digest({
        'row_version': str(page.row_version),
        'page': {
            'id': str(page.pk), 'name': page.name, 'kind': page.kind,
            'parent': str(page.parent_id) if page.parent_id else None,
            'position': page.position, 'published': page.is_published,
        },
        'primary': primary,
    })


def _siblings(parent_id):
    return list(Page.objects.select_for_update()
                .filter(parent_id=parent_id)
                .annotate(row_version=RawSQL('xmin::text', []))
                .order_by('position', 'id'))


def _order_stamp(siblings):
    return schema.digest([
        {
            'id': str(sibling.pk),
            'row_version': str(sibling.row_version),
            'parent': (str(sibling.parent_id)
                       if sibling.parent_id is not None else None),
            'position': sibling.position,
        }
        for sibling in siblings
    ])


def _ancestry(parent_id, moving_page_id, missing_code):
    rows = []
    seen = {moving_page_id}
    current = parent_id
    while current is not None:
        if current in seen:
            raise TreeFault(missing_code)
        seen.add(current)
        try:
            row = (Page.objects.select_for_update()
                   .annotate(row_version=RawSQL('xmin::text', []))
                   .get(pk=current))
        except Page.DoesNotExist:
            raise TreeFault(missing_code) from None
        rows.append(row)
        current = row.parent_id
    return rows


def _ancestry_stamp(rows):
    return schema.digest([
        {
            'id': str(row.pk), 'row_version': str(row.row_version),
            'parent': (str(row.parent_id)
                       if row.parent_id is not None else None),
        }
        for row in rows
    ])


def _name(value):
    if (type(value) is not str or not value.strip() or len(value) > 200
            or any(ord(character) < 32 or ord(character) == 127
                   for character in value)):
        raise TreeFault('TREE_INVALID_NAME', 400)
    try:
        value.encode('utf-8')
    except UnicodeError:
        raise TreeFault('TREE_INVALID_NAME', 400) from None
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
        raise TreeFault('TREE_INVALID_CONFIRMATION', 400) from None


def _optional_uid(value):
    return None if value is None or value == '' else _uid(value)


def _reorder_ticket(value, *, actor, generation, page_id, operation_id):
    try:
        if type(value) is not str or len(value) > 4096:
            raise ValueError()
        data = signing.loads(value, salt=REORDER_SALT)
        if (type(data) is not dict
                or set(data) != {'actor', 'generation', 'page', 'operation',
                                 'parent', 'stamp'}
                or type(data['actor']) is not int
                or type(data['generation']) is not int
                or data['actor'] != actor.pk
                or data['generation'] != generation
                or data['page'] != str(page_id)
                or data['operation'] != str(operation_id)
                or (data['parent'] is not None
                    and str(_uid(data['parent'])) != data['parent'])
                or type(data['stamp']) is not str
                or re.fullmatch('[a-f0-9]{64}', data['stamp']) is None):
            raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError, TreeFault):
        raise TreeFault('TREE_INVALID_CONFIRMATION', 400) from None


def _move_ticket(value, *, actor, generation, page_id, operation_id):
    keys = {'actor', 'generation', 'page', 'operation', 'old_parent',
            'destination', 'old_stamp', 'destination_stamp',
            'ancestry_stamp'}
    try:
        if type(value) is not str or len(value) > 6144:
            raise ValueError()
        data = signing.loads(value, salt=MOVE_SALT)
        if (type(data) is not dict or set(data) != keys
                or type(data['actor']) is not int
                or type(data['generation']) is not int
                or data['actor'] != actor.pk
                or data['generation'] != generation
                or data['page'] != str(page_id)
                or data['operation'] != str(operation_id)):
            raise ValueError()
        for key in ('old_parent', 'destination'):
            if (data[key] is not None
                    and str(_uid(data[key])) != data[key]):
                raise ValueError()
        for key in ('old_stamp', 'destination_stamp', 'ancestry_stamp'):
            if (type(data[key]) is not str
                    or re.fullmatch('[a-f0-9]{64}', data[key]) is None):
                raise ValueError()
        return data
    except (signing.BadSignature, ValueError, TypeError, TreeFault):
        raise TreeFault('TREE_INVALID_CONFIRMATION', 400) from None


def prepare_rename(*, actor, page_id, generation, session_key):
    _outside()
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        operation = uuid4()
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'stamp': _stamp(page),
        }
        return {
            'page': page, 'action': 'rename',
            'token': signing.dumps(data, salt=SALT, compress=True),
            'operation_id': str(operation), 'destination': '',
            'parent_choices': [], 'before_choices': [],
            'parent_name': (Page.objects.filter(pk=page.parent_id)
                            .values_list('name', flat=True).first()
                            if page.parent_id else 'Верхний уровень'),
            'primary_target': Route.objects.filter(
                page=page, kind=Route.Kind.PRIMARY).values_list(
                    'target', flat=True).first(),
        }


def prepare_reorder(*, actor, page_id, generation, session_key):
    _outside()
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        siblings = _siblings(page.parent_id)
        operation = uuid4()
        parent = str(page.parent_id) if page.parent_id is not None else None
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'parent': parent, 'stamp': _order_stamp(siblings),
        }
        return {
            'page': page, 'action': 'reorder',
            'token': signing.dumps(data, salt=REORDER_SALT, compress=True),
            'operation_id': str(operation), 'destination': parent or '',
            'parent_choices': [],
            'before_choices': [sibling for sibling in siblings
                               if sibling.pk != page.pk],
            'parent_name': (Page.objects.filter(pk=page.parent_id)
                            .values_list('name', flat=True).first()
                            if page.parent_id else 'Верхний уровень'),
            'primary_target': Route.objects.filter(
                page=page, kind=Route.Kind.PRIMARY).values_list(
                    'target', flat=True).first(),
        }


def prepare_move(*, actor, page_id, generation, session_key,
                 destination='current'):
    _outside()
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        target = (page.parent_id if destination == 'current'
                  else _optional_uid(destination))
        ancestry = _ancestry(target, page.pk, 'TREE_PARENT_CONFLICT')
        old_siblings = _siblings(page.parent_id)
        destination_siblings = (old_siblings if target == page.parent_id
                                else _siblings(target))
        operation = uuid4()
        old_parent = (str(page.parent_id)
                      if page.parent_id is not None else None)
        target_text = str(target) if target is not None else None
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'old_parent': old_parent, 'destination': target_text,
            'old_stamp': _order_stamp(old_siblings),
            'destination_stamp': _order_stamp(destination_siblings),
            'ancestry_stamp': _ancestry_stamp(ancestry),
        }
        all_pages = {row.pk: row for row in Page.objects.order_by('id')}
        choices = []
        for candidate in all_pages.values():
            seen = {page.pk}
            current = candidate.pk
            while current is not None and current not in seen:
                seen.add(current)
                current = (all_pages[current].parent_id
                           if current in all_pages else page.pk)
            if current is None:
                choices.append(candidate)
        choices.sort(key=lambda row: (row.name, str(row.pk)))
        return {
            'page': page, 'action': 'move',
            'token': signing.dumps(data, salt=MOVE_SALT, compress=True),
            'operation_id': str(operation),
            'destination': target_text or '',
            'parent_choices': choices,
            'before_choices': [row for row in destination_siblings
                               if row.pk != page.pk],
            'parent_name': (Page.objects.filter(pk=page.parent_id)
                            .values_list('name', flat=True).first()
                            if page.parent_id else 'Верхний уровень'),
            'primary_target': Route.objects.filter(
                page=page, kind=Route.Kind.PRIMARY).values_list(
                    'target', flat=True).first(),
        }


def rename(*, actor, page_id, generation, session_key, token,
           operation_id, name):
    _outside()
    page_id, operation_id = _uid(page_id), _uid(operation_id)
    name = _name(name)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        data = _ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id)
        page = _page(page_id)
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(pk=operation_id).exists()):
            raise TreeFault('TREE_OPERATION_CONFLICT')
        if data['stamp'] != _stamp(page):
            raise TreeFault('TREE_BASIS_CHANGED')
        if name == page.name:
            raise TreeFault('TREE_NAME_UNCHANGED')
        page.name = name
        page.save()
        record_event(
            category=Category.PAGES_LINKS, event_code='TREE_RENAME',
            level=Level.INFO, source=Source.APPLICATION,
            result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=page.pk)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'tree_applied',
            'parent_id': str(page.parent_id) if page.parent_id else None,
        }


def reorder(*, actor, page_id, generation, session_key, token,
            operation_id, parent_id, before_id):
    _outside()
    page_id, operation_id = _uid(page_id), _uid(operation_id)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        data = _reorder_ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id)
        parent_id, before_id = (_optional_uid(parent_id),
                                _optional_uid(before_id))
        expected_parent = _optional_uid(data['parent'])
        if parent_id != expected_parent:
            raise TreeFault('TREE_DESTINATION_CHANGED', 400)
        page = _page(page_id)
        if page.parent_id != expected_parent:
            raise TreeFault('TREE_BASIS_CHANGED')
        siblings = _siblings(expected_parent)
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(pk=operation_id).exists()):
            raise TreeFault('TREE_OPERATION_CONFLICT')
        if data['stamp'] != _order_stamp(siblings):
            raise TreeFault('TREE_BASIS_CHANGED')
        by_id = {sibling.pk: sibling for sibling in siblings}
        if page_id not in by_id:
            raise TreeFault('TREE_BASIS_CHANGED')
        if (before_id == page_id
                or (before_id is not None and before_id not in by_id)):
            raise TreeFault('TREE_NEIGHBOUR_CONFLICT')
        ordered = [sibling for sibling in siblings
                   if sibling.pk != page_id]
        at = next((index for index, sibling in enumerate(ordered)
                   if sibling.pk == before_id), len(ordered))
        ordered.insert(at, by_id[page_id])
        changes = [(sibling, position)
                   for position, sibling in enumerate(ordered)
                   if sibling.position != position]
        if not changes:
            raise TreeFault('TREE_ORDER_UNCHANGED')
        for sibling, position in changes:
            sibling.position = position
            sibling.save()
        record_event(
            category=Category.PAGES_LINKS, event_code='TREE_REORDER',
            level=Level.INFO, source=Source.APPLICATION,
            result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=page.pk)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'tree_applied',
            'parent_id': (str(page.parent_id)
                          if page.parent_id is not None else None),
        }


def move(*, actor, page_id, generation, session_key, token,
         operation_id, parent_id, before_id):
    _outside()
    page_id, operation_id = _uid(page_id), _uid(operation_id)
    with transaction.atomic():
        _enter(actor, generation, session_key)
        data = _move_ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id)
        parent_id, before_id = (_optional_uid(parent_id),
                                _optional_uid(before_id))
        expected_old = _optional_uid(data['old_parent'])
        expected_destination = _optional_uid(data['destination'])
        if parent_id != expected_destination:
            raise TreeFault('TREE_DESTINATION_CHANGED', 400)
        page = _page(page_id)
        if page.parent_id != expected_old:
            raise TreeFault('TREE_BASIS_CHANGED')
        ancestry = _ancestry(
            expected_destination, page_id, 'TREE_BASIS_CHANGED')
        old_siblings = _siblings(expected_old)
        destination_siblings = (
            old_siblings if expected_destination == expected_old
            else _siblings(expected_destination))
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(pk=operation_id).exists()):
            raise TreeFault('TREE_OPERATION_CONFLICT')
        if (data['old_stamp'] != _order_stamp(old_siblings)
                or data['destination_stamp'] != _order_stamp(
                    destination_siblings)
                or data['ancestry_stamp'] != _ancestry_stamp(ancestry)):
            raise TreeFault('TREE_BASIS_CHANGED')
        old_by_id = {row.pk: row for row in old_siblings}
        destination_by_id = {row.pk: row for row in destination_siblings}
        if page_id not in old_by_id:
            raise TreeFault('TREE_BASIS_CHANGED')
        if (before_id == page_id
                or (before_id is not None
                    and before_id not in destination_by_id)):
            raise TreeFault('TREE_NEIGHBOUR_CONFLICT')

        changes = {}
        if expected_destination == expected_old:
            destination_order = [row for row in old_siblings
                                 if row.pk != page_id]
        else:
            old_order = [row for row in old_siblings if row.pk != page_id]
            for position, row in enumerate(old_order):
                changes[row.pk] = (row, expected_old, position)
            destination_order = list(destination_siblings)
        at = next((index for index, row in enumerate(destination_order)
                   if row.pk == before_id), len(destination_order))
        moving = old_by_id[page_id]
        destination_order.insert(at, moving)
        for position, row in enumerate(destination_order):
            changes[row.pk] = (row, expected_destination, position)
        changed = [entry for entry in changes.values()
                   if (entry[0].parent_id != entry[1]
                       or entry[0].position != entry[2])]
        if not changed:
            raise TreeFault('TREE_ORDER_UNCHANGED')
        for row, parent, position in sorted(
                changed, key=lambda entry: str(entry[0].pk)):
            row.parent_id, row.position = parent, position
            row.save()
        record_event(
            category=Category.PAGES_LINKS, event_code='TREE_MOVE',
            level=Level.INFO, source=Source.APPLICATION,
            result=Result.SUCCESS, actor_id=actor.pk,
            object_kind='page', object_ref=page.pk)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'tree_applied',
            'parent_id': (str(expected_destination)
                          if expected_destination is not None else None),
        }
