import uuid
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='Head',fields=[
            ('id',models.PositiveSmallIntegerField(primary_key=True,default=1,serialize=False)),
            ('incarnation',models.UUIDField(unique=True)),('generation',models.BigIntegerField(default=0)),
            ('writer_epoch',models.BigIntegerField(default=1)),('mode',models.CharField(max_length=8,default='ACTIVE')),
            ('digest',models.CharField(max_length=64)),('logical_bytes',models.BigIntegerField(default=0)),
            ('reserved_bytes',models.BigIntegerField(default=0))]),
        migrations.CreateModel(name='Credential',fields=[
            ('id',models.CharField(max_length=64,primary_key=True,serialize=False)),('principal',models.CharField(max_length=64)),
            ('role',models.CharField(max_length=8)),('verifier',models.CharField(max_length=64)),
            ('writer_epoch',models.BigIntegerField()),('active',models.BooleanField(default=True))]),
        migrations.CreateModel(name='Operation',fields=[
            ('id',models.UUIDField(primary_key=True,default=uuid.uuid4,serialize=False)),
            ('credential_id',models.CharField(max_length=64)),('principal',models.CharField(max_length=64)),
            ('writer_epoch',models.BigIntegerField()),('kind',models.CharField(max_length=24)),('object_id',models.UUIDField()),
            ('prepare_fingerprint',models.CharField(max_length=64)),('payload',models.JSONField()),
            ('stage',models.CharField(max_length=24,default='PENDING_DENY')),
            ('terminal_fingerprint',models.CharField(max_length=64,null=True)),('phases',models.JSONField(default=dict)),
            ('logical_bytes',models.PositiveIntegerField()),('reserve_bytes',models.PositiveIntegerField())]),
        migrations.CreateModel(name='RoutePolicy',fields=[
            ('key',models.CharField(max_length=64,primary_key=True,serialize=False)),('target',models.TextField()),
            ('object_id',models.UUIDField()),('generation',models.BigIntegerField()),('policy',models.CharField(max_length=24)),
            ('redirect_target',models.TextField(null=True)),
            ('operation',models.ForeignKey(to='journal.operation',on_delete=django.db.models.deletion.PROTECT))]),
        migrations.CreateModel(name='RequestTombstone',fields=[
            ('request_id',models.UUIDField(primary_key=True,serialize=False)),('tombstone_id',models.UUIDField(unique=True,default=uuid.uuid4)),
            ('generation',models.BigIntegerField()),
            ('operation',models.ForeignKey(to='journal.operation',on_delete=django.db.models.deletion.PROTECT))]),
        migrations.AddConstraint(model_name='head',constraint=models.CheckConstraint(condition=models.Q(id=1,generation__gte=0,writer_epoch__gte=1,logical_bytes__gte=0,reserved_bytes__gte=0,mode__in=['ACTIVE','FROZEN']),name='trust_head_shape')),
        migrations.AddConstraint(model_name='operation',constraint=models.CheckConstraint(condition=models.Q(stage__in=['PENDING_DENY','MAIN_RESULT_UNKNOWN','FINAL_RESTRICTION','RECONCILE_REQUIRED']),name='trust_operation_stage')),
        migrations.AddConstraint(model_name='operation',constraint=models.CheckConstraint(condition=(models.Q(stage__in=['FINAL_RESTRICTION','RECONCILE_REQUIRED'],terminal_fingerprint__isnull=False)|models.Q(stage__in=['PENDING_DENY','MAIN_RESULT_UNKNOWN'],terminal_fingerprint__isnull=True)),name='trust_terminal_shape')),
        migrations.RunSQL('''
CREATE FUNCTION trust_guard_head() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'TRUST_IMMUTABLE'; END IF;
 IF NEW.incarnation IS DISTINCT FROM OLD.incarnation OR NEW.id <> OLD.id
 OR NEW.generation < OLD.generation OR NEW.writer_epoch < OLD.writer_epoch
 THEN RAISE EXCEPTION 'TRUST_MONOTONIC'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trust_head_guard BEFORE UPDATE OR DELETE ON journal_head
 FOR EACH ROW EXECUTE FUNCTION trust_guard_head();
CREATE FUNCTION trust_guard_operation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'TRUST_IMMUTABLE'; END IF;
 IF (OLD.terminal_fingerprint IS NOT NULL AND NEW IS DISTINCT FROM OLD)
 OR NEW.id IS DISTINCT FROM OLD.id OR NEW.credential_id IS DISTINCT FROM OLD.credential_id
 OR NEW.principal IS DISTINCT FROM OLD.principal OR NEW.writer_epoch <> OLD.writer_epoch
 OR NEW.kind IS DISTINCT FROM OLD.kind OR NEW.object_id IS DISTINCT FROM OLD.object_id
 OR NEW.prepare_fingerprint IS DISTINCT FROM OLD.prepare_fingerprint OR NEW.payload IS DISTINCT FROM OLD.payload
 OR (OLD.stage = 'MAIN_RESULT_UNKNOWN' AND NEW.stage = 'PENDING_DENY')
 THEN RAISE EXCEPTION 'TRUST_IMMUTABLE'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trust_operation_guard BEFORE UPDATE OR DELETE ON journal_operation
 FOR EACH ROW EXECUTE FUNCTION trust_guard_operation();
CREATE FUNCTION trust_guard_tombstone() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'TRUST_IMMUTABLE'; END $$;
CREATE TRIGGER trust_tombstone_guard BEFORE UPDATE OR DELETE ON journal_requesttombstone
 FOR EACH ROW EXECUTE FUNCTION trust_guard_tombstone();
''', reverse_sql='''
DROP TRIGGER trust_tombstone_guard ON journal_requesttombstone;
DROP FUNCTION trust_guard_tombstone();
DROP TRIGGER trust_operation_guard ON journal_operation;
DROP FUNCTION trust_guard_operation();
DROP TRIGGER trust_head_guard ON journal_head;
DROP FUNCTION trust_guard_head();
'''),
    ]
