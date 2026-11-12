from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from audit.models import AuditEvent
from . import notifications
from .models import ServiceRequest


@override_settings(SERVICE_REQUEST_TRANSPORT_PROFILE='synthetic')
class NotificationTests(TestCase):
    def setUp(self):
        self.row = ServiceRequest.objects.create(
            source='home', name='Тестовый клиент', phone='+70000000000',
            car='', comment='', consent_version='synthetic-v1',
            intent_digest='b' * 64)

    def test_both_channels_and_safe_audit(self):
        with patch('service_requests.notifications._synthetic_email') as email, \
                patch('service_requests.notifications._synthetic_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual([(item.channel, item.success) for item in result], [
            ('email', True), ('telegram', True)])
        email.assert_called_once()
        telegram.assert_called_once()
        self.assertEqual(
            list(AuditEvent.objects.values_list('code', flat=True)),
            ['REQUEST_EMAIL_SENT', 'REQUEST_TELEGRAM_SENT'])
        rendered = str(list(AuditEvent.objects.values('code', 'object_ref')))
        self.assertNotIn(self.row.phone, rendered)
        self.assertNotIn(self.row.name, rendered)

    def test_email_failure_does_not_skip_telegram(self):
        with patch(
                'service_requests.notifications._synthetic_email',
                side_effect=RuntimeError('private transport detail')) as email, \
                patch('service_requests.notifications._synthetic_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual([(item.channel, item.success) for item in result], [
            ('email', False), ('telegram', True)])
        email.assert_called_once()
        telegram.assert_called_once()
        self.assertEqual(set(AuditEvent.objects.values_list('code', flat=True)), {
            'REQUEST_EMAIL_FAILED', 'REQUEST_TELEGRAM_SENT'})

    def test_audit_failure_does_not_escape_or_repeat_transport(self):
        with patch('service_requests.notifications._synthetic_email') as email, \
                patch('service_requests.notifications._synthetic_telegram') as telegram, \
                patch('service_requests.notifications.record_event',
                      side_effect=DatabaseError('private database detail')), \
                self.assertLogs('service_requests.notifications', level='ERROR') as logs:
            result = notifications.deliver(self.row)
        self.assertEqual(len(result), 2)
        email.assert_called_once()
        telegram.assert_called_once()
        self.assertEqual(len(logs.records), 2)
        self.assertTrue(all(
            record.event_code == 'REQUEST_NOTIFICATION_AUDIT_FAILED'
            for record in logs.records))
