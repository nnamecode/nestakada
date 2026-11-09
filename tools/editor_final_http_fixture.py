"""CF07 normal-only synthetic seed/read/proof/retention. No cleanup/reset API."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from uuid import UUID, uuid4, uuid5

ORIGIN = 'http://host.docker.internal:8767'
PAGE_KEYS = ('core', 'fmtA', 'fmtB', 'media', 'foreign', 'max')
FMT_A = '<table data-es-cellpad="4"><caption>Цена 😀 <strong>до/после</strong></caption><thead><tr><th scope="col" colspan="2">Работы</th></tr></thead><tbody><tr><th scope="row" rowspan="2">Кузов</th><td><em>Осмотр</em></td></tr><tr><td>Ремонт панели</td></tr></tbody></table>'
FMT_B = '<table data-es-cellpad="32" data-es-mt="8"><caption><u>Матрица Б</u> 🛠</caption><thead><tr><th scope="colgroup" colspan="2">Проверка</th></tr></thead><tbody><tr><th scope="rowgroup" rowspan="2">Группа</th><td><strong>А</strong><br>Б</td></tr><tr><td><span data-es-fg="#112233">Цена 0.01</span></td></tr></tbody></table>'


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def digest(value):
    return sha(json.dumps(value, default=str, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def rich(label):
    from page_editor.test_combined_http import CombinedMaximumHttpTests
    return CombinedMaximumHttpTests().rich(label)


def stock(value):
    import html5lib
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder('etree'), namespaceHTMLElements=True)
    tree = parser.parseFragment(value)
    count, depth, points = 0, 0, len(tree.text or '')
    pending = [(node, 1) for node in tree]
    while pending:
        node, current = pending.pop()
        count += 1; depth = max(depth, current)
        points += len(node.text or '') + len(node.tail or '')
        pending.extend((child, current + 1) for child in node)
    if parser.errors:
        raise ValueError('CF_STOCK_PARSE')
    return {'sha256': sha(value), 'bytes': len(value.encode()), 'elements': count,
            'depth': depth, 'codepoints': points}


def execute(request):
    if os.environ.get('ESTAKADA_LOCAL_ENV') != 'test' or os.environ.get('DJANGO_SETTINGS_MODULE') != 'estakada.settings.local_http':
        raise ValueError('CF_NORMAL_ENV')
    import django
    django.setup()
    from django.apps import apps
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import connection, transaction
    from django.core import signing
    from accounts.models import UserProfile, PageGrant
    from accounts.services import bootstrap_owner, create_employee, lock_auth
    from content.models import Page, Route, lock_content
    from page_versions import services as V, schema as S
    from page_versions.models import PageRevision, PageContentState, OwnerDraft, RestoreStage, VersionBasePin, OperationReceipt
    from media_library.models import Asset, AssetFile, AssetUsage
    from media_library.uploads import upload
    from media_library.services import attach
    from media_library.storage import MediaStorage
    from shared_content.models import SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin, SharedReceipt, SharedBudget
    from shared_content import reservations, quota
    from shared_content.storage import SharedStorage
    from shared_content.policy import normalize_html as shared_normalize
    from audit.models import AuditEvent
    if settings.ROOT_URLCONF != 'estakada.urls' or settings.ENVIRONMENT != 'test':
        raise ValueError('CF_NORMAL_SETTINGS')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database(),current_user')
        if cursor.fetchone() != ('estakada_foundation', 'app_runtime'):
            raise ValueError('CF_DATABASE_IDENTITY')
    if type(request) is not dict or request.get('kind') not in ('seed', 'resume', 'observe', 'verifyproof', 'retain'):
        raise ValueError('CF_CLOSED_OPERATION')
    run = str(UUID(request['runId'])); User = get_user_model()

    def baseline_catalogue():
        result = {}
        for model in sorted(apps.get_app_config('shared_content').get_models(), key=lambda item: item._meta.label):
            rows = {}
            for row in model.objects.order_by('pk').values().iterator(chunk_size=16):
                if model is SharedBlock:
                    row = {key: val for key, val in row.items() if key not in ('current_revision_id', 'generation')}
                elif model is SharedBudget:
                    row = {key: val for key, val in row.items() if key not in ('snapshot_count', 'charged_bytes')}
                rows[str(row[model._meta.pk.attname])] = digest(row)
            result[model._meta.label] = rows
        return result

    if request['kind'] in ('seed', 'resume'):
        recovering = request['kind'] == 'resume'
        if set(request) != ({'kind', 'runId', 'passwords', 'witness', 'preseed', 'checkpoint', 'intent'} if recovering else {'kind', 'runId', 'passwords'}):
            raise ValueError('CF_SEED_FIELDS')
        import re
        passwords = request['passwords']
        if (type(passwords) is not dict or set(passwords) != {'owner', 'employee', 'priceOnly'}
                or any(type(value) is not str or re.fullmatch('[a-f0-9]{96}', value) is None for value in passwords.values())):
            raise ValueError('CF_PRIVATE_PRESTORED_CREDENTIALS_REQUIRED')
        from page_editor.test_media_http import PNG
        from shared_content.test_shared_http import SharedHttpTests
        from types import SimpleNamespace
        resumed_result = None
        if recovering:
            from django.contrib.auth.hashers import check_password
            witness, preseed = request['witness'], request['preseed']
            if run != '56e66714-a3e3-4043-9ef3-950bef71b646' or witness['runId'] != run:
                raise ValueError('CF_RESUME_RUN')
            users = {key: User.objects.get(username=name) for key, name in {
                'owner': 'nesadmin', 'employee': 'cf-text-' + run[:8], 'priceOnly': 'cf-price-' + run[:8]}.items()}
            if (User.objects.count() != 3 or sorted(user.pk for user in users.values()) != sorted(row['id'] for row in witness['users'])
                    or any(user.first_name != run or not user.is_active or not check_password(passwords[key], user.password)
                           for key, user in users.items())):
                raise ValueError('CF_RESUME_USERS')
            owner, employee, price_user = users['owner'], users['employee'], users['priceOnly']
            if (UserProfile.objects.count() != 3 or any(not UserProfile.objects.filter(user=user, generation=1,
                    role='owner' if key == 'owner' else 'employee').exists() for key, user in users.items())):
                raise ValueError('CF_RESUME_PROFILES')
            pages = {key: Page.objects.get(name='CF07 ' + run + ' ' + key) for key in PAGE_KEYS}
            if Page.objects.count() != 6 or {str(page.pk) for page in pages.values()} != {row['id'] for row in witness['pages']}:
                raise ValueError('CF_RESUME_PAGES')
            expected_grants = {(employee.pk, pages[key].pk, True, True, False) for key in ('core', 'fmtA', 'fmtB', 'media')}
            expected_grants.add((price_user.pk, pages['core'].pk, False, False, True))
            if set(PageGrant.objects.values_list('user_id', 'page_id', 'intro_text', 'main_text', 'price')) != expected_grants:
                raise ValueError('CF_RESUME_GRANTS')
            system = list(Route.objects.filter(kind='system').values('id', 'kind', 'target', 'page_id', 'is_legacy'))
            if json.loads(json.dumps(system, default=str)) != preseed['routes'] or Route.objects.count() != 7:
                raise ValueError('CF_RESUME_ROUTES')
            routes = {key: Route.objects.get(page=page, kind='primary', target='/cf07/' + run + '/' + key.lower() + '/', is_legacy=False)
                      for key, page in pages.items()}
            if (any(model.objects.exists() for model in (OwnerDraft, RestoreStage, VersionBasePin, SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin))
                    or SharedReceipt.objects.count() != 24
                    or apps.get_model('shared_content', 'SharedIdentityReservation').objects.count() != 66
                    or SharedStorage().inventory()['journalCount']):
                raise ValueError('CF_RESUME_NO_INTERVENING_WORK')
            blocks = list(SharedBlock.objects.order_by('kind'))
            if json.loads(json.dumps(list(SharedBlock.objects.order_by('kind').values('id', 'kind', 'current_revision_id', 'generation')), default=str)) != preseed['sharedBlocks']:
                raise ValueError('CF_RESUME_SHARED_BASELINE')
            budget = SharedBudget.objects.get(singleton=True)
            if budget.accounting_version != 'unvetted' or budget.retained_debt_bytes != 0:
                raise ValueError('CF_RESUME_BUDGET')
            from shared_content.lifecycle import require_no_pending
            require_no_pending()
            baseline = baseline_catalogue()  # Reconstructed checkpoint, never claimed as persisted preseed hash.
            initial_shared = {block.kind: {'id': str(block.pk), 'currentId': None, 'generation': block.generation} for block in blocks}
            assets = {}
            homes = {'sharedLogo': 'core', 'privateA': 'media', 'privateB': 'foreign'}
            for name, key in homes.items():
                # The successful original upload owns its page's immutable media home.
                asset = Asset.objects.get(folder=pages[key].media_home.folder, status='ready')
                files = list(asset.files.order_by('id').values('id', 'kind', 'key', 'sha256', 'byte_size'))
                if len(files) != 3 or {row['kind'] for row in files} != {'main', 'preview', 'private-source'}:
                    raise ValueError('CF_RESUME_FILES')
                for file in files:
                    expected = next((row for row in witness['files'] if row['id'] == str(file['id'])), None)
                    if (expected is None or expected['asset_id'] != str(asset.pk) or expected['kind'] != file['kind']
                            or expected['sha256'] != file['sha256'] or expected['byte_size'] != file['byte_size']
                            or MediaStorage().manifest(file['key']) != {'sha256': file['sha256'], 'byte_size': file['byte_size']}):
                        raise ValueError('CF_RESUME_PHYSICAL_FILES')
                main = next(row for row in files if row['kind'] == 'main')
                preview = next(row for row in files if row['kind'] == 'preview')
                source = next(row for row in files if row['kind'] == 'private-source')
                assets[name] = {'id': str(asset.pk), 'mainFileId': str(main['id']), 'mainHash': main['sha256'],
                    'previewFileId': str(preview['id']), 'sourceHash': source['sha256'],
                    'files': [{**row, 'id': str(row['id'])} for row in files]}
            if Asset.objects.count() != 3 or AssetFile.objects.count() != 9:
                raise ValueError('CF_RESUME_ASSET_COUNTS')
            resume_operation = uuid5(UUID(run), 'CF07-remaining-embedded-source-v1')
            resumed_result = OperationReceipt.objects.filter(pk=resume_operation).first()
            expected_current = {row['page_id']: row['current_revision_id'] for row in witness['current']}
            if resumed_result is not None:
                if (resumed_result.action != 'commit_owner' or resumed_result.actor_id != owner.pk or resumed_result.actor_generation != 1
                        or resumed_result.page_id != pages['media'].pk or str(resumed_result.source_revision_id) != expected_current[str(pages['media'].pk)]
                        or resumed_result.result_code != 'applied' or resumed_result.result_id is None):
                    raise ValueError('CF_RESUME_RECEIPT')
                expected_current[str(pages['media'].pk)] = str(resumed_result.result_id)
            if (PageContentState.objects.count() != 6 or PageRevision.objects.count() != (10 if resumed_result else 9)
                    or {str(row.page_id): str(row.current_revision_id) for row in PageContentState.objects.all()} != expected_current):
                raise ValueError('CF_RESUME_CURRENT_CHECKPOINT')
            page_seed = {}
            for key, page in pages.items():
                revisions = list(PageRevision.objects.filter(page=page).order_by('sequence'))
                expected_count = (3 if resumed_result else 2) if key == 'media' else 2 if key in ('core', 'foreign') else 1
                if (page.kind != Page.Kind.ARTICLE or len(revisions) != expected_count
                        or any(row.sequence != index or row.author_id != owner.pk or S.digest(row.payload) != row.payload_hash
                               for index, row in enumerate(revisions, 1))):
                    raise ValueError('CF_RESUME_HISTORY')
                initial = S.snapshot_v1(page.kind, intro_text=rich('S') if key == 'max' else '<p>CF INTRO ' + key + '</p>',
                    main_text=rich('T') if key == 'max' else '<p>CF HISTORICAL ' + key + '</p>',
                    h1='CF protected H1 ' + key, title='CF protected title ' + key).data()
                if revisions[0].payload != initial:
                    raise ValueError('CF_RESUME_INITIAL_PAYLOAD')
                if key in ('media', 'foreign'):
                    expected = dict(initial)
                    name = 'privateA' if key == 'media' else 'privateB'
                    expected['main_image'] = {'asset_id': assets[name]['id'], 'alt': 'CF PRIVATE ' + name,
                        'alignment': 'left', 'width_px': 120, 'height_px': None}
                    if revisions[1].payload != expected:
                        raise ValueError('CF_RESUME_MEDIA_PAYLOAD')
                if key == 'core':
                    expected = dict(initial); expected.update(main_text='<p>CF CURRENT core</p>', h1='CF current protected H1', title='CF current protected title', price=revisions[1].payload['price'])
                    if revisions[1].payload != expected:
                        raise ValueError('CF_RESUME_CORE_PAYLOAD')
                page_seed[key] = {'id': str(page.pk), 'url': '/manage/pages/' + str(page.pk) + '/edit/',
                    'initialRevisionId': str(revisions[0].pk), 'historyRevisionId': str(revisions[0].pk)}
            checkpoint = request['checkpoint']
            if checkpoint['runId'] != run or baseline != checkpoint['shared']:
                raise ValueError('CF_RESUME_CHECKPOINT_SHARED')
            if resumed_result:
                completed = PageRevision.objects.get(pk=resumed_result.result_id)
                for kind, consumer in (('current_page', pages['media'].pk), ('ordinary_version', completed.pk)):
                    actual_slots = dict(AssetUsage.objects.filter(kind=kind, consumer_id=consumer).values_list('slot', 'asset_id'))
                    if {slot: str(identity) for slot, identity in actual_slots.items()} != S.asset_slots(completed.payload):
                        raise ValueError('CF_RESUME_REPLAY_USAGES')
            for label, expected_rows in checkpoint['models'].items():
                model = apps.get_model(label)
                rows = []
                for row in model.objects.order_by('pk').values():
                    if label == 'page_versions.PageRevision':
                        if resumed_result and row['id'] == resumed_result.result_id:
                            continue
                        row['payloadDigest'] = digest(row.pop('payload'))
                    if resumed_result and label == 'page_versions.OperationReceipt' and row['id'] == resumed_result.pk:
                        continue
                    if resumed_result and label == 'media_library.AssetUsage' and row['kind'] == 'ordinary_version' and row['consumer_id'] == resumed_result.result_id:
                        continue
                    if (resumed_result and label == 'media_library.AssetUsage' and row['kind'] == 'current_page'
                            and row['consumer_id'] == pages['media'].pk and row['slot'].startswith('embedded:')):
                        continue
                    if resumed_result and label == 'page_versions.PageContentState' and row['page_id'] == pages['media'].pk:
                        old = next(item for item in expected_rows if item['page_id'] == str(pages['media'].pk))
                        if row['sequence'] != old['sequence'] + 1:
                            raise ValueError('CF_RESUME_REPLAY_SEQUENCE')
                        row['sequence'] = old['sequence']; row['current_revision_id'] = old['current_revision_id']
                    rows.append(row)
                if json.loads(json.dumps(rows, default=str)) != expected_rows:
                    raise ValueError('CF_RESUME_CHECKPOINT_ROWS_' + model._meta.model_name.upper())
        else:
            with transaction.atomic():
                lock_content('default'); lock_auth()
                system = list(Route.objects.values('id', 'kind', 'target', 'page_id', 'is_legacy'))
                if (len(system) != 1 or {key: val for key, val in system[0].items() if key != 'id'} !=
                        {'kind': 'system', 'target': '/manage/', 'page_id': None, 'is_legacy': False}):
                    raise ValueError('CF_SYSTEM_ROUTE')
                if any(model.objects.exists() for model in (User, Page, PageRevision, PageContentState, OwnerDraft, RestoreStage, VersionBasePin, Asset, AssetFile, AssetUsage)):
                    raise ValueError('CF_NONEMPTY_PRESERVED_NO_RESEED')
                blocks = list(SharedBlock.objects.order_by('kind'))
                if [block.kind for block in blocks] != ['footer', 'header']:
                    raise ValueError('CF_SHARED_BASELINE_REQUIRED')
                if SharedStorage().inventory()['journalCount'] or SharedBudget.objects.get(singleton=True).accounting_version == 'faulted':
                    raise ValueError('CF_UNKNOWN_OR_FAULT_BASELINE_PRESERVED')
                from shared_content.lifecycle import require_no_pending
                require_no_pending()
                quota.admit_locked(snapshot_increment=6, new_refs=4)
                baseline = baseline_catalogue()
                initial_shared = {block.kind: {'id': str(block.pk),
                    'currentId': str(block.current_revision_id) if block.current_revision_id else None,
                    'generation': block.generation} for block in blocks}
                owner = bootstrap_owner(passwords['owner'])
                employee = create_employee(actor=owner, username='cf-text-' + run[:8], password=passwords['employee'])
                price_user = create_employee(actor=owner, username='cf-price-' + run[:8], password=passwords['priceOnly'])
                users = {'owner': owner, 'employee': employee, 'priceOnly': price_user}
                for user in users.values():
                    user.first_name = run; user.save(update_fields=['first_name'])
                pages = {key: Page.objects.create(kind=Page.Kind.ARTICLE, name='CF07 ' + run + ' ' + key) for key in PAGE_KEYS}
                routes = {key: Route.objects.create(page=page, kind=Route.Kind.PRIMARY, target='/cf07/' + run + '/' + key.lower() + '/') for key, page in pages.items()}
                for key in ('core', 'fmtA', 'fmtB', 'media'):
                    PageGrant.objects.create(user=employee, page=pages[key], intro_text=True, main_text=True)
                PageGrant.objects.create(user=price_user, page=pages['core'], price=True)
            page_seed = {}
            for key, page in pages.items():
                intro = rich('S') if key == 'max' else '<p>CF INTRO ' + key + '</p>'
                main = rich('T') if key == 'max' else '<p>CF HISTORICAL ' + key + '</p>'
                result = V.initialize(actor=owner, page_id=page.pk,
                    snapshot=S.snapshot_v1(page.kind, intro_text=intro, main_text=main,
                        h1='CF protected H1 ' + key, title='CF protected title ' + key),
                    expected_generation=1, operation_id=uuid4())
                page_seed[key] = {'id': str(page.pk), 'url': '/manage/pages/' + str(page.pk) + '/edit/',
                    'initialRevisionId': result['result_id'], 'historyRevisionId': result['result_id']}
            # A distinct protected current for a genuine selected historical restore.
            page = pages['core']; old = PageRevision.objects.get(pk=page_seed['core']['initialRevisionId'])
            payload = dict(old.payload); payload.update(main_text='<p>CF CURRENT core</p>', h1='CF current protected H1', title='CF current protected title')
            column, row = str(uuid4()), str(uuid4())
            payload['price'] = {'columns': [{'id': column, 'label': 'Цена'}], 'rows': [{'id': row, 'label': 'Работа', 'cells': [{'column_id': column, 'kind': 'text', 'text': ''}]}]}
            V.commit_owner(actor=owner, page_id=page.pk, base_revision=old.pk, snapshot=S.Snapshot.trusted(payload, page.kind), expected_generation=1, operation_id=uuid4())
            assets = {}
            for name, key in (('sharedLogo', 'core'), ('privateA', 'media'), ('privateB', 'foreign')):
                asset = upload(actor=owner, page_id=pages[key].pk, expected_generation=1,
                    upload=SimpleUploadedFile('cf-' + name + '.png', base64.b64decode(PNG), content_type='image/png'))
                if asset.status != 'ready' or asset.files.count() != 3:
                    raise ValueError('CF_READY_MEDIA_REQUIRED')
                files = list(asset.files.order_by('id').values('id', 'kind', 'key', 'sha256', 'byte_size'))
                main = next(item for item in files if item['kind'] == 'main')
                preview = next(item for item in files if item['kind'] == 'preview')
                source = next(item for item in files if item['kind'] == 'private-source')
                assets[name] = {'id': str(asset.pk), 'mainFileId': str(main['id']), 'mainHash': main['sha256'],
                    'previewFileId': str(preview['id']), 'sourceHash': source['sha256'],
                    'files': [{**item, 'id': str(item['id'])} for item in files]}
                if key in ('media', 'foreign'):
                    current = PageRevision.objects.get(pk=PageContentState.objects.get(page=pages[key]).current_revision_id)
                    value = dict(current.payload); value['main_image'] = {'asset_id': str(asset.pk), 'alt': 'CF PRIVATE ' + name,
                        'alignment': 'left', 'width_px': 120, 'height_px': None}
                    V.commit_owner(actor=owner, page_id=pages[key].pk, base_revision=current.pk,
                        snapshot=S.Snapshot.trusted(value, pages[key].kind), expected_generation=1, operation_id=uuid4())
        # Seed one actual producer-derived embedded source, not fabricated layout.
        from page_editor import checks, embedded
        from editor_runtime.guards import EditorSlot
        from editor_runtime.processing import normalize_input
        from page_editor.test_embedded_http import EmbeddedEditorHttpTests
        recovery_intent = request.get('intent') if recovering else None
        if recovery_intent is not None:
            planned = signing.loads(recovery_intent, salt='cf07-fixture-resume-v1')
            if (planned['runId'] != run or planned['checkpointHash'] != digest(checkpoint)
                    or planned['pageId'] != str(pages['media'].pk) or planned['actorId'] != owner.pk
                    or planned['operationId'] != str(resume_operation) or planned['payloadHash'] != S.digest(planned['payload'])
                    or planned['baseId'] != next(row['current_revision_id'] for row in witness['current'] if row['page_id'] == str(pages['media'].pk))):
                raise ValueError('CF_RESUME_INTENT_BINDING')
            if resumed_result:
                result = PageRevision.objects.get(pk=resumed_result.result_id)
                if result.payload != planned['payload'] or result.payload_hash != planned['payloadHash']:
                    raise ValueError('CF_RESUME_REPLAY_PAYLOAD')
                replayed = V.commit_owner(actor=owner, page_id=pages['media'].pk, base_revision=planned['baseId'],
                    snapshot=S.Snapshot.trusted(planned['payload'], pages['media'].kind), expected_generation=1, operation_id=resume_operation)
                if replayed['replay'] is not True or replayed['result_id'] != str(result.pk) or replayed['gone']:
                    raise ValueError('CF_RESUME_ENGINE_REPLAY')
            else:
                V.commit_owner(actor=owner, page_id=pages['media'].pk, base_revision=planned['baseId'],
                    snapshot=S.Snapshot.trusted(planned['payload'], pages['media'].kind), expected_generation=1, operation_id=resume_operation)
        else:
            if resumed_result:
                raise ValueError('CF_RESUME_PRIVATE_INTENT_REQUIRED')
            context = checks.inspect_context(actor=owner, page_id=pages['media'].pk, generation=1, origin=ORIGIN)
            reference = {'asset_id': assets['privateA']['id'], 'alt': 'CF EXISTING EMBEDDED', 'alignment': 'center', 'width_px': 120, 'height_px': None}
            issued = embedded.sign_issue(embedded.issue(context, {'field': 'main_text', 'action': 'insert',
                'image': reference, 'priorPermit': None, 'markerId': None}, []))
            html = EmbeddedEditorHttpTests().block(issued)
            body = {'protocol': 'page-editor-v1', 'generation': 1, 'baseRevisionId': context.child['base_revision_id'],
                'editingFrom': 'current', 'draftBasis': None, 'stageId': None, 'changes': {'main_text': html}}
            raw = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode()
            with EditorSlot():
                normalized = checks.check_worker_result(normalize_input(raw, context.child), raw=raw, context=context)
            value, _ = embedded.validate_derived(context, normalized)
            if recovering:
                recovery_intent = signing.dumps({'runId': run, 'checkpointHash': digest(checkpoint), 'actorId': owner.pk,
                    'pageId': str(pages['media'].pk), 'operationId': str(resume_operation), 'baseId': context.child['base_revision_id'],
                    'payload': value, 'payloadHash': S.digest(value)}, salt='cf07-fixture-resume-v1', compress=True)
            else:
                V.commit_owner(actor=owner, page_id=pages['media'].pk, base_revision=context.child['base_revision_id'],
                    snapshot=S.Snapshot.trusted(value, pages['media'].kind), expected_generation=1, operation_id=uuid4())
        shared = {}
        asset = Asset.objects.get(pk=assets['sharedLogo']['id'])
        for kind in ('header', 'footer'):
            block = SharedBlock.objects.get(kind=kind)
            old_markup = shared_normalize(SharedHttpTests.fixture(SimpleNamespace(asset=asset), kind, 'CF OLD ' + kind), kind)
            new_markup = shared_normalize(SharedHttpTests.fixture(SimpleNamespace(asset=asset), kind, 'CF NEW ' + kind), kind)
            if kind == 'header':
                new_markup = shared_normalize(new_markup['html'].replace('+70000000001', '+70000000002'), kind)
            shared[kind] = {'blockId': str(block.pk), 'oldRevisionId': None,
                'oldMarkup': old_markup['html'], 'newMarkup': new_markup['html']}
        # Both A and B are published later through actual browser Check/Apply.
        if baseline_catalogue() != baseline:
            raise ValueError('CF_SHARED_SEED_CHANGED_BASELINE')
        max_facts = {label: stock(rich(label)) for label in 'STCD'}
        ownership = {'userIds': [str(user.pk) for user in users.values()], 'pageIds': {key: str(page.pk) for key, page in pages.items()},
            'assetIds': {key: item['id'] for key, item in assets.items()}, 'routeIds': [str(route.pk) for route in routes.values()],
            'systemRouteId': str(system[0]['id']), 'sharedSourceIds': [],
            'sharedBaseline': baseline, 'initialShared': initial_shared}
        return {'schemaVersion': 1, 'runId': run, 'accounts': {key: {'id': str(user.pk), 'username': user.username,
                    'password': passwords[key], 'generation': 1} for key, user in users.items()},
            'pages': page_seed, 'assets': assets, 'fmt': {'A': FMT_A, 'B': FMT_B}, 'shared': shared,
            'max': {'algorithm': 'cm001-four-bounds-v1', 'facts': max_facts,
                'source': {'introHash': max_facts['S']['sha256'], 'mainHash': max_facts['T']['sha256'], 'bytesPerField': 1048576},
                'candidate': {'introHash': max_facts['C']['sha256'], 'mainHash': max_facts['D']['sha256']}},
            **({'recoveryIntent': recovery_intent, 'baselineOrigin': 'reconstructed-readonly-checkpoint'} if recovering else {}),
            'ownership': ownership, 'assetHashes': {name: sha((Path(settings.BASE_DIR)/'page_editor'/'assets'/name).read_bytes())
                for name in ('editor.bundle.js', 'editor.css', 'editor-bridge.mjs')}}

    ownership = request['ownership']
    if type(ownership) is not dict or set(ownership['pageIds']) != set(PAGE_KEYS):
        raise ValueError('CF_OWNERSHIP_REQUIRED')
    users = [str(int(identity)) for identity in ownership['userIds']]
    pages = {key: str(UUID(identity)) for key, identity in ownership['pageIds'].items()}
    if (User.objects.count() != 3 or sorted(map(str, User.objects.values_list('pk', flat=True))) != sorted(users)
            or User.objects.exclude(first_name=run).exists() or Page.objects.count() != 6
            or sorted(map(str, Page.objects.values_list('pk', flat=True))) != sorted(pages.values())
            or Page.objects.exclude(name__startswith='CF07 '+run+' ').exists()):
        raise ValueError('CF_FOREIGN_STATE_PRESERVED')

    if request['kind'] == 'verifyproof':
        if request.get('scope') != 'max' or type(request.get('receipt')) is not str:
            raise ValueError('CF_PROOF_SCOPE')
        from page_editor import checks
        from page_editor.input_policy import fingerprint
        owner = User.objects.get(username='nesadmin', pk__in=users)
        context = checks.inspect_context(actor=owner, page_id=pages['max'], generation=1, origin=ORIGIN)
        changes = {field: context.payload[field] for field in context.child['fields']}
        changes.update(intro_text=rich('C'), main_text=rich('D'))
        checks.verify_check_receipt(request['receipt'], context=context, changes=changes, _before_fs=True)
        signed = signing.loads(request['receipt'], salt=checks.SALT)
        if signed['inputFingerprint'] != request.get('inputFingerprint') or signed['normalizedFingerprint'] != fingerprint(changes):
            raise ValueError('CF_PROOF_BINDING')
        return {'verified': True, 'inputFingerprint': signed['inputFingerprint'], 'normalizedFingerprint': signed['normalizedFingerprint'],
            'introHash': sha(changes['intro_text']), 'mainHash': sha(changes['main_text']), 'pageId': pages['max'], 'baseRevisionId': context.child['base_revision_id']}

    def payload_value(payload, key):
        if key == 'max':
            return {'intro_text': stock(payload['intro_text']), 'main_text': stock(payload['main_text']),
                'protectedHash': digest({name: val for name, val in payload.items() if name not in ('intro_text', 'main_text')})}
        return payload

    page_rows = {}
    for key, identity in pages.items():
        state = PageContentState.objects.get(page_id=identity)
        revisions = list(PageRevision.objects.filter(page_id=identity).order_by('sequence'))
        current = next(row for row in revisions if row.pk == state.current_revision_id)
        page_rows[key] = {'id': identity, 'currentId': str(current.pk), 'payload': payload_value(current.payload, key),
            'payloadHash': digest(current.payload), 'versions': [{'id': str(row.pk), 'sequence': row.sequence, 'authorId': row.author_id,
                'payloadHash': digest(row.payload), 'mainHash': sha(row.payload['main_text'])} for row in revisions],
            'drafts': list(OwnerDraft.objects.filter(page_id=identity).values()),
            'stages': list(RestoreStage.objects.filter(page_id=identity).values()),
            'pins': list(VersionBasePin.objects.filter(revision__page_id=identity).values()),
            'receipts': list(OperationReceipt.objects.filter(page_id=identity).values())}
    shared_rows = {}
    for kind in ('header', 'footer'):
        block = SharedBlock.objects.get(kind=kind)
        revisions = list(SharedRevision.objects.filter(block=block).order_by('sequence'))
        shared_rows[kind] = {'blockId': str(block.pk), 'currentId': str(block.current_revision_id) if block.current_revision_id else None,
            'generation': block.generation, 'revisions': [{'id': str(row.pk), 'sequence': row.sequence, 'payloadHash': row.payload_hash,
                'sourceId': str(row.source_revision_id) if row.source_revision_id else None, 'authorId': row.author_id} for row in revisions],
            'drafts': list(SharedDraft.objects.filter(block=block).values('id','revision','base_revision_id','payload_hash')),
            'stages': list(SharedRestoreStage.objects.filter(block=block).values()),
            'pins': list(SharedBasePin.objects.filter(revision__block=block).values()),
            'receipts': list(SharedReceipt.objects.filter(block=block).values())}
    physical = []
    for file in AssetFile.objects.filter(asset_id__in=ownership['assetIds'].values()).order_by('id'):
        manifest = MediaStorage().manifest(file.key)
        if manifest != {'sha256': file.sha256, 'byte_size': file.byte_size}:
            raise ValueError('CF_MEDIA_BYTES_CHANGED')
        physical.append({'id': str(file.pk), 'assetId': str(file.asset_id), 'kind': file.kind, **manifest})
    baseline = baseline_catalogue()
    baseline_preserved = all(baseline.get(model, {}).get(identity) == value
        for model, rows in ownership['sharedBaseline'].items() for identity, value in rows.items())
    result = {'runId': run, 'pages': page_rows, 'shared': shared_rows,
        'metadataHashes': {label: digest(list(apps.get_model(label).objects.order_by('pk').values()))
            for label in ('content.Page', 'content.Route', 'accounts.UserProfile', 'accounts.PageGrant')},
        'assets': list(Asset.objects.filter(pk__in=ownership['assetIds'].values()).values('id', 'status')),
        'usages': list(AssetUsage.objects.order_by('id').values()), 'files': physical,
        'audit': list(AuditEvent.objects.filter(actor_id__in=users).order_by('id').values('id','code','object_kind','object_ref','result')),
        'budget': quota.measure(), 'baselineSharedPreserved': baseline_preserved,
        'systemRoutePreserved': Route.objects.filter(pk=ownership['systemRouteId'], kind='system', target='/manage/', page__isnull=True, is_legacy=False).exists()}
    if request['kind'] == 'retain':
        result = {'runId': run, 'retained': True, 'cleanupPerformed': False, 'outcome': request.get('outcome'),
            'ownership': ownership, 'baselineSharedPreserved': baseline_preserved,
            'systemRoutePreserved': result['systemRoutePreserved'], 'pageCurrent': {key: row['currentId'] for key, row in page_rows.items()},
            'sharedCurrent': {key: row['currentId'] for key, row in shared_rows.items()},
            'retainedUsers': users, 'retainedAssets': ownership['assetIds'], 'assetFiles': physical,
            'pageVersionCounts': {key: len(row['versions']) for key, row in page_rows.items()},
            'sharedVersionCounts': {key: len(row['revisions']) for key, row in shared_rows.items()}, 'budget': result['budget']}
    return result


if __name__ == '__main__':
    try:
        print(json.dumps(execute(json.load(sys.stdin)), default=str, ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'errorClass': type(error).__name__, 'code': 'CF_FIXTURE_FAILED_STATE_PRESERVED'}), file=sys.stderr)
        sys.exit(1)
