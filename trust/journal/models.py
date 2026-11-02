import uuid
from django.db import models
from django.db.models import Q

class Head(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    incarnation = models.UUIDField(unique=True)
    generation = models.BigIntegerField(default=0)
    writer_epoch = models.BigIntegerField(default=1)
    mode = models.CharField(max_length=8, default='ACTIVE')
    digest = models.CharField(max_length=64)
    logical_bytes = models.BigIntegerField(default=0)
    reserved_bytes = models.BigIntegerField(default=0)
    plan_id = models.UUIDField(null=True)
    permitted_operations = models.JSONField(null=True)
    permitted_recovery_actions = models.JSONField(null=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1, generation__gte=0, writer_epoch__gte=1,
            logical_bytes__gte=0, reserved_bytes__gte=0, mode__in=['ACTIVE','FROZEN']), name='trust_head_shape')]

class Credential(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    principal = models.CharField(max_length=64)
    role = models.CharField(max_length=8)
    verifier = models.CharField(max_length=64)
    writer_epoch = models.BigIntegerField()
    active = models.BooleanField(default=True)

class Operation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    credential_id = models.CharField(max_length=64)
    principal = models.CharField(max_length=64)
    writer_epoch = models.BigIntegerField()
    kind = models.CharField(max_length=24)
    object_id = models.UUIDField()
    prepare_fingerprint = models.CharField(max_length=64)
    payload = models.JSONField()
    stage = models.CharField(max_length=24, default='PENDING_DENY')
    terminal_fingerprint = models.CharField(max_length=64, null=True)
    phases = models.JSONField(default=dict)
    logical_bytes = models.PositiveIntegerField()
    reserve_bytes = models.PositiveIntegerField()
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(stage__in=['PENDING_DENY','MAIN_RESULT_UNKNOWN','FINAL_RESTRICTION','RECONCILE_REQUIRED']),name='trust_operation_stage'),
            models.CheckConstraint(condition=(Q(stage__in=['FINAL_RESTRICTION','RECONCILE_REQUIRED'],terminal_fingerprint__isnull=False)|Q(stage__in=['PENDING_DENY','MAIN_RESULT_UNKNOWN'],terminal_fingerprint__isnull=True)),name='trust_terminal_shape')]

class RoutePolicy(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    target = models.TextField()
    object_id = models.UUIDField()
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    generation = models.BigIntegerField()
    policy = models.CharField(max_length=24)
    redirect_target = models.TextField(null=True)

class RequestTombstone(models.Model):
    request_id = models.UUIDField(primary_key=True)
    tombstone_id = models.UUIDField(unique=True, default=uuid.uuid4)
    operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    generation = models.BigIntegerField()

class RecoveryReceipt(models.Model):
    id = models.UUIDField(primary_key=True)
    credential_id = models.CharField(max_length=64)
    principal = models.CharField(max_length=64)
    action = models.CharField(max_length=8)
    fingerprint = models.CharField(max_length=64)
    receipt = models.JSONField()
    logical_bytes = models.PositiveIntegerField()
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(action__in=['fence','activate'],logical_bytes__lte=16384),name='trust_recovery_shape')]
