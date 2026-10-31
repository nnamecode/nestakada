"""Real PostgreSQL engine/ledger tests; no fake public renderer or rich editor."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone as dt_timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier,Event
from unittest.mock import patch
from uuid import uuid4
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import DatabaseError,IntegrityError,close_old_connections,connection
from django.test import TransactionTestCase,override_settings
from accounts.models import UserProfile
from accounts.services import bootstrap_owner,create_employee,set_grant
from audit.models import AuditEvent
from content.models import Page,Route
from media_library.models import MediaFolder,Asset,AssetUsage
from media_library import services as media
from . import engine as E,services as V,schema as S
from .models import (PageRevision,PageContentState,RevisionProtection,RevisionMetadata,OwnerDraft,
                     RestoreStage,VersionBasePin,OperationReceipt,IdentityReservation)

PASSWORD='Versions-test-current-owner-password'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class VersionEngineTests(TransactionTestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_LIBRARY_ROOT=self.temp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.owner=bootstrap_owner(PASSWORD)
        self.employee=create_employee(actor=self.owner,username='versions-employee',password='Versions-employee-current-password')
        self.other=create_employee(actor=self.owner,username='other-versions-employee',password='Other-versions-current-password')
        self.page=Page.objects.create(kind=Page.Kind.ARTICLE,name='Versioned page')
        Route.objects.create(page=self.page,kind=Route.Kind.PRIMARY,target='/versioned/')
        set_grant(actor=self.owner,employee=self.employee,page=self.page,main_text=True)
        self.original=S.snapshot_v1(self.page.kind,main_text='<p>original</p>',h1='Protected H1',title='Protected SEO')
        self.initial_operation=uuid4()
        self.initial=V.initialize(actor=self.owner,page_id=self.page.pk,snapshot=self.original,expected_generation=1,operation_id=self.initial_operation)['result_id']

    def current(self):return PageContentState.objects.get(page=self.page).current_revision_id

    def owner_commit(self,body,**extra):
        return V.commit_owner(actor=self.owner,page_id=self.page.pk,base_revision=self.current(),
            snapshot=S.snapshot_v1(self.page.kind,main_text=body,h1=extra.pop('h1','Protected H1'),**extra),
            expected_generation=1,operation_id=uuid4())

    def manual(self,**metadata):
        proof=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1)
        return V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],expected_generation=1,operation_id=uuid4(),**metadata)

    def stable(self,version_id):
        viewed=V.view_version(actor=self.owner,page_id=self.page.pk,version_id=version_id,expected_generation=1)
        return V.set_stable(actor=self.owner,page_id=self.page.pk,version_id=version_id,view_receipt=viewed['view_receipt'],expected_generation=1,operation_id=uuid4())

    def test_employee_save_is_current_based_and_owner_draft_stays_private_pinned(self):
        before=self.current()
        draft_result=V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=before,
            snapshot=S.snapshot_v1(self.page.kind,main_text='OWNER-DRAFT-PRIVATE-CANARY',h1='Owner draft hidden SEO'),expected_generation=1,operation_id=uuid4())
        result=V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=before,patch=S.TextPricePatch(main_text='employee actual text'),expected_generation=1,operation_id=uuid4())
        saved=PageRevision.objects.get(pk=result['result_id'])
        self.assertEqual(saved.payload['main_text'],'employee actual text');self.assertEqual(saved.payload['h1'],'Protected H1')
        draft=OwnerDraft.objects.get(pk=draft_result['result_id'])
        self.assertEqual(draft.payload['main_text'],'OWNER-DRAFT-PRIVATE-CANARY');self.assertEqual(draft.base_revision_id,before)
        self.assertTrue(VersionBasePin.objects.filter(revision_id=before,holder_kind='owner_draft').exists())
        history=V.history(actor=self.employee,page_id=self.page.pk,expected_generation=1)
        self.assertEqual(len(history['rows']),2)
        for row in history['rows']:
            viewed=V.view_version(actor=self.employee,page_id=self.page.pk,version_id=row['revision'].pk,expected_generation=1)
            self.assertNotIn('OWNER-DRAFT-PRIVATE-CANARY',str(viewed['revision'].payload))

    def test_current_conflict_and_grant_revocation_do_not_write_history(self):
        stale=self.current();self.owner_commit('newer owner state');count=PageRevision.objects.count()
        with self.assertRaises(ValidationError):V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=stale,patch=S.TextPricePatch(main_text='stale'),expected_generation=1,operation_id=uuid4())
        set_grant(actor=self.owner,employee=self.employee,page=self.page,main_text=False)
        with self.assertRaises(PermissionDenied):V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=self.current(),patch=S.TextPricePatch(main_text='denied'),expected_generation=1,operation_id=uuid4())
        self.assertEqual(PageRevision.objects.count(),count)

    def test_manual_uses_saved_current_not_draft_and_preserves_real_dates(self):
        source=self.current()
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=source,snapshot=S.snapshot_v1(self.page.kind,main_text='private draft'),expected_generation=1,operation_id=uuid4())
        created=datetime(2026,10,30,21,0,30,tzinfo=dt_timezone.utc)
        for manual_date in ['1960-01-01T00:00:00+03:00','2099-12-31T23:59:00+03:00']:
            with patch('page_versions.engine.now',return_value=created):result=self.manual(name='Я'*200,comment='К'*1000,manual_date=manual_date)
            row=PageRevision.objects.get(pk=result['result_id'])
            self.assertEqual(row.payload['main_text'],'<p>original</p>');self.assertEqual(row.author_id,self.owner.pk)
            self.assertEqual(row.created_at,created);self.assertNotEqual(row.metadata.manual_date,row.created_at)
            self.assertEqual(row.source_revision_id,source);self.assertEqual(self.current(),source)
        with self.assertRaises(ValidationError):self.manual(manual_date='2026-01-01T10:00:00')
        with self.assertRaises(ValidationError):self.manual(name='x'*201)
        with self.assertRaises(ValidationError):self.manual(comment='x'*1001)
        self.assertEqual(OwnerDraft.objects.get(page=self.page).payload['main_text'],'private draft')

    def test_manual_source_stale_and_metadata_edit_keeps_payload_and_author(self):
        prepared=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1)
        self.owner_commit('next state')
        with self.assertRaises(ValidationError):V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=prepared['confirmation'],expected_generation=1,operation_id=uuid4())
        result=self.manual();row=PageRevision.objects.get(pk=result['result_id']);before=(row.payload,row.created_at,row.author_id,row.sequence)
        V.edit_manual_metadata(actor=self.owner,page_id=self.page.pk,version_id=row.pk,metadata_generation=1,expected_generation=1,operation_id=uuid4(),name='Named',manual_date='1960-01-01T00:00:00Z')
        row.refresh_from_db();self.assertEqual((row.payload,row.created_at,row.author_id,row.sequence),before)
        self.assertEqual(row.metadata.name,'Named');self.assertEqual(row.metadata.generation,2)

    def test_ordinary_limit_stable_extra_and_equal_timestamp_sequence(self):
        fixed=datetime(2026,10,31,tzinfo=dt_timezone.utc)
        self.stable(self.initial)
        with patch('page_versions.engine.now',return_value=fixed):
            first=self.owner_commit('first ordinary')['result_id']
            for n in range(10):self.owner_commit('ordinary '+str(n))
        ordinary=PageRevision.objects.filter(page=self.page,stable_protection__isnull=True)
        self.assertEqual(ordinary.count(),10);self.assertFalse(ordinary.filter(pk=first).exists())
        self.assertTrue(RevisionProtection.objects.filter(revision_id=self.initial).exists())
        self.assertTrue(ordinary.filter(pk=self.current()).exists())
        self.assertFalse(RevisionProtection.objects.filter(revision_id=self.current()).exists())

    def test_receipt_replay_after_prune_returns_gone_never_resurrects(self):
        for n in range(11):self.owner_commit('body '+str(n))
        before=self.current();count=PageRevision.objects.count()
        repeated=V.initialize(actor=self.owner,page_id=self.page.pk,snapshot=self.original,expected_generation=1,operation_id=self.initial_operation)
        self.assertTrue(repeated['replay']);self.assertTrue(repeated['gone']);self.assertEqual(repeated['result_id'],self.initial)
        self.assertEqual(self.current(),before);self.assertEqual(PageRevision.objects.count(),count)
        with self.assertRaises(ValidationError):V.initialize(actor=self.owner,page_id=self.page.pk,snapshot=S.snapshot_v1(self.page.kind,main_text='different'),expected_generation=1,operation_id=self.initial_operation)
        with self.assertRaises(IntegrityError):PageRevision.objects.create(id=self.initial,page=self.page,sequence=100,schema_version=S.SCHEMA,payload=self.original.data(),payload_hash=S.digest(self.original.data()),kind='manual',author_id=self.owner.pk)

    def test_duplicate_concurrent_manual_operation_has_single_result(self):
        prepared=V.prepare_manual(actor=self.owner,page_id=self.page.pk,expected_generation=1);operation=uuid4();barrier=Barrier(2)
        def create():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return V.create_manual(actor=self.owner,page_id=self.page.pk,confirmation=prepared['confirmation'],expected_generation=1,operation_id=operation,name='same operation')
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:create(),range(2)))
        self.assertEqual(results[0]['result_id'],results[1]['result_id'])
        self.assertEqual(PageRevision.objects.filter(kind='manual').count(),1)
        self.assertEqual(AuditEvent.objects.filter(code='VERSION_CREATE_MANUAL').count(),1)

    def test_stable_safe_view_binding_and_unsupported_history_protection(self):
        old=self.initial;self.owner_commit('current')
        row=PageRevision.objects.get(pk=old);payload=row.payload.copy();payload['schema_version']='future-unknown'
        E.raw(PageRevision).filter(pk=old).update(schema_version='future-unknown',payload=payload,payload_hash=S.digest(payload))
        self.stable(old)
        self.assertTrue(RevisionProtection.objects.filter(revision_id=old).exists())
        with self.assertRaises(ValidationError):V.prepare_restore(actor=self.owner,page_id=self.page.pk,version_id=old,expected_generation=1)
        viewed=V.view_version(actor=self.employee,page_id=self.page.pk,version_id=old,expected_generation=1)
        with self.assertRaises(PermissionDenied):V.set_stable(actor=self.employee,page_id=self.page.pk,version_id=old,view_receipt=viewed['view_receipt'],expected_generation=1,operation_id=uuid4())

    def test_demote_requires_current_password_on_execute_and_replay(self):
        self.stable(self.initial);proof=V.prepare_demote(actor=self.owner,page_id=self.page.pk,version_id=self.initial,expected_generation=1)
        operation=uuid4()
        with self.assertRaises(PermissionDenied):V.demote_stable(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],password='wrong',expected_generation=1,operation_id=operation)
        saved_at=PageRevision.objects.get(pk=self.initial).created_at
        result=V.demote_stable(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],password=PASSWORD,expected_generation=1,operation_id=operation)
        self.assertFalse(result['gone']);self.assertEqual(PageRevision.objects.get(pk=self.initial).created_at,saved_at)
        with self.assertRaises(PermissionDenied):V.demote_stable(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],password='wrong',expected_generation=1,operation_id=operation)
        self.assertTrue(V.demote_stable(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],password=PASSWORD,expected_generation=1,operation_id=operation)['replay'])
        for row in OperationReceipt.objects.all():self.assertNotIn('password',str(row.__dict__).lower())

    def test_delete_current_stable_pins_and_exact_metadata_change(self):
        with self.assertRaises(ValidationError):V.prepare_delete(actor=self.owner,page_id=self.page.pk,version_id=self.current(),expected_generation=1)
        target=self.manual()['result_id'];proof=V.prepare_delete(actor=self.owner,page_id=self.page.pk,version_id=target,expected_generation=1)
        V.edit_manual_metadata(actor=self.owner,page_id=self.page.pk,version_id=target,metadata_generation=1,name='changed',expected_generation=1,operation_id=uuid4())
        with self.assertRaises(ValidationError):V.delete_revision(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],expected_generation=1,operation_id=uuid4())
        proof=V.prepare_delete(actor=self.owner,page_id=self.page.pk,version_id=target,expected_generation=1);operation=uuid4()
        result=V.delete_revision(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],expected_generation=1,operation_id=operation)
        self.assertTrue(result['gone']);self.assertEqual(self.current(),E.uid(self.initial))
        self.assertTrue(V.delete_revision(actor=self.owner,page_id=self.page.pk,confirmation=proof['confirmation'],expected_generation=1,operation_id=operation)['replay'])

    def test_all_ten_valid_stage_bases_hold_then_explicit_cancel_allows_manual(self):
        stages=[]
        for _ in range(9):self.manual()
        for row in PageRevision.objects.exclude(pk=self.current()):
            prepared=V.prepare_restore(actor=self.owner,page_id=self.page.pk,version_id=row.pk,expected_generation=1)
            stages.append(V.stage_restore(actor=self.owner,page_id=self.page.pk,preparation=prepared['preparation'],confirm_input_replacement=True,expected_generation=1,operation_id=uuid4())['result_id'])
        count=OperationReceipt.objects.count()
        revision_ids=set(PageRevision.objects.values_list('pk',flat=True))
        reservation_ids=set(IdentityReservation.objects.values_list('pk',flat=True))
        sequence=PageContentState.objects.get(page=self.page).sequence
        audit_count=AuditEvent.objects.count()
        usage_count=AssetUsage.objects.count()
        with self.assertRaisesMessage(ValidationError,'VERSIONS_HISTORY_BASES_HELD'):self.manual()
        self.assertEqual(PageRevision.objects.count(),10);self.assertEqual(OperationReceipt.objects.count(),count)
        self.assertEqual(set(PageRevision.objects.values_list('pk',flat=True)),revision_ids)
        self.assertEqual(set(IdentityReservation.objects.values_list('pk',flat=True)),reservation_ids)
        self.assertEqual(PageContentState.objects.get(page=self.page).sequence,sequence)
        self.assertEqual(AuditEvent.objects.count(),audit_count);self.assertEqual(AssetUsage.objects.count(),usage_count)
        V.cancel_stage(actor=self.owner,page_id=self.page.pk,stage_id=stages[0],expected_generation=1,operation_id=uuid4())
        created=self.manual();self.assertEqual(PageRevision.objects.count(),10)
        self.assertFalse(created['gone']);self.assertTrue(PageRevision.objects.filter(pk=created['result_id']).exists())

    def test_restore_stage_is_not_publish_then_employee_commit_preserves_protected_fields(self):
        source=self.initial;self.owner_commit('current body',h1='Current protected H1')
        before=self.current();count=PageRevision.objects.count()
        prepared=V.prepare_restore(actor=self.employee,page_id=self.page.pk,version_id=source,expected_generation=1)
        staged=V.stage_restore(actor=self.employee,page_id=self.page.pk,preparation=prepared['preparation'],confirm_input_replacement=True,expected_generation=1,operation_id=uuid4())
        self.assertEqual(self.current(),before);self.assertEqual(PageRevision.objects.count(),count)
        candidate=V.get_stage(actor=self.employee,page_id=self.page.pk,stage_id=staged['result_id'],expected_generation=1)
        self.assertEqual(candidate['payload']['h1'],'Current protected H1')
        result=V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=before,patch=S.TextPricePatch(main_text='explicit edited restored text'),stage_id=staged['result_id'],expected_generation=1,operation_id=uuid4())
        row=PageRevision.objects.get(pk=result['result_id'])
        self.assertEqual(row.payload['main_text'],'explicit edited restored text');self.assertEqual(row.payload['h1'],'Current protected H1')
        self.assertEqual(row.source_revision_id,E.uid(source));self.assertEqual(RestoreStage.objects.get(pk=staged['result_id']).status,'consumed')

    def test_current_change_invalidates_stage_but_never_releases_owner_draft_base(self):
        base=self.current();source=self.manual()['result_id']
        V.save_owner_draft(actor=self.owner,page_id=self.page.pk,base_revision=base,snapshot=S.snapshot_v1(self.page.kind,main_text='owner private'),expected_generation=1,operation_id=uuid4())
        proof=V.prepare_restore(actor=self.employee,page_id=self.page.pk,version_id=source,expected_generation=1)
        stage=V.stage_restore(actor=self.employee,page_id=self.page.pk,preparation=proof['preparation'],confirm_input_replacement=True,expected_generation=1,operation_id=uuid4())['result_id']
        self.owner_commit('current changed')
        held=RestoreStage.objects.get(pk=stage)
        self.assertEqual(held.status,'invalidated');self.assertEqual(held.terminal_reason,'CURRENT_CHANGED');self.assertIsNotNone(held.terminal_operation_id)
        self.assertFalse(VersionBasePin.objects.filter(holder_kind='restore_stage',holder_id=stage).exists())
        self.assertTrue(VersionBasePin.objects.filter(holder_kind='owner_draft',revision_id=base).exists())
        self.assertEqual(OwnerDraft.objects.get(page=self.page).base_revision_id,base)

    def test_snapshot_refs_are_real_and_prune_delete_never_unlink_files(self):
        folder=MediaFolder.objects.create(path='versions-real-fs')
        asset=Asset.objects.create(folder=folder,provenance='internal retention fixture, not a decoder claim')
        key=f'img/versions-real-fs/{asset.pk}/retained.data';content=b'actual retained filesystem bytes'
        media.write_file(asset_id=asset.pk,kind='main',key=key,chunks=content);media.mark_ready(asset_id=asset.pk)
        image={'asset_id':str(asset.pk),'alt':'','alignment':'center','width_px':None,'height_px':None}
        version=self.owner_commit('with media',main_image=image)['result_id'];self.stable(version)
        self.owner_commit('without media')
        kinds=set(AssetUsage.objects.filter(asset=asset).values_list('kind',flat=True));self.assertEqual(kinds,{'stable_version'})
        with self.assertRaises(ValidationError):media.prepare_cleanup(actor=self.owner,asset_ids=[asset.pk],expected_generation=1)
        self.assertEqual(Path(self.temp.name,key).read_bytes(),content)

    def test_actual_postgres_abort_after_revision_and_receipt_rolls_back_everything(self):
        for phase in ['revision','receipt']:
            before=(self.current(),PageRevision.objects.count(),OperationReceipt.objects.count(),AssetUsage.objects.count(),IdentityReservation.objects.count())
            if phase=='revision':
                original=E.new_revision
                def failure(*args,**kwargs):
                    original(*args,**kwargs)
                    with connection.cursor() as cursor:cursor.execute('SELECT 1/0')
                target=patch('page_versions.engine.new_revision',side_effect=failure)
            else:
                original=OperationReceipt.save
                def failure(instance,*args,**kwargs):
                    original(instance,*args,**kwargs)
                    with connection.cursor() as cursor:cursor.execute('SELECT 1/0')
                target=patch.object(OperationReceipt,'save',failure)
            with target,self.assertRaises(DatabaseError):self.owner_commit('must rollback')
            self.assertEqual((self.current(),PageRevision.objects.count(),OperationReceipt.objects.count(),AssetUsage.objects.count(),IdentityReservation.objects.count()),before)

    def test_racing_employee_commits_have_one_current_and_one_conflict(self):
        base=self.current();barrier=Barrier(2)
        def save(text):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:return V.commit_employee(actor=self.employee,page_id=self.page.pk,base_revision=base,patch=S.TextPricePatch(main_text=text),expected_generation=1,operation_id=uuid4())
                except ValidationError:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['one','two']))
        self.assertEqual(sum(type(result) is dict for result in results),1);self.assertEqual(results.count('conflict'),1)
        self.assertEqual(PageRevision.objects.count(),2)

    def test_cross_page_raw_pointer_is_refused_on_read(self):
        other=Page.objects.create(kind=Page.Kind.ARTICLE,name='other')
        foreign=V.initialize(actor=self.owner,page_id=other.pk,snapshot=S.snapshot_v1(other.kind,main_text='FOREIGN-PRIVATE-CANARY'),expected_generation=1,operation_id=uuid4())['result_id']
        E.raw(PageContentState).filter(page=self.page).update(current_revision_id=foreign)
        with self.assertRaisesMessage(ValidationError,'VERSIONS_CURRENT_PAGE_MISMATCH'):V.history(actor=self.owner,page_id=self.page.pk,expected_generation=1)

    def test_moscow_history_serialization_and_utc_actual_time(self):
        from .reads import timestamp
        for utc,day in [(datetime(2026,10,30,20,59,30,tzinfo=dt_timezone.utc),'30.10.2026 23:59:30'),(datetime(2026,10,30,21,0,30,tzinfo=dt_timezone.utc),'31.10.2026 00:00:30')]:
            value=timestamp(utc);self.assertEqual(value['moscow'],day);self.assertEqual(value['utc'],utc.isoformat());self.assertEqual(value['zone'],'Europe/Moscow')
