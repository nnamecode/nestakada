from types import MappingProxyType
from uuid import uuid4
from django.test import SimpleTestCase

from .public_body import (PublicHeroBlock, PublicImageBlock, PublicPriceBlock,
                          PublicTextBlock, project_body)
from .public_read import PublicPage, PublicUnavailable


class PublicBodyTests(SimpleTestCase):
    def page(self, *, layout, price=None, intro='<p>INTRO</p>', main='<p>MAIN</p>',
             embedded_images=None, main_image=None, page_kind='article'):
        payload = MappingProxyType({
            'layout': layout, 'price': price,
            'intro_text': intro, 'main_text': main,
            'embedded_images': embedded_images or [],
            'main_image': main_image})
        return PublicPage('r', 'p', 'v', '/p/', 'primary', page_kind,
                          'Page', '0' * 64, payload)

    def test_text_blocks_follow_layout_order(self):
        blocks = project_body(self.page(layout=[
            {'kind': 'text', 'field': 'main_text', 'protected_nodes': []},
            {'kind': 'text', 'field': 'intro_text', 'protected_nodes': []}]))
        self.assertEqual(blocks, (
            PublicTextBlock('text', 'main_text', '<p>MAIN</p>'),
            PublicTextBlock('text', 'intro_text', '<p>INTRO</p>')))

    def test_price_preserves_matrix_and_formats_decimal_without_float(self):
        first = '71de8370-3105-5209-a189-82bb243b0011'
        second = '71de8370-3105-5209-a189-82bb243b0012'
        price = {'columns': [{'id': first, 'label': 'Обычная'},
                             {'id': second, 'label': 'Срочная'}],
                 'rows': [{'id': '71de8370-3105-5209-a189-82bb243b0013',
                           'label': '<Диагностика>', 'cells': [
                               {'column_id': second, 'kind': 'text', 'text': '<по осмотру>'},
                               {'column_id': first, 'kind': 'amount',
                                'amount': '1234567.01', 'from': True}]},
                          {'id': '71de8370-3105-5209-a189-82bb243b0014',
                           'label': 'Пустая', 'cells': []}]}
        block = project_body(self.page(
            layout=[{'kind': 'price'}], price=price))[0]
        self.assertIsInstance(block, PublicPriceBlock)
        self.assertEqual(block.columns, ('Обычная', 'Срочная'))
        self.assertEqual([cell.text for cell in block.rows[0].cells],
                         ['от 1\u202f234\u202f567,01\u00a0₽', '<по осмотру>'])
        self.assertEqual([cell.kind for cell in block.rows[1].cells],
                         ['empty', 'empty'])

    def test_none_price_and_empty_layout_add_nothing(self):
        self.assertEqual(project_body(self.page(layout=[])), ())
        self.assertEqual(project_body(self.page(
            layout=[{'kind': 'price'}], price=None)), ())

    def test_price_decimal_boundaries_and_empty_table(self):
        column = '71de8370-3105-5209-a189-82bb243b0021'
        cases = (
            ('0', '0\u00a0₽'),
            ('0.01', '0,01\u00a0₽'),
            ('999999999.99', '999\u202f999\u202f999,99\u00a0₽'))
        for index, (amount, expected) in enumerate(cases, start=1):
            with self.subTest(amount=amount):
                price = {
                    'columns': [{'id': column, 'label': 'Цена'}],
                    'rows': [{
                        'id': f'71de8370-3105-5209-a189-82bb243b002{index + 1}',
                        'label': 'Услуга',
                        'cells': [{'column_id': column, 'kind': 'amount',
                                   'amount': amount, 'from': False}]}]}
                block = project_body(self.page(
                    layout=[{'kind': 'price'}], price=price))[0]
                self.assertEqual(block.rows[0].cells[0].text, expected)

        empty = project_body(self.page(
            layout=[{'kind': 'price'}],
            price={'columns': [], 'rows': []}))[0]
        self.assertEqual(empty, PublicPriceBlock('price', (), ()))

    def test_standalone_image_uses_exact_layout_position_and_context_url(self):
        image_id = '71de8370-3105-5209-a189-82bb243b0031'
        asset_id = '71de8370-3105-5209-a189-82bb243b0032'
        file_id = '71de8370-3105-5209-a189-82bb243b0033'
        blocks = project_body(self.page(
            embedded_images=[{'id': image_id, 'asset_id': asset_id,
                'alt': '<Диагностика>', 'alignment': 'right',
                'width_px': 640, 'height_px': None}],
            layout=[
                {'kind': 'text', 'field': 'main_text', 'protected_nodes': []},
                {'kind': 'image', 'image_id': image_id},
                {'kind': 'text', 'field': 'intro_text', 'protected_nodes': []}]),
            {'embedded:' + image_id: file_id})
        self.assertEqual(blocks[0].field, 'main_text')
        self.assertEqual(blocks[2].field, 'intro_text')
        self.assertEqual(blocks[1], PublicImageBlock(
            'image', '/public-media/' + file_id + '/?page=p&slot=embedded%3A' + image_id,
            '<Диагностика>', 'right', 640, None))

    def test_service_main_image_replaces_exact_intro_in_saved_order(self):
        image = {
            'asset_id': '71de8370-3105-5209-a189-82bb243b0041',
            'alt': '<Кузовной ремонт>', 'alignment': 'left',
            'width_px': 1200, 'height_px': 700}
        blocks = project_body(self.page(
            page_kind='service_detail', main_image=image,
            layout=[
                {'kind': 'text', 'field': 'main_text',
                 'protected_nodes': []},
                {'kind': 'text', 'field': 'intro_text',
                 'protected_nodes': []}]),
            {'main_image': '71de8370-3105-5209-a189-82bb243b0042'})
        self.assertIsInstance(blocks[0], PublicTextBlock)
        self.assertEqual(blocks[1], PublicHeroBlock(
            'hero',
            '/public-media/71de8370-3105-5209-a189-82bb243b0042/?page=p&slot=main_image',
            '<Кузовной ремонт>', 'left', 1200, 700, '<p>INTRO</p>'))

    def test_main_image_policy_and_ambiguous_intro_fail_closed(self):
        image = {
            'asset_id': '71de8370-3105-5209-a189-82bb243b0043',
            'alt': 'Image', 'alignment': 'center',
            'width_px': None, 'height_px': None}
        ordinary = project_body(self.page(
            page_kind='article', main_image=image,
            layout=[{'kind': 'text', 'field': 'intro_text',
                     'protected_nodes': []}]))
        self.assertEqual(ordinary, (
            PublicTextBlock('text', 'intro_text', '<p>INTRO</p>'),))

        for layout in (
                [],
                [{'kind': 'text', 'field': 'intro_text',
                  'protected_nodes': []},
                 {'kind': 'text', 'field': 'intro_text',
                  'protected_nodes': []}],
                [{'kind': 'text', 'field': 'intro_text',
                  'protected_nodes': [{'id': 'protected'}]}]):
            with self.subTest(layout=layout), self.assertRaises(PublicUnavailable):
                project_body(self.page(
                    page_kind='service_section_overview', main_image=image,
                    layout=layout), {'main_image': str(uuid4())})
