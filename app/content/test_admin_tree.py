"""TREE29-001–007: real owner sessions and PostgreSQL read-only tree UI."""
from uuid import uuid4
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.test import TestCase, override_settings
from accounts import services
from accounts.tests import FAST_HASHERS, PASSWORD, client, login
from page_versions.models import PageRevision
from .models import Page, Route


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None)
class AdminTreeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = services.bootstrap_owner(PASSWORD)
        cls.employee = services.create_employee(actor=cls.owner, username='auth-employee', password=PASSWORD)
        cls.root = Page.objects.create(name='Корень <b>текст</b>', kind='service_catalog', is_published=False)
        cls.child = Page.objects.create(name='Ребёнок', kind='service_detail', parent=cls.root, is_published=True)
        cls.empty = Page.objects.create(name='Без адреса', kind='article', is_published=False)
        Route.objects.create(page=cls.root, target='/Root?Case=X&mode=Y', kind='primary', is_legacy=True)
        Route.objects.create(page=cls.child, target='/child/', kind='primary')
        Route.objects.create(page=cls.child, target='/child-alias/', kind='alias')

    def owner_browser(self):
        browser = client()
        self.assertEqual(login(browser, 'nesadmin').status_code, 303)
        return browser

    def assert_private(self, response):
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn('Cookie', response['Vary'])

    def state(self):
        return (list(Page.objects.order_by('pk').values()), list(Route.objects.order_by('pk').values()),
                list(PageRevision.objects.order_by('pk').values()))

    def test_root_primary_escaping_and_missing_primary(self):
        response = self.owner_browser().get('/manage/pages/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Корень &lt;b&gt;текст&lt;/b&gt;')
        self.assertNotContains(response, 'Корень <b>текст</b>')
        self.assertContains(response, '/Root?Case=X&amp;mode=Y')
        self.assertContains(response, 'Адрес ещё не назначен')
        self.assertNotContains(response, 'data-page-id="'+str(self.child.pk)+'"')
        self.assert_private(response)

    def test_hidden_parent_does_not_hide_child_or_rewrite_tree(self):
        browser = self.owner_browser()
        before = self.state()
        response = browser.get('/manage/pages/', {'parent': str(self.root.pk)})
        self.assertContains(response, 'data-page-id="'+str(self.child.pk)+'"')
        self.assertContains(response, 'Опубликована')
        self.assertContains(response, '<code>/child/</code>', html=True)
        self.assertNotContains(response, '<code>/child-alias/</code>', html=True)
        self.assertContains(response, 'Корень &lt;b&gt;текст&lt;/b&gt;')
        self.assertEqual(self.state(), before)
        self.assert_private(response)

    def test_leaf_and_ancestors(self):
        response = self.owner_browser().get('/manage/pages/', {'parent': str(self.child.pk)})
        self.assertContains(response, 'В этом разделе пока нет страниц.')
        self.assertEqual([item['id'] for item in response.context['ancestry']], [self.root.pk, self.child.pk])

    def test_employee_and_anonymous_stop_before_projection(self):
        browser = client()
        with patch('content.admin_tree.branch') as projection:
            anonymous = browser.get('/manage/pages/')
            self.assertEqual(anonymous.status_code, 401)
            self.assertEqual(login(browser).status_code, 303)
            denied = browser.get('/manage/pages/')
            self.assertEqual(denied.status_code, 403)
            projection.assert_not_called()
        self.assert_private(anonymous)
        self.assert_private(denied)
        self.assertNotContains(denied, self.root.name, status_code=403)

    def test_queries_rejected_without_reflecting_input(self):
        browser = self.owner_browser()
        before = self.state()
        for query in ['parent=not-a-uuid', 'parent=', 'parent='+str(self.root.pk)+'&parent='+str(self.child.pk),
                      'unexpected=PRIVATE-QUERY-CANARY']:
            with self.subTest(query=query):
                response = browser.get('/manage/pages/?'+query)
                self.assertEqual(response.status_code, 400)
                self.assertNotContains(response, 'PRIVATE-QUERY-CANARY', status_code=400)
                self.assert_private(response)
        absent = browser.get('/manage/pages/', {'parent': str(uuid4())})
        self.assertEqual(absent.status_code, 404)
        self.assert_private(absent)
        self.assertEqual(self.state(), before)

    def test_post_is_not_a_mutation(self):
        browser = self.owner_browser()
        before = self.state()
        response = browser.post('/manage/pages/', {'action': 'delete', 'page': str(self.root.pk)})
        self.assertEqual(response.status_code, 405)
        self.assert_private(response)
        self.assertEqual(self.state(), before)

    def test_projection_failure_closed(self):
        browser = self.owner_browser()
        for error in [DatabaseError('PRIVATE-DATABASE-CANARY'), ValidationError('TREE_PARENT_CHAIN_UNAVAILABLE')]:
            with self.subTest(kind=type(error).__name__), patch('content.admin_tree.branch', side_effect=error):
                response = browser.get('/manage/pages/')
                self.assertEqual(response.status_code, 503)
                self.assertNotContains(response, 'PRIVATE-DATABASE-CANARY', status_code=503)
                self.assert_private(response)

    def test_owner_dashboard_link_only(self):
        owner = self.owner_browser().get('/manage/')
        self.assertContains(owner, 'Дерево страниц и разделов')
        browser = client()
        self.assertEqual(login(browser).status_code, 303)
        self.assertNotContains(browser.get('/manage/'), 'Дерево страниц и разделов')

    def test_revoked_session_stops_before_projection(self):
        browser = self.owner_browser()
        services.recover_owner(PASSWORD)
        with patch('content.admin_tree.branch') as projection:
            response = browser.get('/manage/pages/')
            self.assertEqual(response.status_code, 401)
            projection.assert_not_called()
        self.assert_private(response)

    def test_actual_ancestry_cycle_check_is_closed(self):
        browser = self.owner_browser()
        rows = [{'id': self.root.pk, 'name': self.root.name, 'parent_id': self.child.pk},
                {'id': self.child.pk, 'name': self.child.name, 'parent_id': self.root.pk}]
        # Inject a corrupt read stream, never bypass the database tree guard.
        with patch('content.admin_tree.Page.objects.values', return_value=rows):
            response = browser.get('/manage/pages/', {'parent': str(self.root.pk)})
        self.assertEqual(response.status_code, 503)
        self.assert_private(response)
