import hashlib
import multiprocessing
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.http import HttpResponse
from django.db import connections, models
from django.test import TransactionTestCase

from content.public_views import PUBLIC_CSP
from media_library import services as media_services
from media_library.models import Asset, AssetUsage, MediaFolder

from .build import run
from .contracts import ContractError, TargetSpec, active_pointer
from .source import SourceSnapshot
from .storage import ReserveStore


def _full_build_worker(root, ready, release, result, block):
    source = SourceSnapshot(
        'c' * 64, {'seo': ['http://localhost:8767', 'deny-all'],
                   'files': [], 'usages': []}, (TargetSpec('/', 200),))
    response = HttpResponse(b'<!doctype html><p>reserve</p>',
                            content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['Content-Security-Policy'] = PUBLIC_CSP
    response['X-Content-Type-Options'] = 'nosniff'

    def capture():
        if block:
            ready.set()
            release.wait(10)
        return source
    try:
        run(root=Path(root), capture_source=capture,
            render=lambda _target: response, recapture=lambda: source)
    except Exception as error:
        result.put(str(error))
    else:
        result.put('activated')


class ManualBuildTests(TransactionTestCase):
    def stored_generation(self, locked, generation, stamp, asset_ids):
        manifest = {
            'schema': 'html-reserve-manifest-v1',
            'generation': generation,
            'built_at': '2026-11-12T00:00:00Z',
            'source_stamp': stamp,
            'responses': [], 'resources': [],
            'retained_asset_ids': sorted(asset_ids),
            'totals': {'files': 0, 'bytes': 0},
        }
        return locked.write_generation(generation, manifest, {})

    def snapshot(self):
        descriptor = {
            'seo': ['http://localhost:8767', 'deny-all'],
            'files': [], 'usages': [],
        }
        return SourceSnapshot(
            hashlib.sha256(b'source').hexdigest(), descriptor,
            (TargetSpec('/', 200),))

    def response(self):
        response = HttpResponse(
            b'<!doctype html><link rel="stylesheet" href="/static/public.css">',
            content_type='text/html; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        response['Content-Security-Policy'] = PUBLIC_CSP
        response['X-Content-Type-Options'] = 'nosniff'
        return response

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
            self.assertTrue(root.exists())

    def test_unexpected_security_header_fails_before_filesystem_mutation(self):
        source = self.snapshot()
        response = self.response()
        response['Content-Security-Policy-Report-Only'] = "default-src 'none'"
        with TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_RESPONSE_HEADERS_INVALID'):
                run(root=root, capture_source=lambda: source,
                    render=lambda _target: response,
                    recapture=lambda: source)
            self.assertTrue(root.exists())

    def test_missing_or_changed_public_policy_fails_closed(self):
        source = self.snapshot()
        for value in (None, "default-src 'self'"):
            with self.subTest(value=value), TemporaryDirectory() as parent:
                response = self.response()
                if value is None:
                    del response['Content-Security-Policy']
                else:
                    response['Content-Security-Policy'] = value
                root = Path(parent) / 'reserve'
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_RESPONSE_SECURITY_INVALID'):
                    run(root=root, capture_source=lambda: source,
                        render=lambda _target: response,
                        recapture=lambda: source)
                self.assertTrue(root.exists())

    def test_resource_cap_and_unused_public_asset_retention_are_exact(self):
        source = self.snapshot()
        with TemporaryDirectory() as parent, patch(
                'html_reserve.build.MAX_RESOURCES', 0):
            root = Path(parent) / 'reserve'
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_RESOURCE_LIMIT'):
                run(root=root, capture_source=lambda: source,
                    render=lambda _target: self.response(),
                    recapture=lambda: source)

        unused_asset = '11111111-1111-4111-8111-111111111111'
        unused_file = '22222222-2222-4222-8222-222222222222'
        descriptor = {
            'seo': ['http://localhost:8767', 'deny-all'],
            'files': [[unused_file, unused_asset, 'main', 'unused',
                       'a' * 64, 1]],
            'usages': [['33333333-3333-4333-8333-333333333333',
                        'current_page', '44444444-4444-4444-8444-444444444444',
                        'main_image', unused_asset]],
        }
        source = SourceSnapshot('b' * 64, descriptor, (TargetSpec('/', 200),))
        response = self.response()
        response.content = b'<!doctype html><p>No media</p>'
        with TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            result = run(root=root, capture_source=lambda: source,
                         render=lambda _target: response,
                         recapture=lambda: source)
            with ReserveStore(root).locked() as locked:
                pointer = locked.read_pointer()
                manifest = locked.generation_manifest(
                    pointer['current'], pointer['current_manifest_sha256'])
            self.assertEqual(result.status, 'activated')
            self.assertEqual(manifest['retained_asset_ids'], [])

    def test_two_full_build_processes_produce_one_busy_and_one_activation(self):
        with TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            context = multiprocessing.get_context('fork')
            ready, release, result = context.Event(), context.Event(), context.Queue()
            connections.close_all()
            first = context.Process(
                target=_full_build_worker,
                args=(str(root), ready, release, result, True))
            first.start()
            self.assertTrue(ready.wait(10))
            second = context.Process(
                target=_full_build_worker,
                args=(str(root), ready, release, result, False))
            second.start()
            second.join(10)
            release.set()
            first.join(15)
            for process in (first, second):
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                    self.fail('full build worker did not exit')
                self.assertEqual(process.exitcode, 0)
            self.assertEqual({result.get(timeout=5), result.get(timeout=5)},
                             {'activated', 'HTML_RESERVE_BUILD_BUSY'})
            connections.close_all()

    def test_next_run_reconciles_stale_retention_before_capture(self):
        source = self.snapshot()
        response = self.response()
        response.content = b'<!doctype html><p>No media</p>'
        folder = MediaFolder.objects.create(path='html-build-reconcile')
        asset = Asset.objects.create(
            folder=folder, provenance='DEV25 build reconcile test')
        models.QuerySet(model=Asset, using='default').filter(
            pk=asset.pk).update(status=Asset.Status.READY)
        current, previous, stale = (str(uuid4()) for _ in range(3))
        for generation in (current, previous, stale):
            AssetUsage.objects.create(
                asset=asset, kind=AssetUsage.Kind.RETAINED_HTML,
                consumer_id=generation, slot=str(asset.pk))

        with TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
                current_digest = self.stored_generation(
                    locked, current, source.stamp, [str(asset.pk)])
                previous_digest = self.stored_generation(
                    locked, previous, source.stamp, [str(asset.pk)])
                locked.write_pointer(active_pointer(
                    current, previous, current_digest, previous_digest),
                    str(uuid4()))

            observed = []

            def capture_after_reconcile():
                consumers = set(str(value) for value in
                                AssetUsage.objects.filter(
                                    kind=AssetUsage.Kind.RETAINED_HTML
                                ).values_list('consumer_id', flat=True))
                observed.append(consumers)
                return source

            with patch.object(media_services, 'MAX_RETAINED_HTML_USAGES', 3):
                result = run(
                    root=root, capture_source=capture_after_reconcile,
                    render=lambda _target: response,
                    recapture=lambda: source)

            self.assertEqual(result.status, 'activated')
            self.assertEqual(observed, [{current, previous}])
            with ReserveStore(root).locked() as locked:
                pointer = locked.read_pointer()
            self.assertEqual(pointer['current'], result.generation_id)
            self.assertEqual(pointer['previous'], current)
            self.assertEqual(set(str(value) for value in
                                 AssetUsage.objects.filter(
                                     kind=AssetUsage.Kind.RETAINED_HTML
                                 ).values_list('consumer_id', flat=True)),
                             {current})
