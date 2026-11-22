from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.apps import apps
from django.db import models
from django.db.migrations.operations.fields import AddField
from django.db.migrations.operations.models import CreateModel
from django.test import SimpleTestCase


SCHEMA_MODELS = {
    "media": frozenset({"Asset", "AssetFile", "AssetUsage"}),
    "gallery": frozenset({"GalleryAlbum", "GalleryPhoto"}),
}


def _created_models(module_name: str) -> dict[str, CreateModel]:
    migration = importlib.import_module(module_name).Migration
    return {
        operation.name: operation
        for operation in migration.operations
        if isinstance(operation, CreateModel)
    }


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _canonical(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_canonical(item) for item in value)
    if isinstance(value, str):
        return str(value)
    deconstruct = getattr(value, "deconstruct", None)
    if callable(deconstruct):
        parts = deconstruct()
        if len(parts) == 3:
            path, args, kwargs = parts
            return "deconstruct3", path, _canonical(args), _canonical(kwargs)
        if len(parts) == 4:
            _name, path, args, kwargs = parts
            return "deconstruct4", path, _canonical(args), _canonical(kwargs)
        raise TypeError(f"Unsupported deconstruct arity: {len(parts)}")
    return value


def _constraints(constraints: Iterable[models.BaseConstraint]) -> dict[str, Any]:
    return {constraint.name: _canonical(constraint) for constraint in constraints}


def _field_signature(field: models.Field) -> Any:
    _name, path, args, kwargs = field.deconstruct()
    return path, _canonical(args), _canonical(kwargs)


