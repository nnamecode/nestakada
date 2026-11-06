from django.db import migrations


FORWARD = """
    ALTER TABLE app.shared_content_sharedrevision
        DROP CONSTRAINT shared_source_permanent_identity;
    ALTER TABLE app.shared_content_sharedrevision
        ADD CONSTRAINT shared_source_same_block
        FOREIGN KEY(block_id, source_revision_id)
        REFERENCES app.shared_content_sharedrevision(block_id, id);
"""


REVERSE = """
    ALTER TABLE app.shared_content_sharedrevision
        DROP CONSTRAINT shared_source_same_block;
    ALTER TABLE app.shared_content_sharedrevision
        ADD CONSTRAINT shared_source_permanent_identity
        FOREIGN KEY(block_id, source_revision_id, source_identity_kind)
        REFERENCES app.shared_content_sharedidentityreservation(block_id, id, kind);
"""


def restore_legacy_identity_rows(apps, schema_editor):
    """Make a deliberate rollback possible after simple revisions were added."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO app.shared_content_sharedidentityreservation(id, kind, block_id)
            SELECT revision.id, 'sharedrevision', revision.block_id
            FROM app.shared_content_sharedrevision revision
            WHERE NOT EXISTS (
                SELECT 1
                FROM app.shared_content_sharedidentityreservation identity
                WHERE identity.id = revision.id
            )
        """)


class Migration(migrations.Migration):
    dependencies = [('shared_content', '0005_cleanup_jobs')]
    operations = [
        migrations.RunSQL(FORWARD, reverse_sql=REVERSE),
        migrations.RunPython(migrations.RunPython.noop, reverse_code=restore_legacy_identity_rows),
    ]
