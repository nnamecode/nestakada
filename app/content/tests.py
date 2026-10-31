from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, transaction, connection
from django.test import TestCase, TransactionTestCase
from .models import Page, Route
from .reads import public_tree, resolve_target
from .validators import exact_target, new_target, suggest_segment


def page(name='Страница', **kwargs):
    return Page.objects.create(name=name, kind=Page.Kind.ARTICLE, **kwargs)


def route(obj, target, **kwargs):
    return Route.objects.create(page=obj, target=target, kind=kwargs.pop('kind', Route.Kind.PRIMARY), **kwargs)


class ContentModelsTests(TestCase):
    def test_unpaired_surrogate_is_a_validation_error(self):
        value='/' + chr(0xD800) + '/'
        for validate in [exact_target,new_target,resolve_target]:
            with self.assertRaises(ValidationError):validate(value)

    def test_url_suggestion_matches_pr07_and_does_not_change_name(self):
        for name, expected in [('Ремонт ёмкости','remont-yomkosti'),('Шины и диски','shiny-i-diski'),
                               ('Щётки / 2026','schyotki-2026'),('Е\u0308ж -- 01','yozh-01')]:
            self.assertEqual(suggest_segment(name),expected)
        saved=page('Ремонт ёмкости');suggest_segment(saved.name);saved.refresh_from_db()
        self.assertEqual(saved.name,'Ремонт ёмкости')

    def test_url_suggestion_never_falls_back_truncates_or_renumbers(self):
        for name in ['', '  ', 'ъь', 'a'*81, 'имя<script>', '😀']:
            with self.subTest(name=name[:10]),self.assertRaises(ValidationError):suggest_segment(name)

    def test_creation_name_type_identity_and_append(self):
        a,b=page('Я'),page('Б')
        self.assertFalse(a.is_published)
        self.assertNotEqual(a.id,b.id)
        self.assertLess(a.position,b.position)
        for changes in ({'name':'  '},{'name':'x\n'},{'kind':'invented'}):
            args={'name':'A','kind':Page.Kind.ARTICLE};args.update(changes)
            with self.subTest(fields=list(changes)),self.assertRaises(ValidationError): Page.objects.create(**args)

    def test_rename_and_move_do_not_rewrite_route_or_order(self):
        a,b=page(),page();r=route(a,'/fixed/')
        position=a.position;a.name='Другое';a.parent=b;a.save();r.refresh_from_db()
        self.assertEqual((a.position,r.target),(position,'/fixed/'))

    def test_self_and_indirect_cycle_are_rejected(self):
        root=page();child=page(parent=root);last=page(parent=child)
        for parent in [root,last]:
            root.parent=parent
            with self.assertRaises(ValidationError): root.save()
        root.refresh_from_db();self.assertIsNone(root.parent_id)

    def test_hidden_ancestor_only_changes_projection(self):
        root=page(is_published=True);hidden=page(parent=root)
        child=page(parent=hidden,is_published=True);sibling=page(parent=root,is_published=True)
        nodes=public_tree();self.assertEqual([n['id'] for n in nodes],[root.id,child.id,sibling.id])
        self.assertEqual(nodes[1]['parent_id'],root.id)
        child.refresh_from_db();self.assertEqual(child.parent_id,hidden.id)
        hidden.is_published=True;hidden.save();self.assertEqual(public_tree()[2]['parent_id'],hidden.id)

    def test_deletion_and_unvalidated_bulk_changes_are_deferred(self):
        root=page();page(parent=root)
        for action in [lambda:root.delete(),lambda:Page.objects.filter(pk=root.pk).delete(),
                       lambda:Page.objects.filter(pk=root.pk).update(parent_id=root.pk)]:
            with self.assertRaises(ValidationError): action()
        self.assertEqual(Page.objects.count(),2)

    def test_legacy_case_slash_query_and_alias_are_exact(self):
        obj=page(is_published=True);route(obj,'/Gallery/',is_legacy=True)
        for target in ['/Gallery','/gallery/','/Gallery/?page=2']:
            route(obj,target,kind=Route.Kind.ALIAS,is_legacy=True)
            self.assertEqual(resolve_target(target).page_id,obj.pk)
        self.assertEqual(resolve_target('/Gallery/?page=3').state,'unknown')
        self.assertEqual(Route.objects.filter(page=obj).count(),4)

    def test_page_redirect_alias_system_share_unique_namespace(self):
        for kind in Route.Kind.values:
            target='/occupied-'+kind+'/'
            Route.objects.create(target=target,kind=kind,page=None if kind=='system' else page())
            with self.assertRaises(IntegrityError),transaction.atomic():route(page(),target)

    def test_only_one_primary_per_object(self):
        obj=page();route(obj,'/a/')
        with self.assertRaises(IntegrityError),transaction.atomic():route(obj,'/b/')

    def test_redirect_resolves_by_identity_without_chain(self):
        obj=page();current=route(obj,'/b/');route(obj,'/a/',kind=Route.Kind.REDIRECT)
        self.assertEqual(resolve_target('/a/').destination,'/b/')
        current.target='/c/';current.save()
        self.assertEqual(resolve_target('/a/').destination,'/c/')
        self.assertEqual(resolve_target('/c/').state,'hidden')

    def test_missing_redirect_destination_is_inconsistency(self):
        route(page(),'/old/',kind=Route.Kind.REDIRECT)
        with self.assertRaises(ValidationError):resolve_target('/old/')

    def test_legacy_route_and_object_identity_are_immutable(self):
        obj=page();saved=route(obj,'/Exact/',is_legacy=True)
        for field,value in [('target','/changed/'),('kind',Route.Kind.REDIRECT),('is_legacy',False),('page_id',page().pk)]:
            saved.refresh_from_db();setattr(saved,field,value)
            with self.assertRaises(ValidationError):saved.save()
        obj.id=uuid4()
        with self.assertRaises(ValidationError):obj.save()

    def test_new_instance_does_not_overwrite_existing_identity(self):
        saved=page()
        with self.assertRaises(IntegrityError),transaction.atomic():Page(id=saved.pk,name='Подмена',kind=Page.Kind.ARTICLE).save()
        saved.refresh_from_db();self.assertEqual(saved.name,'Страница')

    def test_unsafe_or_overlong_request_targets_are_rejected(self):
        for target in ['https://invalid/','//invalid/','/a#x','/a\\b','/a\n','/'+'я'*1024]:
            with self.subTest(target=repr(target[:20])),self.assertRaises(ValidationError):route(page(),target,is_legacy=True)
        for target in ['/Upper/','/x/?page=2','/'+'a'*81+'/','/a//b/']:
            with self.subTest(target=target[:20]),self.assertRaises(ValidationError):route(page(),target)

    def test_database_constraint_and_transaction_rollback(self):
        obj=page()
        with self.assertRaises(IntegrityError),transaction.atomic(),connection.cursor() as cursor:
            cursor.execute('UPDATE app.content_page SET parent_id=id WHERE id=%s',[obj.pk])
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                route(obj,'/rolled-back/');raise RuntimeError('rollback')
        self.assertEqual(resolve_target('/rolled-back/').state,'unknown')

    def test_hidden_child_is_protected_by_database_foreign_key(self):
        root=page();page(parent=root,is_published=False)
        with self.assertRaises(IntegrityError),transaction.atomic(),connection.cursor() as cursor:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute('DELETE FROM app.content_page WHERE id=%s',[root.pk])
        self.assertEqual(Page.objects.count(),2)


class ContentConcurrencyTests(TransactionTestCase):
    def run_parallel(self, pairs, operation):
        def worker(pair):
            close_old_connections()
            try:return operation(pair)
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:return list(executor.map(worker,pairs))

    def test_competing_route_claims(self):
        barrier=Barrier(2)
        def claim(identity):
            barrier.wait(timeout=5)
            try:Route(page_id=identity,target='/race/',kind=Route.Kind.PRIMARY).save();return 'saved'
            except IntegrityError:return 'collision'
        self.assertEqual(sorted(self.run_parallel([page().pk,page().pk],claim)),['collision','saved'])

    def test_opposite_parent_moves_cannot_create_cycle(self):
        a,b=page(),page()
        barrier=Barrier(2)
        def move(pair):
            obj=Page.objects.get(pk=pair[0]);obj.parent_id=pair[1]
            barrier.wait(timeout=5)
            try:obj.save();return 'saved'
            except ValidationError:return 'cycle'
        self.assertEqual(sorted(self.run_parallel([(a.pk,b.pk),(b.pk,a.pk)],move)),['cycle','saved'])
        self.assertEqual(public_tree(),[])
