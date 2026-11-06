"""Confirmed owner deletion of one leaf Page and its complete history."""
import re
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.db.models import Q
from django.db.models.expressions import RawSQL

from accounts.models import PageGrant
from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from audit.services import record_event
from media_library.models import AssetUsage, PageMediaHome
from page_versions import engine, schema
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  OwnerDraft, PageContentState,
                                  PageRevision, RestoreStage,
                                  RevisionMetadata, RevisionProtection,
                                  VersionBasePin)

from .models import Page, Route
from .simple_tree_commands import _enter, _outside, _page, _uid
from .tree_commands import TreeFault

SALT = 'estakada.simple-page-delete.v1'


def _raw(model):
    return models.QuerySet(model=model, using='default')


def _operation(value):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise TreeFault('PAGE_DELETE_INVALID_INPUT', 400) from None


def _rv(queryset, table):
    return queryset.annotate(
        row_version=RawSQL(f'"{table}"."xmin"::text', []))


def _scope(page):
    children = list(_rv(
        Page.objects.select_for_update().filter(parent=page).order_by('id'),
        'content_page'))
    if children:
        raise TreeFault('PAGE_DELETE_HAS_CHILDREN')
    routes = list(_rv(
        Route.objects.select_for_update().filter(page=page).order_by('id'),
        'content_route'))
    primaries = [row for row in routes if row.kind == Route.Kind.PRIMARY]
    if len(primaries) != 1:
        raise TreeFault('PAGE_DELETE_PRIMARY_REQUIRED')
    try:
        state = _rv(
            PageContentState.objects.select_for_update().filter(page=page),
            'page_versions_pagecontentstate').get()
    except PageContentState.DoesNotExist:
        raise TreeFault('PAGE_DELETE_HISTORY_REQUIRED') from None
    revisions = list(PageRevision.objects.select_for_update().filter(
        page=page).order_by('id'))
    if not revisions or state.current_revision_id not in {
            row.pk for row in revisions}:
        raise TreeFault('PAGE_DELETE_HISTORY_REQUIRED')
    revision_ids = [row.pk for row in revisions]
    metadata = list(RevisionMetadata.objects.select_for_update().filter(
        revision_id__in=revision_ids).order_by('id'))
    stable = list(RevisionProtection.objects.select_for_update().filter(
        revision_id__in=revision_ids).order_by('id'))
    drafts = list(_rv(
        OwnerDraft.objects.select_for_update().filter(page=page).order_by('id'),
        'page_versions_ownerdraft'))
    stages = list(_rv(
        RestoreStage.objects.select_for_update().filter(page=page).order_by('id'),
        'page_versions_restorestage'))
    pins = list(VersionBasePin.objects.select_for_update().filter(
        revision_id__in=revision_ids).order_by('id'))
    grants = list(_rv(
        PageGrant.objects.select_for_update().filter(page=page).order_by('id'),
        'accounts_pagegrant'))
    homes = list(PageMediaHome.objects.select_for_update().filter(
        page=page).order_by('id'))
    draft_ids = [row.pk for row in drafts]
    usages = list(AssetUsage.objects.select_for_update().filter(
        Q(kind=AssetUsage.Kind.CURRENT_PAGE, consumer_id=page.pk)
        | Q(kind__in=(AssetUsage.Kind.ORDINARY_VERSION,
                     AssetUsage.Kind.STABLE_VERSION),
            consumer_id__in=revision_ids)
        | Q(kind=AssetUsage.Kind.DRAFT,
            consumer_id__in=draft_ids)).order_by('id'))
    stamp = schema.digest({
        'page': {
            'id': str(page.pk), 'row_version': str(page.row_version),
            'name': page.name, 'kind': page.kind,
            'parent': str(page.parent_id) if page.parent_id else None,
            'position': page.position, 'published': page.is_published,
        },
        'children': [],
        'routes': [{
            'id': str(row.pk), 'row_version': str(row.row_version),
            'target': row.target, 'kind': row.kind,
            'legacy': row.is_legacy,
        } for row in routes],
        'state': {
            'id': str(state.pk), 'row_version': str(state.row_version),
            'current': str(state.current_revision_id),
            'sequence': state.sequence,
        },
        'revisions': [{
            'id': str(row.pk), 'sequence': row.sequence,
            'hash': row.payload_hash, 'kind': row.kind,
        } for row in revisions],
        'metadata': [{
            'id': str(row.pk), 'revision': str(row.revision_id),
            'generation': row.generation,
        } for row in metadata],
        'stable': [{
            'id': str(row.pk), 'revision': str(row.revision_id),
        } for row in stable],
        'drafts': [{
            'id': str(row.pk), 'row_version': str(row.row_version),
            'revision': row.revision, 'base': str(row.base_revision_id),
            'hash': row.payload_hash,
        } for row in drafts],
        'stages': [{
            'id': str(row.pk), 'row_version': str(row.row_version),
            'status': row.status, 'source': str(row.source_revision_id),
            'base': str(row.base_revision_id), 'holder': row.holder_kind,
        } for row in stages],
        'pins': [{
            'id': str(row.pk), 'revision': str(row.revision_id),
            'holder_kind': row.holder_kind,
            'holder_id': str(row.holder_id),
        } for row in pins],
        'grants': [{
            'id': row.pk, 'user': row.user_id,
            'intro': row.intro_text, 'main': row.main_text,
            'price': row.price,
        } for row in grants],
        'homes': [{
            'id': str(row.pk), 'folder': str(row.folder_id),
        } for row in homes],
        'usages': [{
            'id': str(row.pk), 'kind': row.kind,
            'consumer': str(row.consumer_id),
            'asset': str(row.asset_id), 'slot': row.slot,
        } for row in usages],
    })
    return {
        'primary': primaries[0], 'routes': routes, 'state': state,
        'revisions': revisions, 'metadata': metadata, 'stable': stable,
        'drafts': drafts, 'stages': stages, 'pins': pins,
        'grants': grants, 'homes': homes, 'usages': usages,
        'stamp': stamp,
    }


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
        raise TreeFault('PAGE_DELETE_INVALID_CONFIRMATION', 400) from None


