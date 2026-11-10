"""Minimal anonymous public HTTP boundary."""
from pathlib import Path
from dataclasses import replace

from django.db import DatabaseError
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from shared_content.faults import SharedFault
from shared_content.public import render_shared
from shared_content.public_views import html_response

from .public_read import (PublicBlank, PublicNotFound, PublicPage, PublicRedirect,
                          PublicUnavailable, resolve_target)
from .public_body import PublicHeroBlock, PublicTextBlock, project_body
from .public_shared import PublicSharedHost


STYLESHEET = Path(__file__).with_name('public.css').read_bytes()
PUBLIC_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
              "img-src 'self'; base-uri 'none'; object-src 'none'; "
              "frame-ancestors 'none'")


def _media_url(file_id):
    return '/public-media/%s/' % file_id


def _static_url(name, digest):
    return '/static/shared/%s/%s' % (digest, name)


def _blank_response():
    response = HttpResponse(b'', content_type='text/html; charset=utf-8')
    response['Cache-Control'] = 'no-cache'
    response['Content-Security-Policy'] = PUBLIC_CSP
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _closed_response(status, message):
    response = HttpResponse(message, status=status, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['Content-Security-Policy'] = PUBLIC_CSP
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def stylesheet(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    response = HttpResponse(
        b'' if request.method == 'HEAD' else STYLESHEET,
        content_type='text/css; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def page(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    try:
        result = resolve_target(request.get_full_path())
    except PublicNotFound:
        return _closed_response(404, 'Страница не найдена.')
    except (PublicUnavailable, DatabaseError):
        return _closed_response(503, 'Страница временно недоступна.')
    if isinstance(result, PublicBlank):
        return _blank_response()
    if isinstance(result, PublicRedirect):
        response = HttpResponsePermanentRedirect(result.location)
    elif isinstance(result, PublicPage):
        try:
            host = PublicSharedHost(request.get_full_path())
            emitted_static = {}

            def selected_static(name, digest):
                emitted_static[name] = _static_url(name, digest)
                return emitted_static[name]

            rendered = render_shared(
                capture_host=host.capture,
                media_url=_media_url,
                static_url=selected_static)
            current, _navigation, breadcrumbs, media = host.body()
            body_blocks = tuple(
                replace(block, html=mark_safe(block.html))
                if isinstance(block, (PublicTextBlock, PublicHeroBlock)) else block
                for block in project_body(current, media))
            body = render_to_string('content/public_page.html', {
                'page': current,
                'breadcrumbs': breadcrumbs,
                'body_blocks': body_blocks,
                'header_html': mark_safe(rendered.header_html),
                'footer_html': mark_safe(rendered.footer_html),
                'shared_stylesheet': emitted_static['public-shared.css'],
                'shared_script': emitted_static['public-shared.js'],
            }).encode()
            response = html_response(request, rendered, body)
            response['Content-Security-Policy'] = PUBLIC_CSP
            return response
        except (SharedFault, PublicNotFound, PublicUnavailable, DatabaseError,
                KeyError, TypeError, ValueError):
            return _closed_response(503, 'Страница временно недоступна.')
    else:
        return _closed_response(503, 'Страница временно недоступна.')
    response['Cache-Control'] = 'no-cache'
    return response
