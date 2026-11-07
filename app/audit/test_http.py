from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from accounts import services
from accounts.tests import FAST_HASHERS, PASSWORD, client, login

from .constants import Category, Level, Result, Source
from .models import AuditEvent
from .services import record_event


@override_settings(PASSWORD_HASHERS=FAST_HASHERS, AUTH_TRUSTED_PROXY_HOST=None)
class AuditHttpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = services.bootstrap_owner(PASSWORD)
        cls.employee = services.create_employee(
            actor=cls.owner, username='audit-employee', password=PASSWORD)

    def browser(self, username='nesadmin'):
        browser = client()
        self.assertEqual(login(browser, username).status_code, 303)
        return browser

    def event(self, code, **overrides):
        values = dict(category=Category.SERVICE, event_code=code,
                      level=Level.INFO, source=Source.APPLICATION,
                      result=Result.SUCCESS)
        values.update(overrides)
        return record_event(**values)

    def assert_private(self, response):
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertIn('Cookie', response['Vary'])

    def test_owner_only_gate_stops_employee_and_anonymous_before_read(self):
        with patch('audit.views._events') as projection:
            anonymous = client().get('/manage/audit/')
            employee = self.browser('audit-employee').get('/manage/audit/')
            self.assertEqual(anonymous.status_code, 401)
            self.assertEqual(employee.status_code, 403)
            projection.assert_not_called()
        self.assert_private(anonymous)
        self.assert_private(employee)
        owner = self.browser().get('/manage/audit/')
        self.assertEqual(owner.status_code, 200)
        self.assert_private(owner)

    def test_bounded_newest_first_cursor_and_read_only(self):
        browser = self.browser()
        AuditEvent.objects.all().delete()
        for number in range(55):
            self.event(f'AUDIT_FIXTURE_{number}')
        before = list(AuditEvent.objects.order_by('id').values())
        with CaptureQueriesContext(connection) as queries:
            response = browser.get('/manage/audit/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['events']), 50)
        event_queries = [item['sql'] for item in queries.captured_queries
                         if 'audit_auditevent' in item['sql'].lower()
                         and 'order by' in item['sql'].lower()]
        self.assertEqual(len(event_queries), 1)
        self.assertIn('LIMIT 50', event_queries[0].upper())
        self.assertNotIn('LIMIT 51', event_queries[0].upper())
        ids = [row.id for row in response.context['events']]
        self.assertEqual(ids, sorted(ids, reverse=True))
        self.assertTrue(response.context['next_url'].startswith('?before='))
        second = browser.get('/manage/audit/' + response.context['next_url'])
        self.assertEqual(len(second.context['events']), 5)
        self.assertLess(second.context['events'][0].id, ids[-1])
        self.assertEqual(list(AuditEvent.objects.order_by('id').values()), before)

    def test_exact_filters_and_invalid_queries(self):
        browser = self.browser()
        AuditEvent.objects.all().delete()
        wanted = self.event('AUDIT_WANTED', category=Category.SECURITY,
                            level=Level.ERROR, result=Result.DENIED)
        self.event('AUDIT_OTHER_LEVEL', category=Category.SECURITY,
                   level=Level.INFO, result=Result.DENIED)
        self.event('AUDIT_OTHER_CATEGORY', category=Category.SERVICE,
                   level=Level.ERROR, result=Result.DENIED)
        response = browser.get('/manage/audit/', {
            'category': Category.SECURITY, 'level': Level.ERROR,
            'result': Result.DENIED})
        self.assertEqual([row.pk for row in response.context['events']], [wanted.pk])
        invalid = [
            'category=', 'category=unknown', 'level=INFO&level=ERROR',
            'result=SUCCESS&extra=PRIVATE-QUERY-CANARY', 'before=0',
            'before=01', 'before=9223372036854775808',
        ]
        for query in invalid:
            with self.subTest(query=query):
                denied = browser.get('/manage/audit/?' + query)
                self.assertEqual(denied.status_code, 400)
                self.assertNotContains(denied, 'PRIVATE-QUERY-CANARY', status_code=400)
                self.assert_private(denied)

    def test_safe_fields_are_escaped_and_no_mutation_methods_exist(self):
        browser = self.browser()
        unsafe = get_user_model().objects.create_user(
            username='<script>alert(1)</script>', password=PASSWORD)
        row = self.event('AUDIT_SAFE_RENDER', actor_id=unsafe.pk,
                         object_kind='page', object_ref=123,
                         occurrence_count=3, count_is_lower_bound=True,
                         ip_address='192.0.2.10', ip_related=True)
        before = list(AuditEvent.objects.order_by('id').values())
        response = browser.get('/manage/audit/')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, str(row.event_id))
        self.assertContains(response, 'не менее 3')
        self.assertContains(response, '192.0.2.10')
        self.assertContains(response, 'MSK')
        section = response.content.decode().split(
            '<section class="card audit-events">', 1)[1]
        self.assertNotIn('method="post"', section)
        self.assertNotIn('class="danger"', section)
        self.assertNotIn('name="action"', section)
        for method in ('post', 'put', 'patch', 'delete'):
            denied = getattr(browser, method)('/manage/audit/')
            self.assertEqual(denied.status_code, 405)
            self.assert_private(denied)
        self.assertEqual(list(AuditEvent.objects.order_by('id').values()), before)

    def test_database_failure_is_private_503_without_event_content(self):
        browser = self.browser()
        with patch('audit.views._events', side_effect=DatabaseError('PRIVATE-DB-CANARY')):
            response = browser.get('/manage/audit/?category=security')
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'PRIVATE-DB-CANARY', status_code=503)
        self.assertNotContains(response, 'security', status_code=503)
        self.assert_private(response)
