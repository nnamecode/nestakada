import uuid

from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from modules.pages.models import SiteSettings


class SiteSettingsContractTests(SimpleTestCase):
    def _asset(self, *, state: str = "READY"):
        asset_model = apps.get_model("media", "Asset")
        return asset_model(
            id=uuid.uuid4(),
            purpose="SITE_ASSET",
            source_sha256="a" * 64,
            state=state,
        )

    def _validate(self, settings: SiteSettings) -> None:
        settings.clean_fields(exclude=("logo_asset",))
        settings.clean()

    def _settings(self, **overrides) -> SiteSettings:
        values = {
            "id": uuid.uuid4(),
            "organization_name": "Estakada",
            "phone_display": "+7 499 110-25-52",
            "phone_e164": "+74991102552",
            "address": "Moscow",
            "opening_hours": "09:00–21:00",
            "contact_email": "owner@example.test",
            "map_url": "https://example.test/map",
            "logo_asset": self._asset(),
        }
        values.update(overrides)
        return SiteSettings(**values)

    def test_literal_settings_accept_exact_https_and_ready_logo(self) -> None:
        self._validate(self._settings())

    def test_http_or_staged_logo_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self._validate(self._settings(map_url="http://example.test/map"))
        staged = self._asset(state="STAGED")
        with self.assertRaises(ValidationError):
            self._validate(self._settings(logo_asset=staged))

    def test_url_userinfo_fragment_and_empty_nullable_url_are_rejected(self) -> None:
        for field_name, value in (
            ("map_url", "https://user@example.test/map"),
            ("map_url", "https://example.test/map#fragment"),
            ("max_url", ""),
        ):
            with self.subTest(field=field_name), self.assertRaises(ValidationError):
                self._validate(self._settings(**{field_name: value}))

    def test_invalid_e164_and_non_ascii_email_are_rejected(self) -> None:
        for overrides in (
            {"phone_e164": "74991102552"},
            {"contact_email": "владелец@example.test"},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValidationError):
                self._validate(self._settings(**overrides))
