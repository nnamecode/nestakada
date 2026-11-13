import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.test import SimpleTestCase

from .contracts import ContractError
from .delivery import (
    ABSENT, DeliveryStore, activation_journal, present_selector,
    selector_bytes, selector_record, verify_active,
)
from .delivery_tool import _assert_mount, dispatch


class DeliveryToolTests(SimpleTestCase):
    def root(self, parent):
        root = Path(parent) / 'delivery'
        root.mkdir(mode=0o700, parents=True)
        return root

    def active(self, root):
        delivery = str(uuid4())
        with DeliveryStore(root).locked() as locked:
            digest = locked.write_release(
                delivery=delivery, source_generation=str(uuid4()),
                source_manifest_sha256='a' * 64, maps=b'maps',
                files={'responses/' + 'b' * 64 + '.html': b'body'})
            selected = present_selector(selector_bytes(delivery, digest))
            locked.replace_selector(expected=ABSENT, new=selected)
        return delivery, digest, selected

    def test_verify_active_accepts_only_empty_or_fully_hashed_active(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            self.assertEqual(verify_active(root), {'state': 'EMPTY'})
            delivery, digest, _selected = self.active(root)
            result = verify_active(root)
            self.assertEqual(result['state'], 'ACTIVE')
            self.assertEqual(result['delivery'], delivery)
            self.assertEqual(result['release_sha256'], digest)
            response = root / 'releases' / delivery / 'responses' / (
                'b' * 64 + '.html')
            response.write_bytes(b'tampered')
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_FILE_MISMATCH'):
                verify_active(root)

    def test_verify_empty_rejects_orphan_release_and_unfinished_journal(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            delivery = str(uuid4())
            with DeliveryStore(root).locked() as locked:
                locked.write_release(
                    delivery=delivery, source_generation=str(uuid4()),
                    source_manifest_sha256='a' * 64, maps=b'maps', files={})
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_DELIVERY_EMPTY_INVALID'):
                verify_active(root)
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            _delivery, _digest, selected = self.active(root)
            prepared = activation_journal(
                operation=str(uuid4()), sequence=0, stage='PREPARED',
                old_selector=ABSENT, new_selector=selected,
                previous_sha256=None)
            with DeliveryStore(root).locked() as locked:
                locked.transition_journal(
                    expected_sha256=None, new=prepared)
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_JOURNAL_UNFINISHED'):
                verify_active(root)

    def test_dispatch_has_closed_selector_and_journal_modes(self):
        with TemporaryDirectory() as parent:
            root = self.root(parent)
            delivery = str(uuid4())
            selected = present_selector(selector_bytes(delivery, 'a' * 64))
            result = dispatch(
                'selector-replace', {
                    'expected': selector_record(ABSENT),
                    'new': selector_record(selected)},
                delivery_root=root)
            self.assertEqual(result, {'selector': selector_record(selected)})
            prepared = activation_journal(
                operation=str(uuid4()), sequence=0, stage='PREPARED',
                old_selector=ABSENT, new_selector=selected,
                previous_sha256=None)
            result = dispatch(
                'journal-transition', {
                    'expected_sha256': None, 'journal': prepared},
                delivery_root=root)
            self.assertEqual(result['stage'], 'PREPARED')
            self.assertEqual(
                len(result['journal_sha256']), hashlib.sha256().digest_size * 2)
            with self.assertRaisesRegex(
                    ContractError, 'HTML_RESERVE_TOOL_INPUT_INVALID'):
                dispatch(
                    'verify-active', {'extra': True}, delivery_root=root)

    def test_mount_assertion_rejects_noncanonical_path_before_role_use(self):
        with TemporaryDirectory() as parent, self.assertRaisesRegex(
                ContractError, 'HTML_RESERVE_TOOL_MOUNT_INVALID'):
            _assert_mount(
                Path(parent), exact=Path('/delivery'), read_only=False)
