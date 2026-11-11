from django.test import SimpleTestCase, override_settings

from .checks import check_public_seo_configuration
from .public_seo import (SeoPage, SeoUnavailable, hidden_robots,
                         load_configuration, project_page_seo)


class Dev11SeoProjectionTests(SimpleTestCase):
    def page(self, **changes):
        values = {
            'request_target': '/services/remont/',
            'route_kind': 'primary',
            'page_kind': 'service_catalog',
            'name': 'Ремонт',
            'title': 'Ремонт | Автосервис «Эстакада»',
            'description': 'Описание ремонта',
            'indexing_allowed': True,
            'wash_peer_eligible': False,
        }
        values.update(changes)
        return SeoPage(**values)

    @override_settings(
        PUBLIC_ORIGIN='https://estakada-service.ru',
        SEO_ROBOTS_PROFILE='production')
    def test_s11_projection_001_closed_configuration_and_ordinary_metadata(self):
        configuration = load_configuration()
        self.assertEqual(configuration.origin, 'https://estakada-service.ru')
        self.assertEqual(configuration.robots_profile, 'production')
        projected = project_page_seo(configuration, self.page())
        self.assertEqual(projected.title, 'Ремонт | Автосервис «Эстакада»')
        self.assertEqual(projected.description, 'Описание ремонта')
        self.assertEqual(
            projected.canonical, 'https://estakada-service.ru/services/remont/')
        self.assertIsNone(projected.robots)
        self.assertEqual(projected.og_title, projected.title)
        self.assertEqual(projected.og_description, projected.description)
        self.assertEqual(projected.og_url, projected.canonical)

    @override_settings(
        PUBLIC_ORIGIN='http://localhost:8767',
        SEO_ROBOTS_PROFILE='deny-all')
    def test_s11_projection_002_local_origin_is_explicit_not_request_derived(self):
        configuration = load_configuration()
        self.assertEqual(configuration.origin, 'http://localhost:8767')
        self.assertEqual(
            project_page_seo(configuration, self.page()).canonical,
            'http://localhost:8767/services/remont/')

    def test_s11_projection_003_invalid_configuration_fails_closed(self):
        invalid = (
            (None, 'production'),
            ('http://estakada-service.ru', 'production'),
            ('https://ESTAKADA-service.ru', 'production'),
            ('https://estakada-service.ru/', 'production'),
            ('https://user@estakada-service.ru', 'production'),
            ('https://estakada-service.ru/path', 'production'),
            ('https://estakada-service.ru?x=1', 'production'),
            ('https://estakada-service.ru#x', 'production'),
            ('https://estakada-service.ru\n', 'production'),
            ('http://localhost:8767', 'production'),
            ('http://localhost:8767', 'unknown'),
            ('https://estakada-service.ru', None),
        )
        for origin, profile in invalid:
            with self.subTest(origin=origin, profile=profile), override_settings(
                    PUBLIC_ORIGIN=origin, SEO_ROBOTS_PROFILE=profile):
                with self.assertRaises(SeoUnavailable):
                    load_configuration()

    @override_settings(
        PUBLIC_ORIGIN='https://estakada-service.ru',
        SEO_ROBOTS_PROFILE='production')
    def test_s11_projection_003a_system_check_uses_the_closed_validator(self):
        self.assertEqual(check_public_seo_configuration(None), [])
        with override_settings(SEO_ROBOTS_PROFILE='unknown'):
            errors = check_public_seo_configuration(None)
        self.assertEqual([error.id for error in errors], ['content.E001'])
        self.assertNotIn('unknown', str(errors[0]))

    @override_settings(
        PUBLIC_ORIGIN='https://estakada-service.ru',
        SEO_ROBOTS_PROFILE='production')
    def test_s11_projection_004_title_description_and_noindex_are_literal(self):
        configuration = load_configuration()
        empty = project_page_seo(configuration, self.page(
            name='Имя', title='', description='', indexing_allowed=False))
        self.assertEqual(empty.title, 'Имя')
        self.assertIsNone(empty.description)
        self.assertEqual(empty.robots, 'noindex, follow')
        self.assertIsNone(empty.canonical)
        self.assertEqual(empty.og_title, 'Имя')
        self.assertIsNone(empty.og_description)
        self.assertIsNone(empty.og_url)
        self.assertEqual(hidden_robots(), 'noindex, nofollow')

    @override_settings(
        PUBLIC_ORIGIN='https://estakada-service.ru',
        SEO_ROBOTS_PROFILE='production')
    def test_s11_projection_005_gallery_canonical_matrix_is_closed(self):
        configuration = load_configuration()
        root = 'https://estakada-service.ru/gallery-of-works/'
        for target in (
                '/gallery-of-works/',
                '/gallery-of-works/?page=2',
                '/gallery-of-works/?album=nissan-murano-kuzovnoj-remont',
                '/gallery-of-works/?page=2&album=kuzovnyie-rabotyi-scoda-octavia'):
            with self.subTest(target=target):
                projected = project_page_seo(configuration, self.page(
                    request_target=target, page_kind='gallery_catalog',
                    route_kind=('alias' if 'page=2' in target else 'primary')))
                self.assertEqual(projected.canonical, root)
                self.assertEqual(projected.og_url, root)
        album = project_page_seo(configuration, self.page(
            request_target='/gallery-of-works/nissan-murano-kuzovnoj-remont',
            page_kind='gallery_album'))
        self.assertEqual(
            album.canonical,
            'https://estakada-service.ru/gallery-of-works/nissan-murano-kuzovnoj-remont')
        for target in (
                '/gallery-of-works/?page=1',
                '/gallery-of-works/?page=02',
                '/gallery-of-works/?unknown=1',
                '/services/remont/?tracking=one'):
            with self.subTest(target=target):
                with self.assertRaises(SeoUnavailable):
                    project_page_seo(configuration, self.page(
                        request_target=target,
                        page_kind=('gallery_catalog'
                                   if target.startswith('/gallery')
                                   else 'service_catalog')))

    @override_settings(
        PUBLIC_ORIGIN='https://estakada-service.ru',
        SEO_ROBOTS_PROFILE='production')
    def test_s11_projection_006_content_wash_mapping_never_self_authorizes(self):
        configuration = load_configuration()
        old = '/services/drugie-uslugi/avtomojka'
        eligible = project_page_seo(configuration, self.page(
            request_target=old, route_kind='alias',
            page_kind='service_wash_legacy_alias',
            wash_peer_eligible=True))
        self.assertEqual(
            eligible.canonical,
            'https://estakada-service.ru/services/avtomojka')
        unavailable = project_page_seo(configuration, self.page(
            request_target=old, route_kind='alias',
            page_kind='service_wash_legacy_alias',
            wash_peer_eligible=False))
        self.assertIsNone(unavailable.canonical)
        self.assertIsNone(unavailable.og_url)
        current = project_page_seo(configuration, self.page(
            request_target='/services/avtomojka', route_kind='primary',
            page_kind='service_catalog'))
        self.assertEqual(
            current.canonical,
            'https://estakada-service.ru/services/avtomojka')
        unknown = project_page_seo(configuration, self.page(
            request_target='/unexpected-alias', route_kind='alias'))
        self.assertIsNone(unknown.canonical)
        self.assertIsNone(unknown.og_url)
