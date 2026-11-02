from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[('journal','0001_initial')]
    operations=[
        migrations.AddField(model_name='head',name='plan_id',field=models.UUIDField(null=True)),
        migrations.AddField(model_name='head',name='permitted_operations',field=models.JSONField(null=True)),
        migrations.AddField(model_name='head',name='permitted_recovery_actions',field=models.JSONField(null=True)),
        migrations.CreateModel(name='RecoveryReceipt',fields=[
            ('id',models.UUIDField(primary_key=True,serialize=False)),('credential_id',models.CharField(max_length=64)),
            ('principal',models.CharField(max_length=64)),('action',models.CharField(max_length=8)),
            ('fingerprint',models.CharField(max_length=64)),('receipt',models.JSONField()),
            ('logical_bytes',models.PositiveIntegerField())]),
        migrations.AddConstraint(model_name='recoveryreceipt',constraint=models.CheckConstraint(condition=models.Q(action__in=['fence','activate'],logical_bytes__lte=16384),name='trust_recovery_shape')),
        migrations.RunSQL('''
CREATE TRIGGER trust_recovery_guard BEFORE UPDATE OR DELETE ON journal_recoveryreceipt
 FOR EACH ROW EXECUTE FUNCTION trust_guard_tombstone();
CREATE FUNCTION trust_guard_plan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.plan_id IS NOT NULL AND (NEW.plan_id IS DISTINCT FROM OLD.plan_id
 OR NEW.permitted_operations IS DISTINCT FROM OLD.permitted_operations
 OR NEW.permitted_recovery_actions IS DISTINCT FROM OLD.permitted_recovery_actions)
 THEN RAISE EXCEPTION 'TRUST_PLAN_IMMUTABLE'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER trust_plan_guard BEFORE UPDATE ON journal_head FOR EACH ROW EXECUTE FUNCTION trust_guard_plan();
''',reverse_sql='''
DROP TRIGGER trust_plan_guard ON journal_head;
DROP FUNCTION trust_guard_plan();
DROP TRIGGER trust_recovery_guard ON journal_recoveryreceipt;
''')]
