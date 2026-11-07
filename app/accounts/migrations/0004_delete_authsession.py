from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_loginthrottle_failure_count_lower_bound_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='AuthSession',
        ),
    ]
