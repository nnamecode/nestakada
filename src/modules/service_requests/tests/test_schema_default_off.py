from __future__ import annotations

import importlib
import os
import uuid
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.migrations.operations.models import CreateModel
from django.test import TestCase
from django.utils import timezone

from config.settings import base as base_settings
from modules.service_requests.models import ServiceRequest, ServiceRequestDeletionProjection
from rebuild3_importer.runtime_target import TARGET_MIGRATION_LEAVES, TARGET_TABLES


class ServiceRequestSchemaDefaultOffTests(TestCase):
    def test_exact_models_and_fields(self) -> None:
        self.assertEqual(
            frozenset(model.__name__ for model in apps.get_app_config("service_requests").get_models()),
            frozenset({"ServiceRequest", "ServiceRequestDeletionProjection"}),
        )
        self.assertEqual(
            tuple(field.name for field in ServiceRequest._meta.local_fields),
            (
                "id",
                "created_at",
                "name",
                "phone",
                "vehicle_make",
                "vehicle_model",
                "vehicle_year",
                "comment",
                "consent_text_version",
                "consent_text_sha256",
                "consented_at",
                "telegram_outcome",
                "telegram_attempted_at",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in ServiceRequestDeletionProjection._meta.local_fields),
            ("sequence", "request_id"),
        )
        self.assertEqual(ServiceRequest._meta.db_table, "service_requests_servicerequest")

    def test_migration_creates_only_the_exact_models(self) -> None:
        migration = importlib.import_module(
            "modules.service_requests.migrations.0001_initial"
        ).Migration
        created = tuple(
            operation.name for operation in migration.operations if isinstance(operation, CreateModel)
        )
        self.assertEqual(created, ("ServiceRequest", "ServiceRequestDeletionProjection"))
        request_create = migration.operations[0]
        self.assertEqual(request_create.options["ordering"], ("-created_at", "-id"))
        self.assertEqual(
            tuple(tuple(index.fields) for index in request_create.options["indexes"]),
            (("-created_at", "-id"),),
        )

    def test_default_off_has_no_route_or_home_controls(self) -> None:
        self.assertIs(settings.SERVICE_REQUESTS_ENABLED, False)
        source_root = Path(__file__).resolve().parents[3]
        template = (
            source_root
            / "modules"
            / "pages"
            / "templates"
            / "pages"
            / "public_home.html"
        ).read_text(encoding="utf-8")
        request_block = template.split("{% if service_request_form %}", 1)[1]
        disabled = request_block.split("{% else %}", 1)[1].split("{% endif %}", 1)[0]
        for forbidden in ("<form", "<input", "<textarea", "<button"):
            self.assertNotIn(forbidden, disabled)

    def test_enable_flag_requires_exact_literal_true(self) -> None:
        for value in (None, "", "false", "False", "TRUE", "1", " true"):
            env = {} if value is None else {"ESTAKADA_SERVICE_REQUESTS_ENABLED": value}
            with self.subTest(value=value), patch.dict(os.environ, env, clear=True):
                self.assertIs(base_settings._service_requests_enabled(), False)
        with patch.dict(
            os.environ,
            {"ESTAKADA_SERVICE_REQUESTS_ENABLED": "true"},
            clear=True,
        ):
            self.assertIs(base_settings._service_requests_enabled(), True)

    def test_model_semantic_validation_accepts_multiline_comment(self) -> None:
        request = ServiceRequest(
            id=uuid.uuid4(),
            name="Иван",
            phone="+79991234567",
            vehicle_make="Лада",
            vehicle_model="Веста",
            vehicle_year="2024",
            comment="Первая строка\nВторая строка",
            consent_text_version="v1",
            consent_text_sha256="a" * 64,
            consented_at=timezone.now(),
        )
        request.full_clean()

    def test_model_rejects_noncanonical_semantic_fields(self) -> None:
        valid = {
            "id": uuid.uuid4(),
            "name": "Иван",
            "phone": "+79991234567",
            "vehicle_year": "2024",
            "consent_text_version": "v1",
            "consent_text_sha256": "a" * 64,
            "consented_at": timezone.now(),
        }
        for field, value in (
            ("phone", "89991234567"),
            ("vehicle_year", "２０２４"),
            ("consent_text_sha256", "A" * 64),
        ):
            with self.subTest(field=field):
                request = ServiceRequest(**(valid | {field: value}))
                with self.assertRaises(ValidationError):
                    request.full_clean()

    def test_importer_applies_schema_without_request_table_privileges(self) -> None:
        self.assertIn(("service_requests", "0001_initial"), TARGET_MIGRATION_LEAVES)
        self.assertNotIn("service_requests_servicerequest", TARGET_TABLES)
        self.assertNotIn("service_requests_servicerequestdeletionprojection", TARGET_TABLES)

    def test_generation_v5_includes_request_schema_but_keeps_data_default_off(self) -> None:
        source_root = Path(__file__).resolve().parents[4]
        generation = (source_root / "tools" / "rebuild7_generation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('SCHEMA = "estakada.r7-local-generation-v5"', generation)
        self.assertIn('"service_requests"', generation)
        self.assertIn('"requests": "absent-default-off"', generation)
        self.assertIn("def table_counts()", generation)
        self.assertIn("def table_content_hashes()", generation)
