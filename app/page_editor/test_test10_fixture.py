from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from unittest.mock import MagicMock, patch

from accounts import services as auth
from accounts.models import PageGrant, UserProfile
from content.models import Page
from page_versions.models import PageContentState, PageRevision, RevisionProtection
from shared_content.models import SharedBlock

from .test10_fixture import CASE_IDS, PROFILES, prepare, validate_database_name
from .test10_database import identity, marker_values, prepare as prepare_database, teardown as teardown_database
from .management.commands import test10_fixture as fixture_command


class Test10FixtureTests(TransactionTestCase):
    reset_sequences = True

    secrets = {
        "owner": "o" * 48, "s_edit": "e" * 48,
        "s_other": "x" * 48, "canary": "c" * 64,
    }

    def setUp(self):
        self.instant = timezone.now()

    def make(self):
        return prepare(database_name="estakada_test10_" + "a" * 32,
                       secrets=self.secrets, reference_instant=self.instant)

    def test_closed_contract_rejects_foreign_database_and_secret_shape(self):
        with self.assertRaisesRegex(ValueError, "T10_FIXTURE_DATABASE_REJECTED"):
            validate_database_name("estakada_foundation_unit")
        with self.assertRaisesRegex(ValueError, "T10_FIXTURE_SECRET_SET_REJECTED"):
            prepare(database_name="estakada_test10_" + "a" * 32,
                    secrets={"owner": "o" * 48})
        self.assertEqual(identity("b" * 32), "estakada_test10_" + "b" * 32)
        with self.assertRaisesRegex(ValueError, "T10_DATABASE_RUN_ID_REJECTED"):
            identity("B" * 32)
        self.assertEqual(marker_values("b" * 32, "c" * 64, "d" * 64),
                         ("estakada_test10_" + "b" * 32,
                          ("b" * 32, "estakada_test10_" + "b" * 32,
                           "c" * 64, "d" * 64)))
        with self.assertRaisesRegex(ValueError, "T10_DATABASE_MARKER_REJECTED"):
            marker_values("b" * 32, "C" * 64, "d" * 64)

    def test_fixed_fixture_has_exact_profiles_cases_and_safe_summary(self):
        summary, private = self.make()
        self.assertEqual(tuple(summary["profiles"]), PROFILES)
        self.assertEqual(tuple(summary["caseIds"]), CASE_IDS)
        self.assertFalse(summary["containsSecrets"])
        rendered = str(summary)
        for value in self.secrets.values():
            self.assertNotIn(value, rendered)
        self.assertEqual(set(private["passwords"]), {"OWNER", "S-EDIT", "S-OTHER"})
        self.assertEqual(set(private["sessions"]), {
            "OWNER", "S-EDIT", "S-OTHER", "S-EDIT-IDLE-1801",
            "S-EDIT-ABSOLUTE-43201"})

        self.assertEqual(get_user_model().objects.count(), 3)
        self.assertEqual(set(UserProfile.objects.values_list("role", flat=True)),
                         {"owner", "employee"})
        self.assertEqual(Page.objects.count(), 1)
        page = Page.objects.get()
        self.assertTrue(page.is_published)
        state = PageContentState.objects.get(page=page)
        self.assertEqual(state.sequence, 3)
        self.assertEqual(PageRevision.objects.filter(page=page).count(), 3)
        self.assertEqual(RevisionProtection.objects.filter(
            revision__page=page).count(), 1)
        grant = PageGrant.objects.get(user__username="test10-s-edit", page=page)
        self.assertTrue(grant.intro_text and grant.main_text)
        self.assertFalse(grant.price)
        self.assertEqual(page.routes.get(kind="primary").target,
                         "/test10/assigned/")
        self.assertEqual(state.current_revision_id,
                         PageRevision.objects.get(sequence=2).pk)
        self.assertEqual(PageRevision.objects.get(sequence=3).schema_version,
                         "test10-incompatible-v0")
        self.assertEqual(summary["descriptor"]["page"]["ownerDraftPayloadHash"],
                         page.owner_draft.payload_hash)
        self.assertEqual(set(SharedBlock.objects.values_list("kind", flat=True)),
                         {"header", "footer"})
        self.assertEqual(Session.objects.count(), 5)
        self.assertEqual(summary["descriptor"]["sessionAges"], {
            "active": {"issued": 0, "lastSeen": 0},
            "idleExpired": {"issued": 1801, "lastSeen": 1801},
            "absoluteExpired": {"issued": 43201, "lastSeen": 0}})

        edit = get_user_model().objects.get(username="test10-s-edit")
        with patch("accounts.clock.now", return_value=self.instant):
            auth.check_session_identity(edit, 1, private["sessions"]["S-EDIT"])
            for name in ("S-EDIT-IDLE-1801", "S-EDIT-ABSOLUTE-43201"):
                with self.assertRaisesRegex(ValidationError, "AUTH_SESSION_INVALID"):
                    auth.check_session_identity(edit, 1, private["sessions"][name])
        idle = SessionStore(session_key=private["sessions"]["S-EDIT-IDLE-1801"])
        self.assertEqual(idle[auth.SESSION_ISSUED_AT], idle[auth.SESSION_LAST_SEEN])

    def test_second_prepare_is_closed_on_nonempty_database(self):
        self.make()
        with self.assertRaisesRegex(RuntimeError, "T10_FIXTURE_DATABASE_NOT_EMPTY"):
            self.make()

    @override_settings(ENVIRONMENT="test")
    def test_management_command_writes_private_file_once_and_safe_stdout(self):
        summary = {"schema": "test10a-fixture-v1", "fixtureHash": "a" * 64,
                   "containsSecrets": False}
        private = {"schema": "test10a-fixture-v1", "passwords": {"OWNER": "secret"}}
        with TemporaryDirectory() as root, \
             patch.object(fixture_command, "PRIVATE_ROOT", Path(root)), \
             patch.object(fixture_command, "prepare", return_value=(summary, private)) as writer, \
             patch.dict(os.environ, {"TEST10_FIXTURE_ADMISSION": "D-1040"}, clear=False):
            output = StringIO()
            call_command("test10_fixture", prepare=True, stdout=output)
            path = Path(root) / "actors.json"
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), private)
            self.assertNotIn("secret", output.getvalue())
            self.assertEqual(json.loads(output.getvalue()), summary)
            with self.assertRaisesRegex(CommandError, "T10_FIXTURE_PRIVATE_FILE_EXISTS"):
                call_command("test10_fixture", prepare=True, stdout=StringIO())
            self.assertEqual(writer.call_count, 1)

    @override_settings(ENVIRONMENT="test")
    def test_management_failure_before_prepare_leaves_no_private_file(self):
        with TemporaryDirectory() as root, \
             patch.object(fixture_command, "PRIVATE_ROOT", Path(root)), \
             patch.object(fixture_command, "prepare", side_effect=RuntimeError("synthetic")), \
             patch.dict(os.environ, {"TEST10_FIXTURE_ADMISSION": "D-1040"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                call_command("test10_fixture", prepare=True, stdout=StringIO())
            self.assertFalse((Path(root) / "actors.json").exists())

    @patch("page_editor.test10_database.connection")
    def test_database_collision_and_marker_mismatch_never_drop(self, connect):
        existing = MagicMock()
        existing.__enter__.return_value = existing
        existing.execute.return_value.fetchone.return_value = (1,)
        connect.side_effect = [existing]
        with self.assertRaisesRegex(RuntimeError, "T10_DATABASE_ALREADY_EXISTS"):
            prepare_database("a" * 32, "b" * 64, "c" * 64)
        self.assertFalse(any("DROP DATABASE" in str(call) for call in existing.execute.call_args_list))

        owner = MagicMock()
        owner.__enter__.return_value = owner
        owner.execute.return_value.fetchone.return_value = ("app_migrator",)
        marker = MagicMock()
        marker.__enter__.return_value = marker
        marker.execute.return_value.fetchone.return_value = (
            "a" * 32, "estakada_test10_" + "a" * 32, "b" * 64, "wrong")
        connect.side_effect = [owner, marker]
        with self.assertRaisesRegex(RuntimeError, "T10_DATABASE_MARKER_MISMATCH"):
            teardown_database("a" * 32, "b" * 64, "c" * 64)
        calls = owner.execute.call_args_list + marker.execute.call_args_list
        self.assertFalse(any("DROP DATABASE" in str(call) for call in calls))

    @patch("page_editor.test10_database.connection")
    def test_database_exact_marker_is_required_before_drop(self, connect):
        expected = ("a" * 32, "estakada_test10_" + "a" * 32,
                    "b" * 64, "c" * 64)
        owner = MagicMock(); owner.__enter__.return_value = owner
        owner.execute.return_value.fetchone.return_value = ("app_migrator",)
        marker = MagicMock(); marker.__enter__.return_value = marker
        marker.execute.return_value.fetchone.return_value = expected
        drop = MagicMock(); drop.__enter__.return_value = drop
        connect.side_effect = [owner, marker, drop]
        self.assertEqual(teardown_database(*("a" * 32, "b" * 64, "c" * 64)),
                         "estakada_test10_" + "a" * 32)
        self.assertTrue(any("DROP DATABASE" in str(call)
                            for call in drop.execute.call_args_list))
