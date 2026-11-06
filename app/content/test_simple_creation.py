"""Focused REF-05K tests for receipt-free local page creation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import UUID, uuid4

from django.apps import apps
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import UserProfile
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from audit.models import AuditEvent
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  OwnerDraft, PageContentState,
                                  PageRevision, RevisionMetadata,
                                  VersionBasePin)

from . import creation as legacy, simple_creation as simple
from .models import Page, Route
from .reads import public_tree
from .tree_commands import TreeFault


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   DEV29_LOCAL_CREATE_ENABLED=True, ENVIRONMENT='test')
class SimpleCreationTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='simple-create-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.parent = Page.objects.create(
            name='Catalog', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        Route.objects.create(
            page=self.parent, kind=Route.Kind.PRIMARY,
            target='/catalog/')
        self.unrelated = Page.objects.create(
            name='Unrelated', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        Route.objects.create(
            page=self.unrelated, kind=Route.Kind.PRIMARY,
            target='/unrelated/')

    def prepare(self, **values):
        return simple.prepare(
            actor=self.owner, generation=self.generation,
            session_key=self.session_key, **values)

    def apply(self, prepared, **values):
        data = {
            'actor': self.owner, 'generation': self.generation,
            'session_key': self.session_key,
            'token': prepared['token'],
            'operation_id': prepared['operation_id'],
            'page_id': prepared['page_id'],
            'parent_id': prepared['parent_id'], 'kind': prepared['kind'],
            'name': 'Created page',
            'url': '/created-' + prepared['page_id'] + '/',
            'h1': 'Independent H1', 'title': 'Independent title',
        }
        data.update(values)
        return simple.apply(**data)

    def state(self):
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in ('content', 'page_versions', 'media_library',
                          'audit')
            for model in apps.get_app_config(label).get_models()
        }

    def test_create_exact_hidden_aggregate_without_tree_ledger(self):
        prepared = self.prepare(parent_id=self.parent.pk)
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        result = self.apply(prepared)
        page = Page.objects.get(pk=prepared['page_id'])
        self.assertFalse(result['replayed'])
        self.assertEqual((page.parent_id, page.position, page.is_published),
                         (self.parent.pk, 0, False))
        route = Route.objects.get(page=page)
        self.assertEqual((route.kind, route.target),
                         (Route.Kind.PRIMARY,
                          '/created-' + prepared['page_id'] + '/'))
        revision = PageRevision.objects.get(page=page)
        self.assertEqual((revision.kind, revision.sequence), ('initial', 1))
        self.assertEqual(RevisionMetadata.objects.get(
            revision=revision).generation, 1)
        self.assertEqual(PageContentState.objects.get(
            page=page).current_revision_id, revision.pk)
        draft = OwnerDraft.objects.get(page=page)
        self.assertEqual(draft.base_revision_id, revision.pk)
        self.assertTrue(VersionBasePin.objects.filter(
            revision=revision, holder_kind='owner_draft',
            holder_id=draft.pk).exists())
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=prepared['operation_id']).exists())
        self.assertFalse(IdentityReservation.objects.filter(
            pk__in=[prepared['operation_id'], prepared['page_id']]).exists())
        self.assertEqual(IdentityReservation.objects.count(), identities + 2)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_CREATE',
            object_ref='uuid:' + prepared['page_id']).count(), 1)
        self.assertNotIn(page.pk, [entry['id'] for entry in public_tree()])

    def test_exact_repeat_replays_and_changed_result_conflicts(self):
        prepared = self.prepare(parent_id=self.parent.pk)
        self.apply(prepared)
        after = self.state()
        replay = self.apply(prepared)
        self.assertTrue(replay['replayed'])
        self.assertEqual(self.state(), after)
        for change in ({'name': 'Changed'}, {'url': '/changed/'},
                       {'h1': 'Changed'}, {'title': 'Changed'}):
            with self.subTest(change=change):
                with self.assertRaises(TreeFault):
                    self.apply(prepared, **change)
                self.assertEqual(self.state(), after)

    def test_parent_and_sibling_aba_stale_but_unrelated_change_is_local(self):
        parent_stale = self.prepare(parent_id=self.parent.pk)
        self.parent.name = 'Temporary'
        self.parent.save()
        self.parent.name = 'Catalog'
        self.parent.save()
        with self.assertRaises(TreeFault) as parent:
            self.apply(parent_stale)
        self.assertEqual(parent.exception.code, 'CREATE_BASIS_CHANGED')

        sibling_stale = self.prepare(parent_id=self.parent.pk)
        sibling = Page.objects.create(
            name='Sibling', kind=Page.Kind.ARTICLE, parent=self.parent)
        with self.assertRaises(TreeFault) as changed:
            self.apply(sibling_stale)
        self.assertEqual(changed.exception.code, 'CREATE_BASIS_CHANGED')

        local = self.prepare(parent_id=self.parent.pk)
        self.unrelated.name = 'Changed elsewhere'
        self.unrelated.save()
        result = self.apply(local)
        self.assertFalse(result['replayed'])
        self.assertTrue(Page.objects.filter(pk=result['page_id']).exists())
        self.assertTrue(Page.objects.filter(pk=sibling.pk).exists())

    def test_invalid_url_collision_ids_employee_and_token_are_refused(self):
        for target in ('/manage/', '/wp-admin/', '/.env',
                       '//foreign/', '/bad?query=1'):
            prepared = self.prepare()
            with self.subTest(target=target), self.assertRaises(
                    (TreeFault, ValidationError)):
                self.apply(prepared, url=target)
        occupied = self.prepare()
        with self.assertRaises(TreeFault) as url:
            self.apply(occupied, url='/catalog/')
        self.assertEqual(url.exception.code, 'CREATE_URL_CONFLICT')

        reserved = self.prepare(operation_id=uuid4())
        IdentityReservation.objects.create(
            id=UUID(reserved['operation_id']), kind='synthetic')
        with self.assertRaises(TreeFault) as operation:
            self.apply(reserved)
        self.assertEqual(operation.exception.code,
                         'CREATE_OPERATION_CONFLICT')

        prepared = self.prepare()
        with self.assertRaises(TreeFault):
            simple.apply(
                actor=self.owner, generation=self.generation,
                session_key=self.session_key,
                token=prepared['token'] + 'x',
                operation_id=prepared['operation_id'],
                page_id=prepared['page_id'], parent_id='',
                kind=prepared['kind'], name='Name', url='/name/',
                h1='H1', title='Title')
        with self.assertRaises(PermissionDenied):
            simple.apply(
                actor=self.employee, generation=1,
                session_key=self.session_key, token='invalid',
                operation_id=prepared['operation_id'],
                page_id=prepared['page_id'], parent_id='',
                kind=prepared['kind'], name='Name', url='/name/',
                h1='H1', title='Title')

    def test_preexisting_page_id_without_create_evidence_conflicts(self):
        prepared = self.prepare()
        Page.objects.create(
            id=UUID(prepared['page_id']), name='Created page',
            kind=prepared['kind'], is_published=False)
        before = self.state()
        with self.assertRaises(TreeFault) as conflict:
            self.apply(prepared)
        self.assertEqual(conflict.exception.code, 'CREATE_ID_CONFLICT')
        self.assertEqual(self.state(), before)

    def test_concurrent_double_submit_creates_one_aggregate_and_one_audit(self):
        prepared = self.prepare(parent_id=self.parent.pk)
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.apply(prepared)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(sum(not row['replayed'] for row in results), 1)
        self.assertEqual(sum(row['replayed'] for row in results), 1)
        self.assertEqual(Page.objects.filter(
            pk=prepared['page_id']).count(), 1)
        self.assertEqual(PageRevision.objects.filter(
            page_id=prepared['page_id']).count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_CREATE',
            object_ref='uuid:' + prepared['page_id']).count(), 1)

    def test_audit_failure_rolls_back_whole_aggregate(self):
        prepared = self.prepare(parent_id=self.parent.pk)
        before = self.state()
        with patch('content.simple_creation.record_event',
                   side_effect=RuntimeError(
                       'SYNTHETIC_CREATE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_CREATE_AUDIT_FAILURE'):
                self.apply(prepared)
        self.assertEqual(self.state(), before)
        self.assertFalse(self.apply(prepared)['replayed'])

    def test_legacy_receipt_exact_replays_through_http(self):
        prepared = legacy.prepare(
            actor=self.owner, generation=self.generation,
            session_key=self.session_key)
        values = {
            'actor': self.owner, 'generation': self.generation,
            'session_key': self.session_key, 'token': prepared['token'],
            'operation_id': prepared['operation_id'],
            'page_id': prepared['page_id'], 'parent_id': '',
            'kind': prepared['kind'], 'name': 'Legacy page',
            'url': '/legacy-created/', 'h1': 'H1', 'title': 'Title',
        }
        legacy.apply(**values)
        response = self.browser.post('/manage/pages/new/', {
            **{key: value for key, value in values.items()
               if key not in ('actor', 'generation', 'session_key')},
            'step': 'save'},
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['X-Tree-Result'], 'replay')
