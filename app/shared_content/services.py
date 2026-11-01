"""Fresh owner context, actual media evidence and signed shared Check proof."""
from dataclasses import dataclass, replace
import hashlib
import json
from uuid import UUID

from django.core import signing
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db import connection, transaction

from accounts.models import UserProfile
from accounts.services import lock_auth
from content.models import lock_content
from media_library.models import Asset, AssetFile
from media_library.storage import MediaStorage
from .models import SharedBlock, SharedRevision, SharedDraft, SharedRestoreStage, SharedBasePin
from .faults import SharedFault
from .policy import POLICY, PROTOCOL, canonical_uuid
from .content import descriptor_for, content_html

SALT = 'estakada.shared.check.v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def owner_locked(actor, generation):
    lock_content('default'); lock_auth()
    profile = UserProfile.objects.select_related('user').filter(user_id=actor.pk, user__is_active=True).first()
    if (profile is None or type(generation) is not int or profile.generation != generation
            or profile.role != 'owner' or profile.user.username != 'nesadmin'):
        raise PermissionDenied('SHARED_OWNER_REQUIRED')
    return profile


@dataclass(frozen=True)
class SharedAdmission:
    block_id: str
    kind: str
    generation: int


def admission_locked(*, actor, kind, generation):
    if kind not in ('header', 'footer'):
        raise ObjectDoesNotExist()
    owner_locked(actor, generation)
    block = SharedBlock.objects.select_for_update().only('id', 'kind').get(kind=kind)
    return SharedAdmission(str(block.pk), kind, generation)


def inspect_admission(**kwargs):
    with transaction.atomic():
        return admission_locked(**kwargs)


@dataclass(frozen=True)
class SharedContext:
    actor_id: int
    block_id: str
    kind: str
    generation: int
    current_id: str | None
    source_html: str
    stamp: str
    child: dict
    source_descriptor: dict | None = None


def context_locked(*, actor, kind, generation, source_mode='current', draft_basis=None, stage_id=None):
    if kind not in ('header', 'footer'):
        raise ObjectDoesNotExist()
    owner_locked(actor, generation)
    block = SharedBlock.objects.select_for_update(of=('self',)).select_related('current_revision').get(kind=kind)
    base_id = str(block.current_revision_id) if block.current_revision_id else None
    descriptor = descriptor_for(block.current_revision) if block.current_revision else None
    selected_hash = block.current_revision.payload_hash if block.current_revision else ''
    if source_mode == 'current':
        if draft_basis is not None or stage_id is not None:
            raise SharedFault('SHARED_INPUT_REJECTED', 400)
    elif source_mode == 'owner-draft':
        if (type(draft_basis) is not dict or set(draft_basis) != {'id', 'revision'}
                or stage_id is not None or type(draft_basis['revision']) is not int):
            raise SharedFault('SHARED_INPUT_REJECTED', 400)
        draft = SharedDraft.objects.filter(block=block, pk=UUID(canonical_uuid(draft_basis['id'])),
                                           revision=draft_basis['revision']).first()
        if draft is None:
            raise SharedFault('SHARED_SOURCE_UNAVAILABLE')
        base_id = str(draft.base_revision_id) if draft.base_revision_id else None
        descriptor, selected_hash = descriptor_for(draft), draft.payload_hash
    elif source_mode == 'restore-stage':
        if draft_basis is not None:
            raise SharedFault('SHARED_INPUT_REJECTED', 400)
        stage = SharedRestoreStage.objects.select_related('source_revision').filter(
            pk=UUID(canonical_uuid(stage_id)), block=block, actor_id=actor.pk,
            actor_generation=generation, status='held', policy_version=POLICY,
            schema_version=kind + '-v1').first()
        if stage is None:
            raise SharedFault('SHARED_SOURCE_UNAVAILABLE')
        base_id = str(stage.base_revision_id) if stage.base_revision_id else None
        descriptor, selected_hash = descriptor_for(stage.source_revision), stage.source_revision.payload_hash
    else:
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    child = {'processor': PROTOCOL, 'kind': kind, 'generation': generation,
             'baseRevisionId': base_id, 'sourceMode': source_mode, 'draftBasis': draft_basis,
             'stageId': stage_id, 'policy': POLICY}
    stamp = digest({'block': str(block.pk), 'generation': block.generation, 'current':
        str(block.current_revision_id) if block.current_revision_id else None,
        'actor': actor.pk, 'context': child, 'sourceHash': selected_hash, 'sourceDescriptor': descriptor})
    return SharedContext(actor.pk, str(block.pk), kind, generation,
        str(block.current_revision_id) if block.current_revision_id else None, '', stamp, child, descriptor)


