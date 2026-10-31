import django.core.validators
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("event_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("occurred_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("category", models.CharField(choices=[("access", "Вход и доступ"), ("security", "Безопасность"), ("user_actions", "Действия пользователей"), ("site_errors", "Ошибки сайта"), ("pages_links", "Страницы и ссылки"), ("environment", "Обновления и окружение"), ("backup_maintenance", "Резервирование и обслуживание"), ("performance_integrations", "Производительность и внешние связи"), ("service", "Другие / служебные")], max_length=32)),
                ("level", models.CharField(choices=[("INFO", "INFO"), ("WARNING", "WARNING"), ("ERROR", "ERROR"), ("CRITICAL", "CRITICAL")], max_length=8)),
                ("code", models.CharField(max_length=64, validators=[django.core.validators.RegexValidator("^[A-Z][A-Z0-9_-]{0,63}\\Z", "AUDIT_INVALID_CODE")])),
                ("source", models.CharField(choices=[("application", "Приложение"), ("database", "Основная БД"), ("html_reserve", "HTML-резерв"), ("remote_backup", "Внешние копии"), ("file_logs", "Файловые логи"), ("notification", "Транспорт уведомлений"), ("published_route", "Опубликованный маршрут")], max_length=32)),
                ("result", models.CharField(choices=[("SUCCESS", "Успех"), ("FAILURE", "Отказ"), ("DENIED", "Запрещено"), ("PENDING", "Не завершено"), ("UNKNOWN", "Исход неизвестен")], max_length=8)),
                ("actor_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("object_kind", models.CharField(blank=True, default="", max_length=32, validators=[django.core.validators.RegexValidator("^[a-z][a-z0-9_]{0,31}\\Z", "AUDIT_INVALID_OBJECT_KIND")])),
                ("object_ref", models.CharField(blank=True, default="", max_length=41, validators=[django.core.validators.RegexValidator("^(id:[1-9][0-9]{0,18}|uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\\Z", "AUDIT_INVALID_REFERENCE")])),
                ("request_id", models.UUIDField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, unpack_ipv4=True)),
            ],
            options={
                "ordering": ["id"],
                "indexes": [models.Index(fields=["category", "id"], name="audit_category_id_idx"), models.Index(fields=["occurred_at", "id"], name="audit_time_id_idx")],
                "constraints": [
                    models.CheckConstraint(condition=models.Q(category__in=["access", "security", "user_actions", "site_errors", "pages_links", "environment", "backup_maintenance", "performance_integrations", "service"]), name="audit_known_category"),
                    models.CheckConstraint(condition=models.Q(level__in=["INFO", "WARNING", "ERROR", "CRITICAL"]), name="audit_known_level"),
                    models.CheckConstraint(condition=models.Q(source__in=["application", "database", "html_reserve", "remote_backup", "file_logs", "notification", "published_route"]), name="audit_known_source"),
                    models.CheckConstraint(condition=models.Q(result__in=["SUCCESS", "FAILURE", "DENIED", "PENDING", "UNKNOWN"]), name="audit_known_result"),
                    models.CheckConstraint(condition=models.Q(actor_id__isnull=True) | models.Q(actor_id__gt=0), name="audit_positive_actor"),
                    models.CheckConstraint(condition=models.Q(object_ref="") | ~models.Q(object_kind=""), name="audit_object_kind_required"),
                ],
            },
        ),
    ]
