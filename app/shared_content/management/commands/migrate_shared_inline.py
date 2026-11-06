"""Verified, resumable legacy shared-content migration; never deletes blobs."""
import hashlib
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from audit.constants import Category, Level, Result, Source
from audit.services import record_event
from content.models import lock_content
from shared_content.content import content_html, descriptor_for
from shared_content.models import (SharedBasePin, SharedCleanupJob, SharedDraft,
                                   SharedRestoreStage, SharedRevision)


def raw(model):
    return models.QuerySet(model=model, using='default')


def blockers():
    return {
        'heldStages': SharedRestoreStage.objects.filter(status='held').count(),
        'pins': SharedBasePin.objects.count(),
        'pendingCleanup': SharedCleanupJob.objects.exclude(phase='complete').count(),
    }


def candidates():
    rows = []
    for model, label in ((SharedRevision, 'revision'), (SharedDraft, 'draft')):
        for row in model.objects.filter(storage_kind='file').order_by('pk'):
            rows.append((model, label, row.pk, descriptor_for(row)))
    return rows


def migrate_one(model, identity, descriptor):
    html = content_html(descriptor)
    payload_hash = hashlib.sha256(html.encode('utf-8')).hexdigest()
    if payload_hash != descriptor['payload_hash']:
        raise CommandError('SHARED_INLINE_SOURCE_HASH_MISMATCH')
    with transaction.atomic():
        lock_content('default')
        blocked = blockers()
        if any(blocked.values()):
            raise CommandError(
                'SHARED_INLINE_MIGRATION_BLOCKED ' + json.dumps(blocked, sort_keys=True))
        locked = model.objects.select_for_update().get(pk=identity)
        if descriptor_for(locked) != descriptor:
            raise CommandError('SHARED_INLINE_SOURCE_CHANGED')
        updated = raw(model).filter(pk=identity, storage_kind='file').update(
            html=html, storage_kind='inline', file_key='', byte_size=None,
            file_sha256='', payload_hash=payload_hash)
        if updated != 1:
            raise CommandError('SHARED_INLINE_SOURCE_CHANGED')
        record_event(
            category=Category.BACKUP_MAINTENANCE,
            event_code='SHARED_INLINE_MIGRATE_ROW', level=Level.INFO,
            source=Source.APPLICATION, result=Result.SUCCESS,
            object_kind='shared_block', object_ref=locked.block_id)


class Command(BaseCommand):
    help = 'Verify or migrate legacy Header/Footer blobs to inline PostgreSQL; blobs are retained.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        blocked = blockers()
        if any(blocked.values()):
            raise CommandError('SHARED_INLINE_MIGRATION_BLOCKED ' + json.dumps(blocked, sort_keys=True))
        rows = candidates()
        verified = 0
        for model, _label, identity, descriptor in rows:
            html = content_html(descriptor)
            if hashlib.sha256(html.encode('utf-8')).hexdigest() != descriptor['payload_hash']:
                raise CommandError('SHARED_INLINE_SOURCE_HASH_MISMATCH')
            verified += 1
            if options['apply']:
                migrate_one(model, identity, descriptor)
        remaining = sum(model.objects.filter(storage_kind='file').count()
                        for model in (SharedRevision, SharedDraft))
        if options['apply']:
            if remaining:
                raise CommandError('SHARED_INLINE_MIGRATION_INCOMPLETE')
        self.stdout.write(json.dumps({
            'status': 'APPLIED' if options['apply'] else 'VERIFIED',
            'verified': verified,
            'migrated': verified if options['apply'] else 0,
            'remainingFileRows': remaining,
            'blobsDeleted': 0,
        }, sort_keys=True))
