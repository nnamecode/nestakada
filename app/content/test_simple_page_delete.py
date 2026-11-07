"""DEL-001–010 tests for confirmed leaf Page deletion."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import UUID, uuid4

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, close_old_connections, connection, models
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import PageGrant, UserProfile
from accounts.tests import FAST_HASHERS, OTHER, PASSWORD, client, login
from audit.models import AuditEvent
from media_library.models import (Asset, AssetFile, AssetUsage, MediaFolder,
                                  PageMediaHome)
from page_versions import engine, schema, services as versions
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  OwnerDraft, PageContentState,
                                  PageRevision, RestoreStage,
                                  RevisionMetadata, RevisionProtection,
                                  VersionBasePin)

from . import simple_page_delete as page_delete
from .models import Page, Route
from .reads import resolve_target
from .tree_commands import TreeFault


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimplePageDeleteTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='page-delete-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.page = self.make_page('Delete me', '/delete-me/')
        self.unrelated = self.make_page('Keep me', '/keep-me/')
        Route.objects.create(
            page=self.page, kind=Route.Kind.ALIAS,
            target='/delete-alias/')
        Route.objects.create(
            page=self.page, kind=Route.Kind.REDIRECT,
            target='/delete-old/')
        PageGrant.objects.create(
            user=self.employee, page=self.page,
            intro_text=True, main_text=True, price=False)
        self.build_history_and_media()

    def make_page(self, name, target, parent=None):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, parent=parent,
            is_published=True)
        Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        versions.initialize(
            actor=self.owner, page_id=page.pk,
            snapshot=schema.snapshot_v1(
                page.kind, main_text='Body', h1=name, title=name),
            expected_generation=1, operation_id=uuid4())
        return page

    def build_history_and_media(self):
        self.initial = PageContentState.objects.get(
            page=self.page).current_revision
        payload = schema.snapshot_v1(
            self.page.kind, main_text='Stable body',
            h1='Stable', title='Stable').data()
        self.stable_revision = PageRevision.objects.create(
            page=self.page, sequence=2,
            schema_version=payload['schema_version'], payload=payload,
            payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.MANUAL, author_id=self.owner.pk,
            source_revision_id=self.initial.pk)
        RevisionMetadata.objects.create(
            revision=self.stable_revision, generation=1,
            name='Stable checkpoint')
        RevisionProtection.objects.create(
            revision=self.stable_revision, marked_by_id=self.owner.pk)
        self.draft = OwnerDraft.objects.create(
            page=self.page, base_revision=self.initial,
            payload=self.initial.payload,
            payload_hash=self.initial.payload_hash,
            author_id=self.owner.pk)
        VersionBasePin.objects.create(
            revision=self.initial, holder_kind='owner_draft',
            holder_id=self.draft.pk)
        self.stage = RestoreStage.objects.create(
            page=self.page, actor_id=self.owner.pk,
            actor_generation=1, holder_kind='restore_stage',
            source_revision_id=self.stable_revision.pk,
            base_revision_id=self.initial.pk,
            permission_hash='a' * 64, fields=['main_text'])
        VersionBasePin.objects.create(
            revision=self.stable_revision, holder_kind='restore_stage',
            holder_id=self.stage.pk)

        self.folder = MediaFolder.objects.create(path='delete-fixture')
        PageMediaHome.objects.create(page=self.page, folder=self.folder)
        self.asset = Asset.objects.create(
            folder=self.folder, provenance='synthetic')
        self.file = AssetFile.objects.create(
            asset=self.asset, kind=AssetFile.Kind.MAIN,
            key='img/delete-fixture/image.webp', sha256='b' * 64,
            byte_size=10)
        models.QuerySet(model=Asset).filter(pk=self.asset.pk).update(
            status=Asset.Status.READY)
        self.asset.refresh_from_db()
        for kind, consumer, slot in (
                (AssetUsage.Kind.CURRENT_PAGE, self.page.pk, 'current'),
                (AssetUsage.Kind.ORDINARY_VERSION,
                 self.initial.pk, 'ordinary'),
                (AssetUsage.Kind.STABLE_VERSION,
                 self.stable_revision.pk, 'stable'),
                (AssetUsage.Kind.DRAFT, self.draft.pk, 'draft'),
                (AssetUsage.Kind.CURRENT_PAGE,
                 self.unrelated.pk, 'other-page'),
                (AssetUsage.Kind.SHARED_BLOCK, uuid4(), 'shared'),
                (AssetUsage.Kind.RETAINED_HTML, uuid4(), 'html')):
            AssetUsage.objects.create(
                asset=self.asset, kind=kind,
                consumer_id=consumer, slot=slot)

    def prepare(self):
        return page_delete.prepare(
            actor=self.owner, page_id=self.page.pk,
            generation=self.generation, session_key=self.session_key)

    def apply(self, prepared, **changes):
        data = {
            'actor': self.owner, 'page_id': self.page.pk,
            'generation': self.generation,
            'session_key': self.session_key,
            'token': prepared['token'],
            'operation_id': prepared['operation_id'],
            'confirm_name': self.page.name,
            'confirm_url': '/delete-me/', 'password': PASSWORD,
        }
        data.update(changes)
        return page_delete.apply(**data)

    def target_state(self):
        revision_ids = list(PageRevision.objects.filter(
            page=self.page).values_list('pk', flat=True))
        draft_ids = list(OwnerDraft.objects.filter(
            page=self.page).values_list('pk', flat=True))
        return {
            'page': Page.objects.filter(pk=self.page.pk).count(),
            'routes': Route.objects.filter(page=self.page).count(),
            'revisions': len(revision_ids),
            'metadata': RevisionMetadata.objects.filter(
                revision_id__in=revision_ids).count(),
            'stable': RevisionProtection.objects.filter(
                revision_id__in=revision_ids).count(),
            'state': PageContentState.objects.filter(page=self.page).count(),
            'drafts': len(draft_ids),
            'stages': RestoreStage.objects.filter(page=self.page).count(),
            'pins': VersionBasePin.objects.filter(
                revision_id__in=revision_ids).count(),
            'grants': PageGrant.objects.filter(page=self.page).count(),
            'home': PageMediaHome.objects.filter(page=self.page).count(),
            'usages': AssetUsage.objects.filter(
                models.Q(kind=AssetUsage.Kind.CURRENT_PAGE,
                         consumer_id=self.page.pk)
                | models.Q(kind__in=(AssetUsage.Kind.ORDINARY_VERSION,
                                     AssetUsage.Kind.STABLE_VERSION),
                           consumer_id__in=revision_ids)
                | models.Q(kind=AssetUsage.Kind.DRAFT,
                           consumer_id__in=draft_ids)).count(),
        }

    def test_delete_complete_scope_preserves_assets_shared_refs_and_ledgers(self):
        prepared = self.prepare()
        counts = prepared['counts']
        self.assertEqual((counts['routes'], counts['revisions'],
                          counts['stable'], counts['drafts'],
                          counts['stages']), (3, 2, 1, 1, 1))
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        all_audits = AuditEvent.objects.count()
        preserved_usage_ids = set(AssetUsage.objects.exclude(
            kind__in=(AssetUsage.Kind.ORDINARY_VERSION,
                      AssetUsage.Kind.STABLE_VERSION,
                      AssetUsage.Kind.DRAFT)).exclude(
            kind=AssetUsage.Kind.CURRENT_PAGE,
            consumer_id=self.page.pk).values_list('pk', flat=True))
        result = self.apply(prepared)
        self.assertFalse(result['replay'])
        self.assertEqual(self.target_state(), {
            key: 0 for key in self.target_state()})
        self.assertTrue(Page.objects.filter(pk=self.unrelated.pk).exists())
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())
        self.assertTrue(AssetFile.objects.filter(pk=self.file.pk).exists())
        self.assertTrue(MediaFolder.objects.filter(pk=self.folder.pk).exists())
        self.assertEqual(set(AssetUsage.objects.values_list(
            'pk', flat=True)), preserved_usage_ids)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.count(), all_audits + 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_DELETE_PAGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)
        for target in ('/delete-me/', '/delete-alias/', '/delete-old/'):
            self.assertEqual(resolve_target(target).state, 'unknown')

    def test_child_and_late_child_block_without_subtree_mutation(self):
        child = self.make_page('Child', '/delete-child/', parent=self.page)
        with self.assertRaises(TreeFault) as blocked:
            self.prepare()
        self.assertEqual(blocked.exception.code, 'PAGE_DELETE_HAS_CHILDREN')
        child.parent = self.unrelated
        child.save()
        prepared = self.prepare()
        child.parent = self.page
        child.save()
        before = self.target_state()
        with self.assertRaises(TreeFault) as late:
            self.apply(prepared)
        self.assertEqual(late.exception.code, 'PAGE_DELETE_HAS_CHILDREN')
        self.assertEqual(self.target_state(), before)
        self.assertTrue(Page.objects.filter(pk=child.pk).exists())

    def test_password_exact_confirmation_employee_and_stale_history_refused(self):
        for changes, error_type in (
                ({'password': OTHER}, PermissionDenied),
                ({'confirm_name': 'Wrong'}, TreeFault),
                ({'confirm_url': '/wrong/'}, TreeFault)):
            before = self.target_state()
            with self.subTest(changes=changes), self.assertRaises(
                    error_type):
                self.apply(self.prepare(), **changes)
            self.assertEqual(self.target_state(), before)

        prepared = self.prepare()
        payload = self.initial.payload
        late = PageRevision.objects.create(
            page=self.page, sequence=3,
            schema_version=payload['schema_version'], payload=payload,
            payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.MANUAL, author_id=self.owner.pk)
        RevisionMetadata.objects.create(revision=late, generation=1)
        with self.assertRaises(TreeFault) as stale:
            self.apply(prepared)
        self.assertEqual(stale.exception.code, 'PAGE_DELETE_BASIS_CHANGED')

        prepared = self.prepare()
        with self.assertRaises(PermissionDenied):
            page_delete.apply(
                actor=self.employee, page_id=self.page.pk, generation=1,
                session_key=self.session_key, token=prepared['token'],
                operation_id=prepared['operation_id'],
                confirm_name=self.page.name, confirm_url='/delete-me/',
                password=PASSWORD)
        self.assertTrue(Page.objects.filter(pk=self.page.pk).exists())

    def test_password_hash_change_between_checks_blocks_without_mutation(self):
        prepared = self.prepare()
        before = self.target_state()
        audits = AuditEvent.objects.count()
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        original = page_delete._password

        def change_hash_after_external_check(actor, supplied):
            verified = original(actor, supplied)
            get_user_model().objects.filter(pk=actor.pk).update(
                password=make_password(OTHER))
            return verified

        with patch('content.simple_page_delete._password',
                   side_effect=change_hash_after_external_check):
            with self.assertRaises(TreeFault) as ended:
                self.apply(prepared)
        self.assertEqual(ended.exception.code, 'TREE_SESSION_ENDED')
        self.assertEqual(self.target_state(), before)
        self.assertEqual(AuditEvent.objects.count(), audits)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertFalse(AuditEvent.objects.filter(
            object_ref__contains=PASSWORD).exists())

    def test_page_and_every_route_xmin_aba_make_confirmation_stale(self):
        before = self.target_state()
        prepared = self.prepare()
        original_name = self.page.name
        models.QuerySet(model=Page).filter(pk=self.page.pk).update(
            name='Temporary ABA name')
        models.QuerySet(model=Page).filter(pk=self.page.pk).update(
            name=original_name)
        with self.assertRaises(TreeFault) as page_stale:
            self.apply(prepared)
        self.assertEqual(page_stale.exception.code,
                         'PAGE_DELETE_BASIS_CHANGED')
        self.assertEqual(self.target_state(), before)

        routes = list(Route.objects.filter(page=self.page).order_by('kind'))
        for index, route in enumerate(routes):
            with self.subTest(kind=route.kind):
                prepared = self.prepare()
                original_target = route.target
                temporary = f'/delete-aba-{index}/'
                models.QuerySet(model=Route).filter(pk=route.pk).update(
                    target=temporary)
                models.QuerySet(model=Route).filter(pk=route.pk).update(
                    target=original_target)
                with self.assertRaises(TreeFault) as route_stale:
                    self.apply(prepared)
                self.assertEqual(route_stale.exception.code,
                                 'PAGE_DELETE_BASIS_CHANGED')
                self.assertEqual(self.target_state(), before)

    def test_audit_failure_rolls_back_everything(self):
        prepared = self.prepare()
        before = self.target_state()
        with patch('content.simple_page_delete.record_event',
                   side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):
                self.apply(prepared)
        self.assertEqual(self.target_state(), before)
        self.assertTrue(Asset.objects.filter(pk=self.asset.pk).exists())
        self.assertFalse(AuditEvent.objects.filter(
            code='TREE_DELETE_PAGE',
            object_ref='uuid:' + str(self.page.pk)).exists())

    def test_concurrent_delete_one_apply_one_replay_and_new_url_safe(self):
        prepared = self.prepare()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.apply(prepared)['replay']
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_DELETE_PAGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)
        replacement = self.make_page('Replacement', '/delete-me/')
        replay = self.apply(prepared)
        self.assertTrue(replay['replay'])
        self.assertTrue(Page.objects.filter(pk=replacement.pk).exists())
        self.assertEqual(Route.objects.get(
            page=replacement, kind=Route.Kind.PRIMARY).target,
            '/delete-me/')

    def test_http_roles_csrf_password_privacy_and_success(self):
        url = '/manage/pages/' + str(self.page.pk) + '/delete/'
        before = self.target_state()
        form = self.browser.get(url)
        self.assertEqual(form.status_code, 200)
        self.assertEqual(self.target_state(), before)
        wrong = self.browser.post(url, {
            **form.context['values'], 'confirm_name': self.page.name,
            'confirm_url': '/delete-me/', 'password': OTHER,
        }, content_type='application/x-www-form-urlencoded')
        self.assertEqual(wrong.status_code, 403)
        self.assertNotContains(wrong, OTHER, status_code=403)
        self.assertNotContains(wrong, PASSWORD, status_code=403)

        employee = client()
        self.assertEqual(login(
            employee, 'page-delete-employee').status_code, 303)
        self.assertEqual(employee.get(url).status_code, 403)
        self.assertEqual(client().get(url).status_code, 401)
        csrf = client(csrf=True)
        csrf.cookies = self.browser.cookies
        self.assertEqual(csrf.post(
            url, {**form.context['values'],
                  'confirm_name': self.page.name,
                  'confirm_url': '/delete-me/', 'password': PASSWORD},
            content_type='application/x-www-form-urlencoded').status_code,
            403)

        response = self.browser.post(url, {
            **form.context['values'], 'confirm_name': self.page.name,
            'confirm_url': '/delete-me/', 'password': PASSWORD,
        }, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['X-Tree-Result'], 'applied')
        self.assertFalse(Page.objects.filter(pk=self.page.pk).exists())

    def test_http_lost_response_commit_then_retry_without_password_echo(self):
        url = '/manage/pages/' + str(self.page.pk) + '/delete/'
        form = self.browser.get(url)
        values = {
            **form.context['values'], 'confirm_name': self.page.name,
            'confirm_url': '/delete-me/', 'password': PASSWORD,
        }
        original = page_delete.apply

        def committed_then_lost(**kwargs):
            result = original(**kwargs)
            self.assertFalse(connection.in_atomic_block)
            close_old_connections()
            self.assertFalse(Page.objects.filter(pk=self.page.pk).exists())
            self.assertEqual(AuditEvent.objects.filter(
                code='TREE_DELETE_PAGE',
                object_ref='uuid:' + str(self.page.pk)).count(), 1)
            self.assertFalse(result['replay'])
            raise DatabaseError('synthetic lost response after commit')

        with patch('content.page_delete_views.page_delete.apply',
                   side_effect=committed_then_lost):
            response = self.browser.post(
                url, values,
                content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, PASSWORD, status_code=503)
        self.assertEqual(response.context['values']['confirm_name'],
                         self.page.name)
        repeated = self.browser.post(url, {
            **response.context['values'], 'password': PASSWORD,
        }, content_type='application/x-www-form-urlencoded')
        self.assertEqual(repeated.status_code, 303)
        self.assertEqual(repeated['X-Tree-Result'], 'replay')
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_DELETE_PAGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)
