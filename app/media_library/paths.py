import re
from django.core.exceptions import ValidationError


def relative_path(value):
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise ValidationError('MEDIA_INVALID_RELATIVE_PATH')
    if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', part) or part in ('.', '..')
           for part in value.split('/')):
        raise ValidationError('MEDIA_INVALID_RELATIVE_PATH')
    return value


def storage_key(value):
    relative_path(value)
    if not (value.startswith('img/') or value.startswith('private/sources/')):
        raise ValidationError('MEDIA_WORKING_SPACE_REQUIRED')
    return value
