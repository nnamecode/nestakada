"""PV022 actual PG/FS interleavings; barriers never hold a content domain lock."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from unittest.mock import patch
from uuid import uuid4
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import close_old_connections,connection
from django.test import TransactionTestCase,override_settings
from accounts.services import bootstrap_owner,create_employee,set_grant
from content.models import Page
from media_library.models import Asset,MediaFolder,AssetUsage
from media_library import services as M
from . import services as V,schema as S,engine as E
from .models import PageContentState,PageRevision,RevisionProtection,OperationReceipt


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VersionInterleavingTests(TransactionTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_LIBRARY_ROOT=self.temp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.owner=bootstrap_owner('Concurrency-owner-current-password')
        self.employee=create_employee(actor=self.owner,username='pv-concurrent',password='Concurrency-employee-password')
        self.page=self.new_page('first')
        set_grant(actor=self.owner,employee=self.employee,page=self.page,main_text=True)

    def new_page(self,name):
        page=Page.objects.create(kind=Page.Kind.ARTICLE,name=name)
        V.initialize(actor=self.owner,page_id=page.pk,snapshot=S.snapshot_v1(page.kind,main_text='initial'),expected_generation=1,operation_id=uuid4())
        return page

    def current(self,page=None):return PageContentState.objects.get(page=page or self.page).current_revision_id

    def commit(self,body,page=None,image=None,operation=None):
        page=page or self.page
        return V.commit_owner(actor=self.owner,page_id=page.pk,base_revision=self.current(page),snapshot=S.snapshot_v1(page.kind,main_text=body,main_image=image),expected_generation=1,operation_id=operation or uuid4())

    def stable(self,version_id,page=None):
        page=page or self.page
        view=V.view_version(actor=self.owner,page_id=page.pk,version_id=version_id,expected_generation=1)
        return V.set_stable(actor=self.owner,page_id=page.pk,version_id=version_id,view_receipt=view['view_receipt'],expected_generation=1,operation_id=uuid4())

    def held_preflight(self,entered,release):
        real=E.preflight
        def observed(payload):
            result=real(payload)
            self.assertFalse(connection.in_atomic_block)
            entered.set()
            if not release.wait(10):raise RuntimeError('Test barrier timeout')
            return result
        return observed

    def thread(self,call):
        close_old_connections()
        try:return call()
        finally:close_old_connections()

    def test_stable_before_save_prune_preserves_exact_target_and_inverse_reports_gone(self):
        oldest=self.current()
        for n in range(9):self.commit('before '+str(n))
        other=PageRevision.objects.filter(page=self.page).exclude(pk=oldest).order_by('created_at','sequence').first().pk
        entered,release=Event(),Event()
        with patch('page_versions.engine.preflight',side_effect=self.held_preflight(entered,release)),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.thread,lambda:self.commit('paused commit'))
            try:
                self.assertTrue(entered.wait(10));self.stable(oldest)
                # Promotion frees one ordinary slot; a real manual checkpoint fills it
                # without changing the paused commit's current base.
                prepared=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1)
                V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=prepared['confirmation'],expected_generation=1,operation_id=uuid4())
            finally:release.set()
            future.result(timeout=10)
        self.assertTrue(RevisionProtection.objects.filter(revision_id=oldest).exists())
        self.assertFalse(PageRevision.objects.filter(pk=other).exists())
        self.assertEqual(PageRevision.objects.filter(page=self.page,stable_protection__isnull=True).count(),10)
        inverse=self.new_page('inverse');target=self.current(inverse)
        for n in range(9):self.commit('inverse '+str(n),page=inverse)
        viewed=V.view_version(actor=self.owner,page_id=inverse.pk,version_id=target,expected_generation=1)
        self.commit('prune wins',page=inverse)
        with self.assertRaisesMessage(ValidationError,'VERSIONS_SOURCE_GONE'):
            V.set_stable(actor=self.owner,page_id=inverse.pk,version_id=target,view_receipt=viewed['view_receipt'],expected_generation=1,operation_id=uuid4())
        self.assertFalse(RevisionProtection.objects.filter(revision__page=inverse).exists())

    def test_real_grant_revocation_between_preflight_and_final_commit_refuses_all(self):
        base=self.current();operation=uuid4();entered,release=Event(),Event();before=PageRevision.objects.count()
        def save():return V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=base,patch=S.TextPricePatch(main_text='not authorized anymore'),expected_generation=1,operation_id=operation)
        with patch('page_versions.engine.preflight',side_effect=self.held_preflight(entered,release)),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.thread,save)
            try:
                self.assertTrue(entered.wait(10))
                set_grant(actor=self.owner,employee=self.employee,page=self.page,main_text=False)
            finally:release.set()
            with self.assertRaises(PermissionDenied):future.result(timeout=10)
        self.assertEqual(self.current(),base);self.assertEqual(PageRevision.objects.count(),before)
        self.assertFalse(OperationReceipt.objects.filter(pk=operation).exists())

    def asset(self):
        folder,_=MediaFolder.objects.get_or_create(path='pv-concurrency')
        asset=Asset.objects.create(folder=folder,provenance='real retention bytes, not a decoder fixture')
        key=f'img/pv-concurrency/{asset.pk}/file.data'
        M.write_file(asset_id=asset.pk,kind='main',key=key,chunks=b'actual retained bytes')
        return M.mark_ready(asset_id=asset.pk),key

    def image(self,asset):return {'asset_id':str(asset.pk),'alt':'','alignment':'center','width_px':None,'height_px':None}

    def test_actual_media_cleanup_wins_then_inverse_new_reference_prevents_unlink(self):
        x,xkey=self.asset();y,ykey=self.asset();self.commit('current X',image=self.image(x))
        base=self.current();before=PageRevision.objects.count();operation=uuid4()
        cleanup=M.prepare_cleanup(actor=self.owner,asset_ids=[y.pk],expected_generation=1)
        entered,release=Event(),Event()
        with patch('page_versions.engine.preflight',side_effect=self.held_preflight(entered,release)),ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(self.thread,lambda:self.commit('candidate Y',image=self.image(y),operation=operation))
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(M.confirm_cleanup(actor=self.owner,confirmation=cleanup['confirmation'],expected_generation=1)[0]['state'],'deleted')
            finally:release.set()
            with self.assertRaises((ValidationError,Asset.DoesNotExist)):future.result(timeout=10)
        self.assertEqual(self.current(),base);self.assertEqual(PageRevision.objects.count(),before)
        self.assertFalse(OperationReceipt.objects.filter(pk=operation).exists());self.assertFalse(AssetUsage.objects.filter(asset_id=y.pk).exists())
        self.assertFalse(Path(self.temp.name,ykey).exists());self.assertEqual(Path(self.temp.name,xkey).read_bytes(),b'actual retained bytes')
        other,key=self.asset();old=M.prepare_cleanup(actor=self.owner,asset_ids=[other.pk],expected_generation=1)
        self.commit('new reference first',image=self.image(other))
        with self.assertRaises(ValidationError):M.confirm_cleanup(actor=self.owner,confirmation=old['confirmation'],expected_generation=1)
        self.assertEqual(Path(self.temp.name,key).read_bytes(),b'actual retained bytes')

    def test_stable_after_delete_preparation_refuses_exact_old_confirmation(self):
        prepared=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1)
        target=V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=prepared['confirmation'],expected_generation=1,operation_id=uuid4())['result_id']
        deletion=V.prepare_delete(actor=self.owner,page_id=self.page.pk,version_id=target,expected_generation=1)
        self.stable(target);operation=uuid4()
        with self.assertRaises(ValidationError):V.delete_revision(actor=self.owner,page_id=self.page.pk,confirmation=deletion['confirmation'],expected_generation=1,operation_id=operation)
        self.assertTrue(RevisionProtection.objects.filter(revision_id=target).exists())
        self.assertFalse(OperationReceipt.objects.filter(pk=operation).exists())
