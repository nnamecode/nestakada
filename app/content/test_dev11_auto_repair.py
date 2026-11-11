import json

from django.test import SimpleTestCase, override_settings

from .public_seo import (AutoRepairPage, AutoRepairProfile,
                         SeoUnavailable, VisibleBusinessFacts,
                         build_auto_repair, load_configuration,
                         serialize_auto_repair)


@override_settings(PUBLIC_ORIGIN='https://estakada-service.ru',
                   SEO_ROBOTS_PROFILE='production')
class Dev11AutoRepairTests(SimpleTestCase):
    def inputs(self, **changes):
        hostile = 'Эстакада </script><!-- & \u2028\u2029'
        values = {
            'name': hostile,
            'address': 'Москва, улица <Тестовая> & 1',
            'telephone': '+7 <495> 000-00-00',
        }
        values.update(changes)
        profile = AutoRepairProfile(**values)
        facts = VisibleBusinessFacts(
            name=values['name'], address=values['address'],
            telephone=values['telephone'])
        page = AutoRepairPage(
            page_kind='home', published=True, indexing_allowed=True)
        return profile, facts, page

    def test_s11_schema_001_missing_mismatch_or_wrong_page_omits_whole_node(self):
        configuration = load_configuration()
        profile, facts, page = self.inputs()
        self.assertIsNone(build_auto_repair(None, facts, page, configuration))
        self.assertIsNone(build_auto_repair(profile, None, page, configuration))
        for field in ('name', 'address', 'telephone'):
            changed = {
                'name': facts.name, 'address': facts.address,
                'telephone': facts.telephone}
            changed[field] = ''
            incomplete = VisibleBusinessFacts(**changed)
            with self.subTest(field=field):
                self.assertIsNone(build_auto_repair(
                    profile, incomplete, page, configuration))
        mismatch = VisibleBusinessFacts(
            name=facts.name + ' другая', address=facts.address,
            telephone=facts.telephone)
        self.assertIsNone(build_auto_repair(
            profile, mismatch, page, configuration))
        for wrong in (
                AutoRepairPage('article', True, True),
                AutoRepairPage('home', False, True),
                AutoRepairPage('contacts', True, False)):
            self.assertIsNone(build_auto_repair(
                profile, facts, wrong, configuration))
        minimal = json.loads(serialize_auto_repair(build_auto_repair(
            profile, facts, AutoRepairPage('contacts', True, True),
            configuration)))
        for optional in ('openingHours', 'geo', 'sameAs', 'logo', 'image'):
            self.assertNotIn(optional, minimal)
        for invalid in (
                AutoRepairProfile(profile.name, profile.address,
                                  profile.telephone,
                                  same_as=('http://example.com/profile',)),
                AutoRepairProfile(profile.name, profile.address,
                                  profile.telephone, latitude=55.75),
                AutoRepairProfile(profile.name, profile.address,
                                  profile.telephone,
                                  latitude=float('nan'), longitude=37.61)):
            with self.assertRaises(SeoUnavailable):
                build_auto_repair(invalid, facts, page, configuration)

    def test_s11_schema_002_exact_encoder_escapes_script_boundaries_and_reparses(self):
        configuration = load_configuration()
        profile, facts, page = self.inputs(
            opening_hours=('Mo-Fr 09:00-20:00',),
            latitude=55.75, longitude=37.61,
            same_as=('https://example.com/estakada',),
            logo='https://estakada-service.ru/static/logo.png',
            image='https://estakada-service.ru/static/shop.webp')
        node = build_auto_repair(profile, facts, page, configuration)
        encoded = serialize_auto_repair(node)
        for literal in ('<', '>', '&', '\u2028', '\u2029', '</script>', '<!--'):
            self.assertNotIn(literal, encoded)
        parsed = json.loads(encoded)
        self.assertEqual(parsed['@context'], 'https://schema.org')
        self.assertEqual(parsed['@type'], 'AutoRepair')
        self.assertEqual(
            parsed['@id'], 'https://estakada-service.ru/#auto-repair')
        self.assertEqual(parsed['url'], 'https://estakada-service.ru/')
        self.assertEqual(parsed['name'], profile.name)
        self.assertEqual(parsed['address'], profile.address)
        self.assertEqual(parsed['telephone'], profile.telephone)
        self.assertEqual(parsed['openingHours'], ['Mo-Fr 09:00-20:00'])
        self.assertEqual(parsed['geo']['@type'], 'GeoCoordinates')
        for forbidden in ('review', 'aggregateRating', 'offers',
                          'Offer', 'priceRange'):
            self.assertNotIn(forbidden, parsed)
        with self.assertRaises(SeoUnavailable):
            serialize_auto_repair({'@type': 'AutoRepair'})
