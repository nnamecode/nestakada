from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase, override_settings

from audit.models import AuditEvent
from . import notifications
from .models import RequestSettings, ServiceRequest


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


@override_settings(
    SERVICE_REQUEST_TRANSPORT_PROFILE='live',
    SERVICE_REQUEST_LEGAL_PROFILE='approved-v1',
    SERVICE_REQUEST_SMTP_HOST='smtp.example.test',
    SERVICE_REQUEST_SMTP_PORT='465',
    SERVICE_REQUEST_SMTP_USER='sender@example.test',
    SERVICE_REQUEST_SMTP_SECURITY='ssl',
)
class LiveChannelSelectionTests(TestCase):
    def setUp(self):
        self.row = ServiceRequest.objects.create(
            source='home', name='Тестовый клиент', phone='+70000000000',
            car='', comment='', consent_version='synthetic-v1',
            intent_digest='c' * 64)
        RequestSettings.objects.create(recipient_email='owner@example.test')

    def test_email_only_omits_unconfigured_telegram_without_false_failure(self):
        with self.settings(SERVICE_REQUEST_TELEGRAM_CHAT_ID=''), \
                patch('service_requests.notifications._credential',
                      return_value='s' * 32), \
                patch('service_requests.notifications._live_email') as email, \
                patch('service_requests.notifications._live_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual([(item.channel, item.success) for item in result], [
            ('email', True)])
        email.assert_called_once()
        telegram.assert_not_called()
        self.assertEqual(
            list(AuditEvent.objects.values_list('code', flat=True)),
            ['REQUEST_EMAIL_SENT'])

    def test_partial_invalid_telegram_does_not_block_ready_email(self):
        with self.settings(SERVICE_REQUEST_TELEGRAM_CHAT_ID='not-a-chat-id'), \
                patch('service_requests.notifications._credential',
                      return_value='s' * 32), \
                patch('service_requests.notifications._telegram_token') as token, \
                patch('service_requests.notifications._live_email') as email, \
                patch('service_requests.notifications._live_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual([(item.channel, item.success) for item in result], [
            ('email', True)])
        token.assert_not_called()
        email.assert_called_once()
        telegram.assert_not_called()

    def test_both_fully_configured_channels_remain_independent(self):
        with self.settings(SERVICE_REQUEST_TELEGRAM_CHAT_ID='123456'), \
                patch('service_requests.notifications._credential',
                      return_value='s' * 32), \
                patch('service_requests.notifications._telegram_token',
                      return_value='123456:' + 'a' * 20), \
                patch('service_requests.notifications._live_email') as email, \
                patch('service_requests.notifications._live_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual([(item.channel, item.success) for item in result], [
            ('email', True), ('telegram', True)])
        email.assert_called_once()
        telegram.assert_called_once()

    def test_no_ready_channel_returns_no_delivery_or_audit_success(self):
        RequestSettings.objects.filter(pk=1).update(recipient_email='')
        with self.settings(
                SERVICE_REQUEST_SMTP_HOST='',
                SERVICE_REQUEST_TELEGRAM_CHAT_ID=''), \
                patch('service_requests.notifications._credential') as credential, \
                patch('service_requests.notifications._live_email') as email, \
                patch('service_requests.notifications._live_telegram') as telegram:
            result = notifications.deliver(self.row)
        self.assertEqual(result, ())
        credential.assert_not_called()
        email.assert_not_called()
        telegram.assert_not_called()
        self.assertFalse(AuditEvent.objects.exists())
