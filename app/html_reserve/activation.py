"""Authoritative activation of an already immutable reserve generation."""
from dataclasses import dataclass

from django.db import transaction

from content.models import lock_content
from media_library import services as media_services

from .contracts import ContractError, active_pointer
from .source import capture


@dataclass(frozen=True)
class ActivationResult:
    generation_id: str
    status: str
    durability_warning: bool
    cleanup_warning: bool


def _pointer_for(previous, generation_id, manifest_sha256):
    return active_pointer(
        generation_id, previous['current'], manifest_sha256,
        previous['current_manifest_sha256'])


def activate_prebuilt(*, store, generation_id, manifest_sha256,
                      source_snapshot, recapture=capture, fault=None):
    """Activate once while the caller holds the ReserveStore filesystem lock."""
    previous = store.read_pointer()
    if generation_id in (previous['current'], previous['previous']):
        raise ContractError('HTML_RESERVE_GENERATION_ALREADY_ACTIVE')
    manifest = store.generation_manifest(generation_id, manifest_sha256)
    if manifest['source_stamp'] != source_snapshot.stamp:
        raise ContractError('HTML_RESERVE_MANIFEST_SOURCE_MISMATCH')
    retained = manifest['retained_asset_ids']
    media_services.set_retained_html(
        generation_id=generation_id, asset_ids=retained)
    if fault is not None:
        fault('after_retained_commit')
    wanted = _pointer_for(previous, generation_id, manifest_sha256)
    durability_warning = False
    try:
        with transaction.atomic():
            lock_content('default')
            source_b = recapture()
            if source_b.stamp != source_snapshot.stamp:
                raise ContractError('HTML_RESERVE_SOURCE_CHANGED')
            if store.read_pointer() != previous:
                raise ContractError('HTML_RESERVE_POINTER_CHANGED')
            store.write_pointer(wanted, generation_id)
    except ContractError:
        raise
    except BaseException as error:
        try:
            observed = store.read_pointer()
        except BaseException:
            raise ContractError('HTML_RESERVE_ACTIVATION_RESULT_UNKNOWN') from error
        if observed != wanted:
            raise ContractError('HTML_RESERVE_PRE_ACTIVATION_FAILED') from error
        durability_warning = True

    cleanup_warning = False
    try:
        store.reconcile_orphans()
        media_services.reconcile_retained_html(
            active_generation_ids=[value for value in (
                wanted['current'], wanted['previous']) if value is not None])
    except BaseException:
        cleanup_warning = True
    return ActivationResult(
        generation_id=generation_id, status='activated',
        durability_warning=durability_warning,
        cleanup_warning=cleanup_warning)
