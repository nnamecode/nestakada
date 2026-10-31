from django.urls import include, path

urlpatterns = [
    path('manage/media/',include('media_library.urls')),
    path('manage/pages/<uuid:page_id>/versions/',include('page_versions.urls')),
    path('manage/',include('accounts.urls')),
]
