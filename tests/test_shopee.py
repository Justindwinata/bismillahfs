import unittest

from flashsale.shopee import product_url, shared_url


class ShopeeUrlTests(unittest.TestCase):
    def test_equivalent_product_links_have_same_order_key(self):
        canonical = 'https://shopee.co.id/product/123/456'
        self.assertEqual(product_url('https://shopee.co.id/baju-i.123.456?tracking=abc'), canonical)
        self.assertEqual(product_url(canonical + '?x=1'), canonical)

    def test_share_text_and_short_links(self):
        self.assertEqual(shared_url('Temukan kaos di Shopee! https://id.shp.ee/abc123'), 'https://id.shp.ee/abc123')

    def test_untrusted_destinations_rejected(self):
        for url in ('https://shopee.co.id.attacker.test/product/1/2',
                    'https://shopee.co.id@attacker.test/product/1/2',
                    'http://shopee.co.id/product/1/2',
                    'https://shopee.co.id/buyer/login'):
            with self.assertRaises(ValueError):
                shared_url(url)
