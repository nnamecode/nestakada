"""V07-011: exact money and typed matrix boundaries, no Django required."""
import copy
import unittest
from uuid import UUID

from .price_policy import PricePolicyError, normalize_amount, normalize_price


def identity(number):
    return str(UUID(int=number))


def matrix(rows=1, columns=1):
    return {'columns': [{'id': identity(i + 1), 'label': 'Столбец'} for i in range(columns)],
            'rows': [{'id': identity(1000 + i), 'label': 'Работа',
                      'cells': [{'column_id': identity(j + 1), 'kind': 'text', 'text': ''}
                                for j in range(columns)]} for i in range(rows)]}


class PriceTests(unittest.TestCase):
    def reject(self, value):
        with self.assertRaises(PricePolicyError) as caught:
            normalize_price(value)
        self.assertEqual(str(caught.exception), 'PRICE_INVALID')

    def test_exact_money_and_exponent_positive(self):
        for source, expected in [('0', '0'), ('0.01', '0.01'), ('999999999.99', '999999999.99'),
                                 ('1e2', '100'), ('1.2300', '1.23'), ('1E-2', '0.01'),
                                 ('0E-1000000', '0'), (' 12.50 ', '12.5')]:
            with self.subTest(source=source):
                self.assertEqual(normalize_amount(source), expected)

    def test_money_rejects_nonfinite_negative_overflow_and_rounding(self):
        for source in ['-0.01', 'Infinity', '-Infinity', 'NaN', 'sNaN', '1000000000.00',
                       '0.001', '1e-1000000', '1e1000000', '', 0.01, True, None]:
            with self.subTest(source=source), self.assertRaises(PricePolicyError):
                normalize_amount(source)

    def test_empty_and_numeric_text_stay_text(self):
        source = matrix(1, 3)
        source['rows'][0]['cells'][1]['text'] = '1000'
        source['rows'][0]['cells'][2]['text'] = 'по согласованию'
        self.assertEqual(normalize_price(source), source)
        self.assertIsNone(normalize_price(None))

    def test_amount_from_and_idempotence(self):
        source = matrix()
        source['rows'][0]['cells'][0] = {'column_id': identity(1), 'kind': 'amount',
                                        'amount': '1e2', 'from': True}
        result = normalize_price(source)
        self.assertEqual(result['rows'][0]['cells'][0]['amount'], '100')
        self.assertTrue(result['rows'][0]['cells'][0]['from'])
        self.assertEqual(normalize_price(result), result)
        self.assertEqual(source['rows'][0]['cells'][0]['amount'], '1e2')

    def test_full_matrix_and_shape_boundaries(self):
        source = matrix(500, 20)
        result = normalize_price(source)
        self.assertEqual(sum(len(row['cells']) for row in result['rows']), 10000)
        self.assertEqual(result, source)
        self.assertEqual(len(normalize_price(matrix(0, 32))['columns']), 32)
        self.reject(matrix(501, 0))
        self.reject(matrix(0, 33))
        self.reject(matrix(500, 21))

    def test_codepoint_boundaries_and_crlf(self):
        source = matrix()
        source['columns'][0]['label'] = '🚀' * 500
        source['rows'][0]['label'] = 'Я' * 500
        source['rows'][0]['cells'][0]['text'] = '🚀' * 1000
        self.assertEqual(normalize_price(source), source)
        source['rows'][0]['cells'][0]['text'] += 'a'
        self.reject(source)
        source['rows'][0]['cells'][0]['text'] = 'a\r\nb\rc\t'
        self.assertEqual(normalize_price(source)['rows'][0]['cells'][0]['text'], 'a\nb\nc\t')
        source['rows'][0]['cells'][0]['text'] = 'a' * 999 + '\r\n'
        self.assertEqual(normalize_price(source)['rows'][0]['cells'][0]['text'], 'a' * 999 + '\n')
        source['rows'][0]['cells'][0]['text'] = 'a' * 1000 + '\r\n'
        self.reject(source)

    def test_closed_types_and_keys(self):
        for change in [lambda value: value.update(extra=True),
                       lambda value: value.update(rows=()),
                       lambda value: value['rows'][0].update(id=True),
                       lambda value: value['rows'][0]['cells'][0].update(kind='empty'),
                       lambda value: value['rows'][0]['cells'][0].update(text='\ud800'),
                       lambda value: value['columns'][0].update(label='x\n'),
                       lambda value: value['rows'][0]['cells'][0].update(text='x\x00')]:
            value = matrix()
            change(value)
            self.reject(value)

    def test_duplicate_and_unknown_identity_rejection(self):
        source = matrix(2, 2)
        cases = []
        value = copy.deepcopy(source)
        value['columns'][1]['id'] = value['columns'][0]['id']
        cases.append(value)
        value = copy.deepcopy(source)
        value['rows'][1]['id'] = value['rows'][0]['id']
        cases.append(value)
        value = copy.deepcopy(source)
        value['rows'][0]['cells'][1]['column_id'] = identity(1)
        cases.append(value)
        value = copy.deepcopy(source)
        value['rows'][0]['cells'][0]['column_id'] = identity(999)
        cases.append(value)
        for value in cases:
            self.reject(value)

    def test_from_is_strict_bool(self):
        source = matrix()
        source['rows'][0]['cells'][0] = {'column_id': identity(1), 'kind': 'amount',
                                        'amount': '0.01', 'from': 1}
        self.reject(source)


if __name__ == '__main__':
    unittest.main()
