import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def record_fields():
    return [('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False))]


def block_field(unique=False):
    cls = models.OneToOneField if unique else models.ForeignKey
    return cls(on_delete=django.db.models.deletion.PROTECT, to='shared_content.sharedblock',
               **({'related_name': 'draft'} if unique else {}))


def revision_field(related, null=False):
    return models.ForeignKey(to='shared_content.sharedrevision', on_delete=django.db.models.deletion.PROTECT,
                             related_name=related, null=null, blank=null)


def seed_blocks(apps, schema_editor):
    Block = apps.get_model('shared_content', 'SharedBlock')
    Identity = apps.get_model('shared_content', 'SharedIdentityReservation')
    Budget = apps.get_model('shared_content', 'SharedBudget')
    PageIdentity = apps.get_model('page_versions', 'IdentityReservation')
    AssetUsage = apps.get_model('media_library', 'AssetUsage')
    alias = schema_editor.connection.alias
    identities = {kind: uuid.uuid5(uuid.NAMESPACE_URL, 'estakada:shared:' + kind)
                  for kind in ('header', 'footer')}
    # Inspect both identities before any insert; historical migration models
    # deliberately do not call today's Record.save validation.
    if (PageIdentity.objects.using(alias).filter(pk__in=list(identities.values())).exists()
            or AssetUsage.objects.using(alias).filter(consumer_id__in=list(identities.values())).exists()):
        raise RuntimeError('SHARED_SEED_CONSUMER_ID_RESERVED')
    for kind, identity in identities.items():
        Identity.objects.using(alias).create(id=identity, kind='sharedblock')
        Block.objects.using(alias).create(id=identity, kind=kind)
    Budget.objects.using(alias).create(singleton=True)


class Migration(migrations.Migration):
    initial = True
    dependencies = [('media_library', '0001_initial'), ('page_versions', '0002_editor_request_fingerprint')]
    operations = [
        migrations.CreateModel(name='SharedIdentityReservation', fields=[
            ('id', models.UUIDField(primary_key=True, editable=False, serialize=False)),
            ('kind', models.CharField(max_length=32))]),
        migrations.CreateModel(name='SharedBlock', fields=record_fields() + [
            ('kind', models.CharField(max_length=6, unique=True)),
            ('generation', models.PositiveBigIntegerField(default=1))], options={'constraints': [
                models.CheckConstraint(condition=models.Q(kind__in=['header', 'footer']), name='shared_block_kind'),
                models.CheckConstraint(condition=models.Q(generation__gte=1), name='shared_block_generation')]}),
        migrations.CreateModel(name='SharedRevision', fields=record_fields() + [
            ('block', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                related_name='revisions', to='shared_content.sharedblock')),
            ('sequence', models.PositiveBigIntegerField()), ('schema_version', models.CharField(max_length=32)),
            ('html', models.TextField()), ('payload_hash', models.CharField(max_length=64)),
            ('author_id', models.PositiveBigIntegerField()),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('source_revision_id', models.UUIDField(null=True, blank=True))], options={'constraints': [
                models.UniqueConstraint(fields=['block', 'sequence'], name='shared_revision_sequence'),
                models.UniqueConstraint(fields=['block', 'id'], name='shared_revision_block_id'),
                models.CheckConstraint(condition=models.Q(sequence__gte=1), name='shared_revision_positive_sequence')]}),
        migrations.AddField(model_name='sharedblock', name='current_revision',
                            field=revision_field('current_for', True)),
        migrations.CreateModel(name='SharedDraft', fields=record_fields() + [
            ('block', block_field(True)), ('revision', models.PositiveBigIntegerField(default=1)),
            ('base_revision', revision_field('draft_bases', True)), ('html', models.TextField()),
            ('payload_hash', models.CharField(max_length=64)), ('author_id', models.PositiveBigIntegerField()),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('updated_at', models.DateTimeField(default=django.utils.timezone.now))], options={'constraints': [
                models.CheckConstraint(condition=models.Q(revision__gte=1), name='shared_draft_revision')]}),
        migrations.CreateModel(name='SharedRestoreStage', fields=record_fields() + [
            ('block', block_field()), ('actor_id', models.PositiveBigIntegerField()),
            ('actor_generation', models.PositiveBigIntegerField()),
            ('source_revision', revision_field('restore_sources')), ('base_revision', revision_field('restore_bases', True)),
            ('schema_version', models.CharField(max_length=32)), ('policy_version', models.CharField(max_length=32)),
            ('status', models.CharField(max_length=16, default='held')),
            ('terminal_operation_id', models.UUIDField(null=True, blank=True)),
            ('terminal_actor_id', models.PositiveBigIntegerField(null=True, blank=True)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now))], options={'constraints': [
                models.CheckConstraint(condition=models.Q(status__in=['held', 'consumed', 'released', 'invalidated']),
                    name='shared_stage_status')]}),
        migrations.CreateModel(name='SharedBasePin', fields=record_fields() + [
            ('revision', revision_field('base_pins')), ('holder_kind', models.CharField(max_length=24)),
            ('holder_id', models.UUIDField())], options={'constraints': [
                models.UniqueConstraint(fields=['revision', 'holder_kind', 'holder_id'], name='shared_unique_pin')]}),
        migrations.CreateModel(name='SharedReceipt', fields=record_fields() + [
            ('action', models.CharField(max_length=32)), ('actor_id', models.PositiveBigIntegerField()),
            ('actor_generation', models.PositiveBigIntegerField()), ('block', block_field()),
            ('source_revision_id', models.UUIDField(null=True, blank=True)),
            ('base_revision_id', models.UUIDField(null=True, blank=True)),
            ('fingerprint', models.CharField(max_length=64)), ('result_code', models.CharField(max_length=32)),
            ('result_id', models.UUIDField(null=True, blank=True)),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now))]),
        migrations.CreateModel(name='SharedBudget', fields=[
            ('singleton', models.BooleanField(primary_key=True, default=True, serialize=False)),
            ('snapshot_count', models.PositiveBigIntegerField(default=0)),
            ('charged_bytes', models.PositiveBigIntegerField(default=0)),
            ('accounting_version', models.CharField(max_length=32, default='unvetted'))], options={'constraints': [
                models.CheckConstraint(condition=models.Q(singleton=True), name='shared_budget_singleton')]}),
        # PostgreSQL composite keys enforce ownership even for direct SQL/bulk paths.
        migrations.RunSQL('''
            ALTER TABLE app.shared_content_sharedblock ADD CONSTRAINT shared_current_same_block
                FOREIGN KEY(id,current_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_shareddraft ADD CONSTRAINT shared_draft_same_block
                FOREIGN KEY(block_id,base_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_sharedrestorestage ADD CONSTRAINT shared_stage_source_same_block
                FOREIGN KEY(block_id,source_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_sharedrestorestage ADD CONSTRAINT shared_stage_base_same_block
                FOREIGN KEY(block_id,base_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_sharedrevision ADD CONSTRAINT shared_source_same_block
                FOREIGN KEY(block_id,source_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_source_same_block
                FOREIGN KEY(block_id,source_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
            ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_base_same_block
                FOREIGN KEY(block_id,base_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
        ''', reverse_sql='''
            ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_base_same_block;
            ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_source_same_block;
            ALTER TABLE app.shared_content_sharedrevision DROP CONSTRAINT shared_source_same_block;
            ALTER TABLE app.shared_content_sharedrestorestage DROP CONSTRAINT shared_stage_base_same_block;
            ALTER TABLE app.shared_content_sharedrestorestage DROP CONSTRAINT shared_stage_source_same_block;
            ALTER TABLE app.shared_content_shareddraft DROP CONSTRAINT shared_draft_same_block;
            ALTER TABLE app.shared_content_sharedblock DROP CONSTRAINT shared_current_same_block;
        '''),
        migrations.RunPython(seed_blocks, reverse_code=migrations.RunPython.noop),
    ]
