from django.urls import path

from . import views


app_name = 'service_requests'
urlpatterns = [
    path('', views.request_list, name='list'),
    path('settings/', views.request_settings, name='settings'),
    path('<uuid:request_id>/delete/', views.request_delete, name='delete'),
    path('<uuid:request_id>/', views.request_detail, name='detail'),
]
