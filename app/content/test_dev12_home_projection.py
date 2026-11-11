import copy
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TransactionTestCase

from . import home_projection as projection


class Dev12HomeProjectionTests(TransactionTestCase):
    def profile(self):
        service_id, price_id, work_id = (str(uuid4()) for _ in range(3))
        row_id = str(uuid4())
        return {
            'schema':'home-profile-v1', 'hero':{}, 'advantages':[],
            'comparisons':[], 'steps':[], 'photo_strip':{}, 'reviews':{},
            'services':[{'id':'service', 'label':'Saved service',
                         'url':'/saved-service', 'image_id':'image-service',
                         'fallback_visible':True, 'source_page_id':service_id}],
            'prices':[{'id':'group', 'key':'g', 'url':'/group', 'label':'Saved group',
                       'source_page_id':None, 'rows':[{
                           'id':'row', 'label':'Saved price', 'url':'/saved-price',
                           'price_text':'от 1 000 ₽', 'fallback_visible':True,
                           'source_page_id':price_id, 'source_row_id':row_id}]}],
            'works':[{'id':'work', 'label':'Saved work', 'url':'/saved-work',
                      'image_id':'image-work', 'asset_id':'asset-work',
                      'photo_count_text':'6 фото', 'alt':'Saved alt',
                      'fallback_visible':False, 'source_page_id':work_id}],
        }, service_id, price_id, work_id, row_id

    def facts(self, ids, row_id, *, service=(True, True),
              price=(True, True), work=(True, True), amount='1250.50', from_=True):
        def source(page_id, state, rows):
            present, visible = state
            return {'page_id':page_id, 'present':present, 'visible':visible,
                    'primary':'/source' if present else None,
                    'current_revision_id':str(uuid4()) if present else None,
                    'payload_hash':'a' * 64 if present else None,
                    'price_rows':rows}
        service_id, price_id, work_id = ids
        return {'schema':'home-source-facts-v1', 'sources':sorted([
            source(service_id, service, []),
            source(price_id, price, [{'row_id':row_id, 'amount':amount,
                                      'from':from_}]),
            source(work_id, work, []),
        ], key=lambda item:item['page_id'])}

    def test_dynamic_projection_changes_only_price_amount_and_visibility(self):
        profile, service, price, work, row = self.profile()
        before = copy.deepcopy(profile)
        result = projection.project(
            profile, self.facts((service, price, work), row))['profile']
        self.assertEqual(result['prices'][0]['rows'][0]['price_text'],
                         'от 1 250.5 ₽')
        self.assertEqual(result['services'][0]['label'], 'Saved service')
        self.assertEqual(result['services'][0]['url'], '/saved-service')
        self.assertEqual(result['works'][0]['photo_count_text'], '6 фото')
        self.assertEqual(profile, before)

    def test_hidden_existing_source_hides_items_and_empty_groups(self):
        profile, service, price, work, row = self.profile()
        result = projection.project(profile, self.facts(
            (service, price, work), row, service=(True, False),
            price=(True, False), work=(True, False)))['profile']
        self.assertEqual(result['services'], [])
        self.assertEqual(result['prices'], [])
        self.assertEqual(result['works'], [])

    def test_missing_source_uses_saved_fallback_without_url_lookup(self):
        profile, service, price, work, row = self.profile()
        result = projection.project(profile, self.facts(
            (service, price, work), row, service=(False, False),
            price=(False, False), work=(False, False)))['profile']
        self.assertEqual(result['services'][0]['label'], 'Saved service')
        self.assertEqual(result['prices'][0]['rows'][0]['price_text'],
                         'от 1 000 ₽')
        self.assertEqual(result['works'], [])
        self.assertEqual(result['services'][0]['source_state'], 'missing')

    def test_visible_source_missing_exact_price_row_hides_row(self):
        profile, service, price, work, row = self.profile()
        facts = self.facts((service, price, work), row)
        next(item for item in facts['sources']
             if item['page_id'] == price)['price_rows'] = []
        self.assertEqual(projection.project(profile, facts)['profile']['prices'], [])

    def test_unknown_duplicate_or_cap_plus_one_binding_fails_closed(self):
        profile, service, price, work, row = self.profile()
        facts = self.facts((service, price, work), row)
        facts['sources'].append(copy.deepcopy(facts['sources'][0]))
        with self.assertRaisesMessage(ValidationError, 'HOME_PROJECTION_INVALID'):
            projection.project(profile, facts)
        profile['services'] = [{'source_page_id':str(uuid4()),
                                'fallback_visible':True} for _ in range(65)]
        with self.assertRaisesMessage(ValidationError, 'EDITOR_HOME_SOURCES_CAP'):
            projection.project(profile, {'schema':'home-source-facts-v1',
                                         'sources':[]})

    def test_double_capture_stale_refuses_whole_projection(self):
        profile, service, price, work, row = self.profile()
        facts = self.facts((service, price, work), row)
        first = ({'schema':'home-source-capture-v1', 'facts':facts,
                  'row_versions':{}}, 'a' * 64)
        second = (copy.deepcopy(first[0]), 'b' * 64)
        with transaction.atomic(), patch.object(
                projection, 'capture_once', side_effect=[first, second]):
            with self.assertRaisesMessage(ValidationError,
                                          'HOME_PROJECTION_STALE'):
                projection.capture_coherent(profile)
