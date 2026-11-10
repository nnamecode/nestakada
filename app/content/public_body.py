"""Pure bounded public projection of the closed page-content layout."""
from dataclasses import dataclass
from urllib.parse import urlencode

from .public_read import (PUBLIC_HERO_PAGE_KINDS, PublicPage,
                          PublicUnavailable)


@dataclass(frozen=True)
class PublicTextBlock:
    kind: str
    field: str
    html: str


@dataclass(frozen=True)
class PublicPriceCell:
    kind: str
    text: str


@dataclass(frozen=True)
class PublicPriceRow:
    label: str
    cells: tuple[PublicPriceCell, ...]


@dataclass(frozen=True)
class PublicPriceBlock:
    kind: str
    columns: tuple[str, ...]
    rows: tuple[PublicPriceRow, ...]


@dataclass(frozen=True)
class PublicImageBlock:
    kind: str
    src: str
    alt: str
    alignment: str
    width_px: int | None
    height_px: int | None


@dataclass(frozen=True)
class PublicHeroBlock:
    kind: str
    src: str
    alt: str
    alignment: str
    width_px: int | None
    height_px: int | None
    html: str


def _amount(value, is_from):
    whole, separator, fraction = value.partition('.')
    groups = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    number = '\u202f'.join(reversed(groups))
    fraction = fraction.rstrip('0') if separator else ''
    if fraction:
        number += ',' + fraction
    return ('от ' if is_from else '') + number + '\u00a0₽'


def project_body(page, media=None):
    if not isinstance(page, PublicPage):
        raise PublicUnavailable()
    try:
        payload = page.payload
        media = {} if media is None else media
        embedded = {item['id']: item for item in payload['embedded_images']}
        main_image = (payload['main_image']
                      if page.page_kind in PUBLIC_HERO_PAGE_KINDS else None)
        if main_image is not None:
            intro_nodes = [
                node for node in payload['layout']
                if node['kind'] == 'text' and node['field'] == 'intro_text']
            if (len(intro_nodes) != 1
                    or intro_nodes[0]['protected_nodes']):
                raise PublicUnavailable()
        result = []
        for node in payload['layout']:
            if node['kind'] == 'text':
                if node['protected_nodes']:
                    raise PublicUnavailable()
                if main_image is not None and node['field'] == 'intro_text':
                    file_id = media['main_image']
                    query = urlencode((('page', page.page_id),
                                       ('slot', 'main_image')))
                    result.append(PublicHeroBlock(
                        kind='hero',
                        src='/public-media/' + file_id + '/?' + query,
                        alt=main_image['alt'],
                        alignment=main_image['alignment'],
                        width_px=main_image['width_px'],
                        height_px=main_image['height_px'],
                        html=payload['intro_text']))
                else:
                    result.append(PublicTextBlock(
                        kind='text', field=node['field'],
                        html=payload[node['field']]))
            elif node['kind'] == 'price':
                price = payload['price']
                if price is None:
                    continue
                column_ids = tuple(column['id'] for column in price['columns'])
                rows = []
                for row in price['rows']:
                    source = {cell['column_id']: cell for cell in row['cells']}
                    cells = []
                    for column_id in column_ids:
                        cell = source.get(column_id)
                        if cell is None:
                            cells.append(PublicPriceCell('empty', ''))
                        elif cell['kind'] == 'text':
                            cells.append(PublicPriceCell('text', cell['text']))
                        else:
                            cells.append(PublicPriceCell(
                                'amount', _amount(cell['amount'], cell['from'])))
                    rows.append(PublicPriceRow(row['label'], tuple(cells)))
                result.append(PublicPriceBlock(
                    kind='price',
                    columns=tuple(column['label'] for column in price['columns']),
                    rows=tuple(rows)))
            elif node['kind'] == 'image':
                image = embedded[node['image_id']]
                slot = 'embedded:' + image['id']
                file_id = media[slot]
                query = urlencode((('page', page.page_id), ('slot', slot)))
                result.append(PublicImageBlock(
                    kind='image', src='/public-media/' + file_id + '/?' + query,
                    alt=image['alt'], alignment=image['alignment'],
                    width_px=image['width_px'], height_px=image['height_px']))
            else:
                raise PublicUnavailable()
        return tuple(result)
    except PublicUnavailable:
        raise
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PublicUnavailable() from None
