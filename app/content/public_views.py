"""Minimal anonymous public HTTP boundary."""
from pathlib import Path
from dataclasses import replace

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.http import (HttpResponse, HttpResponsePermanentRedirect,
                         HttpResponseRedirect)
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from shared_content.faults import SharedFault
from shared_content.public import render_shared
from shared_content.public_views import html_response
from service_requests.public import disabled_form_for, form_for

from .public_read import (PublicBlank, PublicNotFound, PublicPage, PublicRedirect,
                          PublicUnavailable, resolve_target)
from .public_body import PublicHeroBlock, PublicTextBlock, project_body
from .public_gallery import page1_redirect_target, parse_gallery_target
from .public_seo import (AutoRepairPage, SeoPage, SeoUnavailable,
                         build_auto_repair, capture_sitemap, hidden_robots,
                         load_configuration,
                         project_page_seo, project_seo_image, robots_text,
                         serialize_auto_repair, sitemap_xml)
from .public_shared import PublicSharedHost
from .models import Route


STYLESHEET = Path(__file__).with_name('public.css').read_bytes()
GALLERY_SCRIPT = Path(__file__).with_name('public-gallery.js').read_bytes()
HOME_SCRIPT = Path(__file__).with_name('public-home.js').read_bytes()
PUBLIC_CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; "
              "img-src 'self'; base-uri 'none'; object-src 'none'; "
              "frame-ancestors 'none'; form-action 'self'")
_RESERVE_RENDER = object()


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


