from django.urls import URLPattern, path, re_path

from config.audit_web import audit_event_list_view
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
    page_create_view,
    page_delete_view,
    page_editor_view,
    page_list_view,
    page_move_view,
    page_publication_view,
    page_rename_view,
    page_reorder_view,
    page_save_view,
    page_undo_view,
    page_url_view,
    site_settings_view,
    staff_deactivate_view,
    staff_reactivate_view,
)
from modules.pages.public_http import public_page_view
from modules.pages.public_seo import robots_view, sitemap_view
from modules.service_requests.web import request_delete_view, request_detail_view, request_list_view
from modules.service_requests.public import intake_configuration, submit_service_request


urlpatterns: list[URLPattern] = [
    path("sitemap.xml", sitemap_view, name="sitemap"),
    path("robots.txt", robots_view, name="robots"),
    path("manage/login/", login_view, name="manage-login"),
    path("manage/logout/", logout_view, name="manage-logout"),
    path("manage/audit/", audit_event_list_view, name="manage-audit"),
    path("manage/requests/", request_list_view, name="manage-service-requests"),
    path("manage/requests/<uuid:request_id>/", request_detail_view, name="manage-service-request-detail"),
    path("manage/requests/<uuid:request_id>/delete/", request_delete_view, name="manage-service-request-delete"),
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
    path("manage/pages/new/", page_create_view, name="manage-page-create"),
    path("manage/pages/reorder/", page_reorder_view, name="manage-page-reorder"),
    path("manage/settings/", site_settings_view, name="manage-site-settings"),
    path("manage/pages/<uuid:page_id>/", page_editor_view, name="manage-page-editor"),
    path(
        "manage/pages/<uuid:page_id>/publication/",
        page_publication_view,
        name="manage-page-publication",
    ),
    path(
        "manage/pages/<uuid:page_id>/move/",
        page_move_view,
        name="manage-page-move",
    ),
    path(
        "manage/pages/<uuid:page_id>/rename/",
        page_rename_view,
        name="manage-page-rename",
    ),
    path(
        "manage/pages/<uuid:page_id>/url/",
        page_url_view,
        name="manage-page-url",
    ),
    path(
        "manage/pages/<uuid:page_id>/delete/",
        page_delete_view,
        name="manage-page-delete",
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
    re_path(r"^.*$", public_page_view, name="public-page"),
]

if intake_configuration() is not None:
    urlpatterns.insert(
        2,
        path("request/submit/", submit_service_request, name="service-request-submit"),
    )
