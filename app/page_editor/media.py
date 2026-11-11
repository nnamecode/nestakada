"""External ImageRef evidence and membership; embedded integration stays closed."""
from dataclasses import dataclass
from urllib.parse import urlencode
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from page_versions import engine as E
from page_versions.models import RestoreStage, RevisionProtection, PageRevision
from media_library.models import Asset, AssetFile, AssetUsage
from media_library.storage import MediaStorage
from .checks import CheckFault, _inspect_context_locked
from .input_policy import fingerprint

FIELDS = ('main_image', 'preview_image')


@dataclass(frozen=True)
class ImageEvidence:
    payload: dict
    files: dict
    proof: str


def external_payload(payload, changes=None, derived=None):
    changes = {} if changes is None else changes
    return {**{field: changes.get(field, payload[field]) for field in FIELDS},
            'embedded_images': payload['embedded_images'] if derived is None else derived['embedded_images']}


def derivatives(asset_id):
    asset = Asset.objects.get(pk=asset_id, status=Asset.Status.READY)
    result = {}
    for kind in (AssetFile.Kind.MAIN, AssetFile.Kind.PREVIEW):
        rows = list(asset.files.filter(kind=kind))
        if len(rows) != 1:
            raise CheckFault('EDITOR_MEDIA_UNAVAILABLE')
        result[kind] = rows[0]
    return result


def file_facts(file):
    return (str(file.pk), str(file.asset_id), file.kind, file.key, file.sha256, file.byte_size)


def open_derivative(file):
    if file.kind not in (AssetFile.Kind.MAIN, AssetFile.Kind.PREVIEW):
        raise CheckFault('EDITOR_MEDIA_UNAVAILABLE')
    source = None
    try:
        source = MediaStorage().open_verified(file.key, {'sha256': file.sha256, 'byte_size': file.byte_size})
        header = source.read(12)
        source.seek(0)
        if header[:4] != b'RIFF' or header[8:12] != b'WEBP':
            raise CheckFault('EDITOR_MEDIA_UNAVAILABLE')
        return source
    except BaseException:
        if source is not None:
            source.close()
        raise


def prepare(context, changes, *, derived=None):
    """Actual FS work only outside domain transactions, inside caller's Slot."""
    E.outside()
    payload = external_payload(context.payload, changes, derived)
    if not payload['embedded_images'] and not any(payload[field] is not None for field in FIELDS) and not any(field in changes for field in FIELDS):
        return None
    try:
        evidence = E.preflight(payload)
        # MAIN/PREVIEW are an editor-preview contract, not a requirement for
        # every immutable image already embedded in a page.  In particular,
        # migrated gallery photographs legitimately have one LEGACY_PUBLIC
        # file.  The version engine still verifies every referenced file
        # above; require preview derivatives only for external slots and for
        # embedded references that this edit actually introduces/replaces.
        derivative_assets = {
            payload[field]['asset_id'] for field in FIELDS
            if payload[field] is not None
        }
        if derived is not None:
            original = {row['id']: row['asset_id']
                        for row in context.payload['embedded_images']}
            derivative_assets.update(
                row['asset_id'] for row in payload['embedded_images']
                if original.get(row['id']) != row['asset_id'])
        for asset_id in sorted(derivative_assets):
            for file in derivatives(asset_id).values():
                with open_derivative(file):
                    pass
        refs = {field: payload[field] for field in FIELDS}
        if payload['embedded_images']:
            refs['embedded_images'] = payload['embedded_images']
        return ImageEvidence(payload, evidence, fingerprint({'references': refs, 'files': evidence}))
    except (ObjectDoesNotExist, OSError, ValidationError, ValueError, TypeError):
        raise CheckFault('EDITOR_MEDIA_UNAVAILABLE') from None


def late_context(*, actor, page_id, generation, session_key, origin, before, evidence):
    """Fresh source/session/descriptor check in one final short transaction."""
    try:
        with transaction.atomic():
            after = _inspect_context_locked(actor=actor, page_id=page_id, generation=generation,
                origin=origin, selector=before.child['source'])
            E.check_editor_session(actor, generation, session_key)
            if before.stamp != after.stamp:
                raise CheckFault('EDITOR_CONTEXT_CHANGED')
            if evidence is not None:
                E.check_evidence(evidence.payload, evidence.files)
            return after
    except ValidationError as exc:
        if 'EDITOR_SESSION_ENDED' in str(exc):
            raise CheckFault('EDITOR_SESSION_ENDED') from None
        raise CheckFault('EDITOR_MEDIA_UNAVAILABLE') from None
    except (ObjectDoesNotExist, OSError):
        raise CheckFault('EDITOR_MEDIA_UNAVAILABLE') from None


def source_query(source):
    if source['editingFrom'] == 'owner-draft':
        query = {'source': 'owner-draft', 'draftId': source['draftBasis']['id'],
                 'draftRevision': source['draftBasis']['revision']}
        if source['rebase']:
            query.update(rebase='1', targetCurrentId=source['targetCurrentId'])
    elif source['editingFrom'] == 'restore-stage':
        query = {'source': 'restore-stage', 'stageId': source['stageId']}
    else:
        return ''
    return '?' + urlencode(query)


def initial_media(context):
    prefix = f"/manage/pages/{context.child['page_id']}/edit/media/files/"
    query = source_query(context.child['source'])
    result = {}
    for field in FIELDS:
        ref = context.payload[field]
        if ref is None:
            result[field] = None
            continue
        url = thumbnail = None
        try:
            files = derivatives(ref['asset_id'])
            chosen = files['main' if field == 'main_image' else 'preview']
            url, thumbnail = prefix + str(chosen.pk) + '/' + query, prefix + str(files['preview'].pk) + '/' + query
        except (ObjectDoesNotExist, CheckFault):
            pass
        result[field] = {'reference': ref, 'url': url, 'thumbnailUrl': thumbnail}
    return result


def member(context, file):
    """Candidate membership AND actual external slot ledger, never UUID alone."""
    slots = [field for field in FIELDS if context.payload[field] is not None
             and context.payload[field]['asset_id'] == str(file.asset_id)]
    embedded = {image['id']: image for image in context.payload['embedded_images']}
    for node in context.payload['layout']:
        if node['kind'] == 'text':
            for protected in node['protected_nodes']:
                image = embedded.get(protected['reference_id'])
                if image is not None and image['asset_id'] == str(file.asset_id):
                    slots.append('embedded:' + image['id'])
    if not slots:
        return False
    source = context.child['source']
    mode = source['editingFrom']
    if mode == 'current':
        kind, consumer = 'current_page', context.child['page_id']
    elif mode == 'owner-draft':
        if not context.child['owner']:
            return False
        kind, consumer = 'draft', source['draftBasis']['id']
    else:
        stage = RestoreStage.objects.get(pk=E.uid(source['stageId']), page_id=context.child['page_id'],
            actor_id=context.actor_id, status='held')
        revision_id = stage.source_revision_id if context.child['owner'] else stage.base_revision_id
        if not PageRevision.objects.filter(pk=revision_id, page_id=context.child['page_id']).exists():
            return False
        kind = 'stable_version' if RevisionProtection.objects.filter(revision_id=revision_id).exists() else 'ordinary_version'
        consumer = revision_id
    return AssetUsage.objects.filter(kind=kind, consumer_id=consumer, slot__in=slots, asset_id=file.asset_id).exists()
