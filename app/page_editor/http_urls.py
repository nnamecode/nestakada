from django.urls import path
from . import views
from . import editor_page

app_name = 'page_editor'
urlpatterns = [path('', editor_page.editor, name='editor'), path('state/', editor_page.state, name='state'),
               path('check/', views.check, name='check'), path('save/', views.save, name='save')]
