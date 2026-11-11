from django.test import SimpleTestCase, override_settings


@override_settings(ROOT_URLCONF='estakada.urls')
class Dev11RobotsTests(SimpleTestCase):
    @override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                       SEO_ROBOTS_PROFILE='deny-all')
    def test_s11_robots_001_deny_all_is_exact_and_has_no_internal_inventory(self):
        expected = b'User-agent: *\nDisallow: /\n'
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, expected)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertEqual(response['Cache-Control'], 'no-cache')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertNotIn(b'Sitemap:', response.content)
        self.assertNotIn(b'/manage/', response.content)

    @override_settings(PUBLIC_ORIGIN='https://estakada-service.ru',
                       SEO_ROBOTS_PROFILE='production')
    def test_s11_robots_002_production_is_fixed_and_origin_is_not_request_derived(self):
        expected = (
            'User-agent: *\n'
            'Disallow: /manage/\n'
            'Disallow: /cgi-bin\n'
            'Disallow: /manager/\n'
            'Disallow: /assets/components/\n'
            'Disallow: /core/\n'
            'Disallow: /connectors/\n'
            'Disallow: /index.php\n'
            'Disallow: /*?\n'
            'Allow: /gallery-of-works/?page=1$\n'
            'Allow: /gallery-of-works/?page=2$\n'
            'Sitemap: https://estakada-service.ru/sitemap.xml\n'
        ).encode()
        response = self.client.get(
            '/robots.txt', HTTP_X_FORWARDED_HOST='attacker.example',
            HTTP_REFERER='https://attacker.example/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, expected)
        self.assertNotIn(b'attacker.example', response.content)
        self.assertNotIn(b'Disallow: /static/', response.content)
        self.assertNotIn(b'Disallow: /public-media/', response.content)

    @override_settings(PUBLIC_ORIGIN='http://localhost:8767',
                       SEO_ROBOTS_PROFILE='deny-all')
    def test_s11_robots_003_head_and_methods_are_closed(self):
        get = self.client.get('/robots.txt')
        head = self.client.head('/robots.txt')
        post = self.client.post('/robots.txt')
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(head['Content-Length'], str(len(get.content)))
        self.assertEqual(post.status_code, 405)
        self.assertEqual(post['Allow'], 'GET, HEAD')
        self.assertEqual(post['Cache-Control'], 'no-store')