def prepare(*, actor, page_id, generation, session_key):
    _outside()
    with transaction.atomic():
        _enter(actor, generation, session_key)
        page = _page(page_id)
        scope = _scope(page)
        operation = uuid4()
        data = {
            'actor': actor.pk, 'generation': generation,
            'page': str(page.pk), 'operation': str(operation),
            'stamp': scope['stamp'],
        }
        return {
            'page': page, 'primary': scope['primary'],
            'operation_id': str(operation),
            'token': signing.dumps(data, salt=SALT, compress=True),
            'counts': {
                'routes': len(scope['routes']),
                'revisions': len(scope['revisions']),
                'stable': len(scope['stable']),
                'drafts': len(scope['drafts']),
                'stages': len(scope['stages']),
            },
        }


def _password(actor, supplied):
    user = get_user_model().objects.get(pk=actor.pk)
    if (type(supplied) is not str or not 0 < len(supplied) <= 4096
            or not check_password(supplied, user.password)):
        raise PermissionDenied('PAGE_DELETE_CURRENT_PASSWORD_REQUIRED')
    return user.password


def apply(*, actor, page_id, generation, session_key, token,
          operation_id, confirm_name, confirm_url, password):
    _outside()
    page_id, operation_id = _uid(page_id), _operation(operation_id)
    verified_hash = _password(actor, password)
    with transaction.atomic():
        profile = _enter(actor, generation, session_key)
        if profile.user.password != verified_hash:
            raise PermissionDenied('PAGE_DELETE_CURRENT_PASSWORD_CHANGED')
        data = _ticket(
            token, actor=actor, generation=generation, page_id=page_id,
            operation_id=operation_id)
        if (OperationReceipt.objects.filter(pk=operation_id).exists()
                or IdentityReservation.objects.filter(
                    pk=operation_id).exists()):
            raise TreeFault('PAGE_DELETE_OPERATION_CONFLICT')
        try:
            page = _page(page_id)
        except Page.DoesNotExist:
            if AuditEvent.objects.filter(
                    code='TREE_DELETE_PAGE',
                    object_ref='uuid:' + str(page_id)).exists():
                return {
                    'operation_id': str(operation_id), 'replay': True,
                    'result_code': 'page_deleted', 'gone': True,
                }
            raise
        scope = _scope(page)
        if data['stamp'] != scope['stamp']:
            raise TreeFault('PAGE_DELETE_BASIS_CHANGED')
        if (type(confirm_name) is not str
                or type(confirm_url) is not str
                or confirm_name != page.name
                or confirm_url != scope['primary'].target):
            raise TreeFault('PAGE_DELETE_EXACT_CONFIRMATION_REQUIRED', 400)

        revision_ids = [row.pk for row in scope['revisions']]
        draft_ids = [row.pk for row in scope['drafts']]
        _raw(AssetUsage).filter(
            Q(kind=AssetUsage.Kind.CURRENT_PAGE, consumer_id=page.pk)
            | Q(kind__in=(AssetUsage.Kind.ORDINARY_VERSION,
                         AssetUsage.Kind.STABLE_VERSION),
                consumer_id__in=revision_ids)
            | Q(kind=AssetUsage.Kind.DRAFT,
                consumer_id__in=draft_ids)).delete()
        engine.raw(VersionBasePin).filter(
            revision_id__in=revision_ids).delete()
        engine.raw(RevisionProtection).filter(
            revision_id__in=revision_ids).delete()
        engine.raw(OwnerDraft).filter(page=page).delete()
        engine.raw(RestoreStage).filter(page=page).delete()
        engine.raw(PageContentState).filter(page=page).delete()
        engine.raw(RevisionMetadata).filter(
            revision_id__in=revision_ids).delete()
        engine.raw(PageRevision).filter(pk__in=revision_ids).delete()
        _raw(PageMediaHome).filter(page=page).delete()
        PageGrant.objects.filter(page=page).delete()
        _raw(Route).filter(page=page).delete()
        _raw(Page).filter(pk=page.pk).delete()
        record_event(
            category=Category.PAGES_LINKS,
            event_code='TREE_DELETE_PAGE', level=Level.WARNING,
            source=Source.APPLICATION, result=Result.SUCCESS,
            actor_id=actor.pk, object_kind='page', object_ref=page_id)
        return {
            'operation_id': str(operation_id), 'replay': False,
            'result_code': 'page_deleted', 'gone': True,
        }
