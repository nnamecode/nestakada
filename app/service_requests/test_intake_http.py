from urllib.parse import urlencode
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.db import DatabaseError, close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from audit.models import AuditEvent
from . import intents
from .models import ServiceRequest


ACTIVE = override_settings(
    SERVICE_REQUEST_INTAKE_ENABLED=True,
    SERVICE_REQUEST_TRANSPORT_PROFILE='synthetic',
    SERVICE_REQUEST_CONSENT_VERSION='synthetic-v1')


@ACTIVE
class IntakeHttpTests(TestCase):
    def payload(self, **changes):
        value = {
            'intent': intents.issue(
                source='home', consent_version='synthetic-v1'),
            'name': 'Тестовый клиент', 'phone': '8 (000) 000-00-00',
            'car': '', 'comment': '', 'consent': 'on',
        }
        value.update(changes)
        return value

    def post(self, payload, *, client=None):
        return (client or self.client).post(
            '/request/submit/', urlencode(payload, doseq=True),
            content_type='application/x-www-form-urlencoded')

    def test_valid_and_duplicate_intent_create_one_row(self):
        payload = self.payload()
        with patch('service_requests.notifications.deliver') as deliver:
            first = self.post(payload)
            second = self.post(payload)
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(ServiceRequest.objects.count(), 1)
        row = ServiceRequest.objects.get()
        self.assertEqual(row.phone, '+70000000000')
        self.assertNotContains(first, str(row.pk))
        self.assertEqual(first['Cache-Control'], 'no-store')
        deliver.assert_called_once_with(row)
        self.assertEqual(
            AuditEvent.objects.filter(code='REQUEST_ACCEPTED').count(), 1)

    def test_invalid_unknown_and_duplicate_fields_create_nothing(self):
        invalid = self.payload(phone='+80000000000')
        self.assertEqual(self.post(invalid).status_code, 400)
        unknown = self.payload(extra='x')
        self.assertEqual(self.post(unknown).status_code, 400)
        duplicate = self.payload()
        duplicate['name'] = ['Один', 'Два']
        self.assertEqual(self.post(duplicate).status_code, 400)
        self.assertEqual(ServiceRequest.objects.count(), 0)

    def test_method_feature_and_csrf_fail_closed(self):
        self.assertEqual(self.client.get('/request/submit/').status_code, 405)
        with override_settings(SERVICE_REQUEST_INTAKE_ENABLED=False):
            self.assertEqual(
                self.post(self.payload()).status_code,
                503)
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(
            self.post(self.payload(), client=csrf_client).status_code,
            403)

    def test_body_limit_sql_text_and_csp(self):
        oversized = self.payload(comment='x' * 9000)
        self.assertEqual(self.post(oversized).status_code, 400)
        malicious = self.payload(
            name="Robert'); DROP TABLE service_requests_servicerequest;--",
            comment='<script>alert(1)</script>')
        response = self.post(malicious)
        self.assertEqual(response.status_code, 200)
        self.assertIn("form-action 'self'", response['Content-Security-Policy'])
        row = ServiceRequest.objects.get()
        self.assertEqual(row.name, malicious['name'])
        self.assertEqual(row.comment, malicious['comment'])
        self.assertTrue(ServiceRequest.objects.filter(pk=row.pk).exists())

    def test_accepted_audit_failure_rolls_back_before_notifications(self):
        with patch('service_requests.services.record_event',
                   side_effect=DatabaseError('private audit failure')), \
                patch('service_requests.notifications.deliver') as deliver:
            response = self.post(self.payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(ServiceRequest.objects.count(), 0)
        deliver.assert_not_called()


@ACTIVE
class ConcurrentIntakeHttpTests(TransactionTestCase):
    reset_sequences = True

    def test_two_posts_have_one_winner_audit_and_delivery(self):
        payload = {
            'intent': intents.issue(
                source='home', consent_version='synthetic-v1'),
            'name': 'Тестовый клиент', 'phone': '8 (000) 000-00-00',
            'car': '', 'comment': '', 'consent': 'on',
        }
        body = urlencode(payload)
        barrier = threading.Barrier(2)

        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return Client().post(
                    '/request/submit/', body,
                    content_type='application/x-www-form-urlencoded').status_code
            finally:
                close_old_connections()

        with patch('service_requests.notifications.deliver') as deliver:
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(lambda _: run(), range(2)))
        self.assertEqual(statuses, [200, 200])
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(code='REQUEST_ACCEPTED').count(), 1)
        self.assertEqual(deliver.call_count, 1)
