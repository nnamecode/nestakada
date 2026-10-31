from uuid import uuid4
from django.core.exceptions import ValidationError
from django.db import models,transaction
from django.db.models import Q
from django.utils import timezone
from content.models import lock_content


class GuardedQuerySet(models.QuerySet):
    def update(self,**kwargs):raise ValidationError('VERSIONS_USE_SERVICE')
    def delete(self):raise ValidationError('VERSIONS_USE_SERVICE')
    def bulk_create(self,*args,**kwargs):raise ValidationError('VERSIONS_USE_SERVICE')
    def bulk_update(self,*args,**kwargs):raise ValidationError('VERSIONS_USE_SERVICE')


class Record(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid4,editable=False)
    objects=GuardedQuerySet.as_manager()
    class Meta:abstract=True
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self._original_id=str(self.pk)
    def save(self,*args,**kwargs):
        if args or not self._state.adding or str(self.pk)!=self._original_id or kwargs.get('update_fields') is not None:
            raise ValidationError('VERSIONS_RECORD_IMMUTABLE')
        using=kwargs.get('using') or 'default'
        with transaction.atomic(using=using):
            lock_content(using);self.full_clean(validate_unique=False,validate_constraints=False)
            if self._meta.model_name in ('pagerevision','ownerdraft','restorestage','operationreceipt'):
                IdentityReservation.objects.using(using).create(id=self.pk,kind=self._meta.model_name)
            kwargs['force_insert']=True
            return super().save(**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError('VERSIONS_USE_SERVICE')


class IdentityReservation(models.Model):
    id=models.UUIDField(primary_key=True,editable=False)
    kind=models.CharField(max_length=24)
    objects=GuardedQuerySet.as_manager()
    def save(self,*args,**kwargs):
        if not self._state.adding:raise ValidationError('VERSIONS_UUID_RESERVED')
        kwargs['force_insert']=True;return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs):raise ValidationError('VERSIONS_UUID_RESERVED')


class PageRevision(Record):
    class Kind(models.TextChoices):
        INITIAL='initial'
        AUTOMATIC='automatic'
        MANUAL='manual'
    page=models.ForeignKey('content.Page',on_delete=models.PROTECT,related_name='content_revisions')
    sequence=models.PositiveBigIntegerField()
    schema_version=models.CharField(max_length=64)
    payload=models.JSONField()
    payload_hash=models.CharField(max_length=64)
    kind=models.CharField(max_length=12,choices=Kind.choices)
    created_at=models.DateTimeField(default=timezone.now,editable=False)
    author_id=models.PositiveBigIntegerField()
    source_revision_id=models.UUIDField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['page','sequence'],name='versions_page_sequence'),
                     models.CheckConstraint(condition=Q(sequence__gte=1),name='versions_positive_sequence'),
                     models.CheckConstraint(condition=Q(kind__in=['initial','automatic','manual']),name='versions_known_kind')]
        ordering=['-created_at','-sequence','-id']


class PageContentState(Record):
    page=models.OneToOneField('content.Page',on_delete=models.PROTECT,related_name='content_state')
    current_revision=models.ForeignKey(PageRevision,on_delete=models.PROTECT,related_name='current_for')
    sequence=models.PositiveBigIntegerField(default=1)
    def clean(self):
        if not PageRevision.objects.filter(pk=self.current_revision_id,page_id=self.page_id).exists():
            raise ValidationError('VERSIONS_CURRENT_PAGE_MISMATCH')


class RevisionMetadata(Record):
    revision=models.OneToOneField(PageRevision,on_delete=models.CASCADE,related_name='metadata')
    generation=models.PositiveBigIntegerField(default=1)
    name=models.CharField(max_length=200,blank=True)
    comment=models.TextField(max_length=1000,blank=True)
    manual_date=models.DateTimeField(null=True,blank=True)


class RevisionProtection(Record):
    revision=models.OneToOneField(PageRevision,on_delete=models.PROTECT,related_name='stable_protection')
    marked_by_id=models.PositiveBigIntegerField()
    marked_at=models.DateTimeField(default=timezone.now,editable=False)


class OwnerDraft(Record):
    page=models.OneToOneField('content.Page',on_delete=models.PROTECT,related_name='owner_draft')
    revision=models.PositiveBigIntegerField(default=1)
    base_revision=models.ForeignKey(PageRevision,on_delete=models.PROTECT,related_name='draft_bases')
    payload=models.JSONField()
    payload_hash=models.CharField(max_length=64)
    author_id=models.PositiveBigIntegerField()
    created_at=models.DateTimeField(default=timezone.now)
    updated_at=models.DateTimeField(default=timezone.now)
    def clean(self):
        if not PageRevision.objects.filter(pk=self.base_revision_id,page_id=self.page_id).exists():
            raise ValidationError('VERSIONS_DRAFT_PAGE_MISMATCH')


class RestoreStage(Record):
    class Status(models.TextChoices):
        HELD='held'
        CONSUMED='consumed'
        RELEASED='released'
        INVALIDATED='invalidated'
    page=models.ForeignKey('content.Page',on_delete=models.PROTECT)
    actor_id=models.PositiveBigIntegerField()
    actor_generation=models.PositiveBigIntegerField()
    holder_kind=models.CharField(max_length=24,default='restore_stage')
    source_revision_id=models.UUIDField()
    base_revision_id=models.UUIDField()
    permission_hash=models.CharField(max_length=64)
    fields=models.JSONField()
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.HELD)
    terminal_reason=models.CharField(max_length=64,blank=True)
    terminal_actor_id=models.PositiveBigIntegerField(null=True,blank=True)
    terminal_operation_id=models.UUIDField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(status__in=['held','consumed','released','invalidated']),name='versions_known_stage_state')]


class VersionBasePin(Record):
    revision=models.ForeignKey(PageRevision,on_delete=models.PROTECT,related_name='base_pins')
    holder_kind=models.CharField(max_length=24)
    holder_id=models.UUIDField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['revision','holder_kind','holder_id'],name='versions_unique_pin')]


class OperationReceipt(Record):
    editor_request_fingerprint=models.CharField(max_length=64,blank=True,default='')
    action=models.CharField(max_length=32)
    actor_id=models.PositiveBigIntegerField()
    actor_generation=models.PositiveBigIntegerField()
    page_id=models.UUIDField()
    source_revision_id=models.UUIDField(null=True,blank=True)
    target_revision_id=models.UUIDField(null=True,blank=True)
    fingerprint=models.CharField(max_length=64)
    result_code=models.CharField(max_length=32)
    result_id=models.UUIDField(null=True,blank=True)
    created_at=models.DateTimeField(default=timezone.now)
