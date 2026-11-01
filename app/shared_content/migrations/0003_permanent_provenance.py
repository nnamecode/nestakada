from django.db import migrations, models
import django.db.models.deletion


# Fixed trusted schema only; no runtime/user SQL identifiers enter migration.
EVIDENCE = '''
    SELECT id,id AS block_id,'sharedblock'::text AS kind FROM app.shared_content_sharedblock
    UNION ALL SELECT id,block_id,'sharedrevision' FROM app.shared_content_sharedrevision
    UNION ALL SELECT id,block_id,'shareddraft' FROM app.shared_content_shareddraft
    UNION ALL SELECT id,block_id,'sharedrestorestage' FROM app.shared_content_sharedrestorestage
    UNION ALL SELECT id,block_id,'sharedreceipt' FROM app.shared_content_sharedreceipt
    UNION ALL SELECT p.id,r.block_id,'sharedbasepin' FROM app.shared_content_sharedbasepin p
        JOIN app.shared_content_sharedrevision r ON r.id=p.revision_id
    UNION ALL SELECT source_revision_id,block_id,'sharedrevision' FROM app.shared_content_sharedrevision
        WHERE source_revision_id IS NOT NULL
    UNION ALL SELECT source_revision_id,block_id,'sharedrevision' FROM app.shared_content_sharedreceipt
        WHERE source_revision_id IS NOT NULL
    UNION ALL SELECT base_revision_id,block_id,'sharedrevision' FROM app.shared_content_sharedreceipt
        WHERE base_revision_id IS NOT NULL
    UNION ALL SELECT result_id,block_id,CASE action
        WHEN 'apply' THEN 'sharedrevision' WHEN 'draft' THEN 'shareddraft'
        WHEN 'restore_prepare' THEN 'sharedrestorestage' END
        FROM app.shared_content_sharedreceipt WHERE result_id IS NOT NULL
'''


