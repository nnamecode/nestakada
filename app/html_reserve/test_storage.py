import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
from unittest import TestCase
from uuid import uuid4

from .contracts import ContractError, active_pointer, canonical_bytes
from .storage import ReserveStore


def _crash_after_generation_rename(root, generation, manifest, files):
    def fault(event):
        if event == 'after_generation_rename':
            os._exit(72)

    with ReserveStore(Path(root), fault=fault).locked() as locked:
        locked.bootstrap()
        locked.write_generation(generation, manifest, files)
    os._exit(99)


def _hold_store_lock(root, connection):
    with ReserveStore(Path(root)).locked():
        connection.send('locked')
        connection.recv()
    connection.close()


def _manifest(generation, files):
    responses = []
    resources = []
    for name, body in files.items():
        row = {
            'name': name.split('/', 1)[1],
            'content_type': ('text/html; charset=utf-8'
                             if name.startswith('responses/') else 'text/css; charset=utf-8'),
            'sha256': hashlib.sha256(body).hexdigest(),
            'byte_size': len(body),
        }
        if name.startswith('responses/'):
            row.update({
                'target': '/', 'status': 200, 'location': None,
                'x_robots_tag': None, 'security_policy_id': 'public-v1',
                'cache_policy_id': 'reserve-v1',
            })
            responses.append(row)
        else:
            row['url'] = '/static/' + row['name']
            resources.append(row)
    return {
        'schema': 'html-reserve-manifest-v1',
        'generation': generation,
        'built_at': '2026-11-12T00:00:00Z',
        'source_stamp': 'a' * 64,
        'responses': responses,
        'resources': resources,
        'retained_asset_ids': [],
        'totals': {'files': len(files), 'bytes': sum(map(len, files.values()))},
    }


