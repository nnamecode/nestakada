"""SH2 actual private filesystem checks, not an enabled write quota profile.

Scan revalidation witnesses these concrete races, not a universal atomic FS
snapshot. Future product writers require the cooperative content-domain lock.
"""
import errno
import hashlib
import os
from pathlib import Path
import stat
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID, uuid4

from django.test import SimpleTestCase, override_settings

from shared_content.faults import SharedFault


class SharedStorageTests(SimpleTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        override.enable()
        self.addCleanup(override.disable)
        from shared_content.storage import SharedStorage
        self.store = SharedStorage()

    def path(self, descriptor):
        root = self.store.root
        path = root / descriptor['file_key']
        self.assertTrue(path.is_relative_to(root))
        return path

    def refuse_unlink(self, descriptor):
        with self.assertRaises(SharedFault) as failure:
            self.store.unlink_verified(descriptor)
        self.assertEqual((failure.exception.code, failure.exception.status),
                         ('SHARED_CLEANUP_FILE_UNAVAILABLE', 503))

    def test_unlink_wrong_sha_symlink_and_hardlink_preserve_every_named_victim(self):
        other = self.store.write_new('LC-UNRELATED-VICTIM')
        other_path = self.store.root / other['file_key']
        for vector in ('wrong-sha', 'symlink', 'hardlink'):
            with self.subTest(vector=vector):
                descriptor = self.store.write_new('LC-SELECTED-VICTIM-' + vector)
                path = self.store.root / descriptor['file_key']
                before = path.read_bytes()
                if vector == 'wrong-sha':
                    descriptor = dict(descriptor, file_sha256='0' * 64)
                else:
                    path.unlink()
                    if vector == 'symlink':
                        path.symlink_to(other_path)
                    else:
                        os.link(other_path, path)
                with patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
                    self.refuse_unlink(descriptor)
                self.assertEqual(unlink.call_count, 0)
                self.assertTrue(path.is_symlink() if vector == 'symlink' else path.is_file())
                expected = before if vector == 'wrong-sha' else b'LC-UNRELATED-VICTIM'
                self.assertEqual(path.read_bytes(), expected)
                self.assertEqual(other_path.read_bytes(), b'LC-UNRELATED-VICTIM')

    def test_unlink_inode_replacement_after_hash_read_preserves_both_files(self):
        descriptor = self.store.write_new('LC-HELD-ORIGINAL')
        path = self.store.root / descriptor['file_key']
        retained = path.with_name('own-retained-original')
        identity = path.stat()
        original, hits = os.read, []

        def replace_after_eof(fd, size):
            value = original(fd, size)
            info = os.fstat(fd)
            if not value and not hits and (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                hits.append('target-eof')
                path.rename(retained)
                path.write_bytes(b'LC-NEW-NAMED-VICTIM')
                path.chmod(0o600)
            return value

        with patch('shared_content.storage.os.read', side_effect=replace_after_eof), \
             patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
            self.refuse_unlink(descriptor)
        self.assertEqual(hits, ['target-eof'])
        self.assertEqual(unlink.call_count, 0)
        self.assertEqual(retained.read_bytes(), b'LC-HELD-ORIGINAL')
        self.assertEqual(path.read_bytes(), b'LC-NEW-NAMED-VICTIM')

    def test_unlink_parent_rename_after_hash_read_preserves_both_trees(self):
        descriptor = self.store.write_new('LC-HELD-PARENT-VICTIM')
        path = self.store.root / descriptor['file_key']
        parent = path.parent
        retained = parent.with_name(parent.name + '-own-retained')
        identity = path.stat()
        original, hits = os.read, []

        def rename_after_eof(fd, size):
            value = original(fd, size)
            info = os.fstat(fd)
            if not value and not hits and (info.st_dev, info.st_ino) == (identity.st_dev, identity.st_ino):
                hits.append('target-eof')
                parent.rename(retained)
                parent.mkdir(mode=0o700)
                path.write_bytes(b'LC-NEW-PARENT-VICTIM')
                path.chmod(0o600)
            return value

        with patch('shared_content.storage.os.read', side_effect=rename_after_eof), \
             patch('shared_content.storage.os.unlink', wraps=os.unlink) as unlink:
            self.refuse_unlink(descriptor)
        self.assertEqual(hits, ['target-eof'])
        self.assertEqual(unlink.call_count, 0)
        self.assertEqual((retained / path.name).read_bytes(), b'LC-HELD-PARENT-VICTIM')
        self.assertEqual(path.read_bytes(), b'LC-NEW-PARENT-VICTIM')

    def actual(self):
        """Independent finite walk: lstat only, never follow test links."""
        allocated, logical, files, directories = 0, 0, 0, 0
        if not self.store.root.exists():
            return allocated, logical, files, directories
        pending = [self.store.root]
        while pending:
            path = pending.pop()
            info = path.lstat()
            allocated += info.st_blocks * 512
            logical += info.st_size
            if stat.S_ISDIR(info.st_mode):
                self.assertEqual((stat.S_IMODE(info.st_mode), info.st_uid), (0o700, os.geteuid()))
                directories += 1
                pending.extend(path.iterdir())
            else:
                self.assertTrue(stat.S_ISREG(info.st_mode))
                files += 1
        return allocated, logical, files, directories

    def assert_inventory(self, *, referenced=()):
        result = self.store.inventory(referenced_keys=referenced)
        allocated, logical, files, directories = self.actual()
        self.assertTrue(result['complete'])
        self.assertEqual(result['actualAllocatedBytes'], allocated)
        self.assertEqual(result['logicalBytes'], logical)
        self.assertEqual(result['blobCount'] + result['journalCount'], files)
        self.assertEqual(result['directoryCount'], directories)
        self.assertFalse(result['fsMetadataReserveAvailable'])
        self.assertIsNone(result['reserveBytes'])
        self.assertFalse(result['profileAvailable'])
        self.assertFalse(result['reservationReadiness'])
        self.assertRegex(result['inventoryStamp'], r'^[0-9a-f]{64}$')
        return result

    def test_utf8_exact_mebibyte_real_roundtrip_modes_and_durable_order(self):
        texts = ('Малый текст 🚀', 'Ж' * 524288)
        original_fsync = os.fsync
        original_open = os.open
        events = []
        opened = []

        def observe_open(*args, **kwargs):
            fd = original_open(*args, **kwargs)
            opened.append(fd)
            return fd

        def observe(fd):
            info = os.fstat(fd)
            kind = 'file' if stat.S_ISREG(info.st_mode) else 'directory'
            original_fsync(fd)
            events.append(kind)

        for text in texts:
            events.clear()
            opened.clear()
            with patch('shared_content.storage.os.fsync', side_effect=observe), \
                 patch('shared_content.storage.os.open', side_effect=observe_open):
                descriptor = self.store.write_new(text)
            self.assertTrue(bool(opened), 'NO_ACTUAL_STORAGE_OPEN_OBSERVED')
            for fd in set(opened):
                with self.assertRaises(OSError) as failure:
                    os.fstat(fd)
                self.assertEqual(failure.exception.errno, errno.EBADF, 'STORAGE_FD_NOT_CLOSED')
            raw = text.encode('utf-8')
            self.assertEqual(descriptor['storage_kind'], 'file')
            self.assertEqual(descriptor['byte_size'], len(raw))
            self.assertEqual(descriptor['file_sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(self.path(descriptor).read_bytes(), raw)
            self.assertEqual(self.store.read(descriptor), text)
            info = self.path(descriptor).lstat()
            self.assertTrue(stat.S_ISREG(info.st_mode))
            self.assertEqual((stat.S_IMODE(info.st_mode), info.st_nlink, info.st_uid),
                             (0o600, 1, os.geteuid()))
            self.assertIn('file', events)
            self.assertEqual(events[-2:], ['file', 'directory'], 'DURABLE_FINAL_ORDER')
        self.assertEqual(len(texts[1].encode()), 1048576)
        result = self.assert_inventory()
        self.assertEqual((result['blobCount'], result['orphanCount']), (2, 2))

    def test_invalid_utf8_size_and_existing_identity_never_overwrite(self):
        for value in (b'\xff', 'X' * 1048577, 42):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(SharedFault):
                    self.store.write_new(value)
        identity = uuid4()
        descriptor = self.store.write_new('ORIGINAL', blob_id=identity)
        original = self.path(descriptor).lstat()
        for value in ('ORIGINAL', 'REPLACED'):
            with self.assertRaises(SharedFault):
                self.store.write_new(value, blob_id=identity)
            self.assertEqual(self.path(descriptor).read_bytes(), b'ORIGINAL')
            self.assertEqual(self.path(descriptor).lstat().st_ino, original.st_ino)
        self.assert_inventory(referenced=(descriptor['file_key'],))

    def test_read_rejects_missing_truncated_changed_same_size_and_wrong_metadata(self):
        descriptor = self.store.write_new('ORIGINAL')
        path = self.path(descriptor)
        for content in (b'X', b'REPLACED', b'\xff' * 8):
            path.write_bytes(content)
            with self.assertRaises(SharedFault):
                self.store.read(descriptor)
            if content == b'\xff' * 8:
                # Even matching length/SHA cannot authorize invalid UTF-8.
                with self.assertRaises(SharedFault):
                    self.store.read({**descriptor, 'byte_size': len(content),
                                     'file_sha256': hashlib.sha256(content).hexdigest()})
                self.assertEqual(self.assert_inventory()['orphanCount'], 1)
        path.write_bytes(b'ORIGINAL')
        for field, value in (('byte_size', 9), ('file_sha256', '0' * 64),
                             ('file_key', '../escape'), ('file_key', '/etc/passwd'),
                             ('file_key', 'blobs/00/' + uuid4().hex + '.html')):
            with self.assertRaises(SharedFault):
                self.store.read({**descriptor, field: value})
        path.unlink()
        with self.assertRaises(SharedFault):
            self.store.read(descriptor)
        with self.assertRaises(SharedFault):
            self.store.inventory(referenced_keys=(descriptor['file_key'],))

    def test_symlink_hardlink_fifo_and_wrong_mode_fail_without_following(self):
        descriptor = self.store.write_new('ORIGINAL')
        path = self.path(descriptor)
        target = Path(self.temp.name) / 'own-target'
        target.write_bytes(b'PRIVATE-TARGET')
        path.unlink()
        os.symlink(target, path)
        for action in (lambda: self.store.read(descriptor), lambda: self.store.inventory()):
            with self.assertRaises(SharedFault):
                action()
        self.assertEqual(target.read_bytes(), b'PRIVATE-TARGET')
        path.unlink()
        path.write_bytes(b'ORIGINAL')
        os.chmod(path, 0o600)
        extra = Path(self.temp.name) / 'own-hardlink'
        os.link(path, extra)
        for action in (lambda: self.store.read(descriptor), lambda: self.store.inventory()):
            with self.assertRaises(SharedFault):
                action()
        extra.unlink()
        os.chmod(path, 0o644)
        for action in (lambda: self.store.read(descriptor), lambda: self.store.inventory()):
            with self.assertRaises(SharedFault):
                action()
        os.chmod(path, 0o600)
        path.unlink()
        os.mkfifo(path, 0o600)
        for action in (lambda: self.store.read(descriptor), lambda: self.store.inventory()):
            with self.assertRaises(SharedFault):
                action()
        path.unlink()
        path.write_bytes(b'ORIGINAL')
        os.chmod(path, 0o600)
        self.assertEqual(self.store.read(descriptor), 'ORIGINAL')
        self.assert_inventory()

    def test_parent_symlink_and_unknown_entry_are_not_empty_measurements(self):
        descriptor = self.store.write_new('ORIGINAL')
        fanout = self.path(descriptor).parent
        moved = Path(self.temp.name) / 'own-moved-fanout'
        fanout.rename(moved)
        os.symlink(moved, fanout)
        with self.assertRaises(SharedFault):
            self.store.read(descriptor)
        with self.assertRaises(SharedFault):
            self.store.inventory()
        fanout.unlink()
        moved.rename(fanout)
        unknown = self.store.root / 'unknown-object'
        unknown.write_bytes(b'UNEXPECTED')
        with self.assertRaises(SharedFault):
            self.store.inventory()
        self.assertTrue(unknown.exists(), 'SCANNER_DELETED_UNKNOWN_ENTRY')
        self.assertEqual(self.path(descriptor).read_bytes(), b'ORIGINAL')

    def test_real_write_and_fsync_faults_preserve_counted_orphans_without_success(self):
        original_write, original_fsync = os.write, os.fsync
        # Same fanout is precreated so directory-fsync fault reaches leaf commit.
        baseline = self.store.write_new('HEALTHY-BASE', blob_id=UUID('aa' + '0' * 30))
        for index, fault in enumerate(('partial', 'file-fsync', 'directory-fsync'), 1):
            identity = UUID('aa' + format(index, '030x'))
            hits = {'write': 0, 'fault': 0, 'fileSynced': False}
            before = self.assert_inventory()

            def write(fd, value):
                hits['write'] += 1
                if fault == 'partial':
                    if hits['write'] == 1:
                        return original_write(fd, value[:5])
                    hits['fault'] += 1
                    raise OSError(errno.EIO, 'SHB_TEST_WRITE_FAULT')
                return original_write(fd, value)

            def fsync(fd):
                is_file = stat.S_ISREG(os.fstat(fd).st_mode)
                if fault == 'file-fsync' and is_file:
                    hits['fault'] += 1
                    raise OSError(errno.EIO, 'SHB_TEST_FILE_FSYNC_FAULT')
                if fault == 'directory-fsync' and not is_file and hits['fileSynced']:
                    hits['fault'] += 1
                    raise OSError(errno.EIO, 'SHB_TEST_DIRECTORY_FSYNC_FAULT')
                original_fsync(fd)
                if is_file:
                    hits['fileSynced'] = True

            with patch('shared_content.storage.os.write', side_effect=write), \
                 patch('shared_content.storage.os.fsync', side_effect=fsync):
                with self.assertRaises(SharedFault):
                    self.store.write_new('FAULT-BODY-' * 100, blob_id=identity)
            self.assertEqual(hits['fault'], 1, 'ACTUAL_STORAGE_FAULT_NOT_REACHED')
            after = self.assert_inventory()
            self.assertEqual(after['blobCount'], before['blobCount'] + 1)
            self.assertEqual(after['orphanCount'], before['orphanCount'] + 1)
            self.assertGreaterEqual(after['actualAllocatedBytes'], before['actualAllocatedBytes'])
            self.assertEqual(self.path(baseline).read_bytes(), b'HEALTHY-BASE',
                             'FAILED_WRITE_CHANGED_EXISTING_SOURCE')
            recovered = self.store.write_new('SEPARATE-HEALTHY-' + fault)
            self.assertEqual(self.store.read(recovered), 'SEPARATE-HEALTHY-' + fault)
        self.assert_inventory()

    def test_unknown_journal_record_is_counted_without_ready_reservation_profile(self):
        self.store.write_new('REFERENCED')
        journal = self.store.root / 'journal'
        journal.mkdir(mode=0o700, exist_ok=True)
        entry = journal / (uuid4().hex + '.json')
        entry.write_bytes(b'{"notAuthoritative":"pending"}')
        os.chmod(entry, 0o600)
        result = self.assert_inventory()
        self.assertEqual(result['journalCount'], 1)
        self.assertFalse(result['profileAvailable'])
        self.assertEqual(entry.read_bytes(), b'{"notAuthoritative":"pending"}')

    def test_actual_file_change_during_verified_read_is_refused(self):
        descriptor = self.store.write_new('R' * 1048576)
        path = self.path(descriptor)
        original_read, hits = os.read, []

        def mutate_after_real_read(fd, size):
            data = original_read(fd, size)
            if data and not hits:
                hits.append(True)
                path.write_bytes(b'Y' + b'R' * 1048575)
            return data

        with patch('shared_content.storage.os.read', side_effect=mutate_after_real_read):
            with self.assertRaises(SharedFault):
                self.store.read(descriptor)
        self.assertEqual(len(hits), 1, 'ACTUAL_READ_MUTATION_NOT_REACHED')
        self.assertEqual(path.read_bytes(), b'Y' + b'R' * 1048575)
        self.assert_inventory()

    def test_existing_empty_media_root_is_zero_without_creating_private_directory(self):
        self.assertTrue(Path(self.temp.name).is_dir())
        self.assertFalse((Path(self.temp.name) / 'private').exists())
        result = self.assert_inventory()
        self.assertEqual((result['actualAllocatedBytes'], result['logicalBytes'],
            result['blobCount'], result['orphanCount'], result['journalCount'],
            result['directoryCount']), (0, 0, 0, 0, 0, 0))
        self.assertEqual(list(Path(self.temp.name).iterdir()), [], 'EMPTY_SCAN_CREATED_DIRECTORIES')
        from shared_content.storage import SharedStorage
        missing = Path(self.temp.name) / 'missing-media-root'
        with override_settings(MEDIA_LIBRARY_ROOT=str(missing)):
            with self.assertRaises(SharedFault) as refusal:
                SharedStorage().inventory()
            self.assertEqual(refusal.exception.code, 'SHARED_MEASUREMENT_UNAVAILABLE')
        self.assertFalse(missing.exists(), 'MISSING_MEDIA_ROOT_WAS_CREATED')

    def test_scan_refuses_earlier_blob_changed_when_later_blob_opens(self):
        a = self.store.write_new('ORIGINAL-A', blob_id=UUID('aa' + '0' * 29 + '1'))
        b = self.store.write_new('ORIGINAL-B', blob_id=UUID('aa' + '0' * 29 + '2'))
        a_path, b_path = self.path(a), self.path(b)
        parent_mtime = a_path.parent.stat().st_mtime_ns
        original_open, hits = os.open, []

        def change_earlier_at_real_later_open(path, flags, *args, **kwargs):
            fd = original_open(path, flags, *args, **kwargs)
            if path == b_path.name and not hits:
                hits.append(True)
                a_path.write_bytes(b'CHANGED-A-LONGER')
            return fd

        with patch('shared_content.storage.os.open', side_effect=change_earlier_at_real_later_open):
            with self.assertRaises(SharedFault) as refusal:
                self.store.inventory()
            self.assertEqual(refusal.exception.code, 'SHARED_MEASUREMENT_UNAVAILABLE')
        self.assertEqual(len(hits), 1, 'SCAN_EARLIER_FILE_MUTATION_NOT_REACHED')
        self.assertEqual(a_path.parent.stat().st_mtime_ns, parent_mtime,
                         'TEST_ACCIDENTALLY_CHANGED_DIRECTORY_MTIME')
        self.assertEqual(a_path.read_bytes(), b'CHANGED-A-LONGER')
        self.assertEqual(b_path.read_bytes(), b'ORIGINAL-B')
        # A separate complete observation includes the retained mutation.
        result = self.assert_inventory()
        self.assertEqual((result['blobCount'], result['orphanCount']), (2, 2))

    def test_read_refuses_fanout_renamed_and_replaced_after_leaf_fd_opened(self):
        baseline = self.store.write_new('UNAFFECTED-BASELINE', blob_id=UUID('bb' + '0' * 30))
        descriptor = self.store.write_new('READ-SOURCE', blob_id=UUID('aa' + '0' * 30))
        original_path = self.path(descriptor)
        held_directory = original_path.parent.with_name('aa-held-renamed')
        original_read, hits = os.read, []

        def replace_parent_after_actual_read(fd, size):
            data = original_read(fd, size)
            if data and not hits:
                hits.append(True)
                original_path.parent.rename(held_directory)
                original_path.parent.mkdir(mode=0o700)
                original_path.write_bytes(b'WRONG-REPLACEMENT')
                os.chmod(original_path, 0o600)
            return data

        with patch('shared_content.storage.os.read', side_effect=replace_parent_after_actual_read):
            with self.assertRaises(SharedFault) as refusal:
                self.store.read(descriptor)
            self.assertEqual(refusal.exception.code, 'SHARED_CONTENT_UNAVAILABLE')
        self.assertEqual(len(hits), 1, 'HELD_READ_PARENT_REPLACEMENT_NOT_REACHED')
        self.assertEqual((held_directory / original_path.name).read_bytes(), b'READ-SOURCE')
        self.assertEqual(original_path.read_bytes(), b'WRONG-REPLACEMENT')
        self.assertEqual(self.store.read(baseline), 'UNAFFECTED-BASELINE')
        with self.assertRaises(SharedFault):
            self.store.inventory()
        self.assertTrue(held_directory.is_dir(), 'FAILED_READ_DELETED_PRESERVED_DIRECTORY')
        # Invalid renamed entry remains. No claim that this corpus is healthy.

    def test_write_refuses_fanout_renamed_and_replaced_after_leaf_fd_opened(self):
        baseline = self.store.write_new('UNAFFECTED-BASELINE', blob_id=UUID('bb' + '0' * 30))
        identity = UUID('aa' + '0' * 30)
        key = 'blobs/aa/' + identity.hex + '.html'
        original_path = self.store.root / key
        held_directory = original_path.parent.with_name('aa-held-renamed')
        original_write, hits = os.write, []
        payload = b'WRITE-SOURCE-UNDER-HELD-FD'

        def replace_parent_after_actual_write(fd, value):
            written = original_write(fd, value)
            if written and not hits:
                hits.append(True)
                original_path.parent.rename(held_directory)
                original_path.parent.mkdir(mode=0o700)
                original_path.write_bytes(b'WRONG-REPLACEMENT')
                os.chmod(original_path, 0o600)
            return written

        with patch('shared_content.storage.os.write', side_effect=replace_parent_after_actual_write):
            with self.assertRaises(SharedFault) as refusal:
                self.store.write_new(payload, blob_id=identity)
            self.assertEqual(refusal.exception.code, 'SHARED_CONTENT_UNAVAILABLE')
        self.assertEqual(len(hits), 1, 'HELD_WRITE_PARENT_REPLACEMENT_NOT_REACHED')
        self.assertEqual((held_directory / original_path.name).read_bytes(), payload)
        self.assertEqual(original_path.read_bytes(), b'WRONG-REPLACEMENT')
        self.assertEqual(self.store.read(baseline), 'UNAFFECTED-BASELINE')
        with self.assertRaises(SharedFault):
            self.store.inventory()
        self.assertTrue(held_directory.is_dir(), 'FAILED_WRITE_DELETED_PRESERVED_DIRECTORY')