def backfill(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""SELECT 1 FROM app.shared_content_sharedreceipt
            WHERE result_id IS NOT NULL AND action NOT IN ('apply','draft','restore_prepare') LIMIT 1""")
        if cursor.fetchone():
            raise RuntimeError('SHARED_PROVENANCE_UNKNOWN_RESULT_ACTION')
        cursor.execute('WITH evidence AS (' + EVIDENCE + ''')
            SELECT 1 FROM evidence GROUP BY id HAVING count(DISTINCT block_id)>1
                OR count(DISTINCT kind)>1 LIMIT 1''')
        if cursor.fetchone():
            raise RuntimeError('SHARED_PROVENANCE_CONFLICT')
        cursor.execute('WITH evidence AS (' + EVIDENCE + ''') SELECT 1 FROM evidence e
            LEFT JOIN app.shared_content_sharedidentityreservation i ON i.id=e.id
            WHERE i.id IS NULL OR i.kind<>e.kind
                OR (i.block_id IS NOT NULL AND i.block_id<>e.block_id) LIMIT 1''')
        if cursor.fetchone():
            raise RuntimeError('SHARED_PROVENANCE_IDENTITY_INVALID')
        cursor.execute('WITH evidence AS (' + EVIDENCE + ''')
            UPDATE app.shared_content_sharedidentityreservation i SET block_id=e.block_id
            FROM (SELECT DISTINCT id,block_id FROM evidence) e WHERE i.id=e.id''')
        cursor.execute("""UPDATE app.shared_content_sharedreceipt SET result_identity_kind=CASE action
            WHEN 'apply' THEN 'sharedrevision' WHEN 'draft' THEN 'shareddraft'
            WHEN 'restore_prepare' THEN 'sharedrestorestage' END WHERE result_id IS NOT NULL""")
        # Validate/flush deferred FK events before subsequent ALTER TABLE steps.
        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def reverse_preflight(apps, schema_editor):
    # This RunPython is the LAST forward step, hence FIRST on reversal.
    # Old 0001 has no result_id FK: a gone result alone does not prevent reversal.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('''SELECT 1 FROM (
            SELECT block_id,source_revision_id AS target FROM app.shared_content_sharedrevision
            UNION ALL SELECT block_id,source_revision_id FROM app.shared_content_sharedreceipt
            UNION ALL SELECT block_id,base_revision_id FROM app.shared_content_sharedreceipt
        ) p LEFT JOIN app.shared_content_sharedrevision r ON r.id=p.target AND r.block_id=p.block_id
        WHERE p.target IS NOT NULL AND r.id IS NULL LIMIT 1''')
        if cursor.fetchone():
            raise RuntimeError('SHARED_PROVENANCE_REVERSE_REQUIRES_LIVE_REVISION')


FORWARD = '''
    ALTER TABLE app.shared_content_sharedrevision DROP CONSTRAINT shared_source_same_block;
    ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_source_same_block;
    ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_base_same_block;
    ALTER TABLE app.shared_content_sharedrevision ADD CONSTRAINT shared_source_permanent_identity
        FOREIGN KEY(block_id,source_revision_id,source_identity_kind)
        REFERENCES app.shared_content_sharedidentityreservation(block_id,id,kind);
    ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_source_permanent_identity
        FOREIGN KEY(block_id,source_revision_id,source_identity_kind)
        REFERENCES app.shared_content_sharedidentityreservation(block_id,id,kind);
    ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_base_permanent_identity
        FOREIGN KEY(block_id,base_revision_id,base_identity_kind)
        REFERENCES app.shared_content_sharedidentityreservation(block_id,id,kind);
    ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_result_permanent_identity
        FOREIGN KEY(block_id,result_id,result_identity_kind)
        REFERENCES app.shared_content_sharedidentityreservation(block_id,id,kind);
'''
REVERSE = '''
    ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_result_permanent_identity;
    ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_base_permanent_identity;
    ALTER TABLE app.shared_content_sharedreceipt DROP CONSTRAINT shared_receipt_source_permanent_identity;
    ALTER TABLE app.shared_content_sharedrevision DROP CONSTRAINT shared_source_permanent_identity;
    ALTER TABLE app.shared_content_sharedrevision ADD CONSTRAINT shared_source_same_block
        FOREIGN KEY(block_id,source_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
    ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_source_same_block
        FOREIGN KEY(block_id,source_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
    ALTER TABLE app.shared_content_sharedreceipt ADD CONSTRAINT shared_receipt_base_same_block
        FOREIGN KEY(block_id,base_revision_id) REFERENCES app.shared_content_sharedrevision(block_id,id);
'''


class Migration(migrations.Migration):
    dependencies = [('shared_content', '0002_private_html_descriptors')]
    operations = [
        migrations.AddField(model_name='sharedidentityreservation', name='block',
            field=models.ForeignKey(to='shared_content.sharedblock', null=True, blank=True,
                related_name='identity_reservations', on_delete=django.db.models.deletion.PROTECT)),
        migrations.AddField(model_name='sharedrevision', name='source_identity_kind',
            field=models.CharField(max_length=32, default='sharedrevision', db_default='sharedrevision', editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='source_identity_kind',
            field=models.CharField(max_length=32, default='sharedrevision', db_default='sharedrevision', editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='base_identity_kind',
            field=models.CharField(max_length=32, default='sharedrevision', db_default='sharedrevision', editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='result_identity_kind',
            field=models.CharField(max_length=32, null=True, blank=True, editable=False)),
        migrations.RunPython(backfill, reverse_code=migrations.RunPython.noop),
        migrations.AddConstraint(model_name='sharedidentityreservation', constraint=models.UniqueConstraint(
            fields=['block','id','kind'], name='shared_identity_block_type')),
        migrations.AddConstraint(model_name='sharedrevision', constraint=models.CheckConstraint(
            condition=models.Q(source_identity_kind='sharedrevision'), name='shared_revision_source_type')),
        migrations.AddConstraint(model_name='sharedreceipt', constraint=models.CheckConstraint(
            condition=models.Q(source_identity_kind='sharedrevision'), name='shared_receipt_source_type')),
        migrations.AddConstraint(model_name='sharedreceipt', constraint=models.CheckConstraint(
            condition=models.Q(base_identity_kind='sharedrevision'), name='shared_receipt_base_type')),
        migrations.AddConstraint(model_name='sharedreceipt', constraint=models.CheckConstraint(condition=(
            models.Q(result_id__isnull=True, result_identity_kind__isnull=True)
            | (models.Q(result_id__isnull=False, result_identity_kind__isnull=False) & (models.Q(action='apply', result_identity_kind='sharedrevision')
                | models.Q(action='draft', result_identity_kind='shareddraft')
                | models.Q(action='restore_prepare', result_identity_kind='sharedrestorestage')))),
            name='shared_receipt_result_type')),
        migrations.RunSQL(FORWARD, reverse_sql=REVERSE),
        migrations.RunPython(migrations.RunPython.noop, reverse_code=reverse_preflight),
    ]
