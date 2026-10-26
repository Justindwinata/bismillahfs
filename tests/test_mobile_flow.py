import unittest
from unittest.mock import MagicMock, patch

from flashsale.shopee import ShopeeSession


class MobileFlowTests(unittest.TestCase):
    def session(self):
        session = ShopeeSession()
        session.page = MagicMock()
        session.data = {'groups': [], 'url': 'https://shopee.co.id/product/1/2'}
        session.guard = MagicMock()
        session.snapshot = MagicMock()
        session.click = MagicMock()
        return session

    def test_desktop_sets_and_reads_quantity_before_buy(self):
        session = self.session()
        quantity = MagicMock()
        quantity.input_value.return_value = '2'
        with patch('flashsale.shopee.quantity_field', return_value=quantity):
            session.prepare_product({'variants': [], 'quantity': 2})
        quantity.fill.assert_not_called()
        quantity.input_value.assert_called()
        session.click.assert_called_once_with('Beli Sekarang')

    def test_mobile_opens_panel_before_looking_for_quantity_again(self):
        session = self.session()
        quantity = MagicMock()
        quantity.input_value.return_value = '2'
        candidate = quantity.locator.return_value.locator.return_value.filter.return_value
        candidate.count.return_value = 1
        candidate.nth.return_value.is_visible.return_value = True
        with patch('flashsale.shopee.quantity_field', side_effect=[None, quantity]), patch('flashsale.shopee.read_labeled_variants', return_value=[]):
            session.prepare_product({'variants': [], 'quantity': 2})
        session.click.assert_called_once_with('Beli Sekarang')
        quantity.fill.assert_not_called()
        candidate.nth.return_value.click.assert_called_once()

    def test_wrong_quantity_does_not_click_buy(self):
        session = self.session()
        quantity = MagicMock()
        quantity.input_value.return_value = '1'
        with patch('flashsale.shopee.quantity_field', return_value=quantity), patch('flashsale.shopee.time.monotonic', side_effect=[0, 4]):
            with self.assertRaisesRegex(ValueError, 'Jumlah pada halaman'):
                session.prepare_product({'variants': [], 'quantity': 2})
        session.click.assert_not_called()

    def test_new_mobile_variants_require_selection_before_continuing(self):
        session = self.session()
        quantity = MagicMock()
        groups = [{'name': 'Ukuran', 'options': [{'label': 'L', 'disabled': False}]}]
        with patch('flashsale.shopee.quantity_field', side_effect=[None, quantity]), patch('flashsale.shopee.read_labeled_variants', return_value=groups):
            with self.assertRaisesRegex(ValueError, 'Pilihan varian baru'):
                session.prepare_product({'variants': [], 'quantity': 2})
        quantity.fill.assert_not_called()
        self.assertEqual(session.data['groups'], groups)