class Rebuild3SchemaSourceTests(SimpleTestCase):
    def test_page_url_authority_field_matches_ordinary_add_field_migration(self) -> None:
        model_field = apps.get_model("pages", "Page")._meta.get_field(
            "primary_url_mutable"
        )
        migration = importlib.import_module(
            "modules.pages.migrations.0003_page_primary_url_mutable"
        ).Migration
        operations = [operation for operation in migration.operations if isinstance(operation, AddField)]
        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual((operation.model_name, operation.name), ("page", "primary_url_mutable"))
        self.assertEqual(_field_signature(model_field), _field_signature(operation.field))
        self.assertIsInstance(model_field, models.BooleanField)
        self.assertFalse(model_field.null)
        self.assertFalse(model_field.default)

    def test_exact_approved_nh3_pin_is_in_the_foundation_input(self) -> None:
        repo = Path(__file__).resolve().parents[2]
        pin = "nh3==0.3.7 --hash=sha256:70f5ac8626e899a4bab0ef74ca2f5bd602f49c7b739e6e5026b4afc6d63dac42"
        foundation = (repo / "environment" / "foundation" / "requirements.lock").read_text(encoding="utf-8")
        editor = (repo / "environment" / "editor-package" / "requirements.lock").read_text(encoding="utf-8")
        self.assertEqual(foundation.splitlines().count(pin), 1)
        self.assertEqual(editor.splitlines().count(pin), 1)

    def test_exact_new_model_set_has_no_placeholder_tables(self) -> None:
        for app_label, expected in SCHEMA_MODELS.items():
            actual = frozenset(model.__name__ for model in apps.get_app_config(app_label).get_models())
            self.assertEqual(actual, expected)

    def test_model_fields_and_constraints_equal_migration_state(self) -> None:
        sources = {
            "media": _created_models("modules.media.migrations.0001_initial"),
            "pages": _created_models("modules.pages.migrations.0002_sitesettings"),
            "gallery": _created_models("modules.gallery.migrations.0001_initial"),
        }
        targets = (
            ("media", "Asset"),
            ("media", "AssetFile"),
            ("media", "AssetUsage"),
            ("pages", "SiteSettings"),
            ("gallery", "GalleryAlbum"),
            ("gallery", "GalleryPhoto"),
        )
        for app_label, model_name in targets:
            with self.subTest(model=f"{app_label}.{model_name}"):
                model = apps.get_model(app_label, model_name)
                operation = sources[app_label][model_name]
                migration_fields = dict(operation.fields)
                model_fields = {field.name: field for field in model._meta.local_fields}
                self.assertEqual(set(model_fields), set(migration_fields))
                for field_name, field in model_fields.items():
                    with self.subTest(field=f"{app_label}.{model_name}.{field_name}"):
                        self.assertEqual(
                            _field_signature(field),
                            _field_signature(migration_fields[field_name]),
                        )
                self.assertEqual(
                    _constraints(model._meta.constraints),
                    _constraints(operation.options.get("constraints", ())),
                )

    def test_deletion_edges_match_the_closed_contract(self) -> None:
        expected = {
            ("media", "AssetFile", "asset"): models.CASCADE,
            ("media", "AssetUsage", "asset"): models.PROTECT,
            ("pages", "SiteSettings", "logo_asset"): models.PROTECT,
            ("gallery", "GalleryAlbum", "page"): models.PROTECT,
            ("gallery", "GalleryPhoto", "album"): models.CASCADE,
            ("gallery", "GalleryPhoto", "asset"): models.PROTECT,
        }
        for (app_label, model_name, field_name), on_delete in expected.items():
            with self.subTest(field=f"{app_label}.{model_name}.{field_name}"):
                field = apps.get_model(app_label, model_name)._meta.get_field(field_name)
                self.assertIs(field.remote_field.on_delete, on_delete)

    def test_literal_field_caps_and_closed_choices(self) -> None:
        field_caps = {
            ("media", "AssetFile", "storage_key"): 1024,
            ("media", "AssetUsage", "slot"): 100,
            ("gallery", "GalleryPhoto", "alt"): 1000,
            ("pages", "SiteSettings", "organization_name"): 120,
            ("pages", "SiteSettings", "legal_name"): 160,
            ("pages", "SiteSettings", "phone_display"): 64,
            ("pages", "SiteSettings", "phone_e164"): 16,
            ("pages", "SiteSettings", "address"): 255,
            ("pages", "SiteSettings", "opening_hours"): 128,
            ("pages", "SiteSettings", "contact_email"): 254,
            ("pages", "SiteSettings", "map_url"): 2048,
            ("pages", "SiteSettings", "max_url"): 2048,
            ("pages", "SiteSettings", "telegram_url"): 2048,
        }
        for (app_label, model_name, field_name), cap in field_caps.items():
            with self.subTest(field=f"{app_label}.{model_name}.{field_name}"):
                field = apps.get_model(app_label, model_name)._meta.get_field(field_name)
                self.assertEqual(field.max_length, cap)

        choices = {
            ("media", "Asset", "purpose"): {"CONTENT", "SITE_ASSET", "GALLERY_ORIGINAL"},
            ("media", "Asset", "state"): {"STAGED", "READY"},
            ("media", "AssetFile", "kind"): {
                "PRIVATE_SOURCE", "MAIN", "PREVIEW", "LEGACY_PUBLIC"
            },
            ("media", "AssetFile", "mime_type"): {
                "image/jpeg", "image/png", "image/webp", "image/svg+xml"
            },
            ("media", "AssetUsage", "scope"): {
                "PAGE_CURRENT", "PAGE_PREVIOUS", "SITE_SETTINGS"
            },
        }
        for (app_label, model_name, field_name), expected in choices.items():
            with self.subTest(field=f"{app_label}.{model_name}.{field_name}"):
                field = apps.get_model(app_label, model_name)._meta.get_field(field_name)
                self.assertEqual({value for value, _ in field.choices}, expected)

    def test_exact_uniqueness_metadata(self) -> None:
        site = apps.get_model("pages", "SiteSettings")
        self.assertTrue(site._meta.get_field("singleton_key").unique)
        asset_file = apps.get_model("media", "AssetFile")
        self.assertTrue(asset_file._meta.get_field("storage_key").unique)
        album = apps.get_model("gallery", "GalleryAlbum")
        self.assertTrue(album._meta.get_field("position").unique)
