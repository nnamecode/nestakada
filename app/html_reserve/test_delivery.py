import hashlib
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.test import SimpleTestCase

from .contracts import ContractError
from .delivery import (
    ABSENT, DeliveryStore, activation_journal, present_selector,
    project_current, selector_bytes,
)
from .contracts import active_pointer, response_name
from .storage import ReserveStore


def _crash_release(root, delivery, boundary):
    def fault(point):
        if point == boundary:
            os._exit(73)
    with DeliveryStore(root).locked() as locked:
        locked.write_release(
            delivery=delivery, source_generation=str(uuid4()),
            source_manifest_sha256='c' * 64,
            maps=b'maps', files={
                'responses/' + 'a' * 64 + '.html': b'x'}, _fault=fault)


def _crash_journal(root, journal, boundary):
    def fault(point):
        if point == boundary:
            os._exit(74)
    with DeliveryStore(root).locked() as locked:
        locked.transition_journal(
            expected_sha256=None, new=journal, _fault=fault)


def _project_while_locked(source, delivery_root, delivery, queue):
    try:
        project_current(
            source_root=source, delivery_root=delivery_root,
            delivery=delivery)
    except ContractError as error:
        queue.put(str(error))
    else:
        queue.put('UNEXPECTED_PASS')


class DeliveryStorageTests(SimpleTestCase):
    def root(self, parent):
        root = Path(parent) / 'delivery'
        root.mkdir(mode=0o700, parents=True)
        return root

    def release_files(self):
        return {
            'responses/' + 'a' * 64 + '.html': b'<p>reserve</p>',
            'resources/' + 'b' * 64 + '.css': b'body{}',
        }

    def source(self, parent):
        root = Path(parent) / 'source'
        generation = str(uuid4())
        target = '/'
        css_url = '/static/public.css'
        files = {
            'responses/' + response_name(target): b'<p>reserve</p>',
            'resources/' + hashlib.sha256(
                css_url.encode('utf-8')).hexdigest() + '.css': b'body{}',
        }
        manifest = {
            'schema': 'html-reserve-manifest-v1',
            'generation': generation,
            'built_at': '2026-11-13T00:00:00Z',
            'source_stamp': 'a' * 64,
            'responses': [{
                'name': response_name(target), 'target': target,
                'status': 200, 'location': None,
                'content_type': 'text/html; charset=utf-8',
                'x_robots_tag': None, 'security_policy_id': 'public-v1',
                'cache_policy_id': 'reserve-v1',
                'sha256': hashlib.sha256(files[
                    'responses/' + response_name(target)]).hexdigest(),
                'byte_size': len(files['responses/' + response_name(target)]),
            }],
            'resources': [{
                'name': hashlib.sha256(
                    css_url.encode('utf-8')).hexdigest() + '.css',
                'url': css_url, 'content_type': 'text/css; charset=utf-8',
                'sha256': hashlib.sha256(files[
                    'resources/' + hashlib.sha256(
                        css_url.encode('utf-8')).hexdigest() + '.css']).hexdigest(),
                'byte_size': 6,
            }],
            'retained_asset_ids': [],
            'totals': {'files': 2, 'bytes': 20},
        }
        with ReserveStore(root).locked() as locked:
            locked.bootstrap()
            digest = locked.write_generation(generation, manifest, files)
            locked._replace_pointer(
                active_pointer(generation, None, digest, None), str(uuid4()))
        return root, generation, digest, files

    def test_release_is_reopened_verified_and_selector_is_reversible(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            delivery = str(uuid4())
            generation = str(uuid4())
            maps = b'# html-reserve-projection-v1\n'
            with DeliveryStore(root).locked() as locked:
                release_sha = locked.write_release(
                    delivery=delivery, source_generation=generation,
                    source_manifest_sha256='c' * 64,
                    maps=maps, files=self.release_files())
                release = locked.read_release(delivery, release_sha)
                self.assertEqual(release['delivery'], delivery)
                self.assertEqual(release['totals'], {'files': 2, 'bytes': 20})
                self.assertEqual(locked.read_selector(), ABSENT)
                body = selector_bytes(delivery, release_sha)
                selected = present_selector(body)
                locked.replace_selector(expected=ABSENT, new=selected)
                self.assertEqual(locked.read_selector(), selected)
                locked.replace_selector(expected=selected, new=ABSENT)
                self.assertEqual(locked.read_selector(), ABSENT)
            self.assertFalse((root / 'selectors' / 'active.conf').exists())

    def test_selector_compare_and_swap_refuses_stale_expected_state(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            first = present_selector(selector_bytes(str(uuid4()), 'a' * 64))
            stale = present_selector(selector_bytes(str(uuid4()), 'b' * 64))
            with DeliveryStore(root).locked() as locked:
                locked.replace_selector(expected=ABSENT, new=first)
                before = (root / 'selectors' / 'active.conf').read_bytes()
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_SELECTOR_STATE_MISMATCH'):
                    locked.replace_selector(expected=stale, new=ABSENT)
                self.assertEqual(
                    (root / 'selectors' / 'active.conf').read_bytes(), before)

    def test_release_rejects_tamper_unknown_entry_and_symlink(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            delivery = str(uuid4())
            with DeliveryStore(root).locked() as locked:
                digest = locked.write_release(
                    delivery=delivery, source_generation=str(uuid4()),
                    source_manifest_sha256='c' * 64, maps=b'maps',
                    files=self.release_files())
            response = root / 'releases' / delivery / 'responses' / (
                'a' * 64 + '.html')
            response.write_bytes(b'tampered')
            with DeliveryStore(root).locked() as locked, self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_FILE_MISMATCH'):
                locked.read_release(delivery, digest)
            response.write_bytes(b'<p>reserve</p>')
            (root / 'unknown').write_text('x', encoding='ascii')
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_ROOT_UNKNOWN'):
                with DeliveryStore(root).locked():
                    pass
            (root / 'unknown').unlink()
            os.symlink(root / 'releases', root / 'linked')
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_ROOT_LINK'):
                with DeliveryStore(root).locked():
                    pass

    def test_release_caps_and_metadata_are_closed_before_publication(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            with DeliveryStore(root).locked() as locked:
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_DELIVERY_FILE_NAME_INVALID'):
                    locked.write_release(
                        delivery=str(uuid4()), source_generation=str(uuid4()),
                        source_manifest_sha256='c' * 64, maps=b'maps',
                        files={'../escape': b'x'})
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_DELIVERY_MAP_LIMIT'):
                    locked.write_release(
                        delivery=str(uuid4()), source_generation=str(uuid4()),
                        source_manifest_sha256='c' * 64,
                        maps=b'x' * (2 * 1024 * 1024 + 1), files={})
            self.assertEqual(list((root / 'releases').iterdir()), [])

    def test_selector_body_and_state_are_canonical(self):
        delivery = str(uuid4())
        body = selector_bytes(delivery, 'a' * 64)
        self.assertEqual(
            body,
            ('# html-reserve-selector-v1 ' + 'a' * 64 + '\ninclude '
             '/delivery/releases/' + delivery + '/maps.conf;\n').encode('ascii'))
        state = present_selector(body)
        self.assertEqual(state['kind'], 'PRESENT')
        self.assertEqual(state['sha256'], hashlib.sha256(body).hexdigest())
        with self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_SELECTOR_BYTES_INVALID'):
            present_selector(b'include /tmp/evil;\n')

    def test_current_source_projects_under_shared_lock_without_source_writes(self):
        with TemporaryDirectory() as parent:
            source, generation, source_sha, files = self.source(parent)
            delivery_root = self.root(Path(parent) / 'target')
            before = {
                str(path.relative_to(source)): (
                    path.stat().st_ino, path.stat().st_size,
                    path.stat().st_mtime_ns)
                for path in source.rglob('*')
            }
            delivery = str(uuid4())
            result = project_current(
                source_root=source, delivery_root=delivery_root,
                delivery=delivery)
            self.assertEqual(result['source_generation'], generation)
            self.assertEqual(result['source_manifest_sha256'], source_sha)
            with DeliveryStore(delivery_root).locked() as locked:
                release = locked.read_release(delivery, result['release_sha256'])
            self.assertEqual(release['source_generation'], generation)
            for name, body in files.items():
                self.assertEqual(
                    (delivery_root / 'releases' / delivery / name).read_bytes(),
                    body)
            after = {
                str(path.relative_to(source)): (
                    path.stat().st_ino, path.stat().st_size,
                    path.stat().st_mtime_ns)
                for path in source.rglob('*')
            }
            self.assertEqual(after, before)

    def test_source_busy_or_tampered_fails_before_delivery_release(self):
        with TemporaryDirectory() as parent:
            source, _generation, _source_sha, _files = self.source(parent)
            delivery_root = self.root(Path(parent) / 'target')
            with ReserveStore(source).locked(), self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_SOURCE_BUSY'):
                project_current(
                    source_root=source, delivery_root=delivery_root,
                    delivery=str(uuid4()))
            self.assertEqual(list((delivery_root).iterdir()), [])
            response = next((source / 'generations').glob(
                '*/responses/*.html'))
            response.write_bytes(b'tampered')
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_SOURCE_FILE_MISMATCH'):
                project_current(
                    source_root=source, delivery_root=delivery_root,
                    delivery=str(uuid4()))
            self.assertEqual(list((delivery_root).iterdir()), [])

    def test_real_child_shared_projector_refuses_exclusive_source_lock(self):
        with TemporaryDirectory() as parent:
            source, _generation, _source_sha, _files = self.source(parent)
            delivery_root = self.root(Path(parent) / 'target')
            context = multiprocessing.get_context('spawn')
            queue = context.Queue()
            child = context.Process(
                target=_project_while_locked,
                args=(str(source), str(delivery_root), str(uuid4()), queue))
            with ReserveStore(source).locked():
                child.start()
                child.join(10)
            self.assertEqual(child.exitcode, 0)
            self.assertEqual(queue.get(timeout=2), 'HTML_RESERVE_SOURCE_BUSY')
            self.assertEqual(list(delivery_root.iterdir()), [])

    def test_journal_is_canonical_cas_and_transition_closed(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            operation = str(uuid4())
            old = ABSENT
            new = present_selector(selector_bytes(str(uuid4()), 'a' * 64))
            prepared = activation_journal(
                operation=operation, sequence=0, stage='PREPARED',
                old_selector=old, new_selector=new, previous_sha256=None)
            with DeliveryStore(root).locked() as locked:
                digest = locked.transition_journal(
                    expected_sha256=None, new=prepared)
                reread, actual_digest = locked.read_journal()
                self.assertEqual((reread, actual_digest), (prepared, digest))
                candidate = activation_journal(
                    operation=operation, sequence=1,
                    stage='SELECTOR_CANDIDATE', old_selector=old,
                    new_selector=new, previous_sha256=digest)
                next_digest = locked.transition_journal(
                    expected_sha256=digest, new=candidate)
                self.assertNotEqual(next_digest, digest)
                with self.assertRaisesRegex(
                        ContractError,
                        'HTML_RESERVE_JOURNAL_STATE_MISMATCH'):
                    locked.transition_journal(
                        expected_sha256=digest, new=candidate)

    def test_real_child_release_crash_has_deterministic_reconcile(self):
        context = multiprocessing.get_context('fork')
        for boundary, expected in (
                ('staging-fsynced', 'REMOVED'),
                ('release-renamed', 'PUBLISHED')):
            with self.subTest(boundary=boundary), TemporaryDirectory() as parent:
                root = self.root(parent)
                delivery = str(uuid4())
                child = context.Process(
                    target=_crash_release,
                    args=(str(root), delivery, boundary))
                child.start()
                child.join(10)
                self.assertEqual(child.exitcode, 73)
                with DeliveryStore(root).locked() as locked:
                    self.assertEqual(
                        locked.reconcile_staging(delivery), expected)

    def test_real_child_journal_crash_has_canonical_temp_recovery(self):
        context = multiprocessing.get_context('fork')
        for boundary, published in (
                ('journal-temp-fsynced', False),
                ('journal-renamed', True)):
            with self.subTest(boundary=boundary), TemporaryDirectory() as parent:
                root = self.root(parent)
                journal = activation_journal(
                    operation=str(uuid4()), sequence=0, stage='PREPARED',
                    old_selector=ABSENT,
                    new_selector=present_selector(selector_bytes(
                        str(uuid4()), 'a' * 64)), previous_sha256=None)
                child = context.Process(
                    target=_crash_journal,
                    args=(str(root), journal, boundary))
                child.start()
                child.join(10)
                self.assertEqual(child.exitcode, 74)
                with DeliveryStore(root).locked() as locked:
                    if published:
                        reread, _digest = locked.read_journal()
                        self.assertEqual(reread, journal)
                    else:
                        self.assertEqual(
                            locked.reconcile_journal_temp(), 'REMOVED')
                        self.assertEqual(locked.read_journal(), (None, None))

    def test_hardlink_is_rejected_for_source_and_delivery_bytes(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            delivery = str(uuid4())
            with DeliveryStore(root).locked() as locked:
                digest = locked.write_release(
                    delivery=delivery, source_generation=str(uuid4()),
                    source_manifest_sha256='c' * 64, maps=b'maps',
                    files=self.release_files())
            response = root / 'releases' / delivery / 'responses' / (
                'a' * 64 + '.html')
            os.link(response, Path(parent) / 'alias')
            with DeliveryStore(root).locked() as locked, self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_FILE_MISMATCH'):
                locked.read_release(delivery, digest)
