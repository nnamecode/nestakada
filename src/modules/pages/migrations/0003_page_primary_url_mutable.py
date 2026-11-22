from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0002_sitesettings"),
    ]

    operations = [
        migrations.AddField(
            model_name="page",
            name="primary_url_mutable",
            field=models.BooleanField(default=False),
        ),
    ]
