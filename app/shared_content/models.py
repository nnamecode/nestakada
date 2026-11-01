from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from content.models import lock_content


class GuardedQuerySet(models.QuerySet):
    def update(self, **kwargs): raise ValidationError('SHARED_USE_SERVICE')
    def delete(self): raise ValidationError('SHARED_USE_SERVICE')
    def bulk_create(self, *args, **kwargs): raise ValidationError('SHARED_USE_SERVICE')
    def bulk_update(self, *args, **kwargs): raise ValidationError('SHARED_USE_SERVICE')


class SharedIdentityReservation(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    kind = models.CharField(max_length=32)
    block = models.ForeignKey('SharedBlock', null=True, blank=True, on_delete=models.PROTECT,
                              related_name='identity_reservations')
    objects = GuardedQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['block', 'id', 'kind'], name='shared_identity_block_type')]

    def save(self, *args, **kwargs):
        if args or not self._state.adding or kwargs.get('update_fields') is not None:
            raise ValidationError('SHARED_ID_RESERVED')
        kwargs['force_insert'] = True
        return super().save(**kwargs)

    def delete(self, *args, **kwargs): raise ValidationError('SHARED_ID_RESERVED')


class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    objects = GuardedQuerySet.as_manager()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._initial_id = str(self.pk)

    def save(self, *args, **kwargs):
        if args or not self._state.adding or str(self.pk) != self._initial_id or kwargs.get('update_fields') is not None:
            raise ValidationError('SHARED_RECORD_IMMUTABLE')
        using = kwargs.get('using') or 'default'
        with transaction.atomic(using=using):
            lock_content(using)
            self.full_clean(validate_unique=False, validate_constraints=False)
            # Draft kind is shared with Page in AssetUsage: never reserve a Page ID.
            from page_versions.models import IdentityReservation as PageIdentity
            from media_library.models import AssetUsage
            if (PageIdentity.objects.using(using).filter(pk=self.pk).exists()
                    or AssetUsage.objects.using(using).filter(consumer_id=self.pk).exists()):
                raise ValidationError('SHARED_CONSUMER_ID_RESERVED')
            if self._meta.model_name == 'sharedblock':
                block_id = self.pk
            elif self._meta.model_name == 'sharedbasepin':
                block_id = SharedRevision.objects.using(using).get(pk=self.revision_id).block_id
            else:
                block_id = getattr(self, 'block_id', None)
            if block_id is None:
                raise ValidationError('SHARED_IDENTITY_BLOCK_REQUIRED')
            SharedIdentityReservation.objects.using(using).create(
                id=self.pk, kind=self._meta.model_name, block_id=block_id)
            kwargs['force_insert'] = True
            return super().save(**kwargs)

    def delete(self, *args, **kwargs): raise ValidationError('SHARED_USE_SERVICE')


class SharedBlock(Record):
    kind = models.CharField(max_length=6, unique=True)
    current_revision = models.ForeignKey('SharedRevision', null=True, blank=True,
        on_delete=models.PROTECT, related_name='current_for')
    generation = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(kind__in=['header', 'footer']), name='shared_block_kind'),
            models.CheckConstraint(condition=Q(generation__gte=1), name='shared_block_generation')]


class SharedRevision(Record):
    block = models.ForeignKey(SharedBlock, on_delete=models.PROTECT, related_name='revisions')
    sequence = models.PositiveBigIntegerField()
    schema_version = models.CharField(max_length=32)
    html = models.TextField()
    storage_kind = models.CharField(max_length=6, default='inline', db_default='inline')
    file_key = models.CharField(max_length=96, blank=True, default='', db_default='')
    byte_size = models.PositiveIntegerField(null=True, blank=True)
    file_sha256 = models.CharField(max_length=64, blank=True, default='', db_default='')
    payload_hash = models.CharField(max_length=64)
    author_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    source_revision_id = models.UUIDField(null=True, blank=True)
    source_identity_kind = models.CharField(max_length=32, default='sharedrevision',
        db_default='sharedrevision', editable=False)

    def clean_fields(self, exclude=None):
        excluded = set(exclude or ())
        if self.storage_kind == 'file':
            excluded.add('html')  # Empty inline body is required by the file descriptor CHECK.
        super().clean_fields(exclude=excluded)

    def clean(self):
        from .content import clean_record
        clean_record(self)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['block', 'sequence'], name='shared_revision_sequence'),
            models.CheckConstraint(condition=Q(source_identity_kind='sharedrevision'), name='shared_revision_source_type'),
            models.UniqueConstraint(fields=['block', 'id'], name='shared_revision_block_id'),
            models.CheckConstraint(condition=Q(sequence__gte=1), name='shared_revision_positive_sequence'),
            models.CheckConstraint(condition=(Q(storage_kind='inline', file_key='', byte_size__isnull=True, file_sha256='')
                | Q(storage_kind='file', html='', file_key__regex=r'^blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html$',
                    byte_size__isnull=False, byte_size__gte=0, byte_size__lte=1048576,
                    file_sha256__regex=r'^[0-9a-f]{64}$', payload_hash=models.F('file_sha256'))),
                name='shared_revision_storage_descriptor')]


