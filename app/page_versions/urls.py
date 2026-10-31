from django.urls import path
from . import views

app_name='page_versions'
urlpatterns=[
    path('',views.history,name='history'),
    path('assets/versions.css',views.stylesheet,name='stylesheet'),
    path('manual/prepare/',views.manual_prepare,name='manual_prepare'),
    path('manual/create/',views.manual_create,name='manual_create'),
    path('draft/',views.owner_draft,name='owner_draft'),
    path('stages/<uuid:stage_id>/',views.stage_read,name='stage_read'),
    path('stages/<uuid:stage_id>/cancel/',views.stage_cancel,name='stage_cancel'),
    path('<uuid:version_id>/',views.read,name='read'),
    path('<uuid:version_id>/compare/',views.compare,name='compare'),
    path('<uuid:version_id>/files/<uuid:file_id>/',views.version_file,name='version_file'),
    path('<uuid:version_id>/metadata/',views.metadata_edit,name='metadata_edit'),
    path('<uuid:version_id>/stable/',views.stable_set,name='stable_set'),
    path('<uuid:version_id>/demote/prepare/',views.demote_prepare,name='demote_prepare'),
    path('<uuid:version_id>/demote/',views.demote,name='demote'),
    path('<uuid:version_id>/delete/prepare/',views.delete_prepare,name='delete_prepare'),
    path('<uuid:version_id>/delete/',views.delete,name='delete'),
    path('<uuid:version_id>/restore/prepare/',views.restore_prepare,name='restore_prepare'),
    path('<uuid:version_id>/restore/stage/',views.restore_stage,name='restore_stage'),
]
