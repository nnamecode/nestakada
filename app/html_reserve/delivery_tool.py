"""Closed one-shot CLI for HTML reserve delivery operations."""
import os
from pathlib import Path
import sys

from .contracts import ContractError, canonical_bytes
from .delivery import (
    DeliveryStore, _canonical_json, _validate_journal, project_current,
    selector_from_record, selector_record, verify_active,
)


SOURCE_ROOT = Path('/var/lib/estakada-html-reserve')
DELIVERY_ROOT = Path('/var/lib/estakada-html-reserve-delivery')
MAX_INPUT_BYTES = 64 * 1024
MODES = frozenset((
    'project', 'verify-active', 'journal-transition', 'selector-replace',
    'recover-transition'))
_RECOVERY_STAGES = frozenset((
    'ROLLBACK_REQUIRED', 'ROLLBACK_SELECTOR', 'ROLLBACK_HUP_INTENT',
    'ROLLED_BACK', 'SUCCESS_RECEIPT_WARNING', 'COMPLETE', 'UNKNOWN'))


def _exact(value, keys, code='HTML_RESERVE_TOOL_INPUT_INVALID'):
    if type(value) is not dict or set(value) != set(keys):
        raise ContractError(code)
    return value


def _assert_mount(path, *, exact, read_only):
    path = Path(path)
    if path != exact or not path.is_absolute() or path.is_symlink():
        raise ContractError('HTML_RESERVE_TOOL_MOUNT_INVALID')
    try:
        info = path.stat()
        flags = os.statvfs(path).f_flag
    except OSError:
        raise ContractError('HTML_RESERVE_TOOL_MOUNT_INVALID') from None
    if not path.is_dir() or (info.st_mode & 0o777) != 0o700:
        raise ContractError('HTML_RESERVE_TOOL_MOUNT_INVALID')
    actual_read_only = bool(flags & os.ST_RDONLY)
    if actual_read_only != read_only:
        raise ContractError('HTML_RESERVE_TOOL_MOUNT_ROLE_INVALID')


def dispatch(mode, payload, *, source_root=SOURCE_ROOT,
             delivery_root=DELIVERY_ROOT):
    """Dispatch an already mount-validated, canonical request."""
    if mode == 'project':
        _exact(payload, {'delivery'})
        return project_current(
            source_root=source_root, delivery_root=delivery_root,
            delivery=payload['delivery'])
    if mode == 'verify-active':
        _exact(payload, set())
        return verify_active(delivery_root)
    if mode == 'selector-replace':
        _exact(payload, {'expected', 'new'})
        expected = selector_from_record(payload['expected'])
        new = selector_from_record(payload['new'])
        with DeliveryStore(delivery_root).locked() as locked:
            locked.replace_selector(expected=expected, new=new)
            return {'selector': selector_record(locked.read_selector())}
    if mode in {'journal-transition', 'recover-transition'}:
        _exact(payload, {'expected_sha256', 'journal'})
        journal = _validate_journal(payload['journal'])
        if (mode == 'journal-transition'
                and journal['stage'] in _RECOVERY_STAGES
                or mode == 'recover-transition'
                and journal['stage'] not in _RECOVERY_STAGES):
            raise ContractError('HTML_RESERVE_TOOL_MODE_STAGE_INVALID')
        with DeliveryStore(delivery_root).locked() as locked:
            digest = locked.transition_journal(
                expected_sha256=payload['expected_sha256'], new=journal)
            return {'journal_sha256': digest, 'stage': journal['stage']}
    raise ContractError('HTML_RESERVE_TOOL_MODE_INVALID')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in MODES:
        raise ContractError('HTML_RESERVE_TOOL_MODE_INVALID')
    mode = argv[0]
    if mode == 'project':
        _assert_mount(SOURCE_ROOT, exact=SOURCE_ROOT, read_only=True)
        _assert_mount(DELIVERY_ROOT, exact=DELIVERY_ROOT, read_only=False)
    elif mode == 'verify-active':
        _assert_mount(DELIVERY_ROOT, exact=DELIVERY_ROOT, read_only=True)
    else:
        _assert_mount(DELIVERY_ROOT, exact=DELIVERY_ROOT, read_only=False)
    body = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    payload = _canonical_json(
        body, max_bytes=MAX_INPUT_BYTES,
        code='HTML_RESERVE_TOOL_INPUT_INVALID')
    result = dispatch(mode, payload)
    sys.stdout.buffer.write(canonical_bytes(result, max_bytes=MAX_INPUT_BYTES))
    sys.stdout.buffer.write(b'\n')


if __name__ == '__main__':
    try:
        main()
    except ContractError as error:
        sys.stderr.write(str(error) + '\n')
        raise SystemExit(2) from None
