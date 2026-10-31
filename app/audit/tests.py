from datetime import datetime
import json
import logging
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .constants import Category, Level, Result, Source
from .formatters import SafeJsonFormatter
from .models import AuditEvent
from .services import record_event


def event(**overrides):
    values = dict(category=Category.ENVIRONMENT, event_code="ENV_CONFIG_CHECKED",
                  level=Level.INFO, source=Source.APPLICATION, result=Result.SUCCESS)
    values.update(overrides)
    return record_event(**values)


def log_record(message, **extras):
    record = logging.LogRecord("django.request", logging.ERROR, __file__, 1, message, (), None)
    record.__dict__.update(extras)
    return record


class FormatterPrivacyTests(SimpleTestCase):
    def test_ipv6_scope_cannot_carry_free_text_into_process_logs(self):
        record = log_record('unused', ip_address='fe80::1%SYNTHETIC-ZONE-TOKEN', ip_related=True)
        raw = SafeJsonFormatter().format(record)
        self.assertNotIn('SYNTHETIC-ZONE-TOKEN', raw)
        self.assertNotIn('ip_address', json.loads(raw))

    def test_sensitive_nested_payload_trace_and_unknown_extras_are_not_rendered(self):
        canaries = {
            "authorization": "Bearer SYNTHETIC-AUTH", "cookie": "SYNTHETIC-COOKIE",
            "password": "SYNTHETIC-PASSWORD", "request-comment": "SYNTHETIC-COMMENT",
            "request-phone": "+70000000000", "secret-key": "SYNTHETIC-KEY",
            "token": "SYNTHETIC-TOKEN",
        }
        record = log_record({"nested": [canaries]}, event_code="FOUNDATION-LOG-BENIGN",
                            authorization=canaries["authorization"], request=canaries,
                            url="https://example.invalid/?token=" + canaries["token"])
        record.args = (canaries,)
        record.exc_info = (ValueError, ValueError(canaries["password"]), None)
        record.stack_info = canaries["secret-key"]
        raw = SafeJsonFormatter().format(record)
        self.assertEqual(json.loads(raw)["event_code"], "FOUNDATION-LOG-BENIGN")
        for value in canaries.values():
            self.assertNotIn(value, raw)
        self.assertNotIn("example.invalid", raw)
        self.assertNotIn("traceback", raw.lower())

    def test_raw_message_and_unknown_object_are_never_stringified(self):
        class ForbiddenRepresentation:
            def __str__(self):
                raise AssertionError("An untrusted repr must not execute")
            __repr__ = __str__
        raw = SafeJsonFormatter().format(log_record(ForbiddenRepresentation(), unknown=ForbiddenRepresentation()))
        self.assertEqual(json.loads(raw)["event_code"], "PROCESS_MESSAGE")

    def test_malformed_record_has_constant_safe_failure_without_logging_fallback(self):
        record = log_record("SYNTHETIC-SECRET-MUST-NOT-LEAK", created=float("nan"))
        raw = SafeJsonFormatter().format(record)
        self.assertEqual(json.loads(raw)["event_code"], "LOG_RECORD_REJECTED")
        self.assertNotIn("SYNTHETIC-SECRET", raw)

    def test_only_typed_references_and_explicitly_related_ip_survive(self):
        request_id = uuid4()
        record = log_record("ignored", event_code="CONTENT_SAVED", actor_id=12,
                            object_kind="page", object_ref="id:33", request_id=request_id,
                            ip_address="2001:db8::1", ip_related=True)
        actual = json.loads(SafeJsonFormatter().format(record))
        self.assertEqual(actual["actor_id"], 12)
        self.assertEqual(actual["object_ref"], "id:33")
        self.assertEqual(actual["request_id"], str(request_id))
        self.assertEqual(actual["ip_address"], "2001:db8::1")
        self.assertTrue(actual["occurred_at"].endswith("Z"))
        record.request_id = "SYNTHETIC-TOKEN"
        record.actor_id = True
        record.object_ref = "https://example.invalid/?password=SYNTHETIC-PASSWORD"
        record.ip_related = False
        actual = json.loads(SafeJsonFormatter().format(record))
        for field in ("actor_id", "object_ref", "object_kind", "request_id", "ip_address"):
            self.assertNotIn(field, actual)

    def test_invalid_code_cannot_smuggle_newline_or_query(self):
        actual = json.loads(SafeJsonFormatter().format(log_record("ignored", event_code="BAD\npassword=secret")))
        self.assertEqual(actual["event_code"], "PROCESS_MESSAGE")


