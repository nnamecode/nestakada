"""Exclusive local editor seed/observer/cleanup; never an HTTP fixture endpoint."""
import json
import os
import secrets
import sys
from uuid import UUID, uuid4


def execute(request):
    if (os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or
            os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http'):
        raise ValueError('Exclusive ordinary local test profile required')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import models, transaction
    from accounts.models import AuthSession, UserProfile, PageGrant
    from content.models import Page, Route, lock_content
    from media_library.models import Asset, AssetUsage, MediaFolder, PageMediaHome
    from page_versions.models import (PageRevision, PageContentState, RevisionMetadata,
        RevisionProtection, OwnerDraft, RestoreStage, VersionBasePin, OperationReceipt)
    from page_versions.models import IdentityReservation as VersionIdentityReservation
    from media_library.models import IdentityReservation as MediaIdentityReservation
    from page_versions.schema import digest
    from audit.models import AuditEvent
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong database')
    if type(request) is not dict or request.get('kind') not in ('seed', 'observe', 'close'):
        raise ValueError('Closed fixture operation required')
    run_id = str(UUID(request['runId']))
    User = get_user_model()
    raw = lambda model: models.QuerySet(model=model, using='default')
    forbidden = [Asset, AssetUsage, MediaFolder, PageMediaHome, OwnerDraft,
                 RestoreStage, VersionBasePin, RevisionProtection]
    def system_route(system_ids=None):
        rows = list(Route.objects.filter(target='/manage/').values('id','target','kind','page_id','is_legacy'))
        if len(rows) != 1:
            raise ValueError('Exact migrated system route required; preserved')
        row = rows[0]
        if row != {'id':row['id'], 'target':'/manage/', 'kind':'system', 'page_id':None, 'is_legacy':False}:
            raise ValueError('Migrated system route changed; preserved')
        ids = [str(row['id'])]
        if system_ids is not None and ids != system_ids:
            raise ValueError('Migrated system route identity changed; preserved')
        return ids
    if request['kind'] == 'seed':
        from accounts.services import bootstrap_owner, create_employee, lock_auth
        from page_versions import services as V, schema as S
        with transaction.atomic():
            lock_content('default')
            lock_auth()
            system_ids = system_route()
            if Route.objects.exclude(pk__in=system_ids).exists():
                raise ValueError('Foreign route at seed; preserved')
            if any(model.objects.exists() for model in [User, Page, PageRevision,
                    PageContentState, AuthSession, Session] + forbidden):
                raise ValueError('Nonempty exclusive fixture; preserved')
            passwords = {name: secrets.token_hex(48) for name in ('owner', 'employee', 'other')}
            owner = bootstrap_owner(passwords['owner'])
            employee = create_employee(actor=owner, username='editor-assigned', password=passwords['employee'])
            other = create_employee(actor=owner, username='editor-other', password=passwords['other'])
            users = [owner, employee, other]
            for user in users:
                user.first_name = run_id
                user.save(update_fields=['first_name'])
            pages = [Page.objects.create(kind=Page.Kind.ARTICLE,
                     name='EDITOR TEST ' + run_id + ' ' + suffix) for suffix in ('A', 'B')]
            routes = [Route.objects.create(page=page, kind=Route.Kind.PRIMARY,
                      target='/editor-fixture/' + run_id + '/' + suffix + '/')
                      for page, suffix in zip(pages, ('a', 'b'))]
            PageGrant.objects.create(user=employee, page=pages[0], intro_text=True, main_text=True)
            PageGrant.objects.create(user=other, page=pages[1], main_text=True)
        current = []
        for index, page in enumerate(pages):
            result = V.initialize(actor=owner, page_id=page.pk,
                snapshot=S.snapshot_v1(page.kind, intro_text='<p>INTRO</p>',
                    main_text='<p>EDITOR ' + ('A' if index == 0 else 'B') + '</p>',
                    h1='Protected fixture heading', title='Protected fixture title'),
                expected_generation=1, operation_id=uuid4())
            current.append(result['result_id'])
        return {'runId':run_id, 'systemRouteIds':system_ids, 'userIds':[str(user.pk) for user in users],
                'pageIds':[str(page.pk) for page in pages], 'routeIds':[str(route.pk) for route in routes],
                'currentIds':current, 'accounts':{name:{'username':user.username, 'password':passwords[name]}
                    for name,user in zip(('owner','employee','other'), users)}}

    users = [str(int(value)) for value in request['userIds']]
    pages = [str(UUID(value)) for value in request['pageIds']]
    routes = [str(UUID(value)) for value in request['routeIds']]
    system_ids = [str(UUID(value)) for value in request['systemRouteIds']]
    if (len(set(users)) != 3 or len(set(pages)) != 2 or len(set(routes)) != 2
            or len(system_ids) != 1 or set(system_ids) & set(routes)):
        raise ValueError('Closed fixture manifest required')
    def validate():
        system_route(system_ids)
        if sorted(str(value) for value in User.objects.values_list('pk', flat=True)) != sorted(users):
            raise ValueError('Foreign user; preserved')
        if any(user.first_name != run_id for user in User.objects.all()):
            raise ValueError('User ownership changed; preserved')
        if sorted(str(value) for value in Page.objects.values_list('pk', flat=True)) != sorted(pages):
            raise ValueError('Foreign page; preserved')
        if any(not page.name.startswith('EDITOR TEST ' + run_id + ' ') for page in Page.objects.all()):
            raise ValueError('Page ownership changed; preserved')
        owned_routes = Route.objects.exclude(pk__in=system_ids)
        if sorted(str(value) for value in owned_routes.values_list('pk', flat=True)) != sorted(routes):
            raise ValueError('Foreign route; preserved')
        expected_targets = {'/editor-fixture/' + run_id + '/' + suffix + '/' for suffix in ('a','b')}
        if set(owned_routes.values_list('target', flat=True)) != expected_targets or owned_routes.exclude(page_id__in=pages).exists():
            raise ValueError('Route ownership changed; preserved')
        if any(model.objects.exists() for model in forbidden):
            raise ValueError('Unexpected media/draft/stage/protection; preserved')
        if (PageRevision.objects.exclude(page_id__in=pages).exists() or
                PageRevision.objects.exclude(author_id__in=users).exists() or
                PageContentState.objects.exclude(page_id__in=pages).exists()):
            raise ValueError('Foreign revision/state; preserved')
        if (PageGrant.objects.exclude(user_id__in=users).exists() or
                PageGrant.objects.exclude(page_id__in=pages).exists() or
                AuthSession.objects.exclude(user_id__in=users).exists()):
            raise ValueError('Foreign grant/session; preserved')
        if OperationReceipt.objects.filter(page_id__in=pages).exclude(actor_id__in=users).exists():
            raise ValueError('Foreign operation actor; preserved')
        # Historical permanent receipts with no live Page are intentionally kept.
        if OperationReceipt.objects.filter(page_id__in=Page.objects.values('pk')).exclude(page_id__in=pages).exists():
            raise ValueError('Foreign live operation; preserved')
        for session in Session.objects.all():
            if str(session.get_decoded().get('_auth_user_id')) not in users:
                raise ValueError('Unowned Django session; preserved')
    validate()
    if request['kind'] == 'observe':
        rows = []
        for page in Page.objects.order_by('id'):
            state = PageContentState.objects.get(page=page)
            revision = PageRevision.objects.get(pk=state.current_revision_id)
            history = PageRevision.objects.filter(page=page).order_by('sequence')
            rows.append({'id':str(page.pk), 'name':page.name, 'currentId':str(revision.pk),
                'payloadHash':revision.payload_hash, 'payload':revision.payload,
                'history':[{'id':str(row.pk), 'kind':row.kind, 'authorId':str(row.author_id),
                    'sourceId':str(row.source_revision_id) if row.source_revision_id else None,
                    'payloadHash':row.payload_hash} for row in history]})
        receipts = OperationReceipt.objects.filter(page_id__in=pages).order_by('id')
        events = AuditEvent.objects.filter(actor_id__in=users, code__startswith='VERSION_')
        return {'runId':run_id, 'systemRouteIds':system_ids, 'pages':rows,
                'receipts':[{'id':str(row.pk), 'pageId':str(row.page_id), 'actorId':str(row.actor_id),
                    'action':row.action, 'resultId':str(row.result_id) if row.result_id else None,
                    'editorFingerprint':row.editor_request_fingerprint} for row in receipts],
                'versionAuditCount':events.count(), 'noMedia':True,
                'domainHash':digest(rows), 'secretsExcluded':True}
    from accounts.services import lock_auth
    with transaction.atomic():
        lock_content('default')
        lock_auth()
        validate()
        revision_ids = list(PageRevision.objects.filter(page_id__in=pages).values_list('pk', flat=True))
        raw(PageContentState).filter(page_id__in=pages).delete()
        raw(RevisionMetadata).filter(revision_id__in=revision_ids).delete()
        raw(PageRevision).filter(pk__in=revision_ids).delete()
        session_keys = list(Session.objects.values_list('pk', flat=True))
        AuthSession.objects.filter(user_id__in=users).delete()
        Session.objects.filter(pk__in=session_keys).delete()
        PageGrant.objects.filter(user_id__in=users, page_id__in=pages).delete()
        raw(Route).filter(pk__in=routes).delete()
        raw(Page).filter(pk__in=pages).delete()
        UserProfile.objects.filter(user_id__in=users).delete()
        User.objects.filter(pk__in=users).delete()
        system_route(system_ids)
    return {'closed':True, 'remainingUsers':User.objects.count(), 'remainingPages':Page.objects.count(),
            'remainingRoutes':Route.objects.count(), 'remainingVersions':PageRevision.objects.count(),
            'systemRouteIds':system_ids, 'systemRoutePreserved':True,
            'versionIdentityTombstones':VersionIdentityReservation.objects.count(),
            'mediaIdentityTombstones':MediaIdentityReservation.objects.count(),
            'permanentOperationReceipts':OperationReceipt.objects.count(),
            'appendOnlyAuditEvents':AuditEvent.objects.count(), 'permanentLedgersPreserved':True}


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)), default=str))
    except Exception as error:
        print(json.dumps({'errorClass':type(error).__name__}), file=sys.stderr)
        sys.exit(1)