def gallery_script(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    response = HttpResponse(
        b'' if request.method == 'HEAD' else GALLERY_SCRIPT,
        content_type='text/javascript; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def home_script(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    response = HttpResponse(
        b'' if request.method == 'HEAD' else HOME_SCRIPT,
        content_type='text/javascript; charset=utf-8')
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _home_media(projection, media):
    if projection is None:
        return None
    value = projection['profile']
    for item in [value['hero'], value['photo_strip'], *value['steps'],
                 *value['services'], *value['works']]:
        file_id = media.get('embedded:' + item['image_id'])
        if file_id is None:
            raise PublicUnavailable()
        item['src'] = _media_url(file_id)
    return value


def _sitemap_boundary():
    pass


def _auto_repair_inputs(_page):
    # DEV-12/CONTACT-01 will provide coherent confirmed visible facts.
    return None, None


def sitemap(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    try:
        configuration = load_configuration()
        with transaction.atomic():
            first = capture_sitemap(configuration)
        body = sitemap_xml(first)
        _sitemap_boundary()
        with transaction.atomic():
            second = capture_sitemap(configuration)
        if second.stamp != first.stamp:
            raise SeoUnavailable()
        response = HttpResponse(
            b'' if request.method == 'HEAD' else body,
            content_type='application/xml; charset=utf-8')
        response['Content-Length'] = str(len(body))
        response['Cache-Control'] = 'no-cache'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except (SeoUnavailable, DatabaseError, ValidationError, TypeError,
            ValueError, AttributeError):
        return _closed_response(503, 'Карта сайта временно недоступна.')


def robots(request):
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    try:
        body = robots_text(load_configuration())
    except (SeoUnavailable, TypeError, ValueError, AttributeError):
        return _closed_response(503, 'robots.txt временно недоступен.')
    response = HttpResponse(
        b'' if request.method == 'HEAD' else body,
        content_type='text/plain; charset=utf-8')
    response['Content-Length'] = str(len(body))
    response['Cache-Control'] = 'no-cache'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _page(request, reserve_context=None):
    if reserve_context not in (None, _RESERVE_RENDER):
        return _closed_response(503, 'Страница временно недоступна.')
    if request.method not in ('GET', 'HEAD'):
        response = _closed_response(405, '')
        response['Allow'] = 'GET, HEAD'
        return response
    target = request.get_full_path()
    redirect = page1_redirect_target(target)
    if redirect is not None:
        response = HttpResponseRedirect(redirect)
        response['Cache-Control'] = 'no-cache'
        return response
    try:
        gallery_request = parse_gallery_target(target)
        result = resolve_target(
            gallery_request.base_target if gallery_request is not None
            else target)
        if (gallery_request is not None
                and gallery_request.selected_target is not None
                and isinstance(result, PublicPage)
                and not Route.objects.filter(
                    target=gallery_request.selected_target,
                    kind=Route.Kind.PRIMARY, page__parent_id=result.page_id,
                    page__is_published=True).exists()):
            raise PublicNotFound()
    except PublicNotFound:
        return _closed_response(404, 'Страница не найдена.')
    except (PublicUnavailable, DatabaseError):
        return _closed_response(503, 'Страница временно недоступна.')
    if isinstance(result, PublicBlank):
        response = _blank_response()
        response['X-Robots-Tag'] = hidden_robots()
        return response
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
            gallery = host.gallery_body()
            home = _home_media(host.home_body(), media)
            seo_media, wash_peer_eligible = host.seo_body()
            seo_configuration = load_configuration()
            seo_image = (None if seo_media is None else project_seo_image(
                seo_configuration, page_id=current.page_id,
                file_id=seo_media.file_id, slot=seo_media.slot,
                alt=seo_media.alt))
            seo = project_page_seo(seo_configuration, SeoPage(
                request_target=request.get_full_path(),
                route_kind=current.route_kind,
                page_kind=current.page_kind,
                name=current.name,
                title=current.payload['title'],
                description=current.payload['description'],
                indexing_allowed=current.payload['indexing_allowed'],
                wash_peer_eligible=wash_peer_eligible), seo_image)
            auto_profile, visible_facts = _auto_repair_inputs(current)
            auto_node = build_auto_repair(
                auto_profile, visible_facts,
                AutoRepairPage(
                    page_kind=current.page_kind, published=True,
                    indexing_allowed=current.payload['indexing_allowed']),
                seo_configuration)
            auto_repair_json = (None if auto_node is None else mark_safe(
                serialize_auto_repair(auto_node)))
            request_form = (disabled_form_for(current.target)
                            if reserve_context is _RESERVE_RENDER
                            else form_for(request, current.target))
            body_blocks = tuple(
                replace(block, html=mark_safe(block.html))
                if isinstance(block, (PublicTextBlock, PublicHeroBlock)) else block
                for block in project_body(current, media))
            body = render_to_string('content/public_page.html', {
                'page': current,
                'breadcrumbs': breadcrumbs,
                'body_blocks': body_blocks,
                'gallery': gallery,
                'home': home,
                'gallery_selected_text': (
                    mark_safe(gallery.selected.main_text)
                    if gallery is not None and gallery.selected is not None
                    else None),
                'seo': seo,
                'auto_repair_json': auto_repair_json,
                'service_request_form': request_form,
                'header_html': mark_safe(rendered.header_html),
                'footer_html': mark_safe(rendered.footer_html),
                'shared_stylesheet': emitted_static['public-shared.css'],
                'shared_script': emitted_static['public-shared.js'],
            }).encode()
            response = html_response(
                request, rendered, body,
                private_dynamic=bool(request_form and request_form['enabled']))
            response['Content-Security-Policy'] = PUBLIC_CSP
            if seo.robots is not None:
                response['X-Robots-Tag'] = seo.robots
            return response
        except (SharedFault, PublicNotFound, PublicUnavailable, DatabaseError,
                KeyError, TypeError, ValueError, ValidationError, SeoUnavailable):
            return _closed_response(503, 'Страница временно недоступна.')
    else:
        return _closed_response(503, 'Страница временно недоступна.')
    response['Cache-Control'] = 'no-cache'
    return response


def page(request):
    return _page(request)


def render_reserve(request):
    """Trusted Python-only entry; no URL can select the reserve context."""
    return _page(request, _RESERVE_RENDER)
