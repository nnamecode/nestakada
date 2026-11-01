from django.urls import include, path
from page_editor import editor_page

urlpatterns = [
    path('manage/pages/<uuid:page_id>/edit/',include('page_editor.http_urls')),
    path('manage/editor-assets/<str:name>',editor_page.asset),
    path('manage/shared/',include('shared_content.urls')),
    path('manage/media/',include('media_library.urls')),
    path('manage/pages/<uuid:page_id>/versions/',include('page_versions.urls')),
    path('manage/',include('accounts.urls')),
]
