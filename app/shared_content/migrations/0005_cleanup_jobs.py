from uuid import uuid4
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('shared_content', '0004_reservation_metadata')]
    operations = [
        migrations.CreateModel(name='SharedCleanupJob', fields=[
            ('id', models.UUIDField(primary_key=True, default=uuid4, editable=False, serialize=False)),
            ('target_id', models.UUIDField(unique=True)),
            ('target_identity_kind', models.CharField(max_length=32, default='sharedrevision', db_default='sharedrevision')),
            ('sequence', models.PositiveBigIntegerField()),
            ('actor_id', models.PositiveBigIntegerField()), ('actor_generation', models.PositiveBigIntegerField()),
            ('fingerprint', models.CharField(max_length=64)), ('source_stamp', models.CharField(max_length=64)),
            ('file_key', models.CharField(max_length=96, db_index=True)),
            ('byte_size', models.PositiveIntegerField()), ('file_sha256', models.CharField(max_length=64)),
            ('phase', models.CharField(max_length=24, default='prepared')),
            ('file_deleted', models.BooleanField(default=False)),
            ('reserved_bytes', models.PositiveBigIntegerField()), ('domain', models.BooleanField(default=True, editable=False)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('block', models.ForeignKey(to='shared_content.sharedblock', on_delete=django.db.models.deletion.PROTECT)),
        ], options={'constraints': [
            models.CheckConstraint(condition=models.Q(domain=True), name='shared_cleanup_domain'),
            models.UniqueConstraint(fields=['domain'], condition=~models.Q(phase='complete'), name='shared_cleanup_one_pending'),
            models.CheckConstraint(condition=models.Q(phase__in=['prepared', 'metadata_deleted', 'complete']), name='shared_cleanup_phase'),
            models.CheckConstraint(condition=models.Q(target_identity_kind='sharedrevision'), name='shared_cleanup_target_type'),
            models.CheckConstraint(condition=models.Q(sequence__gte=1, actor_id__gte=1, actor_generation__gte=1,
                byte_size__lte=1048576, reserved_bytes__gte=1, reserved_bytes__lte=268435456,
                fingerprint__regex=r'^[0-9a-f]{64}$', source_stamp__regex=r'^[0-9a-f]{64}$',
                file_sha256__regex=r'^[0-9a-f]{64}$',
                file_key__regex=r'^blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html$'), name='shared_cleanup_descriptor'),
        ]}),
        migrations.RunSQL('''ALTER TABLE app.shared_content_sharedcleanupjob
            ADD CONSTRAINT shared_cleanup_target_identity FOREIGN KEY(block_id,target_id,target_identity_kind)
            REFERENCES app.shared_content_sharedidentityreservation(block_id,id,kind)''',
            reverse_sql='ALTER TABLE app.shared_content_sharedcleanupjob DROP CONSTRAINT shared_cleanup_target_identity'),
    ]
