"""TP1 test-only editor wiring. Never included by the product URLConf."""
from django.urls import include, path
from . import editor_page

urlpatterns = [
    path('manage/pages/<uuid:page_id>/edit/', include('page_editor.http_urls')),
    path('manage/editor-assets/<str:name>', editor_page.asset),
    path('', include('estakada.urls')),
]
