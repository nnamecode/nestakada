from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from content.models import Page

class UserProfile(models.Model):
    class Role(models.TextChoices):
        OWNER = 'owner'
        EMPLOYEE = 'employee'
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='security_profile')
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.EMPLOYEE)
    generation = models.PositiveBigIntegerField(default=1)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(role__in=['owner','employee']), name='accounts_known_role'),
            models.CheckConstraint(condition=Q(generation__gte=1), name='accounts_positive_generation'),
            models.UniqueConstraint(fields=['role'], condition=Q(role='owner'), name='accounts_single_owner'),
        ]
    def clean(self):
        if self.role == self.Role.OWNER and self.user.username != 'nesadmin':
            raise ValidationError('AUTH_OWNER_IDENTITY_REQUIRED')
    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

class PageGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='page_grants')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='employee_grants')
    intro_text = models.BooleanField(default=False)
    main_text = models.BooleanField(default=False)
    price = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','page'], name='accounts_unique_page_grant')]
    def clean(self):
        if self.page.kind not in (Page.Kind.SERVICE, Page.Kind.ARTICLE, Page.Kind.NEWS_ARTICLE, Page.Kind.WASH):
            raise ValidationError('AUTH_PAGE_NOT_ASSIGNABLE')
        if not UserProfile.objects.filter(user_id=self.user_id, role='employee').exists():
            raise ValidationError('AUTH_EMPLOYEE_REQUIRED')
    def save(self, *args, **kwargs):
        self.full_clean(validate_unique=False, validate_constraints=False)
        return super().save(*args, **kwargs)

class AuthSession(models.Model):
    session_key = models.CharField(max_length=40, primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    generation = models.PositiveBigIntegerField()
    issued_at = models.DateTimeField()
    last_seen = models.DateTimeField(db_index=True)
    denied_owner_count = models.PositiveBigIntegerField(default=0)
    denied_page_count = models.PositiveBigIntegerField(default=0)
    denial_count_lower_bound = models.BooleanField(default=False)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(generation__gte=1), name='accounts_session_generation')]

class LoginThrottle(models.Model):
    ip_address = models.GenericIPAddressField(primary_key=True, unpack_ipv4=True)
    failure_times = models.JSONField(default=list)
    blocked_until = models.DateTimeField(null=True, blank=True)
    last_request_id = models.UUIDField(null=True, blank=True)
    last_seen = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)
    blocked_repeats = models.PositiveBigIntegerField(default=0)
    repeat_count_lower_bound = models.BooleanField(default=False)
    failure_count_total = models.PositiveBigIntegerField(default=0)
    failure_count_lower_bound = models.BooleanField(default=False)
    @property
    def failed_count(self):
        return len(self.failure_times)

class AuthResourceState(models.Model):
    kind = models.CharField(max_length=16, primary_key=True, choices=[('throttle','throttle'),('sessions','sessions')])
    full = models.BooleanField(default=False)
    class Meta:
        constraints = [models.CheckConstraint(condition=Q(kind__in=['throttle','sessions']), name='accounts_known_resource')]
