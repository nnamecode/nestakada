from django.template.loader import render_to_string
from django.test import SimpleTestCase


class PublicRequestFormUiTests(SimpleTestCase):
    def render_form(self, *, enabled):
        context = {'service_request_form': {
            'enabled': enabled,
            'source': 'home',
        }}
        if enabled:
            context['service_request_form'].update({
                'csrf_token': 'csrf-placeholder',
                'intent': 'intent-placeholder',
            })
        return render_to_string(
            'service_requests/public_form.html', context)

    def test_disabled_state_has_no_form_intent_or_legal_links(self):
        source = self.render_form(enabled=False)
        self.assertNotIn('<form', source)
        self.assertNotIn('intent-placeholder', source)
        self.assertNotIn('/privacy/', source)
        self.assertNotIn('/consent-service-request/', source)
        self.assertIn('Онлайн-запись пока недоступна', source)

    def test_enabled_state_has_unchecked_consent_and_same_origin_links(self):
        source = self.render_form(enabled=True)
        self.assertIn('<form method="post" action="/request/submit/">', source)
        self.assertIn(
            '<input type="checkbox" name="consent" value="on" required>',
            source)
        self.assertNotIn('checked', source)
        self.assertIn(
            'href="/consent-service-request/"', source)
        self.assertIn('href="/privacy/"', source)
        self.assertNotIn('<script', source)
        self.assertNotIn('localStorage', source)
        self.assertNotIn('sessionStorage', source)
