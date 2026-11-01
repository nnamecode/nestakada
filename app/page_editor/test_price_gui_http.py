"""TP1 framework initial-state/real producer checks, not native GUI evidence."""
from copy import deepcopy
from urllib.parse import urlencode
from uuid import uuid4

from django.test import TransactionTestCase, override_settings
from django.conf import settings
from accounts.services import set_grant
from page_versions import services as V, schema as S
from page_versions.models import PageRevision, PageContentState, OwnerDraft, RestoreStage
from . import test_check_http as H

TEST_TEMPLATES = deepcopy(settings.TEMPLATES)
TEST_TEMPLATES[0]['DIRS'] = [*TEST_TEMPLATES[0].get('DIRS', []),
                           str(settings.BASE_DIR / 'page_editor' / 'templates')]

@override_settings(ROOT_URLCONF='page_editor.test_check_http', MIDDLEWARE=H.TEST_MIDDLEWARE, AUTH_TRUSTED_PROXY_HOST=None,
    TEMPLATES=TEST_TEMPLATES,
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PriceGuiHttpTests(TransactionTestCase):
    login = H.EditorCheckHttpTests.login
    raw = H.EditorCheckHttpTests.raw
    post = H.EditorCheckHttpTests.post
    payload = H.EditorCheckHttpTests.payload
    state = H.EditorCheckHttpTests.state

    def setUp(self):
        H.EditorCheckHttpTests.setUp(self)
        set_grant(actor=self.owner, employee=self.price_employee, page=self.page, price=True)

    def price(self, amount='0'):
        column, row = str(uuid4()), str(uuid4())
        return {'columns': [{'id': column, 'label': 'PRICE-COLUMN'}],
                'rows': [{'id': row, 'label': 'PRICE-ROW',
                          'cells': [{'column_id': column, 'kind': 'amount', 'amount': amount, 'from': True}]}]}

    def current(self):
        return PageRevision.objects.get(pk=PageContentState.objects.get(page=self.page).current_revision_id)

    def commit_price(self, price):
        payload = deepcopy(self.current().payload); payload['price'] = deepcopy(price)
        result = V.commit_owner(actor=self.owner, page_id=self.page.pk, base_revision=self.current().pk,
            snapshot=S.Snapshot.trusted(payload, self.page.kind), expected_generation=1, operation_id=uuid4())
        return PageRevision.objects.get(pk=result['result_id'])

    def editor(self, client=None, selector=None):
        url = '/manage/pages/%s/edit/' % self.page.pk
        if selector: url += '?' + urlencode(selector)
        return (client or self.owner_client).get(url)

    def checked(self, price, client=None):
        value = self.payload({'price': price}, baseRevisionId=str(self.current().pk))
        response = self.post(client or self.owner_client, value)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        return {**value, 'changes': data['normalisedChanges'], 'operationId': str(uuid4()),
                'checkReceipt': data['checkReceipt']}, data

    def save(self, value, client=None):
        old = self.url
        try:
            self.url = old.replace('/check/', '/save/')
            return self.post(client or self.owner_client, value)
        finally:
            self.url = old

    def test_tp1_002_own_price_key_controls_access_including_price_only_employee(self):
        price = self.price(); self.commit_price(price)
        owner = self.editor().context['initial_state']
        allowed = self.editor(self.price_client).context['initial_state']
        denied = self.editor(self.employee_client).context['initial_state']
        self.assertEqual(owner['values']['price'], price)
        self.assertEqual(allowed['values'], {'price': price})
        self.assertEqual(allowed['fields'], [])
        self.assertNotIn('price', denied['values'])
        before = self.state()
        direct = self.post(self.employee_client, self.payload({'price': price}, baseRevisionId=str(self.current().pk)))
        self.assertEqual(direct.status_code, 403)
        self.assertEqual(self.state(), before)

    def test_tp1_007_actual_selected_current_draft_stage_price_and_employee_draft_denial(self):
        first_price = self.price('0'); old = self.commit_price(first_price)
        draft = OwnerDraft.objects.get(page=self.page)
        draft_price = self.price('0.01')
        payload = deepcopy(draft.payload); payload['price'] = draft_price
        V.save_owner_draft(actor=self.owner, page_id=self.page.pk, base_revision=draft.base_revision_id,
            draft_id=draft.pk, draft_revision=draft.revision, snapshot=S.Snapshot.trusted(payload, self.page.kind),
            expected_generation=1, operation_id=uuid4())
        draft.refresh_from_db()
        current_price = self.price('999999999.99'); self.commit_price(current_price)
        prepared = V.prepare_restore(actor=self.owner, page_id=self.page.pk, version_id=old.pk, expected_generation=1)
        result = V.stage_restore(actor=self.owner, page_id=self.page.pk, preparation=prepared['preparation'],
            confirm_input_replacement=True, expected_generation=1, operation_id=uuid4())
        stage = RestoreStage.objects.get(pk=result['result_id'])
        before = self.state()
        draft_selector = {'source': 'owner-draft', 'draftId': str(draft.pk), 'draftRevision': draft.revision}
        self.assertEqual(self.editor().context['initial_state']['values']['price'], current_price)
        self.assertEqual(self.editor(selector=draft_selector).context['initial_state']['values']['price'], draft_price)
        self.assertEqual(self.editor(selector={'source': 'restore-stage', 'stageId': str(stage.pk)}).context['initial_state']['values']['price'], first_price)
        self.assertEqual(self.editor(self.price_client, draft_selector).status_code, 403)
        self.assertEqual(self.state(), before)

    def test_tp1_001_002_real_price_only_save_decimal_normalization_and_late_revoke(self):
        before = deepcopy(self.current().payload)
        input_price = self.price('1e-2')
        value, checked = self.checked(input_price, self.price_client)
        self.assertTrue(checked['normalisationChanged'])
        self.assertEqual(checked['normalisedChanges']['price']['rows'][0]['cells'][0]['amount'], '0.01')
        saved = self.save(value, self.price_client)
        self.assertEqual(saved.status_code, 200)
        current = self.current().payload
        self.assertEqual({key: item for key, item in current.items() if key != 'price'},
                         {key: item for key, item in before.items() if key != 'price'})
        self.assertEqual(current['price'], checked['normalisedChanges']['price'])
        value, _ = self.checked(self.price('0'), self.price_client)
        set_grant(actor=self.owner, employee=self.price_employee, page=self.page, main_text=True, price=False)
        state = self.state()
        self.assertEqual(self.save(value, self.price_client).status_code, 403)
        self.assertEqual(self.state(), state)

    def test_tp1_004_sparse_prices_and_invalid_amount_or_oversize_are_not_truncated(self):
        price = self.price(); price['columns'].append({'id': str(uuid4()), 'label': 'MISSING-CELL'})
        value, checked = self.checked(price)
        self.assertEqual(checked['normalisedChanges']['price'], price)
        self.assertEqual(len(value['changes']['price']['rows'][0]['cells']), 1)
        for field in ('amount', 'label', 'text'):
            invalid = deepcopy(price)
            if field == 'amount': invalid['rows'][0]['cells'][0]['amount'] = '0.001'
            elif field == 'label': invalid['rows'][0]['label'] = '🚀' * 501
            else: invalid['rows'][0]['cells'][0] = {'column_id': price['columns'][0]['id'], 'kind': 'text', 'text': '🚀' * 1001}
            original, before = deepcopy(invalid), self.state()
            response = self.post(self.owner_client, self.payload({'price': invalid}, baseRevisionId=str(self.current().pk)))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(invalid, original)
            self.assertEqual(self.state(), before)
