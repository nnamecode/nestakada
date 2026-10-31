"""DEV06-S01..S11: actual PostgreSQL ledger/filesystem; not future Stable/HTML integration.

No decoder/upload acceptance oracle is derived from storage of arbitrary bytes.
"""
import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, transaction, IntegrityError
from django.test import TransactionTestCase, override_settings
from accounts.models import UserProfile
from content.models import Page
from .models import MediaFolder, PageMediaHome, Asset, AssetFile, AssetUsage
from .paths import relative_path, storage_key
from .storage import MediaStorage, MediaParentUnavailable
from . import services


class MediaStorageTests(TransactionTestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.override = override_settings(MEDIA_LIBRARY_ROOT=self.temp.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.temp.cleanup)
        self.storage = MediaStorage()
        self.folder = MediaFolder.objects.create(path='pages/fixed-home')
        self.owner = get_user_model().objects.create(username='nesadmin')
        UserProfile.objects.create(user=self.owner,role='owner')
        self.employee = get_user_model().objects.create(username='media-employee')
        UserProfile.objects.create(user=self.employee,role='employee')

    def asset(self, files=1, ready=True):
        asset=Asset.objects.create(folder=self.folder,provenance='DEV06 test trusted producer')
        for n in range(files):
            services.write_file(asset_id=asset.pk,kind=AssetFile.Kind.MAIN,key=f'img/{asset.pk}/file-{n}.data',chunks=f'actual bytes {n}'.encode(),storage=self.storage)
        return services.mark_ready(asset_id=asset.pk,storage=self.storage) if ready else asset

    def prepare(self, asset, actor=None, generation=1):
        return services.prepare_cleanup(actor=actor or self.owner,asset_ids=[asset.pk],expected_generation=generation,storage=self.storage)

    def confirm(self, preview):
        return services.confirm_cleanup(actor=self.owner,confirmation=preview['confirmation'],expected_generation=1,storage=self.storage)

    def test_s01_s11_path_spaces_archive_and_traversal_rejected(self):
        for key in ['../x','/img/x','img//x','img/./x','img/../x','img\\x','img/x\x00','img/%2e%2e/x','C:/img/x','img/x?y','img/x/']:
            with self.subTest(key=key), self.assertRaises(ValidationError):
                storage_key(key)
        for key in ['archive/x','backups/x','private/x']:
            with self.assertRaises(ValidationError):
                self.storage.write_new(key,b'never written')
        with self.assertRaises(ValidationError):
            relative_path('../folder')
        self.assertEqual(relative_path('services/paint-old_1'),'services/paint-old_1')

    def test_s02_real_symlinks_and_hardlinks_are_rejected(self):
        with TemporaryDirectory() as outside:
            sentinel=Path(outside,'sentinel');sentinel.write_bytes(b'outside stays')
            Path(self.temp.name,'img').symlink_to(outside,target_is_directory=True)
            with self.assertRaises(OSError):self.storage.write_new('img/new.data',b'blocked')
            Path(self.temp.name,'img').unlink()
            Path(self.temp.name,'img').mkdir()
            leaf=Path(self.temp.name,'img/link.data');leaf.symlink_to(sentinel)
            with self.assertRaises(OSError):self.storage.manifest('img/link.data')
            with self.assertRaises(OSError):self.storage.unlink('img/link.data',{'sha256':'0'*64,'byte_size':0})
            leaf.unlink();os.link(sentinel,leaf)
            with self.assertRaises(ValidationError):self.storage.manifest('img/link.data')
            self.assertEqual(sentinel.read_bytes(),b'outside stays')
            alias=Path(self.temp.name,'alias');alias.symlink_to(outside,target_is_directory=True)
            with override_settings(MEDIA_LIBRARY_ROOT=str(alias)):
                with self.assertRaises(OSError):MediaStorage().write_new('img/no.data',b'blocked')

    def test_s03_write_exclusive_manifest_and_immutable_metadata(self):
        data=b'known actual bytes'
        actual=self.storage.write_new('img/exclusive.data',[data[:5],data[5:]])
        self.assertEqual(actual,{'sha256':hashlib.sha256(data).hexdigest(),'byte_size':len(data)})
        with self.assertRaises(FileExistsError):self.storage.write_new('img/exclusive.data',b'replacement')
        self.assertEqual(self.storage.manifest('img/exclusive.data'),actual)
        asset=self.asset();record=asset.files.get()
        record.key='img/replaced.data'
        with self.assertRaises(ValidationError):record.save()
        asset.provenance='changed'
        with self.assertRaises(ValidationError):asset.save()
        asset.id=uuid4()
        with self.assertRaises(ValidationError):asset.save()
        with self.assertRaises(ValidationError):AssetFile.objects.filter(pk=record.pk).update(key='img/replaced.data')

    def test_created_directory_is_fsynced_in_parent_before_opening_it(self):
        events=[]
        real_mkdir,real_fsync,real_open=os.mkdir,os.fsync,os.open
        def mkdir(path,*args,**kwargs):
            result=real_mkdir(path,*args,**kwargs)
            events.append(('mkdir',path,kwargs.get('dir_fd')))
            return result
        def fsync(fd):
            result=real_fsync(fd);events.append(('fsync',fd));return result
        def opened(path,flags,*args,**kwargs):
            events.append(('open',path,kwargs.get('dir_fd')))
            return real_open(path,flags,*args,**kwargs)
        with override_settings(MEDIA_LIBRARY_ROOT=str(Path(self.temp.name,'new-root','new-child'))):
            with patch('media_library.storage.os.mkdir',side_effect=mkdir),patch('media_library.storage.os.fsync',side_effect=fsync),patch('media_library.storage.os.open',side_effect=opened):
                MediaStorage().write_new('img/nested/leaf.data',b'real filesystem bytes')
        count=0
        for index,event in enumerate(events):
            if event[0]=='mkdir':
                count+=1
                self.assertEqual(events[index+1],('fsync',event[2]))
                self.assertEqual(events[index+2],('open',event[1],event[2]))
        self.assertEqual(count,4)
        self.assertEqual(Path(self.temp.name,'new-root/new-child/img/nested/leaf.data').read_bytes(),b'real filesystem bytes')

    def test_write_error_preserved_when_partial_leaf_is_missing_or_replaced(self):
        for replace in [False,True]:
            key=f'img/failed-{replace}.data';leaf=Path(self.temp.name,key)
            primary=RuntimeError('original producer failure')
            def failing():
                yield b'partial'
                # Rename keeps the old inode alive, preventing inode-number reuse.
                leaf.rename(leaf.with_suffix('.partial'))
                if replace:leaf.write_bytes(b'foreign replacement must stay')
                raise primary
            with self.assertRaises(RuntimeError) as caught:self.storage.write_new(key,failing())
            self.assertIs(caught.exception,primary)
            if replace:self.assertEqual(leaf.read_bytes(),b'foreign replacement must stay')

    def test_s04_page_rename_does_not_move_home_or_folder(self):
        page=Page.objects.create(kind=Page.Kind.ARTICLE,name='Before')
        home=PageMediaHome.objects.create(page=page,folder=self.folder)
        page.name='After';page.save()
        home.refresh_from_db();self.folder.refresh_from_db()
        self.assertEqual(home.folder_id,self.folder.pk)
        self.assertEqual(self.folder.path,'pages/fixed-home')
        self.folder.path='pages/moved'
        with self.assertRaises(ValidationError):self.folder.save()

    def test_s05_all_six_ledger_kinds_retain_without_claiming_real_consumers(self):
        asset=self.asset();rows=[]
        for kind in AssetUsage.Kind.values:
            rows.append(services.attach(asset_id=asset.pk,kind=kind,consumer_id=uuid4(),slot='main'))
            with self.assertRaises(ValidationError):self.prepare(asset)
        self.assertEqual(len(rows),6)
        for row in rows[:-1]:services.detach(kind=row.kind,consumer_id=row.consumer_id,slot=row.slot)
        with self.assertRaises(ValidationError):self.prepare(asset)
        row=rows[-1];services.detach(kind=row.kind,consumer_id=row.consumer_id,slot=row.slot)
        self.assertGreater(self.prepare(asset)['total_bytes'],0)

    def test_s05_ready_gate_and_failed_replace_preserve_previous_reference(self):
        ready=self.asset();staged=self.asset(ready=False);consumer=uuid4()
        row=services.attach(asset_id=ready.pk,kind='draft',consumer_id=consumer,slot='body')
        with self.assertRaises(ValidationError):services.replace(asset_id=staged.pk,kind='draft',consumer_id=consumer,slot='body')
        self.assertEqual(AssetUsage.objects.get(pk=row.pk).asset_id,ready.pk)
        with self.assertRaises(ValidationError):AssetUsage.objects.create(asset=staged,kind='draft',consumer_id=uuid4(),slot='body')
        with self.assertRaises(ValidationError):services.attach(asset_id=ready.pk,kind='invented',consumer_id=uuid4(),slot='body')

    def test_s06_owner_generation_and_signature_checked(self):
        asset=self.asset()
        with self.assertRaises(PermissionDenied):self.prepare(asset,actor=self.employee)
        with self.assertRaises(PermissionDenied):self.prepare(asset,generation=2)
        preview=self.prepare(asset)
        with self.assertRaises(ValidationError):self.confirm({**preview,'confirmation':preview['confirmation']+'broken'})
        with self.assertRaises(PermissionDenied):
            services.confirm_cleanup(actor=self.employee,confirmation=preview['confirmation'],expected_generation=1,storage=self.storage)
        UserProfile.objects.filter(user=self.owner).update(generation=2)
        with self.assertRaises(PermissionDenied):self.confirm(preview)
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())

    def test_s07_late_reference_prevents_confirm_without_unlink(self):
        asset=self.asset();preview=self.prepare(asset);file=asset.files.get()
        services.attach(asset_id=asset.pk,kind='retained_html',consumer_id=uuid4(),slot='image')
        with self.assertRaises(ValidationError):self.confirm(preview)
        asset.refresh_from_db();self.assertEqual(asset.status,Asset.Status.READY)
        self.assertEqual(self.storage.manifest(file.key)['sha256'],file.sha256)

    def test_s03_s07_changed_file_bytes_invalidate_confirmation(self):
        asset=self.asset();preview=self.prepare(asset);file=asset.files.get()
        Path(self.temp.name,file.key).write_bytes(b'external corruption')
        with self.assertRaises(ValidationError):self.confirm(preview)
        asset.refresh_from_db();self.assertEqual(asset.status,Asset.Status.READY)
        self.assertEqual(Path(self.temp.name,file.key).read_bytes(),b'external corruption')

    def test_private_source_namespace_cannot_be_public_file_metadata(self):
        asset=self.asset(files=0,ready=False)
        with self.assertRaises(ValidationError):
            services.write_file(asset_id=asset.pk,kind='private-source',key='img/should-not-exist.data',chunks=b'private',storage=self.storage)
        self.assertFalse(Path(self.temp.name,'img/should-not-exist.data').exists())
        file=services.write_file(asset_id=asset.pk,kind='private-source',key=f'private/sources/{asset.pk}/original.data',chunks=b'private',storage=self.storage)
        self.assertEqual(self.storage.manifest(file.key)['byte_size'],7)

    def test_s08_cleanup_removes_only_after_committed_deleting(self):
        asset=self.asset(files=2);preview=self.prepare(asset);original=self.storage.unlink
        states=[]
        def unlink(key,expected):
            self.assertFalse(transaction.get_connection().in_atomic_block)
            states.append(Asset.objects.get(pk=asset.pk).status)
            return original(key,expected)
        with patch.object(self.storage,'unlink',side_effect=unlink):result=self.confirm(preview)[0]
        self.assertEqual(states,[Asset.Status.DELETING]*2)
        self.assertEqual(result['state'],'deleted');self.assertEqual(result['pending_files'],0)
        self.assertEqual(result['released_bytes'],preview['total_bytes'])
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())

    def test_s03_deleted_uuid_and_file_key_are_not_reusable(self):
        asset=self.asset();key=asset.files.get().key;asset_id=asset.pk
        self.confirm(self.prepare(asset))
        with self.assertRaises(IntegrityError):
            Asset.objects.create(id=asset_id,folder=self.folder,provenance='attempted reuse')
        replacement=self.asset(files=0,ready=False)
        with self.assertRaises(ValidationError):
            services.write_file(asset_id=replacement.pk,kind='main',key=key,chunks=b'new bytes',storage=self.storage)
        self.assertFalse(Path(self.temp.name,key).exists())

    def test_s09_real_unlink_failure_retains_pending_and_retry_counts_absence_honestly(self):
        asset=self.asset(files=0,ready=False)
        for directory in ['a','z']:
            services.write_file(asset_id=asset.pk,kind='main',key=f'img/{asset.pk}/{directory}/file.data',chunks=b'12345',storage=self.storage)
        asset=services.mark_ready(asset_id=asset.pk,storage=self.storage);preview=self.prepare(asset)
        protected=Path(self.temp.name,f'img/{asset.pk}/z');protected.chmod(0o500)
        try:result=self.confirm(preview)[0]
        finally:protected.chmod(0o700)
        self.assertEqual(result['state'],'delete_failed');self.assertEqual(result['pending_files'],1)
        self.assertEqual(result['released_bytes'],5)
        asset.refresh_from_db();self.assertEqual(asset.status,Asset.Status.DELETE_FAILED)
        with self.assertRaises(ValidationError):services.attach(asset_id=asset.pk,kind='current_page',consumer_id=uuid4(),slot='main')
        retried=services.retry_cleanup(actor=self.owner,asset_id=asset.pk,expected_generation=1,storage=self.storage)
        self.assertEqual([item['state'] for item in retried['files']],['already_absent','removed'])
        self.assertEqual(retried['released_bytes'],5);self.assertEqual(retried['state'],'deleted')

    def test_s10_concurrent_attach_cannot_race_physical_delete(self):
        asset=self.asset();preview=self.prepare(asset);entered,release=Event(),Event();original=self.storage.unlink
        def held(key,expected):
            entered.set()
            if not release.wait(10):raise RuntimeError('Test barrier timeout')
            return original(key,expected)
        def cleanup():
            close_old_connections()
            try:return self.confirm(preview)
            finally:close_old_connections()
        with patch.object(self.storage,'unlink',side_effect=held),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(cleanup)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaises(ValidationError):services.attach(asset_id=asset.pk,kind='stable_version',consumer_id=uuid4(),slot='main')
            finally:release.set()
            self.assertEqual(future.result(timeout=10)[0]['state'],'deleted')

    def test_parent_rename_after_deleting_keeps_metadata_until_restored_and_retried(self):
        asset=self.asset();preview=self.prepare(asset);file=asset.files.get()
        directory=Path(self.temp.name,f'img/{asset.pk}');moved=directory.with_name(directory.name+'-held')
        entered,release=Event(),Event();original=self.storage.unlink
        def held(key,expected):
            entered.set()
            if not release.wait(10):raise RuntimeError('Test barrier timeout')
            return original(key,expected)
        def cleanup():
            close_old_connections()
            try:return self.confirm(preview)
            finally:close_old_connections()
        with patch.object(self.storage,'unlink',side_effect=held),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(cleanup)
            try:
                self.assertTrue(entered.wait(10))
                directory.rename(moved)
            finally:release.set()
            result=future.result(timeout=10)[0]
        self.assertEqual(result['state'],'delete_failed');self.assertEqual(result['pending_files'],1)
        self.assertEqual(result['files'][0]['error'],'MediaParentUnavailable')
        self.assertTrue(AssetFile.objects.filter(pk=file.pk).exists())
        self.assertEqual(Path(moved,'file-0.data').read_bytes(),b'actual bytes 0')
        with self.assertRaises(MediaParentUnavailable):self.storage.manifest(file.key)
        moved.rename(directory)
        retried=services.retry_cleanup(actor=self.owner,asset_id=asset.pk,expected_generation=1,storage=self.storage)
        self.assertEqual(retried['state'],'deleted')
        self.assertFalse(AssetFile.objects.filter(pk=file.pk).exists())

    def test_simultaneous_physical_retry_does_not_unlink_or_count_twice(self):
        asset=self.asset();preview=self.prepare(asset);entered,release=Event(),Event()
        original=self.storage.unlink;unlink_calls=[]
        def held(key,expected):
            unlink_calls.append(key);entered.set()
            if not release.wait(10):raise RuntimeError('Test barrier timeout')
            return original(key,expected)
        def cleanup():
            close_old_connections()
            try:return self.confirm(preview)
            finally:close_old_connections()
        with patch.object(self.storage,'unlink',side_effect=held),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(cleanup)
            try:
                self.assertTrue(entered.wait(10))
                with self.assertRaisesMessage(ValidationError,'MEDIA_CLEANUP_ALREADY_RUNNING'):
                    services.retry_cleanup(actor=self.owner,asset_id=asset.pk,expected_generation=1,storage=self.storage)
            finally:release.set()
            result=future.result(timeout=10)[0]
        self.assertEqual(len(unlink_calls),1)
        self.assertEqual(result['state'],'deleted')
        self.assertEqual(result['released_bytes'],preview['total_bytes'])

    def test_unavailable_storage_root_is_not_missing_leaf(self):
        asset=self.asset();file=asset.files.get();root=Path(self.temp.name);moved=root.with_name(root.name+'-held')
        root.rename(moved)
        try:
            with self.assertRaises(MediaParentUnavailable):self.storage.unlink(file.key,{'sha256':file.sha256,'byte_size':file.byte_size})
            self.assertTrue(AssetFile.objects.filter(pk=file.pk).exists())
            self.assertTrue(Path(moved,file.key).is_file())
        finally:moved.rename(root)

    def test_missing_leaf_under_opened_parent_is_already_absent(self):
        asset=self.asset();preview=self.prepare(asset);file=asset.files.get();original=self.storage.unlink
        def missing_leaf(key,expected):
            Path(self.temp.name,key).unlink()
            return original(key,expected)
        with patch.object(self.storage,'unlink',side_effect=missing_leaf):result=self.confirm(preview)[0]
        self.assertEqual(result['state'],'deleted')
        self.assertEqual(result['files'][0]['state'],'already_absent')
        self.assertEqual(result['released_bytes'],0)

    def test_s11_outer_transaction_cannot_unlink_before_commit(self):
        asset=self.asset();preview=self.prepare(asset)
        with transaction.atomic(),self.assertRaises(ValidationError):self.confirm(preview)
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())

    def test_legacy_ready_requires_original_byte_hash(self):
        asset=Asset.objects.create(folder=self.folder,provenance='test legacy manifest',is_legacy=True,source_url='/gallery/original.jpg',source_sha256='1'*64)
        services.write_file(asset_id=asset.pk,kind='legacy-public',key=f'img/{asset.pk}/original.data',chunks=b'changed bytes',storage=self.storage)
        with self.assertRaises(ValidationError):services.mark_ready(asset_id=asset.pk,storage=self.storage)