def cancel_context_locked(*, actor, kind, generation, stage_id):
    admission = admission_locked(actor=actor, kind=kind, generation=generation)
    stage = SharedRestoreStage.objects.select_for_update().filter(pk=UUID(canonical_uuid(str(stage_id))),
        block_id=admission.block_id, actor_id=actor.pk, actor_generation=generation, status='held',
        terminal_operation_id__isnull=True, terminal_actor_id__isnull=True).first()
    if stage is None:
        raise SharedFault('SHARED_SOURCE_UNAVAILABLE')
    expected = {stage.source_revision_id, stage.base_revision_id} - {None}
    pins = list(SharedBasePin.objects.filter(holder_id=stage.pk)
                .order_by('id').values_list('id', 'revision_id', 'holder_kind'))
    if (len(pins) != len(expected) or {row[1] for row in pins} != expected
            or any(row[2] != 'restore_stage' for row in pins)):
        raise SharedFault('SHARED_SOURCE_UNAVAILABLE')
    child = {'processor': PROTOCOL, 'kind': kind, 'generation': generation,
        'baseRevisionId': str(stage.base_revision_id) if stage.base_revision_id else None,
        'sourceMode': 'restore-stage', 'draftBasis': None, 'stageId': str(stage.pk), 'policy': POLICY}
    stamp = digest({'action': 'restore_cancel', 'stage': str(stage.pk), 'block': admission.block_id,
        'actor': actor.pk, 'generation': generation, 'source': str(stage.source_revision_id),
        'base': child['baseRevisionId'], 'status': stage.status, 'schema': stage.schema_version,
        'policy': stage.policy_version, 'terminalOperation': None, 'terminalActor': None,
        'pins': [[str(identity), str(revision), holder] for identity, revision, holder in pins]})
    block = SharedBlock.objects.only('current_revision_id').get(pk=admission.block_id)
    return SharedContext(actor.pk, admission.block_id, kind, generation,
        str(block.current_revision_id) if block.current_revision_id else None, '', stamp, child)


def inspect_cancel_context(**kwargs):
    if connection.in_atomic_block:
        raise SharedFault('SHARED_CALL_FROM_AUTOCOMMIT', 503)
    with transaction.atomic():
        return cancel_context_locked(**kwargs)


def inspect_context(**kwargs):
    if connection.in_atomic_block:
        raise SharedFault('SHARED_CALL_FROM_AUTOCOMMIT', 503)
    with transaction.atomic():
        context = context_locked(**kwargs)
    # Immutable source bytes are resolved only after content/auth locks are released.
    return replace(context, source_html=content_html(context.source_descriptor)
                   if context.source_descriptor is not None else '')


def asset_evidence(bindings, *, physical=True):
    if type(bindings) is not list or len(bindings) > 4:
        raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
    facts = []
    seen_slots = set()
    for binding in bindings:
        if type(binding) is not dict or set(binding) != {'assetId', 'slot'} or binding['slot'] in seen_slots:
            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
        seen_slots.add(binding['slot'])
        asset = Asset.objects.filter(pk=UUID(canonical_uuid(binding['assetId'])), status=Asset.Status.READY).first()
        if asset is None:
            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
        rows = list(AssetFile.objects.filter(asset=asset, kind__in=[AssetFile.Kind.MAIN, AssetFile.Kind.PREVIEW]).order_by('kind'))
        if len(rows) != 2 or {row.kind for row in rows} != {AssetFile.Kind.MAIN, AssetFile.Kind.PREVIEW}:
            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
        files = []
        for row in rows:
            if physical:
                try:
                    with MediaStorage().open_verified(row.key, {'sha256': row.sha256, 'byte_size': row.byte_size}) as stream:
                        header = stream.read(12)
                        if header[:4] != b'RIFF' or header[8:12] != b'WEBP':
                            raise SharedFault('SHARED_MEDIA_UNAVAILABLE')
                except OSError:
                    raise SharedFault('SHARED_MEDIA_UNAVAILABLE') from None
            files.append([str(row.pk), row.kind, row.key, row.sha256, row.byte_size])
        facts.append({'slot': binding['slot'], 'asset': str(asset.pk), 'files': files})
    return digest(facts)


def validate_result(result, raw):
    if (type(result) is not dict or set(result) != {'html', 'bindings', 'schemaVersion', 'payloadHash', 'inputFingerprint', 'changed'}
            or result['inputFingerprint'] != hashlib.sha256(raw).hexdigest()
            or type(result['html']) is not str or len(result['html'].encode()) > 1048576
            or result['payloadHash'] != hashlib.sha256(result['html'].encode()).hexdigest()
            or type(result['changed']) is not bool):
        raise SharedFault('SHARED_WORKER_PROTOCOL', 503)
    return result


def proof_payload(context, result, media_stamp):
    return {'protocol': 'shared-editor-check-v1', 'policy': POLICY, 'actor': context.actor_id,
        'generation': context.generation, 'block': context.block_id, 'kind': context.kind,
        'contextStamp': context.stamp, 'schemaVersion': result['schemaVersion'],
        'htmlHash': result['payloadHash'], 'mediaStamp': media_stamp}


def issue_proof(context, result, media_stamp):
    return signing.dumps(proof_payload(context, result, media_stamp), salt=SALT, compress=False)


def verify_proof(token, context, result, media_stamp):
    if type(token) is not str or len(token) > 16384:
        raise SharedFault('SHARED_CHECK_RECEIPT_INVALID')
    try:
        value = signing.loads(token, salt=SALT)
    except signing.BadSignature:
        raise SharedFault('SHARED_CHECK_RECEIPT_INVALID') from None
    if value != proof_payload(context, result, media_stamp):
        raise SharedFault('SHARED_CHECK_RECEIPT_INVALID')
    return value


def history(*, actor, kind, generation, page=1):
    if type(page) is not int or not 1 <= page <= 1000000:
        raise SharedFault('SHARED_INPUT_REJECTED', 400)
    with transaction.atomic():
        context = context_locked(actor=actor, kind=kind, generation=generation)
        rows = list(SharedRevision.objects.filter(block_id=context.block_id).order_by('-sequence')
            .values('id', 'sequence', 'schema_version', 'payload_hash', 'author_id', 'created_at')[(page-1)*50:page*50])
    context = replace(context, source_html=content_html(context.source_descriptor)
                      if context.source_descriptor is not None else '')
    return {'context': context, 'rows': rows, 'page': page}
