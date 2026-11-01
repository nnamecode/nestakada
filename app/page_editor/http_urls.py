from django.urls import path
from . import views
from . import editor_page
from . import media_views
from . import embedded_views

app_name = 'page_editor'
urlpatterns = [path('', editor_page.editor, name='editor'), path('state/', editor_page.state, name='state'),
               path('check/', views.check, name='check'), path('save/', views.save, name='save'),
               path('draft/', views.draft, name='draft'), path('draft/cancel/', views.cancel_draft, name='cancel_draft'),
               path('media/', media_views.picker, name='media_picker'),
               path('media/files/<uuid:file_id>/', media_views.contextual_file, name='media_file'),
               path('media/picker-files/<uuid:file_id>/', media_views.picker_file, name='media_picker_file')]
urlpatterns.append(path('embedded/issue/', embedded_views.issue, name='embedded_issue'))
