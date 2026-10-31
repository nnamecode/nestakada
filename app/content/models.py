"""Internal storage invariants; owner operations and external head are DEV-29."""
import uuid
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Max
from .validators import exact_target, new_target

# PR-08: acquire before any content row lock in future domain commands.
CONTENT_LOCK = 7342810401


def lock_content(using):
    from django.db import connections
    with connections[using].cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [CONTENT_LOCK])


class ProtectedQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('CONTENT_USE_VALIDATED_SAVE')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('CONTENT_USE_VALIDATED_SAVE')

    def bulk_create(self, *args, **kwargs):
        raise ValidationError('CONTENT_USE_VALIDATED_SAVE')

    def delete(self):
        raise ValidationError('CONTENT_DELETE_REQUIRES_DEV29')


class IdentityModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    objects = ProtectedQuerySet.as_manager()

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_id = str(self.pk)

    def delete(self, *args, **kwargs):
        raise ValidationError('CONTENT_DELETE_REQUIRES_DEV29')

    def save(self, *args, **kwargs):
        if args or str(self.pk) != self._original_id or kwargs.get('force_update'):
            raise ValidationError('CONTENT_IDENTITY_IMMUTABLE')
        if kwargs.get('update_fields') is not None:
            raise ValidationError('CONTENT_PARTIAL_SAVE_FORBIDDEN')
        using = kwargs.get('using') or self._state.db or 'default'
        with transaction.atomic(using=using):
            lock_content(using)
            self.prepare_save(using)
            self.full_clean(validate_unique=False, validate_constraints=False)
            if self._state.adding:
                kwargs['force_insert'] = True
            else:
                kwargs['force_update'] = True
            return super().save(**kwargs)

    def prepare_save(self, using):
        pass


class Page(IdentityModel):
    class Kind(models.TextChoices):
        HOME = 'home'
        SERVICE = 'service_detail'
        SERVICE_CATALOG = 'service_catalog'
        SERVICE_SECTION = 'service_section_overview'
        SERVICES = 'services_master_catalog'
        ARTICLE = 'article'
        ARTICLES = 'articles_catalog'
        CONTACTS = 'contacts'
        REVIEWS = 'reviews'
        ACTIONS = 'actions'
        GALLERY = 'gallery_catalog'
        ALBUM = 'gallery_album'
        PARTNERS = 'legacy_partner_links'
        DIRECTOR = 'legacy_director_message'
        NEWS_ARTICLE = 'legacy_news_article'
        EMPTY = 'legacy_empty_main'
        NEWS = 'legacy_news_catalog'
        WASH = 'service_wash_legacy_alias'
        CONSTRUCTION = 'legacy_under_construction'
        CAMERA = 'legacy_camera_schedule_text'

    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    position = models.PositiveBigIntegerField()
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['position', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=['home','service_detail','service_catalog','service_section_overview','services_master_catalog','article','articles_catalog','contacts','reviews','actions','gallery_catalog','gallery_album','legacy_partner_links','legacy_director_message','legacy_news_article','legacy_empty_main','legacy_news_catalog','service_wash_legacy_alias','legacy_under_construction','legacy_camera_schedule_text']), name='content_known_page_kind'),
            models.CheckConstraint(condition=~Q(parent=models.F('id')), name='content_no_self_parent'),
            models.CheckConstraint(condition=Q(position__gte=0), name='content_nonnegative_position'),
            models.UniqueConstraint(fields=['parent', 'position'], nulls_distinct=False,
                                    deferrable=models.Deferrable.DEFERRED, name='content_sibling_position'),
        ]

    def prepare_save(self, using):
        if self._state.adding and self.position is None:
            last = Page.objects.using(using).filter(parent_id=self.parent_id).aggregate(value=Max('position'))['value']
            self.position = 0 if last is None else last + 1

    def clean(self):
        if not isinstance(self.name, str) or not self.name.strip() or any(ord(c) < 32 or ord(c) == 127 for c in self.name):
            raise ValidationError('PAGE_INVALID_NAME')
        seen = {self.pk}
        ancestor = self.parent_id
        using = self._state.db or 'default'
        while ancestor is not None:
            if ancestor in seen:
                raise ValidationError('PAGE_TREE_CYCLE')
            seen.add(ancestor)
            row = Page.objects.using(using).filter(pk=ancestor).values_list('parent_id', flat=True).first()
            ancestor = row


class Route(IdentityModel):
    class Kind(models.TextChoices):
        PRIMARY = 'primary'
        ALIAS = 'alias'
        REDIRECT = 'redirect'
        SYSTEM = 'system'

    target = models.CharField(max_length=2048, unique=True, db_collation='C', validators=[exact_target])
    kind = models.CharField(max_length=16, choices=Kind.choices)
    page = models.ForeignKey(Page, null=True, blank=True, on_delete=models.PROTECT, related_name='routes')
    is_legacy = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=['primary', 'alias', 'redirect', 'system']), name='content_known_route_kind'),
            models.CheckConstraint(condition=(Q(kind='system', page__isnull=True) | (~Q(kind='system') & Q(page__isnull=False))), name='content_route_page_required'),
            models.CheckConstraint(condition=~Q(kind='redirect', is_legacy=True), name='content_legacy_not_redirect'),
            models.UniqueConstraint(fields=['page'], condition=Q(kind='primary'), name='content_one_primary_per_page'),
        ]

    def prepare_save(self, using):
        old = Route.objects.using(using).filter(pk=self.pk).values('target', 'is_legacy', 'kind', 'page_id').first()
        if old and old['is_legacy'] and any(old[k] != getattr(self, k) for k in old):
            raise ValidationError('ROUTE_LEGACY_IMMUTABLE')

    def clean(self):
        from django.conf import settings
        prefix = getattr(settings,'PRIVATE_ROUTE_PREFIX','/manage/')
        path = self.target.split('?',1)[0]
        if self.kind != self.Kind.SYSTEM and (path == prefix.rstrip('/') or path.startswith(prefix)):
            raise ValidationError('ROUTE_RESERVED_NAMESPACE')
        if not self.is_legacy and self.kind != self.Kind.SYSTEM:
            new_target(self.target)
        if self.is_legacy and self.kind == self.Kind.REDIRECT:
            raise ValidationError('ROUTE_LEGACY_NOT_REDIRECT')
