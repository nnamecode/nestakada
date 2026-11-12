from urllib.parse import urlencode
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts.models import UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent
from .models import RequestSettings, ServiceRequest


class RequestAdminHttpTests(TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        os.chmod(self.temporary.name, 0o700)
        self.ledger_root = Path(self.temporary.name) / 'ledger'
        self.ledger_root.mkdir(mode=0o700)
        self.ledger_override = self.settings(
            SERVICE_REQUEST_DELETION_LEDGER_ROOT=str(self.ledger_root))
        self.ledger_override.enable()
        users = get_user_model()
        self.owner = users.objects.create_user('nesadmin', password='owner-password-123')
        self.employee = users.objects.create_user('worker1', password='worker-password-123')
        UserProfile.objects.create(user=self.owner, role='owner')
        UserProfile.objects.create(user=self.employee, role='employee')
        self.owner_client = self.authenticated(self.owner)
        self.employee_client = self.authenticated(self.employee)
        self.row = ServiceRequest.objects.create(
            source='contacts', name='<script>Тест</script>',
            phone='+70000000000', car='<b>Авто</b>',
            comment='<img src=x onerror=alert(1)>',
            consent_version='synthetic-v1', intent_digest='c' * 64)

    def tearDown(self):
        self.ledger_override.disable()
        self.temporary.cleanup()

    def authenticated(self, user):
        client = Client()
        client.cookies[settings.SESSION_COOKIE_NAME] = editor_session(user)
        return client

    def post(self, client, url, values):
        return client.post(
            url, urlencode(values),
            content_type='application/x-www-form-urlencoded')

    def test_owner_and_employee_read_anonymous_denied_and_escaped(self):
        for client in (self.owner_client, self.employee_client):
            listing = client.get('/manage/requests/')
            self.assertEqual(listing.status_code, 200)
            self.assertEqual(listing['Cache-Control'], 'private, no-store')
            detail = client.get(f'/manage/requests/{self.row.pk}/')
            self.assertEqual(detail.status_code, 200)
            self.assertContains(detail, '&lt;script&gt;Тест&lt;/script&gt;')
            self.assertNotContains(detail, '<script>Тест</script>')
            self.assertContains(detail, '+70000000000')
        self.assertEqual(self.client.get('/manage/requests/').status_code, 401)

    def test_bounded_pagination_and_query(self):
        ServiceRequest.objects.bulk_create([
            ServiceRequest(
                source='home', name=f'Клиент {number}', phone='+70000000000',
                car='', comment='', consent_version='synthetic-v1',
                intent_digest=f'{number:064x}')
            for number in range(1, 27)
        ])
        first = self.employee_client.get('/manage/requests/')
        self.assertEqual(len(first.context['rows']), 25)
        self.assertTrue(first.context['has_next'])
        second = self.employee_client.get('/manage/requests/?page=2')
        self.assertEqual(len(second.context['rows']), 2)
        for query in ('?page=0', '?page=01', '?page=10001', '?page=1&page=2', '?search=x'):
            with self.subTest(query=query):
                self.assertEqual(
                    self.employee_client.get('/manage/requests/' + query).status_code,
                    400)

    def test_only_owner_changes_recipient(self):
        url = '/manage/requests/settings/'
        self.assertEqual(self.employee_client.get(url).status_code, 403)
        self.assertEqual(self.post(
            self.employee_client, url,
            {'recipient_email': 'employee@example.test'}).status_code, 403)
        response = self.post(
            self.owner_client, url,
            {'recipient_email': 'owner@example.test'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(RequestSettings.objects.get(pk=1).recipient_email,
                         'owner@example.test')
        self.assertTrue(AuditEvent.objects.filter(
            code='REQUEST_SETTINGS_CHANGED', actor_id=self.owner.pk).exists())
        self.assertEqual(self.post(
            self.owner_client, url,
            {'recipient_email': 'not-an-email'}).status_code, 200)
        self.assertEqual(RequestSettings.objects.get(pk=1).recipient_email,
                         'owner@example.test')

    def test_only_owner_deletes_without_password_and_replay_converges(self):
        url = f'/manage/requests/{self.row.pk}/delete/'
        self.assertEqual(self.employee_client.get(url).status_code, 403)
        prepared = self.owner_client.get(url)
        self.assertEqual(prepared.status_code, 200)
        self.assertNotContains(prepared, 'type="password"')
        confirmation = prepared.context['confirmation']
        self.assertEqual(self.post(
            self.employee_client, url,
            {'confirmation': confirmation}).status_code, 403)
        deleted = self.post(
            self.owner_client, url, {'confirmation': confirmation})
        self.assertEqual(deleted.status_code, 303)
        self.assertFalse(ServiceRequest.objects.filter(pk=self.row.pk).exists())
        replay = self.post(
            self.owner_client, url, {'confirmation': confirmation})
        self.assertEqual(replay.status_code, 303)
