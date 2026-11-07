from datetime import datetime, timedelta, timezone as datetime_timezone
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, models
from django.test import TransactionTestCase

from audit.constants import Category, Level, Result, Source
from audit.models import AuditEvent
from content.models import Page

from .management.commands import cleanup_audit


UTC = datetime_timezone.utc
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


class AuditRetentionCommandTests(TransactionTestCase):
    reset_sequences = False

    def event(self, code, occurred_at):
        return AuditEvent(
            event_id=uuid4(), occurred_at=occurred_at,
            category=Category.SERVICE, level=Level.INFO, code=code,
            source=Source.APPLICATION, result=Result.SUCCESS,
        )

    def test_exact_older_than_boundary_and_safe_count(self):
        old = self.event('RETENTION_OLD', NOW - timedelta(days=30, seconds=1))
        boundary = self.event('RETENTION_BOUNDARY', NOW - timedelta(days=30))
        recent = self.event('RETENTION_RECENT', NOW - timedelta(days=1))
        AuditEvent.objects.bulk_create([old, boundary, recent])
        output = StringIO()
        with patch.object(cleanup_audit.timezone, 'now', return_value=NOW):
            call_command('cleanup_audit', stdout=output)
        self.assertEqual(output.getvalue(), 'AUDIT_RETENTION_OK deleted=1\n')
        self.assertEqual(
            set(AuditEvent.objects.values_list('code', flat=True)),
            {'RETENTION_BOUNDARY', 'RETENTION_RECENT'},
        )

    def test_only_audit_changes_and_command_has_no_scope_options(self):
        user = get_user_model().objects.create_user('retention-user')
        page = Page.objects.create(name='Retention page', kind=Page.Kind.ARTICLE)
        Session.objects.create(
            session_key='r' * 32, session_data='e30:fixture', expire_date=NOW)
        AuditEvent.objects.bulk_create([
            self.event('RETENTION_DELETE', NOW - timedelta(days=31)),
            self.event('RETENTION_KEEP', NOW),
        ])
        before = (user.pk, page.pk, get_user_model().objects.count(),
                  Page.objects.count(), Session.objects.count())
        with patch.object(cleanup_audit.timezone, 'now', return_value=NOW):
            call_command('cleanup_audit', stdout=StringIO())
        self.assertEqual(
            (user.pk, page.pk, get_user_model().objects.count(),
             Page.objects.count(), Session.objects.count()), before)
        self.assertEqual(list(AuditEvent.objects.values_list('code', flat=True)),
                         ['RETENTION_KEEP'])
        self.assertNotIn('add_arguments', cleanup_audit.Command.__dict__)

    def test_failure_is_constant_and_transaction_rolls_back(self):
        old = self.event('RETENTION_ROLLBACK', NOW - timedelta(days=31))
        AuditEvent.objects.bulk_create([old])
        actual_delete = models.QuerySet.delete

        def delete_then_fail(queryset):
            actual_delete(queryset)
            raise DatabaseError('PRIVATE-DB-CANARY')

        with patch.object(cleanup_audit.timezone, 'now', return_value=NOW), \
                patch.object(models.QuerySet, 'delete', delete_then_fail):
            with self.assertRaises(CommandError) as failed:
                call_command('cleanup_audit')
        self.assertEqual(str(failed.exception), cleanup_audit.FAILURE)
        self.assertNotIn('PRIVATE', str(failed.exception))
        self.assertTrue(AuditEvent.objects.filter(pk=old.pk).exists())