class ReserveStorageTests(TestCase):
    def test_bootstrap_is_canonical_private_and_lock_is_nonblocking(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            store = ReserveStore(root)
            with store.locked() as locked:
                self.assertEqual(locked.bootstrap(), active_pointer(None, None, None, None))
                with self.assertRaises(ContractError):
                    with ReserveStore(root).locked():
                        pass
            self.assertEqual(os.stat(root).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(root / 'active.json').st_mode & 0o777, 0o600)
            self.assertEqual(
                (root / 'active.json').read_bytes(),
                canonical_bytes(active_pointer(None, None, None, None)))

    def test_unknown_entries_and_links_fail_closed(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
            (root / 'unknown').write_bytes(b'x')
            with self.assertRaises(ContractError):
                with ReserveStore(root).locked():
                    pass
            (root / 'unknown').unlink()
            os.symlink(root / 'active.json', root / 'linked')
            with self.assertRaises(ContractError):
                with ReserveStore(root).locked():
                    pass

    def test_generation_is_verified_then_atomically_made_immutable(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            generation = str(uuid4())
            response = hashlib.sha256(b'/').hexdigest() + '.html'
            files = {'responses/' + response: b'<!doctype html>',
                     'resources/public.css': b'body{}'}
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
                digest = locked.write_generation(
                    generation, _manifest(generation, files), files)
            target = root / 'generations' / generation
            self.assertTrue(target.is_dir())
            self.assertEqual((target / 'manifest.json').read_bytes(),
                             canonical_bytes(_manifest(generation, files)))
            self.assertEqual(len(digest), 64)
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
                with self.assertRaises(ContractError):
                    locked.write_generation(generation, _manifest(generation, files), files)

    def test_manifest_or_path_mismatch_leaves_active_pointer_unchanged(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            generation = str(uuid4())
            files = {'responses/' + hashlib.sha256(b'/').hexdigest() + '.html': b'ok'}
            manifest = _manifest(generation, files)
            manifest['responses'][0]['byte_size'] += 1
            with ReserveStore(root).locked() as locked:
                before = locked.bootstrap()
                with self.assertRaises(ContractError):
                    locked.write_generation(generation, manifest, files)
                with self.assertRaises(ContractError):
                    locked.write_generation(str(uuid4()), _manifest(str(uuid4()), files),
                                            {'../escape': b'x'})
                self.assertEqual(locked.read_pointer(), before)

    def test_pointer_temp_is_never_authority_and_replace_is_exact(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            generation = str(uuid4())
            files = {'responses/' + hashlib.sha256(b'/').hexdigest() + '.html': b'ok'}
            manifest = _manifest(generation, files)
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
                digest = locked.write_generation(generation, manifest, files)
                pointer = active_pointer(generation, None, digest, None)
                locked.write_pointer(pointer, generation)
                self.assertEqual(locked.read_pointer(), pointer)
            raw = json.loads((root / 'active.json').read_text('ascii'))
            self.assertEqual(raw['current'], generation)
            self.assertFalse(list(root.glob('active.*.tmp')))

    def test_missing_pointer_after_bootstrap_and_malformed_temp_fail_closed(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
            (root / 'active.json').unlink()
            with ReserveStore(root).locked() as locked:
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_POINTER_MISSING_AFTER_BOOTSTRAP'):
                    locked.bootstrap()

        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
            temp = root / ('active.%s.tmp' % uuid4())
            temp.write_bytes(b'{}')
            os.chmod(temp, 0o600)
            with ReserveStore(root).locked() as locked:
                with self.assertRaisesRegex(
                        ContractError, 'HTML_RESERVE_POINTER_TEMP_INVALID'):
                    locked.bootstrap()

    def test_fault_before_generation_rename_leaves_pointer_and_bounded_orphan(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            generation = str(uuid4())
            files = {'responses/' + hashlib.sha256(b'/').hexdigest() + '.html': b'ok'}
            manifest = _manifest(generation, files)

            def fault(event):
                if event == 'before_generation_rename':
                    raise OSError('injected-before-rename')

            with ReserveStore(root, fault=fault).locked() as locked:
                before = locked.bootstrap()
                with self.assertRaisesRegex(OSError, 'injected-before-rename'):
                    locked.write_generation(generation, manifest, files)
                self.assertEqual(locked.read_pointer(), before)
            self.assertTrue((root / 'staging' / generation).is_dir())
            with ReserveStore(root).locked() as locked:
                self.assertEqual(locked.bootstrap(), before)

    def test_reopen_verifies_exact_generation_tree_and_file_bytes(self):
        for mutation in ('bytes', 'unknown'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as parent:
                root = Path(parent) / 'reserve'
                generation = str(uuid4())
                name = hashlib.sha256(b'/').hexdigest() + '.html'
                files = {'responses/' + name: b'ok'}
                with ReserveStore(root).locked() as locked:
                    locked.bootstrap()
                    digest = locked.write_generation(
                        generation, _manifest(generation, files), files)
                    locked.write_pointer(
                        active_pointer(generation, None, digest, None), str(uuid4()))
                tree = root / 'generations' / generation
                if mutation == 'bytes':
                    (tree / 'responses' / name).write_bytes(b'NO')
                    os.chmod(tree / 'responses' / name, 0o600)
                else:
                    (tree / 'unknown').write_bytes(b'x')
                    os.chmod(tree / 'unknown', 0o600)
                with ReserveStore(root).locked() as locked:
                    with self.assertRaises(ContractError):
                        locked.read_pointer()

    def test_reconcile_removes_only_verified_inactive_uuid_trees(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            active_generation, orphan_generation = str(uuid4()), str(uuid4())
            name = hashlib.sha256(b'/').hexdigest() + '.html'
            files = {'responses/' + name: b'ok'}
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
                active_digest = locked.write_generation(
                    active_generation, _manifest(active_generation, files), files)
                locked.write_generation(
                    orphan_generation, _manifest(orphan_generation, files), files)
                locked.write_pointer(
                    active_pointer(active_generation, None, active_digest, None),
                    str(uuid4()))
                removed = locked.reconcile_orphans()
            self.assertEqual(removed, (orphan_generation,))
            self.assertTrue((root / 'generations' / active_generation).is_dir())
            self.assertFalse((root / 'generations' / orphan_generation).exists())

            unsafe_generation = str(uuid4())
            unsafe = root / 'staging' / unsafe_generation
            unsafe.mkdir(mode=0o700)
            (unsafe / 'unknown').write_bytes(b'x')
            with ReserveStore(root).locked() as locked:
                with self.assertRaises(ContractError):
                    locked.reconcile_orphans()
            self.assertTrue(unsafe.is_dir())

    def test_real_child_exit_after_generation_rename_reopens_as_orphan(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            generation = str(uuid4())
            files = {'responses/' + hashlib.sha256(b'/').hexdigest() + '.html': b'ok'}
            manifest = _manifest(generation, files)
            context = multiprocessing.get_context('fork')
            process = context.Process(
                target=_crash_after_generation_rename,
                args=(str(root), generation, manifest, files))
            process.start()
            process.join(15)
            if process.is_alive():
                process.terminate()
                process.join(5)
                self.fail('generation crash worker did not exit')
            self.assertEqual(process.exitcode, 72)
            with ReserveStore(root).locked() as locked:
                pointer = locked.read_pointer()
                self.assertIsNone(pointer['current'])
                self.assertEqual(locked.reconcile_orphans(), (generation,))
            self.assertFalse((root / 'generations' / generation).exists())

    def test_separate_process_observes_nonblocking_busy_lock(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / 'reserve'
            with ReserveStore(root).locked() as locked:
                locked.bootstrap()
            context = multiprocessing.get_context('fork')
            parent_connection, child_connection = context.Pipe()
            process = context.Process(
                target=_hold_store_lock,
                args=(str(root), child_connection))
            process.start()
            self.assertTrue(parent_connection.poll(10))
            self.assertEqual(parent_connection.recv(), 'locked')
            with self.assertRaisesRegex(ContractError, 'HTML_RESERVE_BUILD_BUSY'):
                with ReserveStore(root).locked():
                    pass
            parent_connection.send('release')
            process.join(10)
            if process.is_alive():
                process.terminate()
                process.join(5)
                self.fail('lock worker did not exit')
            self.assertEqual(process.exitcode, 0)
            parent_connection.close()
