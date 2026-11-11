"""Closed optional home-profile DTO; plain data only, never template or HTML input."""
import copy
import re
from uuid import UUID


def invalid():
    raise ValueError('VERSIONS_INVALID_HOME_PROFILE')


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        invalid()


def identifier(value, *, nullable=False):
    if nullable and value is None:
        return
    try:
        if type(value) is not str or str(UUID(value)) != value:
            invalid()
    except (ValueError, TypeError, AttributeError):
        invalid()


def plain(value, limit, *, multiline=False):
    if type(value) is not str or not value or len(value) > limit or '<' in value or '>' in value:
        invalid()
    try:
        value.encode('utf-8')
    except UnicodeError:
        invalid()
    allowed = '\n\t' if multiline else ''
    if any((ord(char) < 32 and char not in allowed) or ord(char) == 127 for char in value):
        invalid()


def url(value):
    plain(value, 300)
    if re.fullmatch(r'/[a-z0-9][a-z0-9/-]*/?', value) is None or '?' in value or '#' in value or '//' in value:
        invalid()


def image(value, image_ids):
    identifier(value)
    if value not in image_ids:
        invalid()


def binding(page_id, row_id_marker=False):
    identifier(page_id, nullable=True)
    if row_id_marker is not False:
        identifier(row_id_marker, nullable=True)
        if (page_id is None) != (row_id_marker is None):
            invalid()


def validate(value, embedded_images):
    keys(value, {'schema', 'hero', 'advantages', 'comparisons', 'steps', 'services',
                 'prices', 'photo_strip', 'works', 'reviews'})
    if value['schema'] != 'home-profile-v1' or type(embedded_images) is not list:
        invalid()
    image_map = {item['id']: item for item in embedded_images}
    if len(image_map) != len(embedded_images):
        invalid()

    hero = value['hero']
    keys(hero, {'lead', 'alt', 'image_id'})
    plain(hero['lead'], 500, multiline=True); plain(hero['alt'], 300); image(hero['image_id'], image_map)

    if type(value['advantages']) is not list or len(value['advantages']) != 8:
        invalid()
    for item in value['advantages']:
        plain(item, 160)

    if type(value['comparisons']) is not list or len(value['comparisons']) != 3:
        invalid()
    for item in value['comparisons']:
        keys(item, {'heading', 'bullets', 'result_mark', 'result_text'})
        plain(item['heading'], 160, multiline=True); plain(item['result_mark'], 8); plain(item['result_text'], 300)
        if type(item['bullets']) is not list or not 4 <= len(item['bullets']) <= 5:
            invalid()
        for bullet in item['bullets']:
            plain(bullet, 300)

    if type(value['steps']) is not list or len(value['steps']) != 5:
        invalid()
    for item in value['steps']:
        keys(item, {'alt', 'heading', 'text', 'image_id'})
        plain(item['alt'], 300); plain(item['heading'], 160); plain(item['text'], 500, multiline=True); image(item['image_id'], image_map)

    ids = set()
    if type(value['services']) is not list or len(value['services']) != 8:
        invalid()
    for item in value['services']:
        keys(item, {'id', 'label', 'caption', 'url', 'alt', 'fallback_visible', 'source_page_id', 'image_id'})
        identifier(item['id']); plain(item['label'], 160); plain(item['caption'], 160); url(item['url']); plain(item['alt'], 300)
        if type(item['fallback_visible']) is not bool:
            invalid()
        binding(item['source_page_id']); image(item['image_id'], image_map); ids.add(item['id'])

    if type(value['prices']) is not list or len(value['prices']) != 6:
        invalid()
    price_keys = set(); source_rows = set()
    for group in value['prices']:
        keys(group, {'id', 'key', 'url', 'label', 'rows', 'source_page_id'})
        identifier(group['id']); plain(group['key'], 40); url(group['url']); plain(group['label'], 160); binding(group['source_page_id'])
        if re.fullmatch(r'[a-z][a-z0-9-]*', group['key']) is None or group['key'] in price_keys or type(group['rows']) is not list or not 1 <= len(group['rows']) <= 8:
            invalid()
        price_keys.add(group['key']); ids.add(group['id'])
        for row in group['rows']:
            keys(row, {'id', 'url', 'label', 'price_text', 'fallback_visible', 'source_page_id', 'source_row_id'})
            identifier(row['id']); url(row['url']); plain(row['label'], 160); plain(row['price_text'], 160)
            if type(row['fallback_visible']) is not bool:
                invalid()
            binding(row['source_page_id'], row['source_row_id']); ids.add(row['id'])
            if row['source_row_id'] is not None:
                if row['source_row_id'] in source_rows:
                    invalid()
                source_rows.add(row['source_row_id'])

    strip = value['photo_strip']
    keys(strip, {'alt', 'image_id'}); plain(strip['alt'], 300); image(strip['image_id'], image_map)

    if type(value['works']) is not list or len(value['works']) != 6:
        invalid()
    for item in value['works']:
        keys(item, {'id', 'source_page_id', 'url', 'label', 'photo_count_text', 'image_id', 'asset_id', 'alt', 'fallback_visible'})
        identifier(item['id']); binding(item['source_page_id']); url(item['url']); plain(item['label'], 160, multiline=True)
        plain(item['photo_count_text'], 80); image(item['image_id'], image_map); identifier(item['asset_id']); plain(item['alt'], 300)
        if image_map[item['image_id']]['asset_id'] != item['asset_id'] or type(item['fallback_visible']) is not bool:
            invalid()
        ids.add(item['id'])

    reviews = value['reviews']
    keys(reviews, {'heading', 'url', 'label'}); plain(reviews['heading'], 80); url(reviews['url']); plain(reviews['label'], 160)
    if reviews != {'heading': 'ОТЗЫВЫ', 'url': '/reviews', 'label': 'ОТКРЫТЬ ВСЕ ВИДЕО-ОТЗЫВЫ'}:
        invalid()
    if len(ids) != 8 + 6 + sum(len(group['rows']) for group in value['prices']) + 6:
        invalid()
    return copy.deepcopy(value)


def _protected(value):
    """Return code-owned identity/order/media structure for one valid profile."""
    return {
        'hero_image': value['hero']['image_id'],
        'step_images': [item['image_id'] for item in value['steps']],
        'services': [[item['id'], item['image_id']]
                     for item in value['services']],
        'prices': [[group['id'], group['key'],
                    [row['id'] for row in group['rows']]]
                   for group in value['prices']],
        'photo_strip_image': value['photo_strip']['image_id'],
        'works': [[item['id'], item['image_id'], item['asset_id']]
                  for item in value['works']],
        'reviews': value['reviews'],
    }


def validate_edit(base, candidate, embedded_images):
    """Validate owner-editable data while retaining stable composition identity."""
    base_value = validate(base, embedded_images)
    candidate_value = validate(candidate, embedded_images)
    if _protected(base_value) != _protected(candidate_value):
        invalid()
    return candidate_value
