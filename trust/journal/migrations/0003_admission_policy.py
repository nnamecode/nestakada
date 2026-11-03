from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('journal', '0002_local_test_recovery')]
    operations = [
        migrations.CreateModel(name='AdmissionPolicy', fields=[
            ('id', models.UUIDField(primary_key=True, serialize=False)),
            ('epoch', models.PositiveBigIntegerField(unique=True)),
            ('previous_digest', models.CharField(max_length=64, null=True)),
            ('legacy_seal', models.CharField(max_length=64, null=True)),
            ('policy', models.JSONField()),
            ('policy_digest', models.CharField(max_length=64, unique=True)),
            ('action_id', models.UUIDField(unique=True)),
            ('intent_digest', models.CharField(max_length=64)),
            ('state_digest_version', models.PositiveSmallIntegerField(default=2)),
            ('prior_state', models.JSONField()),
            ('receipt', models.JSONField()),
            ('logical_bytes', models.PositiveIntegerField()),
        ]),
        migrations.AddConstraint(model_name='admissionpolicy', constraint=models.CheckConstraint(
            condition=models.Q(epoch__gte=1, state_digest_version=2,
                logical_bytes__gte=1, logical_bytes__lte=32768), name='trust_admission_shape')),
        migrations.AddConstraint(model_name='admissionpolicy', constraint=models.CheckConstraint(
            condition=(models.Q(epoch=1, previous_digest__isnull=True, legacy_seal__isnull=False)
                | models.Q(epoch__gt=1, previous_digest__isnull=False, legacy_seal__isnull=True)),
            name='trust_admission_predecessor')),
        migrations.AddConstraint(model_name='admissionpolicy', constraint=models.CheckConstraint(
            condition=(models.Q(policy_digest__regex=r'^[0-9a-f]{64}$', intent_digest__regex=r'^[0-9a-f]{64}$')
                & (models.Q(previous_digest__isnull=True) | models.Q(previous_digest__regex=r'^[0-9a-f]{64}$'))
                & (models.Q(legacy_seal__isnull=True) | models.Q(legacy_seal__regex=r'^[0-9a-f]{64}$'))),
            name='trust_admission_digests')),
        migrations.RunSQL('''
CREATE TRIGGER trust_admission_guard BEFORE UPDATE OR DELETE ON journal_admissionpolicy
 FOR EACH ROW EXECUTE FUNCTION trust_guard_tombstone();
''', reverse_sql='DROP TRIGGER trust_admission_guard ON journal_admissionpolicy;'),
    ]
