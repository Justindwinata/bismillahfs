import unittest
from unittest.mock import MagicMock, patch

from flashsale.shopee import ShopeeSession, checkout_controls, is_checkout_url, payment_category, element_selected


class Radio:
    def __init__(self, label, events, selected=False):
        self.label, self.events, self.selected = label, events, selected

    def get_attribute(self, name):
        return str(self.selected).lower() if name == 'aria-checked' else None

    def click(self):
        self.events.append(self.label)
        self.selected = True


class CheckoutRecognitionTests(unittest.TestCase):
    def test_homepage_and_redirect_queries_are_not_checkout(self):
        for value in ('https://shopee.co.id/', 'https://shopee.co.id/?next=/checkout',
                      'https://shopee.co.id/cart?checkout=1', 'https://shopee.co.id/checkout-fake',
                      'https://shopee.co.id.attacker.test/checkout', 'https://shopee.co.id/product/1/2#checkout'):
            self.assertFalse(is_checkout_url(value))
        self.assertTrue(is_checkout_url('https://shopee.co.id/checkout?shopid=123'))

    def test_wrong_route_cannot_reach_payment_controls(self):
        page = MagicMock(url='https://shopee.co.id/?next=/checkout')
        with self.assertRaisesRegex(ValueError, 'tidak berada'):
            checkout_controls(page)
        page.get_by_role.assert_not_called()

    def test_bank_selection_opens_category_then_selects_specific_bank(self):
        events = []
        category = Radio('Transfer Bank', events)
        bank = Radio('Bank BCA', events)
        session = ShopeeSession()
        session.page = MagicMock()
        session.guard = MagicMock()
        with patch('flashsale.shopee.checkout_controls'), patch('flashsale.shopee.unique_visible', side_effect=[category, bank]):
            session.select_payment('Bank BCA')
        self.assertEqual(events, ['Transfer Bank', 'Bank BCA'])
        self.assertTrue(element_selected(bank))

    def test_unavailable_payment_fails_without_manual_prompt(self):
        session = ShopeeSession()
        session.page = MagicMock()
        session.guard = MagicMock()
        events = []
        session.status.connect(lambda state, message: events.append(state))
        with patch('flashsale.shopee.checkout_controls'), patch('flashsale.shopee.unique_visible', return_value=None), patch('flashsale.shopee.time.monotonic', side_effect=[0, 0, 9]):
            with self.assertRaisesRegex(ValueError, 'tidak tersedia'):
                session.select_payment('Bank BCA')
        self.assertNotIn('TINDAKAN MANUAL', events)
        self.assertFalse(session.resume_event.is_set())

    def test_generic_transfer_does_not_silently_choose_a_bank(self):
        with self.assertRaises(ValueError):
            payment_category('Transfer Bank')

    def test_unconfirmed_variant_is_not_treated_as_selected(self):
        element = MagicMock()
        element.get_attribute.side_effect = lambda name: {'aria-pressed':'false','class':'product-variation'}.get(name)
        self.assertFalse(element_selected(element))
