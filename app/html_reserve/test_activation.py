import hashlib
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.db import connections, models
from django.test import TransactionTestCase, override_settings

from media_library import services
from media_library.models import Asset, AssetFile, AssetUsage, MediaFolder
from media_library.storage import MediaStorage
from content.models import Page, Route
from page_versions import schema as page_schema
from page_versions.models import PageContentState, PageRevision
from shared_content.models import SharedBlock, SharedRevision

from .activation import activate_prebuilt
from .contracts import ContractError, response_name
from .source import SourceSnapshot
from .storage import ReserveStore


def _raw(model):
    return models.QuerySet(model=model, using='default')


def _crash_activation_worker(root, generation, digest, stamp, crash_event):
    connections.close_all()
    snapshot = SourceSnapshot(stamp, {}, ())

    def activation_fault(event):
        if event == crash_event:
            os._exit(71)

    def storage_fault(event):
        if event == crash_event:
            os._exit(71)

    with ReserveStore(Path(root), fault=storage_fault).locked() as locked:
        activate_prebuilt(
            store=locked, generation_id=generation,
            manifest_sha256=digest, source_snapshot=snapshot,
            recapture=lambda: snapshot, fault=activation_fault)
    os._exit(99)


class ActivationTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.media_temp = TemporaryDirectory()
        self.reserve_temp = TemporaryDirectory()
        self.settings_override = override_settings(
            MEDIA_LIBRARY_ROOT=self.media_temp.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_temp.cleanup)
        self.addCleanup(self.reserve_temp.cleanup)
        self.root = Path(self.reserve_temp.name) / 'reserve'
        self.folder = MediaFolder.objects.create(path='html-activation')
        self.media = MediaStorage()

    def asset(self):
        asset = Asset.objects.create(
            folder=self.folder, provenance='DEV25 activation test')
        services.write_file(
            asset_id=asset.pk, kind=AssetFile.Kind.MAIN,
            key='img/%s/main.webp' % asset.pk,
            chunks=b'RIFFxxxxWEBPactivation', storage=self.media)
        return services.mark_ready(asset_id=asset.pk, storage=self.media)

    def public_source(self):
        for kind in ('header', 'footer'):
            block = SharedBlock.objects.create(kind=kind)
            body = '<%s>safe</%s>' % (kind, kind)
            revision = SharedRevision.objects.create(
                block=block, sequence=1, schema_version=kind + '-v1',
                html=body,
                payload_hash=hashlib.sha256(body.encode()).hexdigest(),
                author_id=1)
            _raw(SharedBlock).filter(pk=block.pk).update(
                current_revision=revision, generation=1)
        page = Page.objects.create(
            name='Activation source', kind=Page.Kind.ARTICLE,
            position=0, is_published=True)
        Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY,
            target='/activation-source/')
        payload = page_schema.snapshot_v1(
            page.kind, h1=page.name, title=page.name).data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=page_schema.SCHEMA,
            payload=payload, payload_hash=page_schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        state = PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page, state, revision

    def generation(self, locked, *, stamp, asset_ids):
        generation = str(uuid4())
        body = b'<!doctype html><title>reserve</title>'
        name = response_name('/')
        files = {'responses/' + name: body}
        manifest = {
            'schema': 'html-reserve-manifest-v1',
            'generation': generation,
            'built_at': '2026-11-12T00:00:00Z',
            'source_stamp': stamp,
            'responses': [{
                'name': name, 'target': '/', 'status': 200, 'location': None,
                'content_type': 'text/html; charset=utf-8',
                'x_robots_tag': None, 'security_policy_id': 'public-v1',
                'cache_policy_id': 'reserve-v1',
                'sha256': hashlib.sha256(body).hexdigest(),
                'byte_size': len(body),
            }],
            'resources': [],
            'retained_asset_ids': sorted(asset_ids),
            'totals': {'files': 1, 'bytes': len(body)},
        }
        digest = locked.write_generation(generation, manifest, files)
        return generation, digest

    def test_success_moves_current_to_previous_and_reconciles_third(self):
        asset = self.asset()
        snapshot = SourceSnapshot('a' * 64, {}, ())
        with ReserveStore(self.root).locked() as locked:
            locked.bootstrap()
            generations = []
            for _index in range(3):
                generation, digest = self.generation(
                    locked, stamp=snapshot.stamp, asset_ids=[str(asset.pk)])
                result = activate_prebuilt(
                    store=locked, generation_id=generation,
                    manifest_sha256=digest, source_snapshot=snapshot,
                    recapture=lambda: snapshot)
                self.assertEqual(result.status, 'activated')
                generations.append(generation)
            pointer = locked.read_pointer()
        self.assertEqual(pointer['current'], generations[2])
        self.assertEqual(pointer['previous'], generations[1])
        self.assertFalse((self.root / 'generations' / generations[0]).exists())
        self.assertEqual(set(str(value) for value in AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML).values_list(
                'consumer_id', flat=True)), set(generations[1:]))

    def test_source_drift_keeps_pointer_and_safely_over_retains(self):
        asset = self.asset()
        source_a = SourceSnapshot('a' * 64, {}, ())
        source_b = SourceSnapshot('b' * 64, {}, ())
        with ReserveStore(self.root).locked() as locked:
            before = locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=source_a.stamp, asset_ids=[str(asset.pk)])
            with self.assertRaisesRegex(ContractError, 'HTML_RESERVE_SOURCE_CHANGED'):
                activate_prebuilt(
                    store=locked, generation_id=generation,
                    manifest_sha256=digest, source_snapshot=source_a,
                    recapture=lambda: source_b)
            self.assertEqual(locked.read_pointer(), before)
        self.assertTrue(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).exists())

    def test_post_replace_error_is_confirmed_by_reread(self):
        snapshot = SourceSnapshot('a' * 64, {}, ())
        armed = {'value': False}

        def fault(event):
            if armed['value'] and event == 'after_pointer_replace':
                raise OSError('injected-after-replace')

        with ReserveStore(self.root, fault=fault).locked() as locked:
            locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=snapshot.stamp, asset_ids=[])
            armed['value'] = True
            result = activate_prebuilt(
                store=locked, generation_id=generation,
                manifest_sha256=digest, source_snapshot=snapshot,
                recapture=lambda: snapshot)
            self.assertTrue(result.durability_warning)
            self.assertEqual(locked.read_pointer()['current'], generation)

    def test_pre_replace_error_keeps_old_pointer_and_safe_retention(self):
        asset = self.asset()
        snapshot = SourceSnapshot('a' * 64, {}, ())
        armed = {'value': False}

        def fault(event):
            if armed['value'] and event == 'before_pointer_replace':
                raise OSError('injected-before-replace')

        with ReserveStore(self.root, fault=fault).locked() as locked:
            before = locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=snapshot.stamp, asset_ids=[str(asset.pk)])
            armed['value'] = True
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_PRE_ACTIVATION_FAILED'):
                activate_prebuilt(
                    store=locked, generation_id=generation,
                    manifest_sha256=digest, source_snapshot=snapshot,
                    recapture=lambda: snapshot)
            self.assertEqual(locked.read_pointer(), before)
        self.assertTrue(AssetUsage.objects.filter(
            kind=AssetUsage.Kind.RETAINED_HTML,
            consumer_id=generation).exists())

    def test_unreadable_post_replace_pointer_is_result_unknown(self):
        snapshot = SourceSnapshot('a' * 64, {}, ())
        armed = {'value': False}

        def fault(event):
            if armed['value'] and event == 'after_pointer_replace':
                (self.root / 'active.json').write_bytes(b'{}')
                (self.root / 'active.json').chmod(0o600)
                raise OSError('injected-ambiguous-after-replace')

        with ReserveStore(self.root, fault=fault).locked() as locked:
            locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=snapshot.stamp, asset_ids=[])
            armed['value'] = True
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_ACTIVATION_RESULT_UNKNOWN'):
                activate_prebuilt(
                    store=locked, generation_id=generation,
                    manifest_sha256=digest, source_snapshot=snapshot,
                    recapture=lambda: snapshot)

    def test_cleanup_failure_is_warning_without_activation_rollback(self):
        snapshot = SourceSnapshot('a' * 64, {}, ())
        with ReserveStore(self.root).locked() as locked:
            locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=snapshot.stamp, asset_ids=[])
            unsafe = self.root / 'staging' / str(uuid4())
            unsafe.mkdir(mode=0o700)
            (unsafe / 'unknown').write_bytes(b'x')
            result = activate_prebuilt(
                store=locked, generation_id=generation,
                manifest_sha256=digest, source_snapshot=snapshot,
                recapture=lambda: snapshot)
            self.assertTrue(result.cleanup_warning)
            self.assertEqual(locked.read_pointer()['current'], generation)

    def test_real_child_exit_reopens_retained_replace_and_fsync_boundaries(self):
        asset = self.asset()
        snapshot = SourceSnapshot('a' * 64, {}, ())
        context = multiprocessing.get_context('fork')
        expected_active = None
        for event in ('after_retained_commit', 'after_pointer_replace',
                      'after_pointer_fsync'):
            with self.subTest(event=event):
                with ReserveStore(self.root).locked() as locked:
                    locked.bootstrap()
                    generation, digest = self.generation(
                        locked, stamp=snapshot.stamp,
                        asset_ids=[str(asset.pk)])
                connections.close_all()
                process = context.Process(
                    target=_crash_activation_worker,
                    args=(str(self.root), generation, digest,
                          snapshot.stamp, event))
                process.start()
                process.join(15)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                    self.fail('crash worker did not exit')
                self.assertEqual(process.exitcode, 71)
                connections.close_all()
                with ReserveStore(self.root).locked() as locked:
                    pointer = locked.read_pointer()
                    if event == 'after_retained_commit':
                        self.assertEqual(pointer['current'], expected_active)
                    else:
                        self.assertEqual(pointer['current'], generation)
                        expected_active = generation
                    locked.reconcile_orphans()
                    active_ids = [value for value in (
                        pointer['current'], pointer['previous'])
                        if value is not None]
                    services.reconcile_retained_html(
                        active_generation_ids=active_ids)
                retained = set(str(value) for value in AssetUsage.objects.filter(
                    kind=AssetUsage.Kind.RETAINED_HTML).values_list(
                        'consumer_id', flat=True))
                self.assertEqual(retained, set(active_ids))

    @override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                       SEO_ROBOTS_PROFILE='deny-all')
    def test_real_postgresql_source_change_between_a_and_final_lock_refuses(self):
        page, state, revision = self.public_source()
        from .source import capture
        source_a = capture()
        with ReserveStore(self.root).locked() as locked:
            before = locked.bootstrap()
            generation, digest = self.generation(
                locked, stamp=source_a.stamp, asset_ids=[])
            payload = dict(revision.payload)
            payload['title'] = 'Changed between source A and activation'
            changed = PageRevision.objects.create(
                page=page, sequence=2, schema_version=page_schema.SCHEMA,
                payload=payload, payload_hash=page_schema.digest(payload),
                kind=PageRevision.Kind.AUTOMATIC, author_id=1)
            _raw(PageContentState).filter(pk=state.pk).update(
                current_revision=changed, sequence=2)
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_SOURCE_CHANGED'):
                activate_prebuilt(
                    store=locked, generation_id=generation,
                    manifest_sha256=digest, source_snapshot=source_a,
                    recapture=capture)
            self.assertEqual(locked.read_pointer(), before)
