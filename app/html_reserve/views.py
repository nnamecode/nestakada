import os
from pathlib import Path
import stat
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from accounts.services import is_owner
from accounts.views import fields, gate
from audit.constants import Category, Level, Result, Source
from audit.services import record_event

from .build import run as build_run
from .contracts import ContractError
from .source import capture
from .storage import ReserveStore


def _root():
    value = settings.HTML_RESERVE_ROOT
    if type(value) is not str or not value:
        raise ContractError('HTML_RESERVE_ROOT_UNAVAILABLE')
    root = Path(value)
    if not root.is_absolute() or root.parent == root:
        raise ContractError('HTML_RESERVE_ROOT_UNSAFE')
    try:
        info = os.lstat(root)
        resolved = root.resolve(strict=True)
    except OSError:
        raise ContractError('HTML_RESERVE_ROOT_UNAVAILABLE') from None
    if (not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700
            or info.st_uid != os.geteuid() or resolved != root):
        raise ContractError('HTML_RESERVE_ROOT_UNSAFE')
    protected = (
        Path(settings.BASE_DIR), Path(settings.MEDIA_ROOT), Path(settings.STATIC_ROOT),
        Path(settings.SERVICE_REQUEST_DELETION_LEDGER_ROOT),
    )
    for candidate in protected:
        try:
            candidate = candidate.resolve(strict=False)
            if root == candidate or root in candidate.parents or candidate in root.parents:
                raise ContractError('HTML_RESERVE_ROOT_OVERLAP')
        except OSError:
            raise ContractError('HTML_RESERVE_ROOT_UNSAFE') from None
    return root


def _audit(code, request, *, result, generation=None, level=Level.INFO):
    return record_event(
        category=Category.BACKUP_MAINTENANCE, event_code=code,
        level=level, source=Source.HTML_RESERVE, result=result,
        actor_id=request.user.pk,
        object_kind='html_generation' if generation else '',
        object_ref=UUID(generation) if generation else None)


def _status(root):
    if not (root / 'active.json').exists():
        entries = {entry.name: entry for entry in os.scandir(root)}
        if set(entries).issubset({'build.lock', 'staging', 'generations'}):
            for name, entry in entries.items():
                info = entry.stat(follow_symlinks=False)
                if entry.is_symlink():
                    raise ContractError('HTML_RESERVE_STATUS_UNSAFE')
                if name == 'build.lock':
                    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size:
                        raise ContractError('HTML_RESERVE_STATUS_UNSAFE')
                elif (not stat.S_ISDIR(info.st_mode)
                      or stat.S_IMODE(info.st_mode) != 0o700
                      or any(os.scandir(entry.path))):
                    raise ContractError('HTML_RESERVE_STATUS_UNSAFE')
            return {
                'available': True, 'current': None, 'previous': None,
                'stale': True,
            }
        raise ContractError('HTML_RESERVE_STATUS_UNAVAILABLE')
    with ReserveStore(root).locked() as locked:
        pointer = locked.read_pointer()
        if pointer['current'] is None:
            return {
                'available': True, 'current': None, 'previous': None,
                'stale': True,
            }
        manifest = locked.generation_manifest(
            pointer['current'], pointer['current_manifest_sha256'])
    live = capture()
    return {
        'available': True, 'current': pointer['current'],
        'previous': pointer['previous'],
        'built_at': manifest['built_at'],
        'stale': manifest['source_stamp'] != live.stamp,
        'warning': False,
    }


@require_http_methods(['GET', 'POST'])
@gate(owner=True)
def reserve(request):
    assert is_owner(request.user)
    message = warning = None
    try:
        root = _root()
    except ContractError:
        return render(request, 'accounts/html_reserve.html', {
            'owner': True, 'status': {'available': False},
            'message': 'HTML-резерв пока недоступен.'}, status=503)
    if request.method == 'POST':
        try:
            data = fields(request, ['action'])
            if data.get('action') != 'build':
                raise ValidationError('HTML_RESERVE_ACTION_INVALID')
        except ValidationError:
            return render(request, 'accounts/html_reserve.html', {
                'owner': True, 'status': {'available': False},
                'message': 'Некорректная команда.'}, status=400)
        try:
            _audit('HTML_RESERVE_BUILD_STARTED', request, result=Result.PENDING)
        except (DatabaseError, ValidationError):
            return render(request, 'accounts/html_reserve.html', {
                'owner': True, 'status': {'available': False},
                'message': 'Сборка не началась.'}, status=503)
        try:
            result = build_run(root=root)
            message = 'Новая HTML-версия создана и активирована.'
            warning = result.durability_warning or result.cleanup_warning
            try:
                _audit('HTML_RESERVE_BUILD_SUCCEEDED', request,
                       result=Result.SUCCESS, generation=result.generation_id)
                if result.cleanup_warning:
                    _audit('HTML_RESERVE_RECONCILE_WARNING', request,
                           result=Result.FAILURE, generation=result.generation_id,
                           level=Level.WARNING)
            except (DatabaseError, ValidationError):
                warning = True
        except ContractError as error:
            code = str(error)
            audit_result = (Result.UNKNOWN if code == 'HTML_RESERVE_ACTIVATION_RESULT_UNKNOWN'
                            else Result.FAILURE)
            try:
                _audit('HTML_RESERVE_BUILD_BUSY' if code == 'HTML_RESERVE_BUILD_BUSY'
                       else 'HTML_RESERVE_BUILD_FAILED', request,
                       result=audit_result, level=Level.WARNING)
            except (DatabaseError, ValidationError):
                pass
            message = ('Сборка уже выполняется.' if code == 'HTML_RESERVE_BUILD_BUSY'
                       else 'Не удалось создать HTML-версию.')
        except (DatabaseError, OSError, ValidationError):
            try:
                _audit('HTML_RESERVE_BUILD_FAILED', request,
                       result=Result.FAILURE, level=Level.ERROR)
            except (DatabaseError, ValidationError):
                pass
            message = 'Не удалось создать HTML-версию.'
    try:
        status = _status(root)
    except (ContractError, DatabaseError, OSError, ValidationError):
        status = {'available': False}
    return render(request, 'accounts/html_reserve.html', {
        'owner': True, 'status': status, 'message': message,
        'warning': warning})
