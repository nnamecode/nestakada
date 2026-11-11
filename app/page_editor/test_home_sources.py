from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.test import TransactionTestCase
from django.core import signing
from content.models import Page, Route, lock_content
from page_versions import schema as S
from page_versions.models import PageContentState, PageRevision
from .home_sources import capture, synchronize
from .checks import CheckContext, CheckFault, SALT, issue_check_receipt, verify_check_receipt
from .input_policy import fingerprint
from . import policy_constants


class HomeSourceFactsTests(TransactionTestCase):
    reset_sequences = True

    def profile(self, page_id=None, row_id=None):
        return {'services': [{'source_page_id': page_id}],
                'prices': [{'source_page_id': None, 'rows': [
                    {'source_page_id': page_id if row_id else None, 'source_row_id': row_id}]}],
                'works': []}

    def source(self, *, published=True):
        page = Page.objects.create(kind=Page.Kind.SERVICE, name='Source', is_published=published)
        Route.objects.create(page=page, kind=Route.Kind.PRIMARY, target='/source/')
        column_id, row_id = str(uuid4()), str(uuid4())
        price = {'columns': [{'id': column_id, 'label': 'Цена'}], 'rows': [
            {'id': row_id, 'label': 'Работа', 'cells': [
                {'column_id': column_id, 'kind': 'amount', 'amount': '1250', 'from': True}]}]}
        payload = S.snapshot_v1(page.kind, h1='Source', price=price).data(page.kind)
        revision = PageRevision.objects.create(page=page, sequence=1, schema_version=S.SCHEMA,
            payload=payload, payload_hash=S.digest(payload), kind=PageRevision.Kind.INITIAL, author_id=1)
        PageContentState.objects.create(page=page, current_revision=revision, sequence=1)
        return page, revision, row_id

    def test_exact_visibility_revision_and_amount_only_facts(self):
        page, revision, row_id = self.source()
        with transaction.atomic():
            lock_content('default')
            facts, digest = capture(self.profile(str(page.pk), row_id))
        self.assertEqual(len(digest), 64)
        self.assertEqual(facts, {'schema': 'home-source-facts-v1', 'sources': [{
            'page_id': str(page.pk), 'present': True, 'visible': True, 'primary': '/source/',
            'current_revision_id': str(revision.pk), 'payload_hash': revision.payload_hash,
            'price_rows': [{'row_id': row_id, 'amount': '1250', 'from': True}]}]})

    def test_missing_source_is_deterministic_fallback_fact(self):
        missing = str(uuid4())
        with transaction.atomic():
            lock_content('default')
            facts, digest = capture(self.profile(missing))
        self.assertEqual(len(digest), 64)
        self.assertEqual(facts['sources'][0], {
            'page_id': missing, 'present': False, 'visible': False, 'primary': None,
            'current_revision_id': None, 'payload_hash': None, 'price_rows': []})

    def test_existing_source_requires_complete_route_state_revision(self):
        page, _revision, _row_id = self.source()
        models.QuerySet(model=Route, using='default').filter(
            page=page).delete()
        with transaction.atomic():
            lock_content('default')
            with self.assertRaisesMessage(ValidationError,
                                          'EDITOR_HOME_SOURCES_INVALID'):
                capture(self.profile(str(page.pk)))
        page, _revision, _row_id = self.source()
        models.QuerySet(model=PageContentState, using='default').filter(
            page=page).delete()
        with transaction.atomic():
            lock_content('default')
            with self.assertRaisesMessage(ValidationError,
                                          'EDITOR_HOME_SOURCES_INVALID'):
                capture(self.profile(str(page.pk)))

    def test_digest_detects_page_xmin_aba_with_identical_facts(self):
        page, _revision, row_id = self.source()
        with transaction.atomic():
            lock_content('default')
            first, first_digest = capture(self.profile(str(page.pk), row_id))
        models.QuerySet(model=Page, using='default').filter(pk=page.pk).update(
            is_published=False)
        models.QuerySet(model=Page, using='default').filter(pk=page.pk).update(
            is_published=True)
        with transaction.atomic():
            lock_content('default')
            second, second_digest = capture(self.profile(str(page.pk), row_id))
        self.assertEqual(first, second)
        self.assertNotEqual(first_digest, second_digest)

    def test_synchronize_derives_visibility_and_price_but_keeps_unbound(self):
        source_id, row_id = str(uuid4()), str(uuid4())
        base = {
            'services': [{'source_page_id': source_id,
                          'fallback_visible': False}],
            'prices': [{'source_page_id': None, 'rows': [{
                'source_page_id': source_id, 'source_row_id': row_id,
                'fallback_visible': False, 'price_text': 'подмена',
            }]}],
            'works': [{'source_page_id': None, 'fallback_visible': False}],
        }
        candidate = {
            'services': [{'source_page_id': source_id,
                          'fallback_visible': False}],
            'prices': [{'source_page_id': None, 'rows': [{
                'source_page_id': source_id, 'source_row_id': row_id,
                'fallback_visible': False, 'price_text': 'подмена',
            }]}],
            'works': [{'source_page_id': None, 'fallback_visible': True}],
        }
        facts = {'schema': 'home-source-facts-v1', 'sources': [{
            'page_id': source_id, 'present': True, 'visible': True,
            'primary': '/source/', 'current_revision_id': str(uuid4()),
            'payload_hash': 'a' * 64, 'price_rows': [{
                'row_id': row_id, 'amount': '1250', 'from': True,
            }],
        }]}
        result = synchronize(base, candidate, facts)
        self.assertTrue(result['services'][0]['fallback_visible'])
        self.assertTrue(result['prices'][0]['rows'][0]['fallback_visible'])
        self.assertEqual(result['prices'][0]['rows'][0]['price_text'],
                         'от 1 250 ₽')
        self.assertTrue(result['works'][0]['fallback_visible'])

    def test_cap_plus_one_and_corrupt_hash_fail_closed(self):
        profile = self.profile()
        profile['services'] = [{'source_page_id': str(uuid4())} for _ in range(65)]
        with transaction.atomic():
            lock_content('default')
            with self.assertRaisesMessage(ValidationError, 'EDITOR_HOME_SOURCES_CAP'):
                capture(profile)
        page, revision, row_id = self.source()
        models.QuerySet(model=PageRevision, using='default').filter(
            pk=revision.pk).update(payload_hash='0' * 64)
        with transaction.atomic():
            lock_content('default')
            with self.assertRaisesMessage(ValidationError, 'EDITOR_HOME_SOURCES_INVALID'):
                capture(self.profile(str(page.pk), row_id))

    def test_capture_requires_retained_transaction(self):
        with self.assertRaisesMessage(ValidationError, 'EDITOR_HOME_SOURCES_LOCK_REQUIRED'):
            capture(self.profile())

    def test_digest_is_an_exact_signed_receipt_claim(self):
        digest = 'a' * 64
        child = {'policy_version': policy_constants.POLICY_VERSION, 'generation': 1,
                 'page_id': str(uuid4()), 'base_revision_id': str(uuid4()),
                 'source': {'editingFrom': 'current'}}
        context = CheckContext(1, child, 'b' * 64, 'c' * 64, None, digest)
        changes = {'home_profile': {'schema': 'synthetic-receipt-only'}}
        result = {'policy_version': policy_constants.POLICY_VERSION,
                  'input_fingerprint': 'd' * 64,
                  'normalized_fingerprint': fingerprint(changes)}
        token = issue_check_receipt(context=context, result=result)
        claims = verify_check_receipt(token, context=context, changes=changes)
        self.assertEqual(claims['homeSourceDigest'], digest)
        forged = signing.dumps({**claims, 'homeSourceDigest': 'e' * 64},
                               salt=SALT, compress=False)
        with self.assertRaises(CheckFault):
            verify_check_receipt(forged, context=context, changes=changes)
