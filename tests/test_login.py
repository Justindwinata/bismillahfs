import unittest

from flashsale.bridge import ChromePage
from flashsale.shopee import ShopeeSession


class NativeDomBridge:
    """Model the extension's native CSS contract, including rejected pseudos."""
    def request(self, operation, **kwargs):
        if operation == 'info':
            return {'url': 'https://shopee.co.id/'}
        query = kwargs['query']
        root = query
        while 'base' in root:
            root = root['base']
        css = root.get('css', '')
        if ':has-text(' in css:
            raise ValueError('Selector is not valid native CSS')
        account = '.navbar__username' in css
        action = kwargs['action']
        if action == 'count':
            return 1 if account else 0
        if action == 'visible':
            return account
        if action == 'text':
            return 'akun_pengujian'
        raise AssertionError('Unexpected DOM action')


class LoginRegressionTests(unittest.TestCase):
    def test_login_check_uses_native_css_and_unlocks_account(self):
        session = ShopeeSession()
        session.page = ChromePage(NativeDomBridge())
        accounts = []
        session.account.connect(lambda ready, name: accounts.append((ready, name)))
        session.login_check()
        self.assertTrue(session.authenticated)
        self.assertEqual(accounts, [(True, 'akun_pengujian')])

    def test_missing_dom_count_is_clear_error(self):
        class BrokenBridge:
            def request(self, *args, **kwargs):
                return None
        with self.assertRaisesRegex(ValueError, 'jumlah elemen'):
            ChromePage(BrokenBridge()).locator('h1').count()
