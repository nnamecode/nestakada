from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('shared_content', '0003_permanent_provenance')]
    operations = [
        migrations.AddField(model_name='sharedreceipt', name='result_revision',
            field=models.PositiveBigIntegerField(null=True, blank=True, editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='source_stamp',
            field=models.CharField(max_length=64, blank=True, default='', db_default='', editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='reservation_profile',
            field=models.CharField(max_length=32, blank=True, default='', db_default='', editable=False)),
        migrations.AddField(model_name='sharedreceipt', name='reservation_book_sha256',
            field=models.CharField(max_length=64, blank=True, default='', db_default='', editable=False)),
        migrations.AddField(model_name='sharedbudget', name='retained_debt_bytes',
            field=models.PositiveBigIntegerField(default=0, db_default=0)),
        migrations.AddConstraint(model_name='sharedreceipt', constraint=models.CheckConstraint(
            condition=(models.Q(result_revision__isnull=True) | models.Q(result_revision__gte=1,
                action='draft', result_code='applied', result_id__isnull=False)), name='shared_receipt_draft_counter')),
        migrations.AddConstraint(model_name='sharedreceipt', constraint=models.CheckConstraint(condition=(
            models.Q(source_stamp='', reservation_profile='', reservation_book_sha256='')
            | models.Q(source_stamp__regex=r'^[0-9a-f]{64}$', reservation_profile__regex=r'^[a-z][a-z0-9-]{0,31}$',
                reservation_book_sha256__regex=r'^[0-9a-f]{64}$')), name='shared_receipt_reservation_binding')),
    ]
