from django.urls import path
from . import views

app_name='media_library'
urlpatterns=[
    path('assets/media.css',views.stylesheet,name='stylesheet'),
    path('',views.catalog,name='catalog'),
    path('pages/<uuid:page_id>/upload/',views.upload_view,name='upload'),
    path('files/<uuid:file_id>/',views.preview,name='preview'),
    path('cleanup/',views.cleanup_catalog,name='cleanup'),
    path('cleanup/prepare/',views.cleanup_prepare,name='cleanup_prepare'),
    path('cleanup/confirm/',views.cleanup_confirm,name='cleanup_confirm'),
    path('cleanup/<uuid:asset_id>/retry/',views.cleanup_retry,name='cleanup_retry'),
]
