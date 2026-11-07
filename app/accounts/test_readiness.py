from io import StringIO
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from audit.models import AuditEvent
from content.models import Page

from .management.commands import readiness


class ReadinessCommandTests(TransactionTestCase):
    reset_sequences = False

    def state(self):
        return (Page.objects.count(), AuditEvent.objects.count(),
                Session.objects.count())

    def test_real_postgresql_read_only_bounded_select_without_output_or_write(self):
        before = self.state()
        stdout, stderr = StringIO(), StringIO()
        with CaptureQueriesContext(connection) as queries:
            call_command('readiness', stdout=stdout, stderr=stderr)
        sql = [item['sql'] for item in queries.captured_queries]
        joined = '\n'.join(sql).upper()
        self.assertIn('SET TRANSACTION READ ONLY', joined)
        self.assertIn('SET_CONFIG', joined)
        self.assertIn('STATEMENT_TIMEOUT', joined)
        self.assertIn('SELECT 1::INTEGER', joined)
        self.assertFalse(any(token in joined for token in (
            'INSERT INTO', 'UPDATE ', 'DELETE FROM', 'TRUNCATE ')))
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), '')
        self.assertEqual(self.state(), before)

    def test_query_contract_is_parameterized_and_exact(self):
        calls = []

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, parameters=None):
                calls.append((sql, parameters))

            def fetchone(self):
                return (1,)

        with patch.object(readiness.connection, 'cursor', return_value=Cursor()):
            call_command('readiness')
        self.assertEqual(calls, [
            ('SET TRANSACTION READ ONLY', None),
            ('SELECT set_config(%s, %s, %s)',
             ['statement_timeout', '2000ms', True]),
            ('SELECT %s::integer', [1]),
        ])

    def test_database_failure_and_unexpected_result_are_constant(self):
        with patch.object(readiness.connection, 'cursor',
                          side_effect=DatabaseError('PRIVATE-DB-CANARY')):
            with self.assertRaises(CommandError) as failed:
                call_command('readiness')
        self.assertEqual(str(failed.exception), readiness.FAILURE)
        self.assertNotIn('PRIVATE', str(failed.exception))

        class WrongCursor:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, parameters=None):
                pass

            def fetchone(self):
                return (2,)

        with patch.object(readiness.connection, 'cursor',
                          return_value=WrongCursor()):
            with self.assertRaises(CommandError) as wrong:
                call_command('readiness')
        self.assertEqual(str(wrong.exception), readiness.FAILURE)
