"""Approved D-102 categories and technical field vocabulary, not business flows."""
from django.db.models import TextChoices


class Category(TextChoices):
    ACCESS = "access", "Вход и доступ"
    SECURITY = "security", "Безопасность"
    USER_ACTIONS = "user_actions", "Действия пользователей"
    SITE_ERRORS = "site_errors", "Ошибки сайта"
    PAGES_LINKS = "pages_links", "Страницы и ссылки"
    ENVIRONMENT = "environment", "Обновления и окружение"
    BACKUP_MAINTENANCE = "backup_maintenance", "Резервирование и обслуживание"
    PERFORMANCE_INTEGRATIONS = "performance_integrations", "Производительность и внешние связи"
    SERVICE = "service", "Другие / служебные"


class Level(TextChoices):
    INFO = "INFO", "INFO"
    WARNING = "WARNING", "WARNING"
    ERROR = "ERROR", "ERROR"
    CRITICAL = "CRITICAL", "CRITICAL"


class Source(TextChoices):
    APPLICATION = "application", "Приложение"
    DATABASE = "database", "Основная БД"
    HTML_RESERVE = "html_reserve", "HTML-резерв"
    REMOTE_BACKUP = "remote_backup", "Внешние копии"
    FILE_LOGS = "file_logs", "Файловые логи"
    NOTIFICATION = "notification", "Транспорт уведомлений"
    PUBLISHED_ROUTE = "published_route", "Опубликованный маршрут"


class Result(TextChoices):
    SUCCESS = "SUCCESS", "Успех"
    FAILURE = "FAILURE", "Отказ"
    DENIED = "DENIED", "Запрещено"
    PENDING = "PENDING", "Не завершено"
    UNKNOWN = "UNKNOWN", "Исход неизвестен"


CODE_PATTERN = r"^[A-Z][A-Z0-9_-]{0,63}\Z"
KIND_PATTERN = r"^[a-z][a-z0-9_]{0,31}\Z"
REFERENCE_PATTERN = (
    r"^(id:[1-9][0-9]{0,18}|uuid:[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\Z"
)
