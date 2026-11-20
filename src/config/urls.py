from django.urls import URLPattern, path

from modules.accounts.web import (
    login_view,
    logout_view,
    staff_create_view,
    staff_list_view,
    staff_password_view,
)
from modules.pages.web import (
    grant_employee_view,
    grant_form_view,
    grant_staff_list_view,
    page_editor_view,
    page_list_view,
    page_publication_view,
    page_rename_view,
    page_save_view,
    page_undo_view,
    site_settings_view,
    staff_deactivate_view,
    staff_reactivate_view,
)


urlpatterns: list[URLPattern] = [
    path("manage/login/", login_view, name="manage-login"),
    path("manage/logout/", logout_view, name="manage-logout"),
    path("manage/staff/", staff_list_view, name="manage-staff"),
    path("manage/staff/new/", staff_create_view, name="manage-staff-create"),
    path(
        "manage/staff/<uuid:staff_id>/password/",
        staff_password_view,
        name="manage-staff-password",
    ),
    path(
        "manage/staff/<uuid:staff_id>/deactivate/",
        staff_deactivate_view,
        name="manage-staff-deactivate",
    ),
    path(
        "manage/staff/<uuid:staff_id>/reactivate/",
        staff_reactivate_view,
        name="manage-staff-reactivate",
    ),
    path("manage/pages/", page_list_view, name="manage-pages"),
    path("manage/settings/", site_settings_view, name="manage-site-settings"),
    path("manage/pages/<uuid:page_id>/", page_editor_view, name="manage-page-editor"),
    path(
        "manage/pages/<uuid:page_id>/publication/",
        page_publication_view,
        name="manage-page-publication",
    ),
    path(
        "manage/pages/<uuid:page_id>/rename/",
        page_rename_view,
        name="manage-page-rename",
    ),
    path("manage/pages/<uuid:page_id>/save/", page_save_view, name="manage-page-save"),
    path("manage/pages/<uuid:page_id>/undo/", page_undo_view, name="manage-page-undo"),
    path("manage/grants/", grant_staff_list_view, name="manage-grant-staff"),
    path("manage/grants/<uuid:staff_id>/", grant_employee_view, name="manage-grant-employee"),
    path(
        "manage/grants/<uuid:staff_id>/<uuid:page_id>/",
        grant_form_view,
        name="manage-grant-form",
    ),
]
