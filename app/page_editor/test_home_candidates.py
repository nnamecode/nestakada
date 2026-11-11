import copy
import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4
from django.conf import settings
from django.db import models
from django.test import Client, TransactionTestCase, override_settings
from accounts.services import bootstrap_owner, create_employee
from content.models import Page, Route
from page_versions import schema as S
from page_versions.models import PageContentState, PageRevision
from .test_check_http import TEST_MIDDLEWARE


PACKAGE = Path(__file__).resolve().parents[1] / 'content' / 'dev12_home_profile.json'
PASSWORD = 'Home-candidate-owner-password'
EMPLOYEE_PASSWORD = 'Home-candidate-employee-password'


@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HomeCandidateHttpTests(TransactionTestCase):
    def setUp(self):
        package = json.loads(PACKAGE.read_text(encoding='utf-8'))
        embedded = [{'id': item['image_id'], 'asset_id': item['asset_id'],
                     'alt': item['alt'], 'alignment': 'center',
                     'width_px': None, 'height_px': None}
                    for item in package['media']]
        embedded += [{'id': item['image_id'], 'asset_id': item['asset_id'],
                      'alt': item['alt'], 'alignment': 'center',
                      'width_px': None, 'height_px': None}
                     for item in package['profile']['works']]
        self.owner = bootstrap_owner(PASSWORD)
        self.employee = create_employee(actor=self.owner, username='home-candidate-employee',
                                        password=EMPLOYEE_PASSWORD)
        self.home = Page.objects.create(kind=Page.Kind.HOME, name='Home')
        Route.objects.create(page=self.home, kind=Route.Kind.PRIMARY, target='/')
        payload = S.snapshot_v1(Page.Kind.HOME, h1='Home', embedded_images=embedded,
            home_profile=copy.deepcopy(package['profile'])).data(Page.Kind.HOME)
        self.revision(self.home, payload)
        self.owner_client = self.login('nesadmin', PASSWORD)
        self.employee_client = self.login(self.employee.username, EMPLOYEE_PASSWORD)
        self.visitor = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')
        self.url = f'/manage/pages/{self.home.pk}/edit/sources/'

    def login(self, username, password):
        client = Client(enforce_csrf_checks=True, HTTP_HOST='localhost')
        self.assertEqual(client.get('/manage/login/').status_code, 200)
        token = client.cookies[settings.CSRF_COOKIE_NAME].value
        body = urlencode({'username': username, 'password': password,
                          'csrfmiddlewaretoken': token})
        self.assertEqual(client.post('/manage/login/', body,
            content_type='application/x-www-form-urlencoded').status_code, 303)
        return client

    def revision(self, page, payload=None):
        payload = payload or S.snapshot_v1(page.kind, h1=page.name).data(page.kind)
        row = PageRevision.objects.create(page=page, sequence=1, schema_version=S.SCHEMA,
            payload=payload, payload_hash=S.digest(payload), kind=PageRevision.Kind.INITIAL,
            author_id=self.owner.pk)
        PageContentState.objects.create(page=page, current_revision=row, sequence=1)
        return row

    def candidate(self, index, *, published=False):
        page = Page.objects.create(kind=Page.Kind.SERVICE, name=f'Candidate {index:02d}',
                                   is_published=published)
        Route.objects.create(page=page, kind=Route.Kind.PRIMARY,
                             target=f'/candidate-{index:02d}/')
        return page, self.revision(page)

    def test_owner_exact_twenty_plus_one_and_deterministic_shape(self):
        rows = [self.candidate(index, published=index % 2 == 0) for index in range(22)]
        response = self.owner_client.get(self.url, {'q': 'candidate-'})
        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertEqual(set(value), {'protocol', 'results', 'hasNext'})
        self.assertEqual(value['protocol'], 'home-source-candidates-v1')
        self.assertTrue(value['hasNext']); self.assertEqual(len(value['results']), 20)
        self.assertEqual([item['path'] for item in value['results']],
                         [f'/candidate-{index:02d}/' for index in range(20)])
        self.assertEqual(set(value['results'][0]), {
            'pageId', 'path', 'name', 'kind', 'published', 'currentRevisionId'})
        self.assertEqual(value['results'][0]['pageId'], str(rows[0][0].pk))
        self.assertFalse(value['results'][1]['published'])
        self.assertIn('no-store', response['Cache-Control'])

    def test_query_is_required_closed_and_never_bulk_lists(self):
        self.candidate(0)
        for suffix in ('', '?q=', '?q=%20x', '?q=x%20', '?q=x&q=y',
                       '?q=x&extra=1', '?q=' + 'x' * 101, '?q=%0A'):
            with self.subTest(suffix=suffix):
                response = self.owner_client.get(self.url + suffix)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {
                    'ok': False, 'code': 'EDITOR_SOURCE_QUERY_INVALID'})

    def test_owner_only_and_home_profile_only(self):
        self.assertEqual(self.visitor.get(self.url + '?q=x').status_code, 401)
        self.assertEqual(self.employee_client.get(self.url + '?q=x').status_code, 403)
        article = Page.objects.create(kind=Page.Kind.ARTICLE, name='Article')
        Route.objects.create(page=article, kind=Route.Kind.PRIMARY, target='/article/')
        self.revision(article)
        response = self.owner_client.get(
            f'/manage/pages/{article.pk}/edit/sources/?q=x')
        self.assertEqual(response.status_code, 403)

    def test_corrupt_matching_current_fails_whole_response(self):
        _page, revision = self.candidate(0)
        models.QuerySet(model=PageRevision, using='default').filter(
            pk=revision.pk).update(payload_hash='0' * 64)
        response = self.owner_client.get(self.url, {'q': 'candidate-'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'ok': False, 'code': 'EDITOR_SOURCE_UNAVAILABLE'})
        self.assertNotIn('Candidate 00', response.content.decode())

    def test_editor_exposes_profile_and_closed_local_ui_module(self):
        response = self.owner_client.get(f'/manage/pages/{self.home.pk}/edit/')
        self.assertEqual(response.status_code, 200)
        initial = response.context['initial_state']
        self.assertTrue(initial['owner'])
        self.assertEqual(initial['values']['home_profile']['schema'], 'home-profile-v1')
        asset = self.owner_client.get('/manage/editor-assets/home-profile-editor.mjs')
        self.assertEqual(asset.status_code, 200)
        source = b''.join(asset.streaming_content).decode('utf-8')
        for required in ('mountHomeProfileEditor', 'Содержимое главной страницы',
                         'Поля и порядок секций фиксированы', 'Найти источник'):
            self.assertIn(required, source)
        for forbidden in ('innerHTML', 'eval(', 'Function(', 'fetch(', 'WebSocket',
                          'localStorage', 'sessionStorage', 'document.cookie'):
            self.assertNotIn(forbidden, source)
