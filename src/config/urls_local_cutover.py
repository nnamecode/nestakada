from __future__ import annotations

from django.urls import path

from config.local_cutover_identity import target_identity_view
from config.urls import urlpatterns as base_urlpatterns


urlpatterns = [
    path(
        "__r7c_target_identity__",
        target_identity_view,
        name="r7c-target-identity",
    ),
    *base_urlpatterns,
]
