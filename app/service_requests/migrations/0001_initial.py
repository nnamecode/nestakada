import uuid

from django.db import migrations, models
class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RequestSettings',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('recipient_email', models.EmailField(blank=True, max_length=254)),
            ],
            options={
                'constraints': [
                    models.CheckConstraint(condition=models.Q(('id', 1)), name='request_settings_singleton'),
                ],
            },
        ),
        migrations.CreateModel(
            name='ServiceRequest',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('source', models.CharField(choices=[('home', 'Главная'), ('contacts', 'Контакты')], max_length=16)),
                ('name', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=12)),
                ('car', models.CharField(blank=True, max_length=300)),
                ('comment', models.CharField(blank=True, max_length=4000)),
                ('consent_version', models.CharField(max_length=64)),
                ('intent_digest', models.CharField(editable=False, max_length=64, unique=True)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
                'indexes': [models.Index(fields=['-created_at', '-id'], name='request_created_id_idx')],
                'constraints': [
                    models.CheckConstraint(condition=models.Q(('source__in', ['home', 'contacts'])), name='request_known_source'),
                    models.CheckConstraint(condition=models.Q(('name', ''), _negated=True), name='request_name_nonempty'),
                    models.CheckConstraint(condition=models.Q(('phone__regex', r'^\+7[0-9]{10}$')), name='request_phone_canonical'),
                    models.CheckConstraint(condition=models.Q(('consent_version', ''), _negated=True), name='request_consent_nonempty'),
                    models.CheckConstraint(condition=models.Q(('intent_digest__regex', r'^[0-9a-f]{64}$')), name='request_intent_digest'),
                ],
            },
        ),
    ]
