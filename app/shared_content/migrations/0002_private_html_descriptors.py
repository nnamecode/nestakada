from django.db import migrations, models


def descriptor_constraint(name):
    return models.CheckConstraint(condition=(
        models.Q(storage_kind='inline', file_key='', byte_size__isnull=True, file_sha256='')
        | models.Q(storage_kind='file', html='', file_key__regex=r'^blobs/([0-9a-f]{2})/\1[0-9a-f]{30}\.html$',
            byte_size__isnull=False, byte_size__gte=0, byte_size__lte=1048576,
            file_sha256__regex=r'^[0-9a-f]{64}$', payload_hash=models.F('file_sha256'))), name=name)


class Migration(migrations.Migration):
    dependencies = [('shared_content', '0001_initial')]
    operations = [
        migrations.AddField(model_name='sharedrevision', name='storage_kind',
            field=models.CharField(max_length=6, default='inline', db_default='inline')),
        migrations.AddField(model_name='sharedrevision', name='file_key',
            field=models.CharField(max_length=96, blank=True, default='', db_default='')),
        migrations.AddField(model_name='sharedrevision', name='byte_size',
            field=models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField(model_name='sharedrevision', name='file_sha256',
            field=models.CharField(max_length=64, blank=True, default='', db_default='')),
        migrations.AddField(model_name='shareddraft', name='storage_kind',
            field=models.CharField(max_length=6, default='inline', db_default='inline')),
        migrations.AddField(model_name='shareddraft', name='file_key',
            field=models.CharField(max_length=96, blank=True, default='', db_default='')),
        migrations.AddField(model_name='shareddraft', name='byte_size',
            field=models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField(model_name='shareddraft', name='file_sha256',
            field=models.CharField(max_length=64, blank=True, default='', db_default='')),
        migrations.AddConstraint(model_name='sharedrevision', constraint=descriptor_constraint('shared_revision_storage_descriptor')),
        migrations.AddConstraint(model_name='shareddraft', constraint=descriptor_constraint('shared_draft_storage_descriptor')),
    ]
