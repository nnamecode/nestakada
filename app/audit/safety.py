"""Canonical identifiers only; free text/request payload is never audit data."""
import ipaddress
import re
from uuid import UUID

from django.core.exceptions import ValidationError

from .constants import CODE_PATTERN, KIND_PATTERN, REFERENCE_PATTERN


def positive_id(value):
    if type(value) is not int or not 0 < value <= 9_223_372_036_854_775_807:
        raise ValidationError("AUDIT_INVALID_ID")
    return value


def canonical_reference(value):
    if value is None:
        return ""
    if type(value) is int:
        return "id:" + str(positive_id(value))
    if type(value) is UUID:
        return "uuid:" + str(value)
    raise ValidationError("AUDIT_REFERENCE_MUST_BE_INTERNAL_ID")


def canonical_uuid(value):
    if value is None:
        return None
    if type(value) is UUID:
        return value
    # No coercion of arbitrary strings or objects in the persistence API.
    raise ValidationError("AUDIT_INVALID_UUID")


def code(value):
    if not isinstance(value, str) or re.fullmatch(CODE_PATTERN, value) is None:
        raise ValidationError("AUDIT_INVALID_CODE")
    return value


def object_kind(value):
    if value == "":
        return value
    if not isinstance(value, str) or re.fullmatch(KIND_PATTERN, value) is None:
        raise ValidationError("AUDIT_INVALID_OBJECT_KIND")
    return value


def related_ip(value, explicitly_related):
    if value is None:
        return None
    if explicitly_related is not True or not isinstance(value, str):
        raise ValidationError("AUDIT_IP_REQUIRES_EVENT_RELATION")
    # IPv6 zone IDs are free text, not an audit IP address.
    if '%' in value:
        raise ValidationError("AUDIT_INVALID_IP")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        raise ValidationError("AUDIT_INVALID_IP") from None


def formatted_reference(value):
    """A previously canonicalized identifier in a structured logging record."""
    if not isinstance(value, str) or re.fullmatch(REFERENCE_PATTERN, value) is None:
        raise ValidationError("AUDIT_INVALID_REFERENCE")
    return value
