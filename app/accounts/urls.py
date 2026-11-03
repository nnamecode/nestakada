from django.urls import path
from . import views
from content.tree_views import command as tree_command
from content.creation_views import create_page
app_name='accounts'
urlpatterns=[
    path('',views.dashboard,name='dashboard'),
    path('login/',views.login_view,name='login'),
    path('logout/',views.logout_view,name='logout'),
    path('session/',views.session_state,name='session'),
    path('assets/manage.css',views.stylesheet,name='stylesheet'),
    path('pages/',views.page_tree,name='page-tree'),
    path('pages/new/',create_page,name='page-create'),
    path('pages/<uuid:page_id>/structure/<str:action>/',tree_command,name='tree-command'),
    path('employees/',views.employees,name='employees'),
    path('employees/<int:user_id>/password/',views.employee_password,name='employee-password'),
    path('employees/<int:user_id>/active/',views.employee_active,name='employee-active'),
    path('employees/<int:user_id>/grants/',views.employee_grant,name='employee-grant'),
    path('pages/<uuid:page_id>/',views.assigned_page,name='page-access'),
]
