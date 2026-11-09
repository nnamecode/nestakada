"""Finite RC calibration, explicitly unvetted; dedicated existing state volume."""
import hashlib
import os
import random
from unittest import skipUnless

from django.test import TransactionTestCase, override_settings

from . import test_shared_reservation as R


@skipUnless(os.environ.get('ESTAKADA_RUN_SHARED_CALIBRATION') == '1',
            'Finite large calibration runs only in its dedicated runner suite')
@override_settings(ROOT_URLCONF='estakada.urls', AUTH_TRUSTED_PROXY_HOST=None,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SharedCalibrationTests(R.ReservationFixture, TransactionTestCase):
    def max_html(self, kind, *, label='MAX', noisy=False, seed=1):
        from .policy import normalize_html
        marker = 'CALIBRATION_CONTENT_TOKEN'
        template = normalize_html(self.fixture(kind, marker), kind)['html']
        remaining = 1048576 - len(template.encode()) + len(marker) - len(label)
        if noisy:
            text = ''.join(random.Random(seed).choices(
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/', k=remaining))
        else:
            text = '🚀' * (remaining // 4) + 'A' * (remaining % 4)
        result = template.replace(marker, label + text)
        self.assertEqual(len(result.encode()), 1048576, 'CALIBRATION_MAX_FIXTURE_NOT_EXACT')
        return result

    def test_calibration_exact_mebibyte_both_blocks_and_32_real_draft_updates(self):
        from .models import SharedDraft, SharedRevision
        with self.candidate() as evidence:
            for kind in ('header', 'footer'):
                html = self.max_html(kind, label='MAX-' + kind)
                result = self.applied(kind, 'apply', self.intent(kind, html))
                row = SharedRevision.objects.get(pk=result['resultId'])
                self.assertTrue(hashlib.sha256(self.body(row).encode()).hexdigest() == hashlib.sha256(html.encode()).hexdigest(),
                                'CALIBRATION_MAX_BODY_CHANGED')
            context = self.context('header')
            identity = None
            for index in range(32):
                html = self.max_html('header', label='WARM-%02d' % index)
                result = self.applied('header', 'draft', self.intent('header', html, context=context))
                identity = result['resultId'] if identity is None else identity
                self.assertEqual(result['resultId'], identity)
                context = result['editorContext']
                self.assertEqual(context['draftBasis']['revision'], index + 1)
            self.assertEqual(SharedDraft.objects.count(), 1)
            self.assertEqual(SharedDraft.objects.get(pk=identity).revision, 32)
            self.report('FINITE_MAX_1MIB_AND_WARM32', evidence)