class AuditWriterTests(TestCase):
    def test_categories_are_the_nine_approved_categories(self):
        self.assertEqual(set(Category.labels), {
            "Вход и доступ", "Безопасность", "Действия пользователей", "Ошибки сайта",
            "Страницы и ссылки", "Обновления и окружение", "Резервирование и обслуживание",
            "Производительность и внешние связи", "Другие / служебные",
        })

    def test_one_insert_stable_uuid_and_typed_references(self):
        object_id, request_id = uuid4(), uuid4()
        saved = event(actor_id=42, object_kind="page", object_ref=object_id, request_id=request_id)
        actual = AuditEvent.objects.get(pk=saved.pk)
        self.assertEqual(actual.event_id, saved.event_id)
        self.assertEqual(actual.object_ref, "uuid:" + str(object_id))
        self.assertEqual(actual.request_id, request_id)
        self.assertTrue(timezone.is_aware(actual.occurred_at))
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_enclosing_operation_rollback_removes_its_event(self):
        with self.assertRaisesRegex(RuntimeError, "operation rollback"):
            with transaction.atomic():
                event()
                raise RuntimeError("operation rollback")
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_database_failure_is_propagated_without_fake_success(self):
        failure = DatabaseError("SYNTHETIC-DB-FAILURE")
        with patch.object(AuditEvent, "save", side_effect=failure):
            with self.assertRaises(DatabaseError) as caught:
                event()
        self.assertIs(caught.exception, failure)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_duplicate_event_id_does_not_produce_two_events(self):
        event_id = uuid4()
        event(event_id=event_id)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                event(event_id=event_id)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_raw_payload_arguments_are_rejected(self):
        for key in ("password", "request_body", "request_comment", "cookie", "token", "url"):
            with self.subTest(key=key), self.assertRaises(TypeError):
                event(**{key: "SYNTHETIC-SECRET"})
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_untyped_references_and_unrelated_ip_are_rejected(self):
        cases = [dict(actor_id=True), dict(actor_id=0), dict(object_ref="+70000000000"),
                 dict(object_ref="https://example.invalid"), dict(request_id="token"),
                 dict(object_ref=1), dict(ip_address="192.0.2.1"),
                 dict(category="invalid\nSYNTHETIC-SECRET"), dict(event_code="bad password")]
        for overrides in cases:
            with self.subTest(overrides=list(overrides)), self.assertRaises(ValidationError):
                event(**overrides)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_related_ip_is_validated_and_event_model_is_append_only(self):
        with self.assertRaises(ValidationError):
            event(ip_address='fe80::1%SYNTHETIC-ZONE-TOKEN', ip_related=True)
        self.assertEqual(AuditEvent.objects.count(), 0)
        saved = event(ip_address="192.0.2.1", ip_related=True)
        self.assertEqual(saved.ip_address, "192.0.2.1")
        saved.code = "REWRITTEN"
        with self.assertRaises(ValidationError):
            saved.save()
        self.assertEqual(AuditEvent.objects.get(pk=saved.pk).code, "ENV_CONFIG_CHECKED")

    def test_new_instance_with_existing_pk_cannot_overwrite_an_event(self):
        saved = event()
        for options in ({}, {'force_update': True}, {'update_fields': ['code']}):
            replacement = AuditEvent(id=saved.pk, category=Category.SERVICE, level=Level.INFO,
                                    code='REWRITTEN', source=Source.APPLICATION, result=Result.SUCCESS)
            with self.subTest(options=list(options)), self.assertRaises(ValidationError):
                replacement.save(**options)
            actual = AuditEvent.objects.get(pk=saved.pk)
            self.assertEqual(actual.event_id, saved.event_id)
            self.assertEqual(actual.code, saved.code)

    def test_database_choice_constraint_survives_bulk_api_bypass(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AuditEvent.objects.bulk_create([AuditEvent(category="invented", level=Level.INFO,
                    code="CONTROLLED_EVENT", source=Source.APPLICATION, result=Result.SUCCESS)])

    def test_naive_timestamp_cannot_be_saved(self):
        value = AuditEvent(category=Category.SERVICE, level=Level.INFO, code="CONTROLLED_EVENT",
                           source=Source.APPLICATION, result=Result.SUCCESS, occurred_at=datetime(2026, 1, 1))
        with self.assertRaises(ValidationError):
            value.save()
