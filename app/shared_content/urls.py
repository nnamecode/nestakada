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
    path('<str:kind>/compare/', views.compare, name='compare'),
    path('<str:kind>/restore/prepare/', views.restore_prepare, name='restore_prepare'),
    path('<str:kind>/stages/<uuid:stage_id>/cancel/', views.restore_cancel, name='restore_cancel'),
    path('<str:kind>/result/<uuid:operation_id>/', views.result, name='result'),
    path('<str:kind>/cleanup/<uuid:version_id>/', views.cleanup_preview, name='cleanup_preview'),
    path('<str:kind>/cleanup/jobs/<uuid:operation_id>/', views.cleanup_status, name='cleanup_status'),
    path('<str:kind>/cleanup/jobs/<uuid:operation_id>/resume/', views.cleanup_resume, name='cleanup_resume'),
    path('<str:kind>/diagnostics/<uuid:operation_id>/', views.diagnostics, name='diagnostics'),
    path('<str:kind>/diagnostics/<uuid:operation_id>/reconcile/', views.diagnostic_reconcile, name='diagnostic_reconcile'),
]
