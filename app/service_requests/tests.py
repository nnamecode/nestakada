from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from . import intents, policy
from .models import RequestSettings, ServiceRequest


class PolicyTests(SimpleTestCase):
    def test_normalizes_agreed_fields(self):
        value = policy.normalize(
            source='home', name='  Тестовый   клиент ',
            phone='8 (000) 000-00-00', car='  Марка   Модель ',
            comment=' строка 1\r\nстрока 2 ', consent='on',
            consent_version='synthetic-v1')
        self.assertEqual(value.name, 'Тестовый клиент')
        self.assertEqual(value.phone, '+70000000000')
        self.assertEqual(value.car, 'Марка Модель')
        self.assertEqual(value.comment, 'строка 1\nстрока 2')

    def test_phone_matrix(self):
        for raw in ['+7 000 000-00-00', '+7(000)0000000', '8 000 000 00 00']:
            with self.subTest(raw=raw):
                self.assertEqual(policy.normalize_phone(raw), '+70000000000')
        for raw in ['', '70000000000', '+80000000000', '+7 000 abc', '+7\x00000000000']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValidationError):
                    policy.normalize_phone(raw)

    def test_rejects_required_limits_controls_and_source(self):
        base = dict(source='contacts', name='Имя', phone='+70000000000', car='',
                    comment='', consent='on', consent_version='synthetic-v1')
        for change in [
                {'source': 'external'}, {'name': ''}, {'name': 'x' * 101},
                {'car': 'x' * 301}, {'comment': 'x' * 4001},
                {'comment': 'x\x00y'}, {'consent': ''},
                {'consent_version': ''}]:
            with self.subTest(change=change):
                with self.assertRaises(ValidationError):
                    policy.normalize(**{**base, **change})


@override_settings(SECRET_KEY='test-secret-key-with-enough-entropy-0001')
class IntentTests(SimpleTestCase):
    def test_issue_verify_and_digest(self):
        token = intents.issue(source='home', consent_version='synthetic-v1')
        payload = intents.verify(token)
        self.assertEqual(payload['source'], 'home')
        self.assertEqual(payload['consent_version'], 'synthetic-v1')
        self.assertRegex(payload['nonce'], r'^[0-9a-f]{32}$')
        self.assertRegex(intents.digest(token), r'^[0-9a-f]{64}$')

    def test_tamper_wrong_shape_and_expiry_fail_closed(self):
        token = intents.issue(source='contacts', consent_version='synthetic-v1')
        with self.assertRaises(ValidationError):
            intents.verify(token + 'x')
        malformed = signing.dumps(
            {'schema': 'service-request-intent-v1', 'source': 'contacts'},
            salt=intents.INTENT_SALT)
        with self.assertRaises(ValidationError):
            intents.verify(malformed)
        with patch('django.core.signing.time.time', return_value=1_000):
            old = intents.issue(source='home', consent_version='synthetic-v1')
        with patch('django.core.signing.time.time', return_value=2_801):
            with self.assertRaises(ValidationError):
                intents.verify(old)


class ModelTests(TestCase):
    def test_minimal_schema_and_ordering(self):
        row = ServiceRequest.objects.create(
            source='home', name='Тестовый клиент', phone='+70000000000',
            car='', comment='', consent_version='synthetic-v1',
            intent_digest='a' * 64)
        self.assertIsNotNone(row.created_at)
        self.assertEqual(ServiceRequest.objects.get().pk, row.pk)
        self.assertFalse(hasattr(row, 'status'))
        self.assertFalse(hasattr(row, 'updated_at'))

    def test_settings_are_singleton(self):
        row = RequestSettings.objects.create(recipient_email='owner@example.test')
        self.assertEqual(row.pk, 1)
        with self.assertRaises(ValidationError):
            RequestSettings(id=2, recipient_email='owner@example.test').save()
