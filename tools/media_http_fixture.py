"""Host-invoked exclusive test seed/observer. No HTTP endpoint or action substitute."""
import json
import os
import secrets
import sys
from uuid import UUID


def execute(request):
    if os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http':
        raise ValueError('Exclusive ordinary local test profile required')
    import django
    django.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.db import models, transaction
    from accounts.models import AuthSession, UserProfile, PageGrant
    from content.models import Page, lock_content
    from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder, PageMediaHome
    from media_library.storage import MediaStorage
    if settings.DATABASES['default']['NAME'] != 'estakada_foundation':
        raise ValueError('Wrong database')
    run_id = str(UUID(request['runId']))
    User = get_user_model()
    if request['kind'] == 'seed':
        from accounts.services import bootstrap_owner, create_employee
        with transaction.atomic():
            lock_content('default')
            if User.objects.exists() or Page.objects.exists() or Asset.objects.exists() or MediaFolder.objects.exists():
                raise ValueError('Nonempty exclusive fixture; nothing reset')
            passwords = {key: secrets.token_hex(48) for key in ['owner', 'employee']}
            owner = bootstrap_owner(passwords['owner'])
            employee = create_employee(actor=owner, username='media-employee', password=passwords['employee'])
            for user in [owner, employee]:
                user.first_name = run_id
                user.save(update_fields=['first_name'])
            pages = [Page.objects.create(kind=Page.Kind.ARTICLE, name='MEDIA TEST '+run_id+' '+name) for name in ['A', 'B', 'C']]
            prefix='fixture-'+run_id
            folder_rows=[]
            for page,suffix in zip(pages,['foo','foo/child','foobar']):
                folder=MediaFolder.objects.create(path=prefix+'/'+suffix)
                PageMediaHome.objects.create(page=page,folder=folder)
                folder_rows.append({'pageId':str(page.pk),'folderId':str(folder.pk),'path':folder.path})
            PageGrant.objects.create(user=employee, page=pages[0], intro_text=True)
        return {'runId':run_id, 'userIds':[str(owner.pk),str(employee.pk)], 'pageIds':[str(p.pk) for p in pages], 'folders':folder_rows,
                'accounts':{'owner':{'username':owner.username,'password':passwords['owner']},
                            'employee':{'username':employee.username,'password':passwords['employee']}}}
    owned_users=request['userIds']; owned_pages=request['pageIds']
    if sorted(str(v) for v in User.objects.values_list('pk',flat=True)) != sorted(owned_users):
        raise ValueError('Foreign user; fixture preserved')
    if any(u.first_name != run_id for u in User.objects.all()):
        raise ValueError('Fixture identity changed')
    if sorted(str(v) for v in Page.objects.values_list('pk',flat=True)) != sorted(owned_pages):
        raise ValueError('Foreign page; fixture preserved')
    homes=list(PageMediaHome.objects.filter(page_id__in=owned_pages))
    folders={str(home.folder_id) for home in homes}
    if any(str(v) not in folders for v in Asset.objects.values_list('folder_id',flat=True)):
        raise ValueError('Foreign asset; fixture preserved')
    storage=MediaStorage()
    if request['kind']=='observe':
        def actual(key):
            from media_library.storage import MediaParentUnavailable
            try:
                return storage.manifest(key)
            except FileNotFoundError:
                return None
            except MediaParentUnavailable:
                return {'unavailable':True}
        rows=[]
        for asset in Asset.objects.order_by('pk'):
            files=[]
            for file in asset.files.order_by('kind','key'):
                physical=actual(file.key)
                files.append({'id':str(file.pk),'kind':file.kind,'key':file.key,'physical':physical})
            rows.append({'id':str(asset.pk),'status':asset.status,'folderId':str(asset.folder_id),'files':files,
                         'usageCount':AssetUsage.objects.filter(asset=asset).count()})
        # This allowlist is accumulated by the host from earlier real DB observations,
        # never accepted as arbitrary paths from browser/control requests.
        known=request.get('knownFiles',[])
        if not isinstance(known,list):raise ValueError('Invalid known-file allowlist')
        physical_files=[]
        from media_library.paths import storage_key
        for row in known:
            asset_id=str(UUID(row['assetId']));key=storage_key(row['key'])
            allowed=key.startswith('private/sources/'+asset_id+'/') or any(
                key.startswith('img/'+h.folder.path+'/'+asset_id+'/') for h in homes)
            if not allowed:raise ValueError('Known file escaped owned fixture')
            physical_files.append({'assetId':asset_id,'key':key,'physical':actual(key)})
        return {'assets':rows,'physicalFiles':physical_files,'homes':[{'pageId':str(h.page_id),'folderId':str(h.folder_id),'path':h.folder.path} for h in homes]}
    if request['kind']=='close':
        from media_library.services import prepare_cleanup, confirm_cleanup
        owner=User.objects.get(username='nesadmin',first_name=run_id)
        for asset in Asset.objects.all():
            if asset.status!='ready' or asset.usages.exists():
                raise ValueError('Pending or retained fixture; preserve for explicit investigation')
            preview=prepare_cleanup(actor=owner,asset_ids=[asset.pk],expected_generation=1,storage=storage)
            result=confirm_cleanup(actor=owner,confirmation=preview['confirmation'],expected_generation=1,storage=storage)
            if any(row['state']!='deleted' for row in result):
                raise ValueError('Fixture physical cleanup incomplete')
        with transaction.atomic():
            lock_content('default')
            keys=list(AuthSession.objects.filter(user_id__in=owned_users).values_list('pk',flat=True))
            AuthSession.objects.filter(pk__in=keys).delete();Session.objects.filter(pk__in=keys).delete()
            PageGrant.objects.filter(user_id__in=owned_users).delete()
            models.QuerySet(model=PageMediaHome).filter(page_id__in=owned_pages).delete()
            models.QuerySet(model=MediaFolder).filter(pk__in=folders).delete()
            models.QuerySet(model=Page).filter(pk__in=owned_pages).delete()
            UserProfile.objects.filter(user_id__in=owned_users).delete()
            User.objects.filter(pk__in=owned_users).delete()
        return {'closed':True,'remainingUsers':User.objects.count(),'remainingAssets':Asset.objects.count()}
    raise ValueError('Unknown fixture operation')


if __name__=='__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin))))
    except Exception as exc:
        print(json.dumps({'errorClass':type(exc).__name__}),file=sys.stderr)
        sys.exit(1)
