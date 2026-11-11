"""Django startup checks for the closed public SEO configuration."""
from django.core.checks import Error, register

from .public_seo import SeoUnavailable, load_configuration


@register()
def check_public_seo_configuration(app_configs, **kwargs):
    del app_configs, kwargs
    try:
        load_configuration()
    except SeoUnavailable:
        return [Error(
            'Public SEO configuration is missing or invalid.',
            hint=('Set PUBLIC_ORIGIN and SEO_ROBOTS_PROFILE to an approved '
                  'environment-specific pair.'),
            id='content.E001',
        )]
    return []