class SharedDraft(Record):
    block = models.OneToOneField(SharedBlock, on_delete=models.PROTECT, related_name='draft')
    revision = models.PositiveBigIntegerField(default=1)
    base_revision = models.ForeignKey(SharedRevision, null=True, blank=True,
        on_delete=models.PROTECT, related_name='draft_bases')
    html = models.TextField()
    storage_kind = models.CharField(max_length=6, default='inline', db_default='inline')
    file_key = models.CharField(max_length=96, blank=True, default='', db_default='')
    byte_size = models.PositiveIntegerField(null=True, blank=True)
    file_sha256 = models.CharField(max_length=64, blank=True, default='', db_default='')
    payload_hash = models.CharField(max_length=64)
    author_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    def clean_fields(self, exclude=None):
        excluded = set(exclude or ())
        if self.storage_kind == 'file':
            excluded.add('html')
        super().clean_fields(exclude=excluded)

    def clean(self):
        from .content import clean_record
        clean_record(self)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(revision__gte=1), name='shared_draft_revision'),
            models.CheckConstraint(condition=(Q(storage_kind='inline', file_key='', byte_size__isnull=True, file_sha256='')
                | Q(storage_kind='file', html='', file_key__regex=r'^blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html$',
                    byte_size__isnull=False, byte_size__gte=0, byte_size__lte=1048576,
                    file_sha256__regex=r'^[0-9a-f]{64}$', payload_hash=models.F('file_sha256'))),
                name='shared_draft_storage_descriptor')]


class SharedRestoreStage(Record):
    block = models.ForeignKey(SharedBlock, on_delete=models.PROTECT)
    actor_id = models.PositiveBigIntegerField()
    actor_generation = models.PositiveBigIntegerField()
    source_revision = models.ForeignKey(SharedRevision, on_delete=models.PROTECT, related_name='restore_sources')
    base_revision = models.ForeignKey(SharedRevision, null=True, blank=True,
        on_delete=models.PROTECT, related_name='restore_bases')
    schema_version = models.CharField(max_length=32)
    policy_version = models.CharField(max_length=32)
    status = models.CharField(max_length=16, default='held')
    terminal_operation_id = models.UUIDField(null=True, blank=True)
    terminal_actor_id = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(status__in=['held', 'consumed', 'released', 'invalidated']),
            name='shared_stage_status')]


class SharedBasePin(Record):
    revision = models.ForeignKey(SharedRevision, on_delete=models.PROTECT, related_name='base_pins')
    holder_kind = models.CharField(max_length=24)
    holder_id = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['revision', 'holder_kind', 'holder_id'], name='shared_unique_pin')]


