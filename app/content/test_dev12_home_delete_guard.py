import copy
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TransactionTestCase

from page_versions import engine, schema
from page_versions.models import PageContentState, PageRevision

from . import dev12_home_apply as home_apply
from . import home_projection
from .models import Page, Route


def raw(model):
    return models.QuerySet(model=model, using='default')


class Dev12HomeDeleteGuardTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        package = home_apply._read_package()
        self.payload = home_apply._target_payload(package)
        bound = next(item for item in self.payload['home_profile']['services']
                     if item['source_page_id'] is not None)
        self.source_id = bound['source_page_id']
        self.bound = bound
        self.source = Page.objects.create(
            id=UUID(self.source_id), name='Bound source',
            kind=Page.Kind.SERVICE, is_published=True)
        Route.objects.create(page=self.source, target='/bound-source/',
                             kind=Route.Kind.PRIMARY)
        source_payload = schema.snapshot_v1(
            self.source.kind, h1='Bound source').data(self.source.kind)
        source_revision = PageRevision.objects.create(
            page=self.source, sequence=1, schema_version=schema.SCHEMA,
            payload=source_payload, payload_hash=schema.digest(source_payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=self.source, current_revision=source_revision, sequence=1)
        self.home = Page.objects.create(
            id=UUID(home_apply.HOME_ID), name='Главная', kind=Page.Kind.HOME)
        self.home_revision = PageRevision.objects.create(
            page=self.home, sequence=1, schema_version=schema.SCHEMA,
            payload=self.payload, payload_hash=schema.digest(self.payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=self.home, current_revision=self.home_revision, sequence=1)

    def guard(self):
        return self.guard_for(self.source.pk)

    def guard_for(self, page_id):
        with transaction.atomic():
            return home_projection.delete_dependency_guard(page_id)

    def update_profile(self, action):
        payload = copy.deepcopy(self.payload)
        action(payload['home_profile'])
        raw(PageRevision).filter(pk=self.home_revision.pk).update(
            payload=payload, payload_hash=schema.digest(payload))
        self.payload = payload

    def test_visible_source_with_exact_visible_fallback_allows_delete_preflight(self):
        value, digest = self.guard()
        self.assertEqual(value['target'], self.source_id)
        self.assertEqual(len(value['homes']), 1)
        self.assertEqual(len(digest), 64)

    def test_hidden_source_requires_explicit_saved_hidden_fallback(self):
        raw(Page).filter(pk=self.source.pk).update(is_published=False)
        with self.assertRaisesMessage(
                ValidationError, 'HOME_DELETE_DEPENDENCY_REQUIRES_SYNC'):
            self.guard()
        self.update_profile(lambda profile: next(
            item for item in profile['services']
            if item['source_page_id'] == self.source_id).__setitem__(
                'fallback_visible', False))
        value, _digest = self.guard()
        self.assertEqual(len(value['homes']), 1)

    def test_unbinding_removes_dependency_without_url_or_name_capture(self):
        self.update_profile(lambda profile: next(
            item for item in profile['services']
            if item['source_page_id'] == self.source_id).__setitem__(
                'source_page_id', None))
        value, _digest = self.guard()
        self.assertEqual(value['homes'], [])
        Page.objects.create(name='Bound source', kind=Page.Kind.SERVICE)
        value, _digest = self.guard()
        self.assertEqual(value['homes'], [])

    def test_work_unbinding_removes_delete_dependency(self):
        work = self.payload['home_profile']['works'][0]
        work_page = Page.objects.create(
            id=UUID(work['source_page_id']), name='Bound work',
            kind=Page.Kind.ALBUM, is_published=True)
        Route.objects.create(page=work_page, target='/bound-work/',
                             kind=Route.Kind.PRIMARY)
        work_payload = schema.snapshot_v1(
            work_page.kind, h1='Bound work').data(work_page.kind)
        work_revision = PageRevision.objects.create(
            page=work_page, sequence=1, schema_version=schema.SCHEMA,
            payload=work_payload, payload_hash=schema.digest(work_payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=work_page, current_revision=work_revision, sequence=1)
        value, _digest = self.guard_for(work_page.pk)
        self.assertEqual(len(value['homes']), 1)
        self.update_profile(lambda profile: profile['works'][0].__setitem__(
            'source_page_id', None))
        value, _digest = self.guard_for(work_page.pk)
        self.assertEqual(value['homes'], [])

    def test_guard_requires_transaction_and_rejects_corrupt_home(self):
        with self.assertRaisesMessage(
                ValidationError, 'HOME_DELETE_GUARD_TRANSACTION_REQUIRED'):
            home_projection.delete_dependency_guard(self.source.pk)
        raw(PageRevision).filter(pk=self.home_revision.pk).update(
            payload_hash='0' * 64)
        with self.assertRaisesMessage(
                ValidationError, 'HOME_DELETE_GUARD_INVALID'):
            self.guard()
