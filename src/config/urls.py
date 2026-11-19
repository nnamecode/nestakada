from django.urls import URLPattern, path

from modules.accounts.web import login_view, logout_view
from modules.pages.web import page_editor_view, page_list_view, page_save_view, page_undo_view


urlpatterns: list[URLPattern] = [
    path("manage/login/", login_view, name="manage-login"),
    path("manage/logout/", logout_view, name="manage-logout"),
    path("manage/pages/", page_list_view, name="manage-pages"),
    path("manage/pages/<uuid:page_id>/", page_editor_view, name="manage-page-editor"),
    path("manage/pages/<uuid:page_id>/save/", page_save_view, name="manage-page-save"),
    path("manage/pages/<uuid:page_id>/undo/", page_undo_view, name="manage-page-undo"),
]
