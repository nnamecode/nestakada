"""D-408: local test-only atomic creation; never publication or TRUST admission."""
import re
from uuid import uuid4
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from page_versions import engine as versions, schema
from page_versions.creation import initial_snapshot, initial_aggregate
from page_versions.models import IdentityReservation, OperationReceipt
from . import tree_commands as tree
from .models import Page, Route
from .validators import new_target, suggest_segment

KINDS = ('service_detail', 'article', 'service_catalog', 'service_section_overview', 'articles_catalog')
SALT = 'estakada.tree-create.v1'


def _enabled():
    if getattr(settings, 'DEV29_LOCAL_CREATE_ENABLED', False) is not True or settings.ENVIRONMENT != 'test':
        raise tree.TreeFault('CREATE_DISABLED', 503)
    tree._outside()


def _selection(pages, parent_id, kind):
    parent = tree.optional_uid(parent_id)
    if kind not in KINDS or (parent is not None and parent not in pages):
        raise tree.TreeFault('CREATE_INVALID_SELECTION', 400)
    return parent


def prepare(*, actor, generation, session_key, parent_id=None, kind='article', operation_id=None, page_id=None):
    _enabled()
    operation = tree.uid(operation_id) if operation_id is not None else uuid4()
    identifier = tree.uid(page_id) if page_id is not None else uuid4()
    if operation == identifier:
        raise tree.TreeFault('CREATE_ID_CONFLICT', 400)
    with transaction.atomic():
        tree._enter(actor, generation, session_key)
        pages = tree._pages(); parent = _selection(pages, parent_id, kind)
        payload = {'actor': actor.pk, 'generation': generation,
            'page': str(identifier), 'operation': str(operation), 'parent': str(parent) if parent else None,
            'kind': kind, 'basis': tree._basis(pages)}
        return {'token': signing.dumps(payload, salt=SALT, compress=True), 'operation_id': str(operation),
            'page_id': str(identifier), 'parent_id': str(parent) if parent else None, 'kind': kind,
            'parents': sorted(pages.values(), key=lambda page: (page.name, str(page.pk))), 'kinds': KINDS}


def preview(*, name, parent_id=None):
    """Suggestion only: no reservations, receipt, Page, or URL rewriting."""
    _enabled()
    h1 = name if type(name) is str else ''
    result = {'url': '', 'manual_required': True, 'reason': '', 'h1': h1,
        'title': h1 + ' | Автосервис «Эстакада»'}
    try:
        segment = suggest_segment(name)
        parent = tree.optional_uid(parent_id)
        base = '/'
        if parent is not None:
            if not Page.objects.filter(pk=parent).exists():
                raise ValidationError('CREATE_PARENT_UNAVAILABLE')
            base = Route.objects.filter(page_id=parent, kind=Route.Kind.PRIMARY).values_list('target', flat=True).first()
            if base is None or '?' in base:
                raise ValidationError('CREATE_PARENT_REQUIRES_MANUAL_URL')
            new_target(base)
        target = base.rstrip('/') + '/' + segment + '/'
        new_target(target)
        result.update(url=target, manual_required=False)
    except (ValidationError, tree.TreeFault) as exc:
        result['reason'] = exc.code if isinstance(exc, tree.TreeFault) else exc.messages[0]
    return result


def _ticket(token, expected):
    try:
        if type(token) is not str or len(token) > 8192:
            raise ValueError()
        payload = signing.loads(token, salt=SALT)
        if (type(payload) is not dict or set(payload) != set(expected) | {'basis'}
                or any(type(payload[key]) is not type(value) or payload[key] != value for key, value in expected.items())
                or type(payload['basis']) is not str or re.fullmatch('[a-f0-9]{64}', payload['basis']) is None):
            raise ValueError()
        return payload
    except (signing.BadSignature, ValueError, TypeError):
        raise tree.TreeFault('CREATE_INVALID_CONFIRMATION', 400) from None


def apply(*, actor, generation, session_key, token, operation_id, page_id, parent_id, kind, name, url, h1, title):
    _enabled()
    identifier, operation, parent = tree.uid(page_id), tree.uid(operation_id), tree.optional_uid(parent_id)
    if identifier == operation or kind not in KINDS:
        raise tree.TreeFault('CREATE_INVALID_SELECTION', 400)
    # All validation is exact; no trimming, silent truncation, or URL suffixing.
    schema.text(name, 200); schema.text(h1, 255); schema.text(title, 255)
    if not name.strip() or any(ord(char) == 127 for char in name + h1 + title):
        raise tree.TreeFault('CREATE_INVALID_METADATA', 400)
    new_target(url)
    snapshot = initial_snapshot(kind, h1=h1, title=title)
    with transaction.atomic():
        tree._enter(actor, generation, session_key)
        expected = {'actor': actor.pk, 'generation': generation,
            'page': str(identifier), 'operation': str(operation), 'parent': str(parent) if parent else None, 'kind': kind}
        ticket = _ticket(token, expected)
        parameters = {**ticket, 'name': name, 'url': url, 'snapshot': snapshot.data(kind)}
        fingerprint = schema.digest({'action': 'tree_create', 'parameters': parameters})
        previous = OperationReceipt.objects.filter(pk=operation).first()
        if previous is not None:
            if (previous.action != 'tree_create' or previous.actor_id != actor.pk or previous.actor_generation != generation
                    or previous.page_id != identifier or previous.result_id != identifier or previous.fingerprint != fingerprint):
                raise tree.TreeFault('CREATE_OPERATION_CONFLICT')
            return {'operation_id': str(operation), 'page_id': str(identifier), 'replayed': True, 'replay': True,
                'exists': Page.objects.filter(pk=identifier).exists(), 'result_code': previous.result_code}
        for value in (identifier, operation):
            if (IdentityReservation.objects.filter(pk=value).exists() or Page.objects.filter(pk=value).exists()
                    or Route.objects.filter(pk=value).exists()):
                raise tree.TreeFault('CREATE_ID_CONFLICT')
        pages = tree._pages()
        if ticket['basis'] != tree._basis(pages):
            raise tree.TreeFault('CREATE_BASIS_CHANGED')
        _selection(pages, parent, kind)
        if Route.objects.filter(target=url).exists():
            raise tree.TreeFault('CREATE_URL_CONFLICT')
        # full_clean includes private and scanner namespaces before the first insert.
        candidate = Route(target=url, kind=Route.Kind.PRIMARY, page_id=identifier)
        candidate.clean()
        IdentityReservation.objects.create(id=identifier, kind='tree_page')
        page = Page.objects.create(id=identifier, name=name, kind=kind, parent_id=parent, is_published=False)
        candidate.page = page; candidate.save()
        initial_aggregate(page=page, actor=actor, snapshot=snapshot)
        OperationReceipt.objects.create(id=operation, action='tree_create', actor_id=actor.pk,
            actor_generation=generation, page_id=identifier, result_id=identifier,
            fingerprint=fingerprint, result_code='created_hidden', created_at=versions.now())
        record_event(category=Category.PAGES_LINKS, event_code='TREE_CREATE', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS, actor_id=actor.pk, object_kind='page', object_ref=identifier)
        return {'operation_id': str(operation), 'page_id': str(identifier), 'replayed': False, 'replay': False,
            'exists': True, 'result_code': 'created_hidden'}
