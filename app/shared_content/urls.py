from django.urls import path
from . import views

app_name = 'shared_content'
urlpatterns = [
    path('assets/<str:name>', views.asset, name='asset'),
    path('<str:kind>/edit/', views.editor, name='editor'),
    path('<str:kind>/check/', views.check, name='check'),
    path('<str:kind>/draft/', views.draft, name='draft'),
    path('<str:kind>/apply/', views.apply, name='apply'),
    path('<str:kind>/history/', views.history, name='history'),
    path('<str:kind>/versions/<uuid:version_id>/', views.version, name='version'),
    path('<str:kind>/versions/<uuid:version_id>/restore/', views.restore_version, name='restore_version'),
    path('<str:kind>/compare/', views.compare, name='compare'),
]
