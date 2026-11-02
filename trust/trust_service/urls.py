from django.urls import path
from journal import views
urlpatterns = [path('v1/head', views.head), path('v1/snapshot', views.snapshot),
    path('v1/snapshot-manifest',views.snapshot_manifest),
    path('v1/operations/<uuid:operation_id>', views.operation),
    path('v1/prepare', views.prepare), path('v1/report-result', views.report),
    path('v1/recovery/fence',views.fence),path('v1/recovery/activate',views.activate)]
