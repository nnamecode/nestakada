from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from modules.accounts.api import StaffAccessError, StaffRole, lock_staff_session
from modules.audit.api import Action, ActorRef, TargetType, append_event
from modules.media.api import (
    MediaUsageError,
    lock_site_logo_usage,
    replace_site_logo_usage,
)

from .models import SiteSettings


class SiteSettingsCommandError(RuntimeError):
    def __init__(self, code: str, *, generation: int | None = None):
        super().__init__(code)
        self.code = code
        self.generation = generation


@dataclass(frozen=True, slots=True)
class SiteSettingsResult:
    settings_generation: int


_CORE_SCALARS = (
    "organization_name",
    "phone_display",
    "phone_e164",
    "address",
    "opening_hours",
    "contact_email",
    "map_url",
)


def update_site_settings(
    *,
    actor_id: object,
    session_generation: object,
    base_settings_generation: object,
    organization_name: object,
    phone_display: object,
    phone_e164: object,
    address: object,
    opening_hours: object,
    contact_email: object,
    map_url: object,
    logo_asset_id: object,
) -> SiteSettingsResult:
    if type(base_settings_generation) is not int or base_settings_generation < 1:
        raise SiteSettingsCommandError("INVALID_BASIS")
    scalar_values = {
        "organization_name": organization_name,
        "phone_display": phone_display,
        "phone_e164": phone_e164,
        "address": address,
        "opening_hours": opening_hours,
        "contact_email": contact_email,
        "map_url": map_url,
    }
    if any(type(value) is not str for value in scalar_values.values()):
        raise SiteSettingsCommandError("INVALID_SETTINGS")
    if type(logo_asset_id) is not uuid.UUID:
        raise SiteSettingsCommandError("INVALID_SETTINGS")
    try:
        with transaction.atomic():
            actor = lock_staff_session(
                actor_id=actor_id,
                session_generation=session_generation,
            )
            if (
                actor.role != StaffRole.OWNER
                or actor.username != "nesadmin"
                or not actor.is_superuser
            ):
                raise SiteSettingsCommandError("FORBIDDEN")
            try:
                settings = SiteSettings.objects.select_for_update().get(singleton_key=True)
            except SiteSettings.DoesNotExist:
                raise SiteSettingsCommandError("SETTINGS_UNAVAILABLE") from None
            if settings.settings_generation != base_settings_generation:
                raise SiteSettingsCommandError(
                    "STALE_SETTINGS",
                    generation=settings.settings_generation,
                )

            current_logo_id = settings.logo_asset_id
            changed = current_logo_id != logo_asset_id or any(
                getattr(settings, name) != scalar_values[name] for name in _CORE_SCALARS
            )
            lock_site_logo_usage(
                settings_id=settings.id,
                current_asset_id=current_logo_id,
                new_asset_id=logo_asset_id,
            )
            for name in _CORE_SCALARS:
                setattr(settings, name, scalar_values[name])
            settings.logo_asset_id = logo_asset_id
            try:
                settings.full_clean()
            except ValidationError:
                raise SiteSettingsCommandError("INVALID_SETTINGS") from None

            if not changed:
                raise SiteSettingsCommandError(
                    "NO_CHANGE",
                    generation=settings.settings_generation,
                )
            replace_site_logo_usage(
                settings_id=settings.id,
                current_asset_id=current_logo_id,
                new_asset_id=logo_asset_id,
            )
            settings.settings_generation += 1
            settings.save(update_fields=(*_CORE_SCALARS, "logo_asset", "settings_generation"))
            append_event(
                action=Action.SITE_SETTINGS_CHANGED,
                actor=ActorRef.user(actor.id, actor.role),
                target_type=TargetType.SITE_SETTINGS,
                target_uuid=None,
                detail={"generation": settings.settings_generation},
            )
            return SiteSettingsResult(settings.settings_generation)
    except StaffAccessError as exc:
        raise SiteSettingsCommandError(exc.code) from exc
    except MediaUsageError as exc:
        raise SiteSettingsCommandError(exc.code) from exc
