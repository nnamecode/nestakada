"""PUB-001–009 focused tests for simple receipt-free publication."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import UUID, uuid4

from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, close_old_connections, connection
from django.test import TransactionTestCase, override_settings

from accounts import services as auth
from accounts.models import UserProfile
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from audit.models import AuditEvent
from page_versions import engine, schema, services as versions
from page_versions.models import (IdentityReservation, OperationReceipt,
                                  PageContentState)

from . import simple_publication as publication
from .models import Page, Route
from .reads import public_tree, resolve_target
from .tree_commands import TreeFault


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimplePublicationTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='publication-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.parent = self.make_page('Parent', '/parent/', published=True)
        self.page = self.make_page(
            'Article', '/article/', parent=self.parent, published=False)
        self.child = self.make_page(
            'Child', '/child/', parent=self.page, published=True)
        self.unrelated = self.make_page(
            'Unrelated', '/unrelated/', published=True)

    def make_page(self, name, target, parent=None, published=False):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, parent=parent,
            is_published=published)
        Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target=target)
        versions.initialize(
            actor=self.owner, page_id=page.pk,
            snapshot=schema.snapshot_v1(
                page.kind, main_text='Body', h1=name, title=name),
            expected_generation=1, operation_id=uuid4())
        return page

    def prepare(self, action='publish', page=None):
        return publication.prepare(
            actor=self.owner, page_id=(page or self.page).pk,
            action=action, generation=self.generation,
            session_key=self.session_key)

    def apply(self, prepared, action=None, page=None, **changes):
        data = {
            'actor': self.owner, 'page_id': (page or self.page).pk,
            'action': action or prepared['action'],
            'generation': self.generation,
            'session_key': self.session_key,
            'token': prepared['token'],
            'operation_id': prepared['operation_id'],
        }
        data.update(changes)
        return publication.apply(**data)

    def protected_state(self):
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in ('page_versions', 'media_library')
            for model in apps.get_app_config(label).get_models()
        } | {'routes': list(Route.objects.order_by('pk').values())}

    def test_publish_changes_only_flag_and_audit_without_ledger(self):
        prepared = self.prepare()
        protected = self.protected_state()
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        self.assertEqual(resolve_target('/article/').state, 'hidden')
        self.assertNotIn(self.page.pk, [row['id'] for row in public_tree()])
        result = self.apply(prepared)
        self.page.refresh_from_db()
        self.assertTrue(self.page.is_published)
        self.assertEqual(result['result_code'], 'publication_applied')
        self.assertEqual(self.protected_state(), protected)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_PUBLISH', object_ref='uuid:' + str(self.page.pk)
        ).count(), 1)
        self.assertEqual(resolve_target('/article/').state, 'published')
        self.assertIn(self.page.pk, [row['id'] for row in public_tree()])

    def test_hidden_parent_preserves_child_and_dynamic_navigation(self):
        self.apply(self.prepare())
        hidden = self.prepare('hide')
        self.apply(hidden, action='hide')
        self.page.refresh_from_db()
        self.child.refresh_from_db()
        self.assertFalse(self.page.is_published)
        self.assertTrue(self.child.is_published)
        tree = {row['id']: row['parent_id'] for row in public_tree()}
        self.assertNotIn(self.page.pk, tree)
        self.assertEqual(tree[self.child.pk], self.parent.pk)
        self.apply(self.prepare('publish'))
        tree = {row['id']: row['parent_id'] for row in public_tree()}
        self.assertEqual(tree[self.page.pk], self.parent.pk)
        self.assertEqual(tree[self.child.pk], self.page.pk)

    def test_tampering_employee_noop_and_operation_collision_fail_closed(self):
        prepared = self.prepare()
        with self.assertRaises(TreeFault):
            self.apply(prepared, token=prepared['token'] + 'x')
        with self.assertRaises(TreeFault):
            self.apply(prepared, action='hide')
        with self.assertRaises(PermissionDenied):
            publication.apply(
                actor=self.employee, page_id=self.page.pk,
                action='publish', generation=1,
                session_key=self.session_key, token=prepared['token'],
                operation_id=prepared['operation_id'])
        collision = self.prepare()
        IdentityReservation.objects.create(
            id=UUID(collision['operation_id']), kind='synthetic')
        with self.assertRaises(TreeFault) as error:
            self.apply(collision)
        self.assertEqual(error.exception.code,
                         'PUBLICATION_OPERATION_CONFLICT')
        self.apply(prepared)
        repeated = self.prepare()
        with self.assertRaises(TreeFault) as unchanged:
            self.apply(repeated)
        self.assertEqual(unchanged.exception.code, 'PUBLICATION_UNCHANGED')

    def test_page_route_and_current_aba_are_stale_but_unrelated_is_local(self):
        page_stale = self.prepare()
        self.page.name = 'Temporary'
        self.page.save()
        self.page.name = 'Article'
        self.page.save()
        with self.assertRaises(TreeFault) as changed:
            self.apply(page_stale)
        self.assertEqual(changed.exception.code, 'PUBLICATION_BASIS_CHANGED')

        route_stale = self.prepare()
        route = Route.objects.get(page=self.page, kind=Route.Kind.PRIMARY)
        route.target = '/temporary/'
        route.save()
        route.target = '/article/'
        route.save()
        with self.assertRaises(TreeFault) as changed:
            self.apply(route_stale)
        self.assertEqual(changed.exception.code, 'PUBLICATION_BASIS_CHANGED')

        state_stale = self.prepare()
        state = PageContentState.objects.get(page=self.page)
        engine.raw(PageContentState).filter(pk=state.pk).update(
            current_revision_id=state.current_revision_id)
        with self.assertRaises(TreeFault) as changed:
            self.apply(state_stale)
        self.assertEqual(changed.exception.code, 'PUBLICATION_BASIS_CHANGED')

        local = self.prepare()
        self.unrelated.name = 'Changed elsewhere'
        self.unrelated.save()
        self.apply(local)
        self.page.refresh_from_db()
        self.assertTrue(self.page.is_published)

    def test_missing_primary_or_content_and_damaged_payload_are_refused(self):
        missing_route = Page.objects.create(
            name='No route', kind=Page.Kind.ARTICLE)
        with self.assertRaises(TreeFault) as route:
            self.prepare(page=missing_route)
        self.assertEqual(route.exception.code,
                         'PUBLICATION_PRIMARY_REQUIRED')
        no_content = Page.objects.create(
            name='No content', kind=Page.Kind.ARTICLE)
        Route.objects.create(
            page=no_content, kind=Route.Kind.PRIMARY,
            target='/no-content/')
        with self.assertRaises(TreeFault) as content:
            self.prepare(page=no_content)
        self.assertEqual(content.exception.code,
                         'PUBLICATION_CONTENT_REQUIRED')
        prepared = self.prepare()
        revision = PageContentState.objects.get(
            page=self.page).current_revision
        engine.raw(type(revision)).filter(pk=revision.pk).update(
            payload_hash='0' * 64)
        with self.assertRaises(TreeFault) as damaged:
            self.apply(prepared)
        self.assertEqual(damaged.exception.code,
                         'PUBLICATION_CONTENT_DAMAGED')

    def test_audit_failure_rolls_back_flag(self):
        prepared = self.prepare()
        with patch('content.simple_publication.record_event',
                   side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):
                self.apply(prepared)
        self.page.refresh_from_db()
        self.assertFalse(self.page.is_published)
        self.assertFalse(AuditEvent.objects.filter(
            code='TREE_PUBLISH', object_ref='uuid:' + str(self.page.pk)
        ).exists())

    def test_concurrent_submit_has_one_success_and_one_conflict(self):
        prepared = self.prepare()
        barrier = Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return self.apply(prepared)['result_code']
                except TreeFault as error:
                    return error.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: run(), range(2)))
        self.assertEqual(results.count('publication_applied'), 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_PUBLISH', object_ref='uuid:' + str(self.page.pk)
        ).count(), 1)

    def test_http_owner_employee_csrf_repeat_and_tree_links(self):
        url = ('/manage/pages/' + str(self.page.pk)
               + '/publication/publish/')
        form = self.browser.get(url)
        self.assertEqual(form.status_code, 200)
        values = {
            'operation_id': form.context['values']['operation_id'],
            'token': form.context['values']['token'],
        }
        response = self.browser.post(
            url, values, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['X-Tree-Result'], 'applied')
        self.assertEqual(self.browser.post(
            url, values, content_type='application/x-www-form-urlencoded'
        ).status_code, 409)

        employee = client()
        self.assertEqual(login(
            employee, 'publication-employee').status_code, 303)
        self.assertEqual(employee.get(url).status_code, 403)
        self.assertEqual(client().get(url).status_code, 401)

        csrf = client(csrf=True)
        self.assertEqual(login(csrf, 'nesadmin').status_code, 403)
        csrf.cookies = self.browser.cookies
        current = csrf.get(
            '/manage/pages/' + str(self.page.pk)
            + '/publication/hide/')
        self.assertEqual(current.status_code, 200)
        self.assertEqual(csrf.post(
            '/manage/pages/' + str(self.page.pk) + '/publication/hide/',
            current.context['values'],
            content_type='application/x-www-form-urlencoded').status_code,
            403)
        tree = self.browser.get('/manage/pages/', {'parent': str(self.parent.pk)})
        self.assertContains(tree, 'Скрыть')

    def test_http_lost_response_after_commit_preserves_exact_retry(self):
        url = ('/manage/pages/' + str(self.page.pk)
               + '/publication/publish/')
        form = self.browser.get(url)
        values = {
            'operation_id': form.context['values']['operation_id'],
            'token': form.context['values']['token'],
        }
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        original = publication.apply
        observed = {}

        def committed_then_lost(**kwargs):
            result = original(**kwargs)
            self.assertFalse(connection.in_atomic_block)
            close_old_connections()
            observed['published'] = Page.objects.get(
                pk=self.page.pk).is_published
            observed['audits'] = AuditEvent.objects.filter(
                code='TREE_PUBLISH',
                object_ref='uuid:' + str(self.page.pk)).count()
            observed['receipts'] = OperationReceipt.objects.count()
            observed['identities'] = IdentityReservation.objects.count()
            observed['result'] = result['result_code']
            raise DatabaseError('synthetic lost response after commit')

        with patch('content.publication_views.publication.apply',
                   side_effect=committed_then_lost):
            response = self.browser.post(
                url, values,
                content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(observed, {
            'published': True, 'audits': 1,
            'receipts': receipts, 'identities': identities,
            'result': 'publication_applied',
        })
        self.assertEqual(response.context['values']['operation_id'],
                         values['operation_id'])
        self.assertEqual(response.context['values']['token'], values['token'])
        self.assertContains(response, 'Повторить ту же команду',
                            status_code=503)

        repeated = self.browser.post(
            url, values, content_type='application/x-www-form-urlencoded')
        self.assertEqual(repeated.status_code, 409)
        self.assertTrue(Page.objects.get(pk=self.page.pk).is_published)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_PUBLISH',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
