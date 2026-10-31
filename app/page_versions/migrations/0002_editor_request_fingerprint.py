from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('page_versions', '0001_initial')]
    operations = [migrations.AddField(model_name='operationreceipt',
        name='editor_request_fingerprint', field=models.CharField(blank=True, default='', max_length=64))]
