import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import Client, TestCase

from accounts.models import UserProfile
from accounts.test_support import editor_session
from audit.models import AuditEvent

from .activation import ActivationResult
from .contracts import ContractError, active_pointer
from .source import SourceSnapshot
from .storage import ReserveStore


class HtmlReserveHttpTests(TestCase):
    def stored_generation(self, locked, generation, stamp):
        manifest = {
            'schema': 'html-reserve-manifest-v1',
            'generation': generation,
            'built_at': '2026-11-12T00:00:00Z',
            'source_stamp': stamp,
            'responses': [], 'resources': [], 'retained_asset_ids': [],
            'totals': {'files': 0, 'bytes': 0},
        }
        return locked.write_generation(generation, manifest, {})

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'reserve'
        self.root.mkdir(mode=0o700)
        os.chmod(self.root, 0o700)
        self.root_override = self.settings(HTML_RESERVE_ROOT=str(self.root))
        self.root_override.enable()
        self.addCleanup(self.root_override.disable)
        users = get_user_model()
        self.owner = users.objects.create_user('nesadmin', password='owner-password-123')
        self.employee = users.objects.create_user('reserve-worker', password='worker-password-123')
        UserProfile.objects.create(user=self.owner, role='owner')
        UserProfile.objects.create(user=self.employee, role='employee')

    def browser(self, user, *, csrf=False):
        browser = Client(enforce_csrf_checks=csrf)
        browser.cookies[settings.SESSION_COOKIE_NAME] = editor_session(user)
        return browser

    def post(self, browser, values, token=None):
        if token is not None:
            values = {**values, 'csrfmiddlewaretoken': token}
        return browser.post(
            '/manage/html-reserve/', urlencode(values),
            content_type='application/x-www-form-urlencoded')

    def test_owner_only_get_is_private_and_initial_root_shows_button(self):
        self.assertEqual(Client().get('/manage/html-reserve/').status_code, 401)
        self.assertEqual(self.browser(self.employee).get(
            '/manage/html-reserve/').status_code, 403)
        response = self.browser(self.owner).get('/manage/html-reserve/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertContains(response, 'Создать новую HTML-версию')

    def test_dashboard_links_html_reserve_only_for_owner(self):
        owner = self.browser(self.owner).get('/manage/')
        employee = self.browser(self.employee).get('/manage/')
        self.assertContains(owner, '/manage/html-reserve/')
        self.assertNotContains(employee, '/manage/html-reserve/')

    def test_status_shows_current_and_previous_or_neutral_absence(self):
        stamp = 'a' * 64
        current = '11111111-1111-4111-8111-111111111111'
        previous = '22222222-2222-4222-8222-222222222222'
        with ReserveStore(self.root).locked() as locked:
            locked.bootstrap()
            current_digest = self.stored_generation(locked, current, stamp)
            previous_digest = self.stored_generation(locked, previous, stamp)
            locked.write_pointer(active_pointer(
                current, previous, current_digest, previous_digest),
                str(uuid4()))
        snapshot = SourceSnapshot(stamp, {}, ())
        with patch('html_reserve.views.capture', return_value=snapshot):
            response = self.browser(self.owner).get('/manage/html-reserve/')
        self.assertContains(response, '11111111')
        self.assertContains(response, '22222222')
        self.assertContains(response, 'Предыдущее поколение')

        with patch('html_reserve.views._status', return_value={
                'available': True, 'current': current, 'previous': None,
                'built_at': '2026-11-12T00:00:00Z', 'stale': False}):
            response = self.browser(self.owner).get('/manage/html-reserve/')
        self.assertContains(response, 'Нет')

    def test_csrf_exact_form_and_success_audit(self):
        browser = self.browser(self.owner, csrf=True)
        get = browser.get('/manage/html-reserve/')
        token = browser.cookies[settings.CSRF_COOKIE_NAME].value
        self.assertEqual(self.post(browser, {'action': 'build'}).status_code, 403)
        with patch('html_reserve.views.build_run', return_value=ActivationResult(
                generation_id='11111111-1111-4111-8111-111111111111',
                status='activated', durability_warning=False,
                cleanup_warning=False)) as build:
            bad = self.post(browser, {'action': 'build', 'extra': 'x'}, token)
            self.assertEqual(bad.status_code, 400)
            self.assertFalse(build.called)
            success = self.post(browser, {'action': 'build'}, token)
            self.assertEqual(success.status_code, 200)
            self.assertEqual(build.call_count, 1)
        self.assertEqual(list(AuditEvent.objects.order_by('id').values_list(
            'code', flat=True)), [
                'HTML_RESERVE_BUILD_STARTED', 'HTML_RESERVE_BUILD_SUCCEEDED'])
        self.assertContains(success, 'создана и активирована')

    def test_start_audit_failure_blocks_build(self):
        browser = self.browser(self.owner)
        with patch('html_reserve.views.record_event',
                   side_effect=DatabaseError('private-canary')), patch(
                       'html_reserve.views.build_run') as build:
            response = self.post(browser, {'action': 'build'})
        self.assertEqual(response.status_code, 503)
        self.assertFalse(build.called)
        self.assertNotContains(response, 'private-canary', status_code=503)

    def test_missing_root_is_neutral_and_never_calls_build(self):
        missing = self.root / 'missing'
        with self.settings(HTML_RESERVE_ROOT=str(missing)), patch(
                'html_reserve.views.build_run') as build:
            get = self.browser(self.owner).get('/manage/html-reserve/')
            post = self.post(self.browser(self.owner), {'action': 'build'})
        self.assertEqual(get.status_code, 503)
        self.assertEqual(post.status_code, 503)
        self.assertFalse(build.called)
        self.assertNotContains(get, str(missing), status_code=503)

    def test_busy_is_neutral_and_audited_without_retry(self):
        browser = self.browser(self.owner)
        with patch('html_reserve.views.build_run',
                   side_effect=ContractError('HTML_RESERVE_BUILD_BUSY')) as build:
            response = self.post(browser, {'action': 'build'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(build.call_count, 1)
        self.assertContains(response, 'уже выполняется')
        self.assertEqual(list(AuditEvent.objects.order_by('id').values_list(
            'code', flat=True)), [
                'HTML_RESERVE_BUILD_STARTED', 'HTML_RESERVE_BUILD_BUSY'])

    def test_success_audit_failure_keeps_activated_result_with_warning(self):
        browser = self.browser(self.owner)
        result = ActivationResult(
            generation_id='11111111-1111-4111-8111-111111111111',
            status='activated', durability_warning=False,
            cleanup_warning=False)
        with patch('html_reserve.views.build_run', return_value=result), patch(
                'html_reserve.views._audit',
                side_effect=[None, DatabaseError('private-success-audit')]):
            response = self.post(browser, {'action': 'build'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'создана и активирована')
        self.assertContains(response, 'требуется проверить предупреждение')
        self.assertNotContains(response, 'private-success-audit')

    def test_owner_private_request_state_is_not_forwarded_to_builder(self):
        browser = self.browser(self.owner)
        browser.cookies['private-canary'] = 'OWNER-COOKIE-CANARY'
        result = ActivationResult(
            generation_id='11111111-1111-4111-8111-111111111111',
            status='activated', durability_warning=False,
            cleanup_warning=False)
        with patch('html_reserve.views.build_run', return_value=result) as build:
            response = browser.post(
                '/manage/html-reserve/', urlencode({'action': 'build'}),
                content_type='application/x-www-form-urlencoded',
                HTTP_IF_NONE_MATCH='"OWNER-ETAG-CANARY"',
                HTTP_X_PRIVATE_CANARY='OWNER-HEADER-CANARY')
        self.assertEqual(response.status_code, 200)
        build.assert_called_once_with(root=self.root)
        for marker in ('OWNER-COOKIE-CANARY', 'OWNER-ETAG-CANARY',
                       'OWNER-HEADER-CANARY'):
            self.assertNotContains(response, marker)
