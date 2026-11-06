"""URLC-001–010 tests for receipt-free non-legacy URL changes."""
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
from page_versions import schema, services as versions
from page_versions.models import IdentityReservation, OperationReceipt

from . import simple_url_change as url_change
from .models import Page, Route
from .reads import resolve_target
from .tree_commands import TreeFault


@override_settings(PASSWORD_HASHERS=FAST_HASHERS,
                   AUTH_TRUSTED_PROXY_HOST=None)
class SimpleUrlChangeTests(TransactionTestCase):
    def setUp(self):
        self.owner = auth.bootstrap_owner(PASSWORD)
        self.employee = auth.create_employee(
            actor=self.owner, username='url-change-employee',
            password=PASSWORD)
        self.browser = client()
        self.assertEqual(login(self.browser, 'nesadmin').status_code, 303)
        self.session_key = self.browser.session.session_key
        self.generation = UserProfile.objects.get(
            user=self.owner).generation
        self.page = self.make_page('Article', '/article/', published=False)
        self.child = self.make_page(
            'Child', '/child/', parent=self.page, published=True)
        self.alias = Route.objects.create(
            page=self.page, kind=Route.Kind.ALIAS,
            target='/article-alias/')
        self.unrelated = self.make_page(
            'Unrelated', '/unrelated/', published=True)
        self.legacy = self.make_page(
            'Legacy', '/Legacy/', published=True, legacy=True)

    def make_page(self, name, target, parent=None, published=False,
                  legacy=False):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, parent=parent,
            is_published=published)
        Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY,
            target=target, is_legacy=legacy)
        versions.initialize(
            actor=self.owner, page_id=page.pk,
            snapshot=schema.snapshot_v1(
                page.kind, main_text='Body', h1=name, title=name),
            expected_generation=1, operation_id=uuid4())
        return page

    def prepare(self, page=None):
        return url_change.prepare(
            actor=self.owner, page_id=(page or self.page).pk,
            generation=self.generation, session_key=self.session_key)

    def apply(self, prepared, target='/changed/', page=None, **changes):
        data = {
            'actor': self.owner, 'page_id': (page or self.page).pk,
            'generation': self.generation,
            'session_key': self.session_key,
            'token': prepared['token'],
            'operation_id': prepared['operation_id'], 'target': target,
        }
        data.update(changes)
        return url_change.apply(**data)

    def protected_state(self):
        return {
            model._meta.db_table: list(model.objects.order_by('pk').values())
            for label in ('page_versions', 'media_library')
            for model in apps.get_app_config(label).get_models()
        } | {'pages': list(Page.objects.order_by('pk').values())}

    def test_change_updates_primary_adds_direct_redirect_and_audit_only(self):
        prepared = self.prepare()
        protected = self.protected_state()
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        other_routes = list(Route.objects.exclude(
            page=self.page, kind=Route.Kind.PRIMARY).order_by('pk').values())
        result = self.apply(prepared)
        primary = Route.objects.get(
            page=self.page, kind=Route.Kind.PRIMARY)
        redirect = Route.objects.get(
            page=self.page, kind=Route.Kind.REDIRECT,
            target='/article/')
        self.assertEqual(primary.target, '/changed/')
        self.assertFalse(redirect.is_legacy)
        self.assertEqual(result['redirect_id'], str(redirect.pk))
        self.assertEqual(resolve_target('/article/').destination,
                         '/changed/')
        self.assertEqual(resolve_target('/changed/').state, 'hidden')
        self.assertEqual(self.protected_state(), protected)
        self.assertEqual(list(Route.objects.exclude(
            pk__in=[primary.pk, redirect.pk]).order_by('pk').values()),
            other_routes)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_URL_CHANGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)

    def test_repeated_changes_are_direct_and_keep_children_publication(self):
        self.apply(self.prepare(), '/second/')
        self.apply(self.prepare(), '/third/')
        self.page.refresh_from_db()
        self.child.refresh_from_db()
        self.assertFalse(self.page.is_published)
        self.assertTrue(self.child.is_published)
        self.assertEqual(Route.objects.get(
            page=self.child, kind=Route.Kind.PRIMARY).target, '/child/')
        for old in ('/article/', '/second/'):
            match = resolve_target(old)
            self.assertEqual((match.state, match.destination),
                             ('redirect', '/third/'))
        self.assertEqual(resolve_target('/third/').state, 'hidden')
        self.assertEqual(Route.objects.filter(
            page=self.page, kind=Route.Kind.REDIRECT).count(), 2)

    def test_legacy_missing_primary_invalid_and_occupied_targets_refused(self):
        with self.assertRaises(TreeFault) as legacy:
            self.prepare(self.legacy)
        self.assertEqual(legacy.exception.code,
                         'URL_CHANGE_LEGACY_PROTECTED')
        no_route = Page.objects.create(
            name='No route', kind=Page.Kind.ARTICLE)
        with self.assertRaises(TreeFault) as missing:
            self.prepare(no_route)
        self.assertEqual(missing.exception.code,
                         'URL_CHANGE_PRIMARY_REQUIRED')

        for target in ('/Upper/', '/bad?query=1', '/a//b/',
                       '/manage/', '/wp-admin/', '/.env', '//foreign/'):
            with self.subTest(target=target), self.assertRaises(TreeFault):
                self.apply(self.prepare(), target)
        occupied = ['/unrelated/', '/article-alias/']
        Route.objects.create(
            page=self.unrelated, kind=Route.Kind.REDIRECT,
            target='/occupied-redirect/')
        Route.objects.create(
            kind=Route.Kind.SYSTEM, target='/occupied-system/')
        occupied += ['/occupied-redirect/', '/occupied-system/']
        for target in occupied:
            with self.subTest(target=target), self.assertRaises(
                    TreeFault) as conflict:
                self.apply(self.prepare(), target)
            self.assertEqual(conflict.exception.code,
                             'URL_CHANGE_TARGET_CONFLICT')

    def test_tampering_employee_noop_and_operation_collision_fail_closed(self):
        prepared = self.prepare()
        with self.assertRaises(TreeFault):
            self.apply(prepared, token=prepared['token'] + 'x')
        with self.assertRaises(TreeFault):
            self.apply(prepared, page=self.unrelated)
        with self.assertRaises(PermissionDenied):
            url_change.apply(
                actor=self.employee, page_id=self.page.pk,
                generation=1, session_key=self.session_key,
                token=prepared['token'],
                operation_id=prepared['operation_id'],
                target='/employee/')
        with self.assertRaises(TreeFault) as unchanged:
            self.apply(prepared, '/article/')
        self.assertEqual(unchanged.exception.code,
                         'URL_CHANGE_UNCHANGED')
        collision = self.prepare()
        IdentityReservation.objects.create(
            id=UUID(collision['operation_id']), kind='synthetic')
        with self.assertRaises(TreeFault) as operation:
            self.apply(collision)
        self.assertEqual(operation.exception.code,
                         'URL_CHANGE_OPERATION_CONFLICT')

    def test_page_and_primary_aba_stale_but_unrelated_change_is_local(self):
        page_stale = self.prepare()
        self.page.name = 'Temporary'
        self.page.save()
        self.page.name = 'Article'
        self.page.save()
        with self.assertRaises(TreeFault) as stale:
            self.apply(page_stale)
        self.assertEqual(stale.exception.code, 'URL_CHANGE_BASIS_CHANGED')

        route_stale = self.prepare()
        primary = Route.objects.get(
            page=self.page, kind=Route.Kind.PRIMARY)
        primary.target = '/temporary/'
        primary.save()
        primary.target = '/article/'
        primary.save()
        with self.assertRaises(TreeFault) as stale:
            self.apply(route_stale)
        self.assertEqual(stale.exception.code, 'URL_CHANGE_BASIS_CHANGED')

        local = self.prepare()
        self.unrelated.name = 'Changed elsewhere'
        self.unrelated.save()
        self.apply(local)
        self.assertEqual(Route.objects.get(
            page=self.page, kind=Route.Kind.PRIMARY).target, '/changed/')

    def test_audit_failure_rolls_back_primary_and_redirect(self):
        prepared = self.prepare()
        before = list(Route.objects.order_by('pk').values())
        with patch('content.simple_url_change.record_event',
                   side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):
                self.apply(prepared)
        self.assertEqual(list(Route.objects.order_by('pk').values()), before)
        self.assertFalse(AuditEvent.objects.filter(
            code='TREE_URL_CHANGE',
            object_ref='uuid:' + str(self.page.pk)).exists())

    def test_concurrent_submit_has_one_redirect_and_one_audit(self):
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
        self.assertEqual(results.count('url_changed'), 1)
        self.assertEqual(len(results), 2)
        self.assertEqual(Route.objects.filter(
            page=self.page, kind=Route.Kind.REDIRECT,
            target='/article/').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_URL_CHANGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)

    def test_http_roles_csrf_success_and_tree_hides_legacy_action(self):
        url = '/manage/pages/' + str(self.page.pk) + '/url/'
        form = self.browser.get(url)
        self.assertEqual(form.status_code, 200)
        values = {
            'operation_id': form.context['values']['operation_id'],
            'token': form.context['values']['token'],
            'target': '/http-changed/',
        }
        response = self.browser.post(
            url, values, content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response['X-Tree-Result'], 'applied')
        employee = client()
        self.assertEqual(login(
            employee, 'url-change-employee').status_code, 303)
        self.assertEqual(employee.get(url).status_code, 403)
        self.assertEqual(client().get(url).status_code, 401)

        csrf = client(csrf=True)
        csrf.cookies = self.browser.cookies
        current = csrf.get(url)
        self.assertEqual(current.status_code, 200)
        self.assertEqual(csrf.post(
            url, {**current.context['values'], 'target': '/csrf/'},
            content_type='application/x-www-form-urlencoded').status_code,
            403)

        tree = self.browser.get('/manage/pages/')
        self.assertContains(
            tree, '/manage/pages/' + str(self.page.pk) + '/url/')
        self.assertNotContains(
            tree, '/manage/pages/' + str(self.legacy.pk) + '/url/')

    def test_http_lost_response_commit_then_exact_retry_conflicts(self):
        url = '/manage/pages/' + str(self.page.pk) + '/url/'
        form = self.browser.get(url)
        values = {
            'operation_id': form.context['values']['operation_id'],
            'token': form.context['values']['token'],
            'target': '/lost-response/',
        }
        receipts = OperationReceipt.objects.count()
        identities = IdentityReservation.objects.count()
        original = url_change.apply
        observed = {}

        def committed_then_lost(**kwargs):
            result = original(**kwargs)
            self.assertFalse(connection.in_atomic_block)
            close_old_connections()
            primary = Route.objects.get(
                page=self.page, kind=Route.Kind.PRIMARY)
            observed.update(
                target=primary.target,
                redirects=Route.objects.filter(
                    page=self.page, kind=Route.Kind.REDIRECT,
                    target='/article/').count(),
                audits=AuditEvent.objects.filter(
                    code='TREE_URL_CHANGE',
                    object_ref='uuid:' + str(self.page.pk)).count(),
                receipts=OperationReceipt.objects.count(),
                identities=IdentityReservation.objects.count(),
                result=result['result_code'])
            raise DatabaseError('synthetic lost response after commit')

        with patch('content.url_change_views.url_change.apply',
                   side_effect=committed_then_lost):
            response = self.browser.post(
                url, values,
                content_type='application/x-www-form-urlencoded')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(observed, {
            'target': '/lost-response/', 'redirects': 1, 'audits': 1,
            'receipts': receipts, 'identities': identities,
            'result': 'url_changed',
        })
        self.assertEqual(response.context['values']['operation_id'],
                         values['operation_id'])
        self.assertEqual(response.context['values']['token'], values['token'])
        self.assertEqual(response.context['values']['target'], values['target'])
        self.assertContains(response, 'Повторите ту же команду',
                            status_code=503)

        repeated = self.browser.post(
            url, values, content_type='application/x-www-form-urlencoded')
        self.assertEqual(repeated.status_code, 409)
        self.assertEqual(Route.objects.filter(
            page=self.page, kind=Route.Kind.REDIRECT,
            target='/article/').count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            code='TREE_URL_CHANGE',
            object_ref='uuid:' + str(self.page.pk)).count(), 1)
        self.assertEqual(OperationReceipt.objects.count(), receipts)
        self.assertEqual(IdentityReservation.objects.count(), identities)
