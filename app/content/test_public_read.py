from uuid import uuid4

from django.db import models
from django.test import TestCase

from audit.models import AuditEvent
from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route
from .public_read import (PublicBlank, PublicNotFound, PublicPage, PublicRedirect,
                          PublicUnavailable, resolve_target)


def raw(model):
    return models.QuerySet(model=model, using='default')


class PublicReadTests(TestCase):
    def page(self, name, target, *, published=True, parent=None,
             kind=Page.Kind.ARTICLE, route_kind=Route.Kind.PRIMARY):
        page = Page.objects.create(
            name=name, kind=kind, parent=parent, position=Page.objects.filter(
                parent=parent).count(), is_published=published)
        route = Route.objects.create(
            page=page, kind=route_kind, target=target,
            is_legacy='?' in target)
        payload = schema.snapshot_v1(
            kind, h1='H1 ' + name, title='Title ' + name,
            main_text='<p>Public ' + name + '</p>').data()
        revision = PageRevision(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        revision.save()
        PageContentState(page=page, current_revision=revision, sequence=1).save()
        return page, route, revision

    def counts(self):
        return tuple(model.objects.count() for model in (
            Page, Route, PageRevision, PageContentState, AuditEvent))

    def test_primary_and_alias_return_verified_immutable_payload_without_writes(self):
        page, route, revision = self.page('Primary', '/primary/')
        alias = Route.objects.create(
            page=page, kind=Route.Kind.ALIAS, target='/legacy/?page=1',
            is_legacy=True)
        before = self.counts()
        for target, kind in ((route.target, Route.Kind.PRIMARY),
                             (alias.target, Route.Kind.ALIAS)):
            result = resolve_target(target)
            self.assertIsInstance(result, PublicPage)
            self.assertEqual((result.page_id, result.revision_id, result.route_kind),
                             (str(page.pk), str(revision.pk), kind))
            self.assertEqual(result.payload['main_text'], '<p>Public Primary</p>')
            with self.assertRaises(TypeError):
                result.payload['main_text'] = 'changed'
        self.assertEqual(self.counts(), before)

    def test_redirect_is_direct_to_same_page_primary(self):
        page, primary, _revision = self.page('Redirected', '/current/')
        old = Route.objects.create(
            page=page, kind=Route.Kind.REDIRECT, target='/old/')
        self.assertEqual(resolve_target(old.target),
                         PublicRedirect(location=primary.target))

    def test_redirect_with_invalid_stored_primary_fails_closed(self):
        page, primary, _revision = self.page('Redirected', '/current/')
        old = Route.objects.create(
            page=page, kind=Route.Kind.REDIRECT, target='/old/')
        raw(Route).filter(pk=primary.pk).update(target='//evil.example/')
        with self.assertRaises(PublicUnavailable):
            resolve_target(old.target)

    def test_unknown_invalid_and_system_routes_are_closed(self):
        hidden, hidden_route, _ = self.page(
            'Hidden', '/hidden/', published=False)
        system = Route.objects.create(
            page=None, kind=Route.Kind.SYSTEM, target='/manage-system/')
        for target in ('/missing/', '//host/path', system.target):
            with self.subTest(target=target), self.assertRaises(PublicNotFound):
                resolve_target(target)
        self.assertEqual(
            resolve_target(hidden_route.target),
            PublicBlank(
                route_id=str(hidden_route.pk), page_id=str(hidden.pk),
                target=hidden_route.target, route_kind=Route.Kind.PRIMARY))

    def test_published_child_below_hidden_parent_remains_public(self):
        parent, _route, _ = self.page(
            'Parent', '/parent/', published=False)
        child, child_route, _ = self.page(
            'Child', '/parent/child/', parent=parent, published=True)
        result = resolve_target(child_route.target)
        self.assertIsInstance(result, PublicPage)
        self.assertEqual(result.page_id, str(child.pk))
        child.refresh_from_db()
        self.assertTrue(child.is_published)

    def test_published_child_below_deep_hidden_ancestor_remains_public(self):
        root, _route, _ = self.page('Root', '/root/', published=False)
        middle, _route, _ = self.page(
            'Middle', '/root/middle/', parent=root, published=True)
        _child, child_route, _ = self.page(
            'Child', '/root/middle/child/', parent=middle, published=True)
        self.assertIsInstance(resolve_target(child_route.target), PublicPage)

    def test_missing_or_foreign_current_and_damaged_payload_fail_closed(self):
        no_state, no_state_route, revision = self.page('No state', '/no-state/')
        raw(PageContentState).filter(page=no_state).delete()
        with self.assertRaises(PublicUnavailable):
            resolve_target(no_state_route.target)

        other, _other_route, other_revision = self.page('Other', '/other/')
        raw(PageContentState).bulk_create([
            PageContentState(id=uuid4(), page=no_state,
                             current_revision=other_revision, sequence=1)])
        with self.assertRaises(PublicUnavailable):
            resolve_target(no_state_route.target)

        raw(PageContentState).filter(page=no_state).delete()
        raw(PageContentState).bulk_create([
            PageContentState(id=uuid4(), page=no_state,
                             current_revision=revision, sequence=1)])
        raw(PageRevision).filter(pk=revision.pk).update(payload_hash='0' * 64)
        with self.assertRaises(PublicUnavailable):
            resolve_target(no_state_route.target)

    def test_invalid_revision_and_payload_schema_fail_closed(self):
        _page, route, revision = self.page('Schema', '/schema/')
        original_payload = revision.payload

        raw(PageRevision).filter(pk=revision.pk).update(
            schema_version='future-schema')
        with self.assertRaises(PublicUnavailable):
            resolve_target(route.target)

        raw(PageRevision).filter(pk=revision.pk).update(
            schema_version=schema.SCHEMA)
        invalid_schema = dict(original_payload)
        invalid_schema['schema_version'] = 'future-schema'
        for payload in (invalid_schema, {'schema_version': schema.SCHEMA}):
            raw(PageRevision).filter(pk=revision.pk).update(
                payload=payload, payload_hash=schema.digest(payload))
            with self.subTest(payload=payload), self.assertRaises(PublicUnavailable):
                resolve_target(route.target)

    def test_parameter_text_is_data_not_sql_or_template_source(self):
        target = "/literal/?q='%20OR%201=1--&template=%7B%7B7*7%7D%7D"
        _page, _route, _revision = self.page('Literal', target)
        result = resolve_target(target)
        self.assertIsInstance(result, PublicPage)
        self.assertEqual(result.target, target)
