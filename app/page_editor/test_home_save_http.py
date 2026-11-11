import copy
import hashlib
import json
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.test import TransactionTestCase, override_settings

from page_versions.models import PageContentState, PageRevision
from media_library import services as media_services
from media_library.models import Asset, AssetFile, MediaFolder

from .test_check_http import TEST_MIDDLEWARE
from .test_home_candidates import HomeCandidateHttpTests


@override_settings(ROOT_URLCONF='page_editor.test_check_http',
                   MIDDLEWARE=TEST_MIDDLEWARE,
                   AUTH_TRUSTED_PROXY_HOST=None,
                   PASSWORD_HASHERS=[
                       'django.contrib.auth.hashers.MD5PasswordHasher'])
class HomeSaveHttpTests(TransactionTestCase):
    login = HomeCandidateHttpTests.login
    revision = HomeCandidateHttpTests.revision
    candidate = HomeCandidateHttpTests.candidate

    def setUp(self):
        HomeCandidateHttpTests.setUp(self)
        self.media_temp = TemporaryDirectory()
        self.addCleanup(self.media_temp.cleanup)
        media_root = override_settings(MEDIA_LIBRARY_ROOT=self.media_temp.name)
        media_root.enable()
        self.addCleanup(media_root.disable)
        self.seed_home_media()
        self.check_url = f'/manage/pages/{self.home.pk}/edit/check/'
        self.save_url = f'/manage/pages/{self.home.pk}/edit/save/'

    def seed_home_media(self):
        """Real registered files for every ImageRef in the home fixture."""
        folder = MediaFolder.objects.create(path='tests/home-save')
        images = self.current().payload['embedded_images']
        for index, image in enumerate(images):
            data = b'home-save-fixture-' + str(index).encode()
            digest = hashlib.sha256(data).hexdigest()
            legacy = index >= 15
            asset = Asset.objects.create(
                id=image['asset_id'], folder=folder,
                provenance='home save integration fixture',
                is_legacy=legacy,
                source_url=(f'https://fixture.invalid/{index}' if legacy else ''),
                source_sha256=(digest if legacy else ''))
            kind = (AssetFile.Kind.LEGACY_PUBLIC if legacy
                    else AssetFile.Kind.MAIN)
            suffix = 'legacy.webp' if legacy else 'main.webp'
            media_services.write_file(
                asset_id=asset.pk, kind=kind,
                key=f'img/{asset.pk}/{suffix}', chunks=data)
            media_services.mark_ready(asset_id=asset.pk)

    def post(self, url, value):
        data = json.dumps(value, ensure_ascii=False,
                          separators=(',', ':')).encode()
        # Django Client has no interruptible WSGI socket. Replace only that
        # transport read seam; the production child/normalizer remains real.
        with patch('page_editor.views.read_json_bytes',
                   side_effect=lambda request, profile: request.body):
            return self.owner_client.post(
                url, data, content_type='application/json',
                HTTP_X_CSRFTOKEN=self.owner_client.cookies[
                    settings.CSRF_COOKIE_NAME].value)

    def current(self):
        state = PageContentState.objects.get(page=self.home)
        return PageRevision.objects.get(pk=state.current_revision_id)

    def check(self, profile):
        value = {
            'protocol': 'page-editor-v1', 'generation': 1,
            'baseRevisionId': str(self.current().pk),
            'editingFrom': 'current', 'draftBasis': None, 'stageId': None,
            'changes': {'home_profile': profile},
        }
        return value, self.post(self.check_url, value)

    def save_checked(self, value, checked):
        body = {**value,
                'changes': checked['normalisedChanges'],
                'operationId': str(uuid4()),
                'checkReceipt': checked['checkReceipt']}
        return self.post(self.save_url, body)

    def test_owner_bind_save_and_unbind_use_candidate_digest(self):
        source, _revision = self.candidate(90, published=True)
        profile = copy.deepcopy(self.current().payload['home_profile'])
        profile['services'][0]['source_page_id'] = str(source.pk)
        profile['services'][0]['fallback_visible'] = False
        value, first = self.check(profile)
        self.assertEqual(first.status_code, 200, first.content)
        first_value = first.json()
        self.assertTrue(first_value['normalisationChanged'])
        canonical = first_value['normalisedChanges']['home_profile']
        self.assertTrue(canonical['services'][0]['fallback_visible'])

        value, second = self.check(canonical)
        self.assertEqual(second.status_code, 200)
        second_value = second.json()
        self.assertFalse(second_value['normalisationChanged'])
        saved = self.save_checked(value, second_value)
        self.assertEqual(saved.status_code, 200)
        profile = self.current().payload['home_profile']
        self.assertEqual(profile['services'][0]['source_page_id'],
                         str(source.pk))
        self.assertTrue(profile['services'][0]['fallback_visible'])

        profile = copy.deepcopy(profile)
        profile['services'][0]['source_page_id'] = None
        value, checked = self.check(profile)
        self.assertEqual(checked.status_code, 200)
        self.assertFalse(checked.json()['normalisationChanged'])
        saved = self.save_checked(value, checked.json())
        self.assertEqual(saved.status_code, 200)
        self.assertIsNone(
            self.current().payload['home_profile']['services'][0][
                'source_page_id'])

        profile = copy.deepcopy(self.current().payload['home_profile'])
        self.assertIsNotNone(profile['works'][0]['source_page_id'])
        profile['works'][0]['source_page_id'] = None
        value, checked = self.check(profile)
        self.assertEqual(checked.status_code, 200, checked.content)
        self.assertFalse(checked.json()['normalisationChanged'])
        saved = self.save_checked(value, checked.json())
        self.assertEqual(saved.status_code, 200, saved.content)
        self.assertIsNone(
            self.current().payload['home_profile']['works'][0][
                'source_page_id'])

    def test_forged_stable_identity_is_rejected_without_revision(self):
        before = self.current()
        profile = copy.deepcopy(before.payload['home_profile'])
        profile['services'][0]['id'] = str(uuid4())
        _value, response = self.check(profile)
        self.assertEqual((response.status_code, response.json()), (400, {
            'ok': False, 'code': 'EDITOR_INPUT_REJECTED'}))
        self.assertEqual(self.current().pk, before.pk)
