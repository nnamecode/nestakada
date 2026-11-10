from types import SimpleNamespace
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from audit.models import AuditEvent
from page_versions import schema
from page_versions.models import PageContentState, PageRevision

from .models import Page, Route
from .public_read import (PublicNavigationItem, PublicUnavailable,
                          public_navigation)
from .public_shared import project_breadcrumbs
from .test_public_http import fake_shared


class PublicNavigationTests(TestCase):
    def page(self, name, target=None, *, parent=None, published=True):
        page = Page.objects.create(
            name=name, kind=Page.Kind.ARTICLE, parent=parent,
            position=Page.objects.filter(parent=parent).count(),
            is_published=published)
        route = None
        if target is not None:
            route = Route.objects.create(
                page=page, kind=Route.Kind.PRIMARY, target=target,
                is_legacy='?' in target)
        payload = schema.snapshot_v1(
            page.kind, h1='H1 ' + name, title='Title ' + name,
            main_text='<p>Main</p>').data()
        revision = PageRevision.objects.create(
            page=page, sequence=1, schema_version=schema.SCHEMA,
            payload=payload, payload_hash=schema.digest(payload),
            kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(
            page=page, current_revision=revision, sequence=1)
        return page, route

    def counts(self):
        return tuple(model.objects.count() for model in (
            Page, Route, PageRevision, PageContentState, AuditEvent))

    def test_stable_primary_preorder_promotes_hidden_descendants_and_excludes_route_kinds(self):
        first, first_route = self.page('First', '/first/')
        child, child_route = self.page('Child', '/first/child/', parent=first)
        hidden, _ = self.page('Hidden', '/hidden/', published=False)
        promoted, promoted_route = self.page(
            'Hidden child', '/hidden/child/', parent=hidden, published=True)
        last, last_route = self.page('Last', '/Last/?mode=X')
        Route.objects.create(page=first, kind=Route.Kind.ALIAS, target='/alias/')
        Route.objects.create(page=child, kind=Route.Kind.REDIRECT, target='/old-child/')
        Route.objects.create(page=None, kind=Route.Kind.SYSTEM, target='/system-nav/')
        before = self.counts()
        items = public_navigation()
        self.assertEqual(
            [(item.page_id, item.parent_id, item.target) for item in items],
            [(str(first.pk), None, first_route.target),
             (str(child.pk), str(first.pk), child_route.target),
             (str(promoted.pk), None, promoted_route.target),
             (str(last.pk), None, last_route.target)])
        self.assertEqual(self.counts(), before)

    def test_hidden_parent_needs_no_primary_and_promotes_to_visible_grandparent(self):
        root, root_route = self.page('Root', '/root/')
        hidden, hidden_route = self.page(
            'Hidden', '/root/hidden/', parent=root, published=False)
        child, child_route = self.page(
            'Child', '/root/hidden/child/', parent=hidden, published=True)
        Route.objects.filter(pk=hidden_route.pk)._raw_delete('default')
        items = public_navigation()
        self.assertEqual(
            [(item.page_id, item.parent_id, item.target) for item in items],
            [(str(root.pk), None, root_route.target),
             (str(child.pk), str(root.pk), child_route.target)])

    def test_missing_or_invalid_visible_primary_fails_closed(self):
        page, route = self.page('Broken', '/broken/')
        Route.objects.filter(pk=route.pk)._raw_delete('default')
        with self.assertRaises(PublicUnavailable):
            public_navigation()
        Route.objects.create(
            page=page, kind=Route.Kind.PRIMARY, target='/restored/')
        from django.db import models
        models.QuerySet(model=Route, using='default').filter(
            page=page, kind=Route.Kind.PRIMARY).update(target='//external.example/')
        with self.assertRaises(PublicUnavailable):
            public_navigation()

    def test_corrupt_disconnected_tree_fails_closed(self):
        one = SimpleNamespace(pk='one', parent_id='two', position=0,
                              name='One', is_published=True)
        two = SimpleNamespace(pk='two', parent_id='one', position=0,
                              name='Two', is_published=True)
        with patch('content.public_read.Page.objects.all') as pages:
            pages.return_value.only.return_value = [one, two]
            with self.assertRaises(PublicUnavailable):
                public_navigation()

    def test_alias_page_is_current_and_names_urls_are_escaped(self):
        root, _root_route = self.page('Root <safe>', '/')
        hidden, _hidden_route = self.page(
            'Hidden', '/hidden/', parent=root, published=False)
        page, _route = self.page(
            'Name <unsafe>', '/exact/?a=1&b=2', parent=hidden)
        Route.objects.create(
            page=page, kind=Route.Kind.ALIAS, target='/alias-current/')
        with patch('content.public_views.render_shared', side_effect=fake_shared):
            response = self.client.get('/alias-current/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Name &lt;unsafe&gt;', html=False)
        self.assertContains(response, 'href="/exact/?a=1&amp;b=2" aria-current="page"')
        self.assertNotContains(response, 'href="/alias-current/"')
        self.assertContains(response, 'aria-label="Хлебные крошки"')
        self.assertContains(response, '<a href="/">Root &lt;safe&gt;</a>', html=True)
        self.assertContains(
            response, '<span aria-current="page">Name &lt;unsafe&gt;</span>',
            html=True)
        self.assertNotContains(response, '>Hidden<')
        self.assertNotContains(response, 'class="public-name"')

    def test_root_breadcrumb_and_malformed_chains_fail_closed(self):
        self.page('Root', '/')
        with patch('content.public_views.render_shared', side_effect=fake_shared):
            response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, '<span aria-current="page">Root</span>', html=True)

        current = SimpleNamespace(page_id='current')
        valid = PublicNavigationItem('current', None, 'Current', '/current/')
        for navigation in (
                (),
                (valid, valid),
                (PublicNavigationItem('current', 'missing', 'Current', '/current/'),),
                (PublicNavigationItem('current', 'parent', 'Current', '/current/'),
                 PublicNavigationItem('parent', 'current', 'Parent', '/parent/'))):
            with self.assertRaises(PublicUnavailable):
                project_breadcrumbs(current, navigation)

    def test_unknown_skips_navigation_and_navigation_failure_is_closed_503(self):
        with patch('content.public_shared.public_navigation') as navigation:
            self.assertEqual(self.client.get('/missing/').status_code, 404)
            navigation.assert_not_called()
        self.page('Available', '/available/')
        with patch('content.public_shared.public_navigation',
                   side_effect=DatabaseError()):
            response = self.client.get('/available/')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.content, 'Страница временно недоступна.'.encode())
        self.assertEqual(response['Cache-Control'], 'no-store')