class SharedReceipt(Record):
    action = models.CharField(max_length=32)
    actor_id = models.PositiveBigIntegerField()
    actor_generation = models.PositiveBigIntegerField()
    block = models.ForeignKey(SharedBlock, on_delete=models.PROTECT)
    source_revision_id = models.UUIDField(null=True, blank=True)
    base_revision_id = models.UUIDField(null=True, blank=True)
    source_identity_kind = models.CharField(max_length=32, default='sharedrevision',
        db_default='sharedrevision', editable=False)
    base_identity_kind = models.CharField(max_length=32, default='sharedrevision',
        db_default='sharedrevision', editable=False)
    fingerprint = models.CharField(max_length=64)
    result_code = models.CharField(max_length=32)
    result_id = models.UUIDField(null=True, blank=True)
    result_identity_kind = models.CharField(max_length=32, null=True, blank=True, editable=False)
    result_revision = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    source_stamp = models.CharField(max_length=64, blank=True, default='', db_default='', editable=False)
    reservation_profile = models.CharField(max_length=32, blank=True, default='', db_default='', editable=False)
    reservation_book_sha256 = models.CharField(max_length=64, blank=True, default='', db_default='', editable=False)
    created_at = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        if self._state.adding and self.result_id is not None and self.result_identity_kind is None:
            self.result_identity_kind = {'apply': 'sharedrevision', 'draft': 'shareddraft',
                'restore_prepare': 'sharedrestorestage'}.get(self.action)
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(source_identity_kind='sharedrevision'), name='shared_receipt_source_type'),
            models.CheckConstraint(condition=Q(base_identity_kind='sharedrevision'), name='shared_receipt_base_type'),
            models.CheckConstraint(condition=(Q(result_id__isnull=True, result_identity_kind__isnull=True)
                | (Q(result_id__isnull=False, result_identity_kind__isnull=False) & (Q(action='apply', result_identity_kind='sharedrevision')
                    | Q(action='draft', result_identity_kind='shareddraft')
                    | Q(action='restore_prepare', result_identity_kind='sharedrestorestage')))),
                name='shared_receipt_result_type'),
            models.CheckConstraint(condition=(Q(result_revision__isnull=True)
                | Q(result_revision__gte=1, action='draft', result_code='applied', result_id__isnull=False)),
                name='shared_receipt_draft_counter'),
            models.CheckConstraint(condition=(Q(source_stamp='', reservation_profile='', reservation_book_sha256='')
                | Q(source_stamp__regex=r'^[0-9a-f]{64}$', reservation_profile__regex=r'^[a-z][a-z0-9-]{0,31}$',
                    reservation_book_sha256__regex=r'^[0-9a-f]{64}$')), name='shared_receipt_reservation_binding')]


class SharedCleanupJob(Record):
    block = models.ForeignKey(SharedBlock, on_delete=models.PROTECT)
    target_id = models.UUIDField(unique=True)
    target_identity_kind = models.CharField(max_length=32, default='sharedrevision', db_default='sharedrevision')
    sequence = models.PositiveBigIntegerField()
    actor_id = models.PositiveBigIntegerField()
    actor_generation = models.PositiveBigIntegerField()
    fingerprint = models.CharField(max_length=64)
    source_stamp = models.CharField(max_length=64)
    file_key = models.CharField(max_length=96, db_index=True)
    byte_size = models.PositiveIntegerField()
    file_sha256 = models.CharField(max_length=64)
    phase = models.CharField(max_length=24, default='prepared')
    file_deleted = models.BooleanField(default=False)
    reserved_bytes = models.PositiveBigIntegerField()
    domain = models.BooleanField(default=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(domain=True), name='shared_cleanup_domain'),
            models.UniqueConstraint(fields=['domain'], condition=~Q(phase='complete'), name='shared_cleanup_one_pending'),
            models.CheckConstraint(condition=Q(phase__in=['prepared', 'metadata_deleted', 'complete']), name='shared_cleanup_phase'),
            models.CheckConstraint(condition=Q(target_identity_kind='sharedrevision'), name='shared_cleanup_target_type'),
            models.CheckConstraint(condition=Q(sequence__gte=1, actor_id__gte=1, actor_generation__gte=1,
                byte_size__lte=1048576, reserved_bytes__gte=1, reserved_bytes__lte=268435456,
                fingerprint__regex=r'^[0-9a-f]{64}$', source_stamp__regex=r'^[0-9a-f]{64}$',
                file_sha256__regex=r'^[0-9a-f]{64}$',
                file_key__regex=r'^blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html$'), name='shared_cleanup_descriptor'),
        ]


class SharedBudget(models.Model):
    singleton = models.BooleanField(primary_key=True, default=True)
    snapshot_count = models.PositiveBigIntegerField(default=0)
    charged_bytes = models.PositiveBigIntegerField(default=0)
    accounting_version = models.CharField(max_length=32, default='unvetted')
    retained_debt_bytes = models.PositiveBigIntegerField(default=0, db_default=0)
    objects = GuardedQuerySet.as_manager()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(singleton=True), name='shared_budget_singleton')]
