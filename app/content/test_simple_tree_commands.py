"""Focused REF-5 rename tests for the receipt-free PostgreSQL command."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, close_old_connections, transaction
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import UserProfile
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from audit.models import AuditEvent
from media_library.models import AssetUsage
from page_versions import schema, services as versions
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  OwnerDraft, PageContentState,
                                  PageRevision, RevisionProtection)

from .models import Page, Route
from . import simple_tree_commands as simple, tree_commands as legacy


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimpleRenameTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='simple-rename-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.parent = Page.objects.create(
            name='Parent', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.page = Page.objects.create(
            name='Original', kind=Page.Kind.ARTICLE, parent=self.parent,
            is_published=True)
        Route.objects.create(
            page=self.page, target='/Exact?Case=X',
            kind=Route.Kind.PRIMARY, is_legacy=True)
        Route.objects.create(
            page=self.page, target='/alias/', kind=Route.Kind.ALIAS)
        self.initial = versions.initialize(
            actor=self.owner, page_id=self.page.pk,
            snapshot=schema.snapshot_v1(
                self.page.kind, main_text='Body', h1='Independent H1',
                title='Independent SEO'), expected_generation=1,
            operation_id=uuid4())['result_id']

    def prepare(self):
        return simple.prepare_rename(
            actor=self.owner, page_id=self.page.pk,
            generation=self.generation, session_key=self.session_key)

    def rename(self, prepared, name='Renamed'):
        return simple.rename(
            actor=self.owner, page_id=self.page.pk,
            generation=self.generation, session_key=self.session_key,
            token=prepared['token'],
            operation_id=prepared['operation_id'], name=name)

    def protected_state(self):
        return {
            'routes': list(Route.objects.order_by('id').values()),
            'page_context': list(Page.objects.filter(pk=self.page.pk).values(
                'id', 'kind', 'parent_id', 'position', 'is_published')),
            'revisions': list(PageRevision.objects.order_by('id').values()),
            'states': list(PageContentState.objects.order_by('id').values()),
            'stable': list(RevisionProtection.objects.order_by('id').values()),
            'drafts': list(OwnerDraft.objects.order_by('id').values()),
            'usages': list(AssetUsage.objects.order_by('id').values()),
        }

    def test_rename_changes_only_name_and_audit_without_ledger(self):
        prepared = self.prepare()
        protected = self.protected_state()
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        audits = AuditEvent.objects.filter(code='TREE_RENAME').count()
        result = self.rename(prepared, 'New catalogue name')
        self.page.refresh_from_db()
        self.assertEqual(self.page.name, 'New catalogue name')
        self.assertFalse(result['replay'])
        self.assertEqual(self.protected_state(), protected)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_RENAME').count(), audits + 1)
        payload = PageRevision.objects.get(pk=self.initial).payload
        self.assertEqual(payload['h1'], 'Independent H1')
        self.assertEqual(payload['title'], 'Independent SEO')

    def test_invalid_tampered_employee_and_repeat_do_not_mutate(self):
        prepared = self.prepare()
        before = self.protected_state()
        before_name = self.page.name
        for value in ('', '   ', 'x' * 201, 'bad\nname', '\ud800'):
            with self.subTest(value=repr(value)):
                with self.assertRaises(legacy.TreeFault):
                    self.rename(prepared, value)
        with self.assertRaises(legacy.TreeFault):
            simple.rename(
                actor=self.owner, page_id=self.page.pk,
                generation=self.generation, session_key=self.session_key,
                token=prepared['token'] + 'x',
                operation_id=prepared['operation_id'], name='Tampered')
        with self.assertRaises(PermissionDenied):
            simple.rename(
                actor=self.employee, page_id=self.page.pk,
                generation=1, session_key=self.session_key,
                token=prepared['token'],
                operation_id=prepared['operation_id'], name='Employee')
        with self.assertRaises(legacy.TreeFault):
            self.rename(prepared, before_name)
        self.page.refresh_from_db()
        self.assertEqual(self.page.name, before_name)
        self.assertEqual(self.protected_state(), before)

    def test_stale_and_aba_row_version_are_rejected(self):
        prepared = self.prepare()
        self.page.name = 'Intermediate'
        self.page.save()
        self.page.name = 'Original'
        self.page.save()
        with self.assertRaises(legacy.TreeFault) as caught:
            self.rename(prepared, 'Must not apply')
        self.assertEqual(caught.exception.code, 'TREE_BASIS_CHANGED')
        self.page.refresh_from_db()
        self.assertEqual(self.page.name, 'Original')

    def test_concurrent_double_submit_has_one_change_and_one_audit(self):
        prepared = self.prepare()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return self.rename(prepared, 'Concurrent rename')
                except legacy.TreeFault as error:
                    return error.code
            finally:
                close_old_connections()

        before = AuditEvent.objects.filter(code='TREE_RENAME').count()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(len([row for row in results if isinstance(row, dict)]), 1)
        self.assertEqual(results.count('TREE_BASIS_CHANGED'), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_RENAME').count(), before + 1)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=prepared['operation_id']).exists())
        self.assertFalse(IdentityReservation.objects.filter(
            pk=prepared['operation_id']).exists())

    def test_audit_failure_rolls_back_name(self):
        prepared = self.prepare()
        before = self.protected_state()
        with patch('content.simple_tree_commands.record_event',
                   side_effect=RuntimeError('SYNTHETIC_RENAME_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_RENAME_AUDIT_FAILURE'):
                self.rename(prepared, 'Must rollback')
        self.page.refresh_from_db()
        self.assertEqual(self.page.name, 'Original')
        self.assertEqual(self.protected_state(), before)

    def test_legacy_receipt_replays_through_http(self):
        old = legacy.prepare(
            actor=self.owner, page_id=self.page.pk, action='rename',
            generation=self.generation, session_key=self.session_key)
        legacy.apply(
            actor=self.owner, page_id=self.page.pk, action='rename',
            generation=self.generation, session_key=self.session_key,
            token=old['token'], operation_id=old['operation_id'],
            name='Legacy committed')
        path = '/manage/pages/%s/structure/rename/' % self.page.pk
        response = self.browser.post(path, {
            'operation_id': old['operation_id'], 'token': old['token'],
            'name': 'Legacy committed'},
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['X-Tree-Result'], 'replay')
        self.assertEqual(OperationReceipt.objects.filter(
            pk=old['operation_id']).count(), 1)

        move = legacy.prepare(
            actor=self.owner, page_id=self.page.pk, action='move',
            generation=self.generation, session_key=self.session_key,
            destination=None)
        legacy.apply(
            actor=self.owner, page_id=self.page.pk, action='move',
            generation=self.generation, session_key=self.session_key,
            token=move['token'], operation_id=move['operation_id'],
            parent_id='', before_id='')
        before_name = Page.objects.get(pk=self.page.pk).name
        mismatch = self.browser.post(path, {
            'operation_id': move['operation_id'], 'token': move['token'],
            'name': 'Cross action must fail'},
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(Page.objects.get(pk=self.page.pk).name, before_name)


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimpleReorderTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='simple-reorder-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.parent = Page.objects.create(
            name='Parent', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.other_parent = Page.objects.create(
            name='Other parent', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.a = Page.objects.create(
            name='A', kind=Page.Kind.ARTICLE, parent=self.parent,
            is_published=True)
        self.b = Page.objects.create(
            name='B', kind=Page.Kind.ARTICLE, parent=self.parent,
            is_published=False)
        self.c = Page.objects.create(
            name='C', kind=Page.Kind.ARTICLE, parent=self.parent,
            is_published=True)
        self.foreign = Page.objects.create(
            name='Foreign', kind=Page.Kind.ARTICLE,
            parent=self.other_parent, is_published=True)
        Route.objects.create(page=self.a, target='/a/', kind=Route.Kind.PRIMARY)
        self.initial = versions.initialize(
            actor=self.owner, page_id=self.a.pk,
            snapshot=schema.snapshot_v1(
                self.a.kind, main_text='Body', h1='H1', title='SEO'),
            expected_generation=1, operation_id=uuid4())['result_id']

    def prepare(self, page=None):
        return simple.prepare_reorder(
            actor=self.owner, page_id=(page or self.a).pk,
            generation=self.generation, session_key=self.session_key)

    def reorder(self, prepared, *, parent_id=None, before_id=None):
        return simple.reorder(
            actor=self.owner, page_id=prepared['page'].pk,
            generation=self.generation, session_key=self.session_key,
            token=prepared['token'], operation_id=prepared['operation_id'],
            parent_id=(prepared['destination'] if parent_id is None
                       else parent_id),
            before_id=('' if before_id is None else before_id))

    def order(self, parent=None):
        parent = self.parent if parent is None else parent
        return list(Page.objects.filter(parent=parent).order_by(
            'position', 'id').values_list('id', 'position'))

    def protected_state(self):
        return {
            'routes': list(Route.objects.order_by('id').values()),
            'page_fields': list(Page.objects.order_by('id').values(
                'id', 'name', 'kind', 'parent_id', 'is_published')),
            'revisions': list(PageRevision.objects.order_by('id').values()),
            'states': list(PageContentState.objects.order_by('id').values()),
            'stable': list(RevisionProtection.objects.order_by('id').values()),
            'drafts': list(OwnerDraft.objects.order_by('id').values()),
            'usages': list(AssetUsage.objects.order_by('id').values()),
        }

    def test_reorder_changes_only_sibling_positions_and_audit_without_ledger(self):
        prepared = self.prepare(self.c)
        protected = self.protected_state()
        foreign = self.order(self.other_parent)
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        audits = AuditEvent.objects.filter(code='TREE_REORDER').count()
        result = self.reorder(prepared, before_id=str(self.a.pk))
        self.assertFalse(result['replay'])
        self.assertEqual(self.order(), [
            (self.c.pk, 0), (self.a.pk, 1), (self.b.pk, 2)])
        self.assertEqual(self.order(self.other_parent), foreign)
        self.assertEqual(self.protected_state(), protected)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_REORDER').count(), audits + 1)

    def test_tampered_parent_foreign_neighbour_employee_and_noop_refused(self):
        prepared = self.prepare()
        before = self.order()
        with self.assertRaises(legacy.TreeFault) as parent:
            self.reorder(prepared, parent_id=str(self.other_parent.pk))
        self.assertEqual(parent.exception.code, 'TREE_DESTINATION_CHANGED')
        with self.assertRaises(legacy.TreeFault) as neighbour:
            self.reorder(prepared, before_id=str(self.foreign.pk))
        self.assertEqual(neighbour.exception.code, 'TREE_NEIGHBOUR_CONFLICT')
        with self.assertRaises(legacy.TreeFault):
            simple.reorder(
                actor=self.owner, page_id=self.a.pk,
                generation=self.generation, session_key=self.session_key,
                token=prepared['token'] + 'x',
                operation_id=prepared['operation_id'],
                parent_id=prepared['destination'], before_id='')
        with self.assertRaises(PermissionDenied):
            simple.reorder(
                actor=self.employee, page_id=self.a.pk, generation=1,
                session_key=self.session_key, token='invalid',
                operation_id=prepared['operation_id'],
                parent_id=prepared['destination'], before_id='')
        noop = self.prepare(self.c)
        with self.assertRaises(legacy.TreeFault) as unchanged:
            self.reorder(noop, before_id='')
        self.assertEqual(unchanged.exception.code, 'TREE_ORDER_UNCHANGED')
        self.assertEqual(self.order(), before)

    def test_unrelated_branch_change_does_not_make_local_order_stale(self):
        prepared = self.prepare(self.c)
        self.foreign.name = 'Unrelated rename'
        self.foreign.save()
        self.reorder(prepared, before_id=str(self.a.pk))
        self.assertEqual([row[0] for row in self.order()],
                         [self.c.pk, self.a.pk, self.b.pk])

    def test_stale_and_aba_sibling_versions_are_rejected(self):
        prepared = self.prepare(self.c)
        with transaction.atomic():
            self.b.position = 2
            self.b.save()
            self.c.position = 1
            self.c.save()
        with transaction.atomic():
            self.b.position = 1
            self.b.save()
            self.c.position = 2
            self.c.save()
        with self.assertRaises(legacy.TreeFault) as caught:
            self.reorder(prepared, before_id=str(self.a.pk))
        self.assertEqual(caught.exception.code, 'TREE_BASIS_CHANGED')
        self.assertEqual(self.order(), [
            (self.a.pk, 0), (self.b.pk, 1), (self.c.pk, 2)])

    def test_concurrent_double_submit_has_one_order_and_one_audit(self):
        prepared = self.prepare(self.c)
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return self.reorder(
                        prepared, before_id=str(self.a.pk))
                except legacy.TreeFault as error:
                    return error.code
            finally:
                close_old_connections()

        before = AuditEvent.objects.filter(code='TREE_REORDER').count()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(len([row for row in results
                              if isinstance(row, dict)]), 1)
        self.assertEqual(results.count('TREE_BASIS_CHANGED'), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_REORDER').count(), before + 1)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=prepared['operation_id']).exists())
        self.assertFalse(IdentityReservation.objects.filter(
            pk=prepared['operation_id']).exists())

    def test_audit_failure_rolls_back_all_positions(self):
        prepared = self.prepare(self.c)
        before = self.order()
        with patch('content.simple_tree_commands.record_event',
                   side_effect=RuntimeError(
                       'SYNTHETIC_REORDER_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_REORDER_AUDIT_FAILURE'):
                self.reorder(prepared, before_id=str(self.a.pk))
        self.assertEqual(self.order(), before)

    def test_http_success_lost_response_repeat_and_legacy_replay(self):
        path = f'/manage/pages/{self.c.pk}/structure/reorder/'
        prepared = self.browser.get(path).context['prepared']
        data = {
            'operation_id': prepared['operation_id'],
            'token': prepared['token'],
            'parent_id': prepared['destination'],
            'before_id': str(self.a.pk),
        }
        original = simple.reorder

        def lost(**kwargs):
            result = original(**kwargs)
            raise DatabaseError('SYNTHETIC confirmation lost after COMMIT')

        with patch.object(simple, 'reorder', lost):
            response = self.browser.post(
                path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.assertEqual([row[0] for row in self.order()],
                         [self.c.pk, self.a.pk, self.b.pk])
        repeat = self.browser.post(
            path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(repeat.status_code, 409)

        legacy_prepared = legacy.prepare(
            actor=self.owner, page_id=self.c.pk, action='reorder',
            generation=self.generation, session_key=self.session_key)
        legacy.apply(
            actor=self.owner, page_id=self.c.pk, action='reorder',
            generation=self.generation, session_key=self.session_key,
            token=legacy_prepared['token'],
            operation_id=legacy_prepared['operation_id'], name=None,
            parent_id=legacy_prepared['destination'], before_id='')
        replay = self.browser.post(path, {
            'operation_id': legacy_prepared['operation_id'],
            'token': legacy_prepared['token'],
            'parent_id': legacy_prepared['destination'],
            'before_id': ''},
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(replay.status_code, 303)
        self.assertEqual(replay['X-Tree-Result'], 'replay')


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimpleMoveTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='simple-move-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.source = Page.objects.create(
            name='Source', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.destination = Page.objects.create(
            name='Destination', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.unrelated = Page.objects.create(
            name='Unrelated', kind=Page.Kind.SERVICE_CATALOG,
            is_published=True)
        self.a = Page.objects.create(
            name='A', kind=Page.Kind.ARTICLE, parent=self.source,
            is_published=True)
        self.b = Page.objects.create(
            name='B', kind=Page.Kind.ARTICLE, parent=self.source,
            is_published=False)
        self.child = Page.objects.create(
            name='Child', kind=Page.Kind.ARTICLE, parent=self.a,
            is_published=True)
        self.d = Page.objects.create(
            name='D', kind=Page.Kind.ARTICLE, parent=self.destination,
            is_published=True)
        self.e = Page.objects.create(
            name='E', kind=Page.Kind.ARTICLE, parent=self.destination,
            is_published=False)
        self.foreign = Page.objects.create(
            name='Foreign', kind=Page.Kind.ARTICLE,
            parent=self.unrelated, is_published=True)
        Route.objects.create(page=self.a, target='/a/', kind=Route.Kind.PRIMARY)
        self.initial = versions.initialize(
            actor=self.owner, page_id=self.a.pk,
            snapshot=schema.snapshot_v1(
                self.a.kind, main_text='Body', h1='H1', title='SEO'),
            expected_generation=1, operation_id=uuid4())['result_id']

    def prepare(self, destination='current'):
        return simple.prepare_move(
            actor=self.owner, page_id=self.a.pk,
            generation=self.generation, session_key=self.session_key,
            destination=destination)

    def move(self, prepared, *, parent_id=None, before_id=None):
        return simple.move(
            actor=self.owner, page_id=self.a.pk,
            generation=self.generation, session_key=self.session_key,
            token=prepared['token'], operation_id=prepared['operation_id'],
            parent_id=(prepared['destination'] if parent_id is None
                       else parent_id),
            before_id=('' if before_id is None else before_id))

    def order(self, parent):
        return list(Page.objects.filter(parent=parent).order_by(
            'position', 'id').values_list('id', 'position'))

    def protected_state(self):
        return {
            'routes': list(Route.objects.order_by('id').values()),
            'page_fields': list(Page.objects.order_by('id').values(
                'id', 'name', 'kind', 'is_published')),
            'revisions': list(PageRevision.objects.order_by('id').values()),
            'states': list(PageContentState.objects.order_by('id').values()),
            'stable': list(RevisionProtection.objects.order_by('id').values()),
            'drafts': list(OwnerDraft.objects.order_by('id').values()),
            'usages': list(AssetUsage.objects.order_by('id').values()),
        }

    def test_move_changes_only_two_groups_parent_positions_and_one_audit(self):
        prepared = self.prepare(str(self.destination.pk))
        protected = self.protected_state()
        unrelated = self.order(self.unrelated)
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        audits = AuditEvent.objects.filter(code='TREE_MOVE').count()
        result = self.move(prepared, before_id=str(self.e.pk))
        self.assertFalse(result['replay'])
        self.a.refresh_from_db()
        self.child.refresh_from_db()
        self.assertEqual(self.a.parent_id, self.destination.pk)
        self.assertEqual(self.order(self.source), [(self.b.pk, 0)])
        self.assertEqual(self.order(self.destination), [
            (self.d.pk, 0), (self.a.pk, 1), (self.e.pk, 2)])
        self.assertEqual(self.child.parent_id, self.a.pk)
        self.assertEqual(self.order(self.unrelated), unrelated)
        self.assertEqual(self.protected_state(), protected)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_MOVE').count(), audits + 1)

    def test_root_same_parent_noop_and_same_parent_reorder(self):
        root = self.prepare('')
        self.move(root)
        self.a.refresh_from_db()
        self.assertIsNone(self.a.parent_id)
        self.assertEqual(self.order(self.source), [(self.b.pk, 0)])

        same = simple.prepare_move(
            actor=self.owner, page_id=self.b.pk,
            generation=self.generation, session_key=self.session_key)
        with self.assertRaises(legacy.TreeFault) as unchanged:
            simple.move(
                actor=self.owner, page_id=self.b.pk,
                generation=self.generation, session_key=self.session_key,
                token=same['token'], operation_id=same['operation_id'],
                parent_id=same['destination'], before_id='')
        self.assertEqual(unchanged.exception.code, 'TREE_ORDER_UNCHANGED')

        extra = Page.objects.create(
            name='Extra', kind=Page.Kind.ARTICLE, parent=self.source)
        reorder = simple.prepare_move(
            actor=self.owner, page_id=extra.pk,
            generation=self.generation, session_key=self.session_key)
        simple.move(
            actor=self.owner, page_id=extra.pk,
            generation=self.generation, session_key=self.session_key,
            token=reorder['token'], operation_id=reorder['operation_id'],
            parent_id=reorder['destination'], before_id=str(self.b.pk))
        self.assertEqual(self.order(self.source), [
            (extra.pk, 0), (self.b.pk, 1)])

    def test_cycles_tampering_foreign_neighbour_and_employee_refused(self):
        for destination in (str(self.a.pk), str(self.child.pk)):
            with self.subTest(destination=destination):
                with self.assertRaises(legacy.TreeFault) as cycle:
                    self.prepare(destination)
                self.assertEqual(cycle.exception.code,
                                 'TREE_PARENT_CONFLICT')
        prepared = self.prepare(str(self.destination.pk))
        before_source = self.order(self.source)
        before_destination = self.order(self.destination)
        with self.assertRaises(legacy.TreeFault) as changed:
            self.move(prepared, parent_id=str(self.unrelated.pk))
        self.assertEqual(changed.exception.code, 'TREE_DESTINATION_CHANGED')
        with self.assertRaises(legacy.TreeFault) as neighbour:
            self.move(prepared, before_id=str(self.foreign.pk))
        self.assertEqual(neighbour.exception.code, 'TREE_NEIGHBOUR_CONFLICT')
        with self.assertRaises(legacy.TreeFault):
            simple.move(
                actor=self.owner, page_id=self.a.pk,
                generation=self.generation, session_key=self.session_key,
                token=prepared['token'] + 'x',
                operation_id=prepared['operation_id'],
                parent_id=prepared['destination'], before_id='')
        with self.assertRaises(PermissionDenied):
            simple.move(
                actor=self.employee, page_id=self.a.pk, generation=1,
                session_key=self.session_key, token='invalid',
                operation_id=prepared['operation_id'],
                parent_id=prepared['destination'], before_id='')
        self.assertEqual(self.order(self.source), before_source)
        self.assertEqual(self.order(self.destination), before_destination)

    def test_unrelated_branch_change_does_not_make_move_stale(self):
        prepared = self.prepare(str(self.destination.pk))
        self.foreign.name = 'Unrelated rename'
        self.foreign.save()
        self.move(prepared, before_id=str(self.d.pk))
        self.a.refresh_from_db()
        self.assertEqual(self.a.parent_id, self.destination.pk)

    def test_sibling_and_ancestry_aba_are_rejected(self):
        prepared = self.prepare(str(self.destination.pk))
        with transaction.atomic():
            self.d.position = 1
            self.d.save()
            self.e.position = 0
            self.e.save()
        with transaction.atomic():
            self.d.position = 0
            self.d.save()
            self.e.position = 1
            self.e.save()
        with self.assertRaises(legacy.TreeFault) as sibling:
            self.move(prepared, before_id=str(self.d.pk))
        self.assertEqual(sibling.exception.code, 'TREE_BASIS_CHANGED')

        ancestry = self.prepare(str(self.destination.pk))
        self.destination.name = 'Temporary destination name'
        self.destination.save()
        self.destination.name = 'Destination'
        self.destination.save()
        with self.assertRaises(legacy.TreeFault) as parent:
            self.move(ancestry, before_id=str(self.d.pk))
        self.assertEqual(parent.exception.code, 'TREE_BASIS_CHANGED')

    def test_concurrent_double_submit_has_one_move_and_one_audit(self):
        prepared = self.prepare(str(self.destination.pk))
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return self.move(prepared, before_id=str(self.d.pk))
                except legacy.TreeFault as error:
                    return error.code
            finally:
                close_old_connections()

        before = AuditEvent.objects.filter(code='TREE_MOVE').count()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(len([row for row in results
                              if isinstance(row, dict)]), 1)
        self.assertEqual(results.count('TREE_BASIS_CHANGED'), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_MOVE').count(), before + 1)
        self.assertFalse(OperationReceipt.objects.filter(
            pk=prepared['operation_id']).exists())
        self.assertFalse(IdentityReservation.objects.filter(
            pk=prepared['operation_id']).exists())

    def test_audit_failure_rolls_back_parent_and_both_groups(self):
        prepared = self.prepare(str(self.destination.pk))
        source = self.order(self.source)
        destination = self.order(self.destination)
        with patch('content.simple_tree_commands.record_event',
                   side_effect=RuntimeError('SYNTHETIC_MOVE_AUDIT_FAILURE')):
            with self.assertRaisesRegex(
                    RuntimeError, 'SYNTHETIC_MOVE_AUDIT_FAILURE'):
                self.move(prepared, before_id=str(self.d.pk))
        self.a.refresh_from_db()
        self.assertEqual(self.a.parent_id, self.source.pk)
        self.assertEqual(self.order(self.source), source)
        self.assertEqual(self.order(self.destination), destination)

    def test_http_lost_response_repeat_and_legacy_exact_replay(self):
        path = f'/manage/pages/{self.a.pk}/structure/move/'
        prepared = self.browser.get(
            path, {'parent': str(self.destination.pk)}).context['prepared']
        data = {
            'operation_id': prepared['operation_id'],
            'token': prepared['token'],
            'parent_id': prepared['destination'],
            'before_id': str(self.d.pk),
        }
        original = simple.move

        def lost(**kwargs):
            result = original(**kwargs)
            raise DatabaseError('SYNTHETIC confirmation lost after COMMIT')

        with patch.object(simple, 'move', lost):
            response = self.browser.post(
                path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.a.refresh_from_db()
        self.assertEqual(self.a.parent_id, self.destination.pk)
        repeat = self.browser.post(
            path, data, content_type='application/x-www-form-urlencoded')
        self.assertEqual(repeat.status_code, 409)

        legacy_prepared = legacy.prepare(
            actor=self.owner, page_id=self.a.pk, action='move',
            generation=self.generation, session_key=self.session_key,
            destination=str(self.source.pk))
        legacy.apply(
            actor=self.owner, page_id=self.a.pk, action='move',
            generation=self.generation, session_key=self.session_key,
            token=legacy_prepared['token'],
            operation_id=legacy_prepared['operation_id'], name=None,
            parent_id=legacy_prepared['destination'], before_id='')
        replay = self.browser.post(path, {
            'operation_id': legacy_prepared['operation_id'],
            'token': legacy_prepared['token'],
            'parent_id': legacy_prepared['destination'],
            'before_id': ''},
            content_type='application/x-www-form-urlencoded')
        self.assertEqual(replay.status_code, 303)
        self.assertEqual(replay['X-Tree-Result'], 'replay')
