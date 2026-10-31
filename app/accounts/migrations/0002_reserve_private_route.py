import uuid
from django.db import migrations


def reserve(apps, schema_editor):
    Route=apps.get_model('content','Route')
    existing=Route.objects.filter(target='/manage/').first()
    if existing is not None:
        if existing.kind!='system' or existing.page_id is not None:
            raise RuntimeError('AUTH_PRIVATE_NAMESPACE_OCCUPIED')
    else:
        Route.objects.create(id=uuid.uuid4(),target='/manage/',kind='system',page=None,is_legacy=False)


class Migration(migrations.Migration):
    dependencies=[('accounts','0001_initial'),('content','0001_initial')]
    operations=[migrations.RunPython(reserve,migrations.RunPython.noop)]
