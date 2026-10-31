import re
import uuid
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from content.models import lock_content
from .paths import relative_path, storage_key


class ProtectedQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('MEDIA_USE_SERVICE')
    def bulk_create(self, *args, **kwargs):
        raise ValidationError('MEDIA_USE_SERVICE')
    def bulk_update(self, *args, **kwargs):
        raise ValidationError('MEDIA_USE_SERVICE')
    def delete(self):
        raise ValidationError('MEDIA_USE_SERVICE')


class IdentityReservation(models.Model):
    """Small tombstone: deleted asset/file UUIDs are never reassigned."""
    id = models.UUIDField(primary_key=True, editable=False)
    record_kind = models.CharField(max_length=12, choices=[('asset','asset'),('assetfile','assetfile')])
    objects = ProtectedQuerySet.as_manager()
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('MEDIA_RESERVATION_IMMUTABLE')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('MEDIA_RESERVATION_IMMUTABLE')


class FileKeyReservation(models.Model):
    """Retains a key after physical deletion; no original bytes/credentials."""
    key = models.CharField(max_length=1024, primary_key=True)
    file_id = models.UUIDField()
    objects = ProtectedQuerySet.as_manager()
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('MEDIA_RESERVATION_IMMUTABLE')
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('MEDIA_RESERVATION_IMMUTABLE')


class ImmutableRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects = ProtectedQuerySet.as_manager()
    class Meta:
        abstract = True
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_id = str(self.pk)
    def save(self, *args, **kwargs):
        if args or str(self.pk) != self._original_id or kwargs.get('update_fields') is not None:
            raise ValidationError('MEDIA_RECORD_IMMUTABLE')
        using = kwargs.get('using') or self._state.db or 'default'
        with transaction.atomic(using=using):
            lock_content(using)
            if not self._state.adding:
                original = type(self)._base_manager.using(using).get(pk=self.pk)
                if any(getattr(self, field.attname) != getattr(original, field.attname) for field in self._meta.concrete_fields):
                    raise ValidationError('MEDIA_RECORD_IMMUTABLE')
                return
            self.full_clean(validate_unique=False, validate_constraints=False)
            if self._meta.model_name in ('asset','assetfile'):
                IdentityReservation.objects.using(using).create(id=self.pk,record_kind=self._meta.model_name)
            if self._meta.model_name == 'assetfile':
                FileKeyReservation.objects.using(using).create(key=self.key,file_id=self.pk)
            kwargs['force_insert'] = True
            return super().save(**kwargs)
    def delete(self, *args, **kwargs):
        raise ValidationError('MEDIA_USE_SERVICE')


class MediaFolder(ImmutableRecord):
    path = models.CharField(max_length=1024, unique=True)
    def clean(self):
        relative_path(self.path)


class PageMediaHome(ImmutableRecord):
    page = models.OneToOneField('content.Page', on_delete=models.PROTECT, related_name='media_home')
    folder = models.ForeignKey(MediaFolder, on_delete=models.PROTECT)


class Asset(ImmutableRecord):
    class Status(models.TextChoices):
        STAGED = 'staged'
        READY = 'ready'
        DELETING = 'deleting'
        DELETE_FAILED = 'delete_failed'
    folder = models.ForeignKey(MediaFolder, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STAGED)
    provenance = models.CharField(max_length=200)
    is_legacy = models.BooleanField(default=False)
    source_url = models.TextField(blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True)
    deletion_manifest = models.JSONField(null=True, blank=True, editable=False)
    deletion_error = models.CharField(max_length=100, blank=True, editable=False)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(status__in=['staged','ready','deleting','delete_failed']), name='media_asset_known_state')]
    def clean(self):
        if self._state.adding and (self.status != self.Status.STAGED or self.deletion_manifest is not None or self.deletion_error):
            raise ValidationError('MEDIA_ASSET_STARTS_STAGED')
        if self.is_legacy and (not self.source_url or not re.fullmatch('[a-f0-9]{64}', self.source_sha256)):
            raise ValidationError('MEDIA_LEGACY_PROVENANCE_REQUIRED')
        if self.source_sha256 and not re.fullmatch('[a-f0-9]{64}', self.source_sha256):
            raise ValidationError('MEDIA_INVALID_SOURCE_HASH')


class AssetFile(ImmutableRecord):
    class Kind(models.TextChoices):
        PRIVATE_SOURCE = 'private-source'
        MAIN = 'main'
        PREVIEW = 'preview'
        LEGACY_PUBLIC = 'legacy-public'
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='files')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    key = models.CharField(max_length=1024, unique=True)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(kind__in=['private-source','main','preview','legacy-public']), name='media_file_known_kind')]
    def clean(self):
        storage_key(self.key)
        if not re.fullmatch('[a-f0-9]{64}', self.sha256):
            raise ValidationError('MEDIA_INVALID_FILE_HASH')
        if (self.kind == self.Kind.PRIVATE_SOURCE) != self.key.startswith('private/sources/'):
            raise ValidationError('MEDIA_PRIVATE_PUBLIC_SPACE_MISMATCH')
        if Asset.objects.filter(pk=self.asset_id).values_list('status', flat=True).first() != Asset.Status.STAGED:
            raise ValidationError('MEDIA_FILES_REQUIRE_STAGED_ASSET')


class AssetUsage(ImmutableRecord):
    class Kind(models.TextChoices):
        CURRENT_PAGE = 'current_page'
        SHARED_BLOCK = 'shared_block'
        ORDINARY_VERSION = 'ordinary_version'
        STABLE_VERSION = 'stable_version'
        DRAFT = 'draft'
        RETAINED_HTML = 'retained_html'
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, related_name='usages')
    kind = models.CharField(max_length=24, choices=Kind.choices)
    consumer_id = models.UUIDField()
    slot = models.CharField(max_length=100)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['kind','consumer_id','slot'], name='media_unique_consumer_slot'),
                       models.CheckConstraint(condition=Q(kind__in=['current_page','shared_block','ordinary_version','stable_version','draft','retained_html']), name='media_usage_known_kind')]
    def clean(self):
        if Asset.objects.filter(pk=self.asset_id).values_list('status', flat=True).first() != Asset.Status.READY:
            raise ValidationError('MEDIA_REFERENCE_REQUIRES_READY')
