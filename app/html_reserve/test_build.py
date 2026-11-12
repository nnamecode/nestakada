import hashlib
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import HttpResponse
from django.test import TransactionTestCase

from .build import run
from .contracts import ContractError, TargetSpec
from .source import SourceSnapshot
from .storage import ReserveStore


class ManualBuildTests(TransactionTestCase):
    def snapshot(self):
        descriptor = {
            'seo': ['http://localhost:8767', 'deny-all'],
            'files': [], 'usages': [],
        }
        return SourceSnapshot(
            hashlib.sha256(b'source').hexdigest(), descriptor,
            (TargetSpec('/', 200),))

    def response(self):
        return HttpResponse(
            b'<!doctype html><link rel="stylesheet" href="/static/public.css">',
            content_type='text/html; charset=utf-8')

    def test_synchronous_build_writes_resources_and_activates_once(self):
        source = self.snapshot()
        with TemporaryDirectory() as parent, patch(
                'html_reserve.build.resource_bytes',
                return_value=(b'body{}', 'text/css; charset=utf-8')):
            root = Path(parent) / 'reserve'
            result = run(
                root=root, capture_source=lambda: source,
                render=lambda _target: self.response(),
                recapture=lambda: source,
                now=lambda: datetime(
                    2026, 11, 12, tzinfo=datetime_timezone.utc))
            self.assertEqual(result.status, 'activated')
            with ReserveStore(root).locked() as locked:
                pointer = locked.read_pointer()
                manifest = locked.generation_manifest(
                    pointer['current'], pointer['current_manifest_sha256'])
            self.assertEqual(manifest['source_stamp'], source.stamp)
            self.assertEqual(len(manifest['responses']), 1)
            self.assertEqual(manifest['resources'][0]['url'],
                             '/static/public.css')
            self.assertEqual(manifest['totals']['files'], 2)

    def test_private_response_state_fails_before_activation(self):
        source = self.snapshot()
        response = self.response()
        response.set_cookie('private', 'canary')
        with TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_RESPONSE_PRIVATE_STATE'):
                run(root=root, capture_source=lambda: source,
                    render=lambda _target: response,
                    recapture=lambda: source)
            self.assertFalse(root.exists())
