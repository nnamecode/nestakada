"""QA-only public host. Never included by the production URLConf.

This synthetic host projects every published fixture Page/PRIMARY Route. That
test selection is not the future production navigation or Page resolver.
"""
import hashlib
import json
from html import escape

from django.urls import include, path
from django.views.decorators.http import require_safe

from content.models import Route
from content.reads import public_tree
from .faults import SharedFault

HOST_BODY = '<main id="shared-test-body"><h1>Shared renderer QA host</h1></main>'


def media_url(file_id):
    return '/__shared_public__/media/%s/' % file_id


def static_url(name, digest):
    return '/__shared_public__/static/%s/%s/' % (digest, name)


def capture_host():
    from .public import HostContext, NavItem
    tree = public_tree()
    primary = dict(Route.objects.filter(kind=Route.Kind.PRIMARY,
        page_id__in=[row['id'] for row in tree]).values_list('page_id', 'target'))
    navigation = tuple(NavItem(row['name'], primary[row['id']]) for row in tree)
    # The synthetic body is immutable. A real DEV-08 host must bind its own body.
    stamp = hashlib.sha256(json.dumps([HOST_BODY,
        [[str(row['id']), row['name'], primary[row['id']]] for row in tree]],
        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return HostContext(stamp, navigation)


@require_safe
def host(request):
    from .public import render_shared
    from .public_views import html_response, unavailable_response
    try:
        emitted_static = {}
        def selected_static(name, digest):
            emitted_static[name] = static_url(name, digest)
            return emitted_static[name]
        rendered = render_shared(capture_host=capture_host, media_url=media_url, static_url=selected_static)
        body = ('<!doctype html><html lang="ru"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="stylesheet" href="' + escape(emitted_static['public-shared.css'], quote=True) + '">'
            '<script defer src="' + escape(emitted_static['public-shared.js'], quote=True) + '"></script>'
            '</head><body>' + rendered.header_html + HOST_BODY + rendered.footer_html + '</body></html>').encode()
        response = html_response(request, rendered, body)
    except (SharedFault, KeyError, ValueError):
        response = unavailable_response()
    response['Content-Security-Policy'] = ("default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'")
    return response


def media(request, file_id):
    from .public_views import media_response
    return media_response(request, file_id)


def static(request, digest, name):
    from .public_views import static_response
    return static_response(request, name, digest)


urlpatterns = [
    path('__shared_public__/', host, name='shared-public-test-host'),
    path('__shared_public__/media/<uuid:file_id>/', media, name='shared-public-test-media'),
    path('__shared_public__/static/<str:digest>/<str:name>/', static, name='shared-public-test-static'),
    path('', include('estakada.urls')),
]
