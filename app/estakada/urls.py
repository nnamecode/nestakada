from django.urls import include, path, re_path
from page_editor import editor_page
from content import public_views
from shared_content import public_views as shared_public_views

urlpatterns = [
    path('manage/pages/<uuid:page_id>/edit/',include('page_editor.http_urls')),
    path('manage/editor-assets/<str:name>',editor_page.asset),
    path('manage/shared/',include('shared_content.urls')),
    path('manage/media/',include('media_library.urls')),
    path('manage/pages/<uuid:page_id>/versions/',include('page_versions.urls')),
    path('manage/',include('accounts.urls')),
    path('static/public.css', public_views.stylesheet),
    path('static/public-gallery.js', public_views.gallery_script),
    path('static/public-home.js', public_views.home_script),
    path('sitemap.xml', public_views.sitemap),
    path('robots.txt', public_views.robots),
    path('static/shared/<str:digest>/<str:name>', shared_public_views.static_response),
    path('public-media/<uuid:file_id>/', shared_public_views.media_response),
    re_path(r'^(?!manage(?:/|$)).*$', public_views.page),
]
