from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError
from django.test import TestCase

from audit.models import AuditEvent
from page_versions import schema
from page_versions.models import PageContentState, PageRevision
from shared_content import policy as shared_policy
from shared_content.public_markup import hydrate

from .models import Page, Route
from .public_read import (PublicNavigationItem, PublicUnavailable,
                          public_navigation)
from .public_shared import PublicSharedHost, project_breadcrumbs
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

    def test_pubnav_009_header_uses_only_approved_six_without_losing_full_tree(self):
        targets = (
            ('home', None, 'Главная', '/'),
            ('services', 'home', 'Старое имя услуг', '/services/'),
            ('child', 'services', 'Ремонт бамперов', '/services/body/bumpers'),
            ('actions', 'home', 'Акции', '/actions'),
            ('gallery', 'home', 'Галерея работ', '/gallery-of-works/'),
            ('reviews', 'home', 'Отзывы', '/reviews'),
            ('articles', 'home', 'Статьи', '/articles/'),
            ('contacts', 'home', 'Контакты', '/contacts'),
            ('about', 'home', 'О компании', '/about'),
        )
        navigation = tuple(PublicNavigationItem(*item) for item in targets)

        header = PublicSharedHost._header_navigation(
            navigation, current_page_id='gallery')

        self.assertEqual(len(navigation), 9)
        self.assertEqual(
            [(item.label, item.url, item.current) for item in header],
            [('Услуги и цены', '/services/', False),
             ('Акции', '/actions', False),
             ('Наши работы', '/gallery-of-works/', True),
             ('Отзывы', '/reviews', False),
             ('Статьи', '/articles/', False),
             ('Контакты', '/contacts', False)])

    def test_pubshell_001_logo_is_local_and_css_uses_approved_v3_breakpoint(self):
        marker = '00000000-0000-4000-8000-000000000001'
        source = (
            '<header class="es-header"><a class="es-brand" '
            'href="https://estakada-service.ru/" aria-label="Эстакада">'
            f'<img data-es-shared-asset="{marker}" alt="Эстакада"></a>'
            '<button class="es-menu-button" type="button" aria-expanded="false" '
            'aria-controls="es-nav"><span></span><span></span><span></span>'
            '<b>Меню</b></button><nav id="es-nav" aria-label="Основное меню"></nav>'
            '<div class="es-header-contacts"><div class="es-header-socials"></div>'
            '<a class="es-header-address" href="https://yandex.ru/maps/org/57771430682">'
            '<b>Москва</b><span>Проспект 60-летия Октября, 15Б</span></a>'
            '<a class="es-header-phone" href="tel:+74991102552">'
            '<strong>+7 (499) 110-25-52</strong><span>Ежедневно с 9:00 до 21:00</span>'
            '</a></div></header>')
        canonical = shared_policy.normalize_html(source, 'header')['html']

        rendered = hydrate(
            canonical, 'header', (), {marker: '/public-media/logo/'})
        app_root = Path(__file__).parents[1]
        css = (app_root / 'shared_content' / 'assets' /
               'public-shared.css').read_text(encoding='utf-8')
        page_css = (app_root / 'content' / 'public.css').read_text(
            encoding='utf-8')
        page_template = (app_root / 'content' / 'templates' / 'content' /
                         'public_page.html').read_text(encoding='utf-8')

        self.assertIn('class="es-brand" href="/"', rendered)
        self.assertNotIn('https://estakada-service.ru/', rendered)
        self.assertIn(
            '.es-header{min-height:76px;padding:7px 40px;', css)
        self.assertIn(
            '.es-brand img{width:94px;height:54px;object-fit:contain}', css)
        self.assertIn(
            '@media(min-width:801px) and (max-width:1000px){', css)
        self.assertIn(
            '.es-header[data-menu-ready="true"] nav{display:none;', css)
        self.assertIn('.es-header>.es-brand{flex:0 0 94px}', css)
        self.assertIn('.es-header-contacts{margin-left:auto;display:flex;', css)
        self.assertIn('flex:0 0 auto', css)
        self.assertIn(
            '.public-shell{width:100%;margin:0;padding:52px 40px 58px}',
            page_css)
        self.assertIn('.public-shell-home{padding:0}', page_css)
        self.assertIn(
            '.public-reviews .public-text-main_text ul{display:grid;'
            'grid-template-columns:repeat(3,minmax(0,1fr));', page_css)
        self.assertIn(
            '<main class="public-shell{% if home %} public-shell-home{% endif %}">',
            page_template)

    def test_homev4_001_approved_composition_and_privacy_contract(self):
        app_root = Path(__file__).parents[1]
        template = (app_root / 'content' / 'templates' / 'content' /
                    '_public_home.html').read_text(encoding='utf-8')
        css = (app_root / 'content' / 'public.css').read_text(
            encoding='utf-8')
        markers = (
            'class="es-hero"', 'class="es-proof"',
            'class="es-solutions"', 'class="es-process"',
            'class="es-section es-services"',
            'class="es-section es-prices"', 'class="es-photo-strip"',
            'class="es-section es-works"',
            'class="es-section es-reviews"')
        positions = [template.index(marker) for marker in markers]

        self.assertEqual(positions, sorted(positions))
        for binding in (
                '{{ home.hero.src }}', '{{ home.hero.lead }}',
                'home.advantages', 'home.comparisons', 'home.steps',
                'home.services', 'home.prices', 'home.photo_strip.src',
                'home.works', 'home.reviews.url'):
            self.assertIn(binding, template)
        self.assertIn('data-home-price-tab', template)
        self.assertIn('data-home-price-panel', template)
        self.assertNotIn('<iframe', template.lower())
        self.assertNotIn('<script', template.lower())
        self.assertIn('.es-home .es-hero{', css)
        self.assertIn('.es-home .es-proof{display:grid;', css)
        self.assertIn('.es-home .es-service-grid{display:grid;', css)
        self.assertIn('.es-home .es-step-grid{', css)
        self.assertIn('.es-home .es-work-grid{display:grid;', css)
        self.assertIn('@media(max-width:1000px){.es-home .es-proof{', css)
        self.assertIn('@media(max-width:700px){.es-home .es-hero{', css)

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
        self.assertNotContains(response, 'href="/exact/?a=1&amp;b=2"')
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
