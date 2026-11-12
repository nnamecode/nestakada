from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from shared_content.public import RenderedShared
from shared_content.public_views import html_response
from . import middleware, notifications, public
from .models import RequestSettings


class CacheAndBodyBoundaryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_dynamic_response_never_returns_shared_304(self):
        rendered = RenderedShared('', '', '"shared-etag"', 'fingerprint')
        request = self.factory.get('/', HTTP_IF_NONE_MATCH='"shared-etag"')
        cached = html_response(request, rendered, b'body')
        self.assertEqual(cached.status_code, 304)
        dynamic = html_response(
            request, rendered, b'private-body', private_dynamic=True)
        self.assertEqual(dynamic.status_code, 200)
        self.assertEqual(dynamic.content, b'private-body')
        self.assertEqual(dynamic['Cache-Control'], 'private, no-store')
        self.assertEqual(dynamic['Vary'], 'Cookie')
        self.assertNotIn('ETag', dynamic)

    @override_settings(
        SERVICE_REQUEST_INTAKE_ENABLED=True,
        SERVICE_REQUEST_TRANSPORT_PROFILE='synthetic',
        SERVICE_REQUEST_CONSENT_VERSION='synthetic-v1')
    def test_two_clients_receive_different_intent_and_csrf(self):
        first = public.form_for(self.factory.get('/'), '/')
        second = public.form_for(self.factory.get('/'), '/')
        self.assertTrue(first['enabled'])
        self.assertNotEqual(first['intent'], second['intent'])
        self.assertNotEqual(first['csrf_token'], second['csrf_token'])

    def test_default_off_has_no_intent_or_csrf(self):
        value = public.form_for(self.factory.get('/'), '/')
        self.assertEqual(value, {'enabled': False, 'source': 'home'})

    def test_exact_middleware_rejects_missing_and_mismatched_length(self):
        boundary = middleware.RequestBodyLimitMiddleware(
            lambda request: HttpResponse('accepted'))
        missing = self.factory.post(
            '/request/submit/', 'a=1',
            content_type='application/x-www-form-urlencoded')
        missing.META.pop('CONTENT_LENGTH', None)
        self.assertEqual(boundary(missing).status_code, 400)
        mismatch = self.factory.post(
            '/request/submit/', 'a=1',
            content_type='application/x-www-form-urlencoded')
        ignored = mismatch.body
        mismatch.META['CONTENT_LENGTH'] = '99'
        self.assertEqual(boundary(mismatch).status_code, 400)
        huge = self.factory.post(
            '/request/submit/', 'a=1',
            content_type='application/x-www-form-urlencoded')
        huge.META['CONTENT_LENGTH'] = '9' * 10_000
        self.assertEqual(boundary(huge).status_code, 400)

    @override_settings(
        SERVICE_REQUEST_INTAKE_ENABLED=True,
        SERVICE_REQUEST_TRANSPORT_PROFILE='live',
        SERVICE_REQUEST_CONSENT_VERSION='approved-v1')
    def test_live_profile_does_not_issue_intent_before_launch_gate(self):
        value = public.form_for(self.factory.get('/'), '/')
        self.assertEqual(value, {'enabled': False, 'source': 'home'})


class FakeResponse:
    def __init__(self, body=b'{"ok":true}', status=200):
        self.body = body
        self.status = status
        self.closed = False

    def read(self, limit):
        return self.body

    def close(self):
        self.closed = True


class FakeOpener:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return self.response


@override_settings(
    SERVICE_REQUEST_LEGAL_PROFILE='approved-v1',
    SERVICE_REQUEST_SMTP_HOST='smtp.example.test',
    SERVICE_REQUEST_SMTP_PORT='465',
    SERVICE_REQUEST_SMTP_USER='sender@example.test',
    SERVICE_REQUEST_SMTP_SECURITY='ssl',
    SERVICE_REQUEST_TELEGRAM_CHAT_ID='123456')
class TelegramBoundaryTests(TestCase):
    def setUp(self):
        RequestSettings.objects.create(recipient_email='owner@example.test')
        self.payload = {
            'name': 'Тестовый клиент', 'phone': '+70000000000',
            'car': '', 'comment': '', 'source': 'home',
        }

    def test_fixed_https_no_proxy_no_redirect_and_bounded_response(self):
        response = FakeResponse()
        opener = FakeOpener(response)
        captured = {}

        def build(*handlers):
            captured['handlers'] = handlers
            return opener

        with patch('service_requests.notifications._credential',
                   return_value='123456789:telegram-token-with-enough-entropy'), \
                patch('service_requests.notifications.request.build_opener',
                      side_effect=build):
            notifications._live_telegram(self.payload)
        sent, timeout = opener.calls[0]
        self.assertTrue(sent.full_url.startswith(
            'https://api.telegram.org/bot123456789:'))
        self.assertTrue(sent.full_url.endswith('/sendMessage'))
        self.assertEqual(timeout, 5)
        self.assertTrue(response.closed)
        self.assertTrue(any(
            isinstance(item, notifications._NoRedirect)
            for item in captured['handlers']))
        proxy = next(item for item in captured['handlers']
                     if isinstance(item, notifications.request.ProxyHandler))
        self.assertEqual(proxy.proxies, {})
        self.assertIsNone(notifications._NoRedirect().redirect_request(
            None, None, 302, '', {}, 'https://example.test'))

    def test_oversized_response_fails_closed(self):
        opener = FakeOpener(FakeResponse(body=b'x' * 4097))
        with patch('service_requests.notifications._credential',
                   return_value='123456789:telegram-token-with-enough-entropy'), \
                patch('service_requests.notifications.request.build_opener',
                      return_value=opener):
            with self.assertRaises(OSError):
                notifications._live_telegram(self.payload)

    def test_token_delimiters_fail_before_opener(self):
        with patch('service_requests.notifications._credential',
                   return_value='123456789:bad/token-with-enough-entropy'), \
                patch('service_requests.notifications.request.build_opener') as opener:
            with self.assertRaises(ValueError):
                notifications._live_telegram(self.payload)
        opener.assert_not_called()
