import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from flashsale.core import ZONE
from flashsale.shopee import ShopeeSession


class CheckoutFlowTests(unittest.TestCase):
    def setup_flow(self):
        session = ShopeeSession()
        session.page = MagicMock()
        session.data = {'url': 'https://shopee.co.id/product/1/2', 'groups': []}
        session.page.url = session.data['url']
        session.authenticated = True
        session.preflight = MagicMock()
        session.guard = MagicMock()
        session.await_checkout = MagicMock()
        session.select_payment = MagicMock()
        session.verify_checkout_item = MagicMock()
        session.snapshot = MagicMock()
        session.stock_rejection = MagicMock(return_value=False)
        session.prepare_product = lambda config: setattr(session.page, 'url', 'https://shopee.co.id/checkout')
        payment, total, submit = MagicMock(), MagicMock(), MagicMock()
        payment.is_checked.return_value = True
        total.locator.return_value.inner_text.return_value = 'Rp100.000'
        submit.is_enabled.return_value = True
        config = {'url': session.data['url'], 'time': datetime.now(ZONE).isoformat(),
                  'immediate': True, 'quantity': 1, 'payment': 'QRIS', 'limit': 150000, 'variants': []}
        return session, config, payment, total, submit

    def test_inspection_mode_never_reserves_or_submits_order(self):
        session, config, payment, total, submit = self.setup_flow()
        config['stop_before_submit'] = True
        with patch('flashsale.shopee.checkout_controls', return_value=(total, submit)), patch('flashsale.shopee.Store') as store:
            session.checkout(config)
            store.assert_not_called()
        submit.click.assert_not_called()

    def test_success_needs_pending_marker_and_order_id(self):
        session, config, payment, total, submit = self.setup_flow()
        submit.click.side_effect = lambda: setattr(session.page, 'url', 'https://shopee.co.id/user/purchase/order/123')
        pending = session.page.get_by_text.return_value
        pending.count.return_value = 1
        pending.nth.return_value.is_visible.return_value = True
        with patch('flashsale.shopee.checkout_controls', return_value=(total, submit)), patch('flashsale.shopee.Store') as store:
            store.return_value.reserve.return_value = 7
            session.checkout(config)
            store.return_value.finish.assert_called_once_with(7, 'PENDING_PAYMENT', '123')
        submit.click.assert_called_once()
        self.assertIsNone(session.attempt)

    def test_budget_failure_stops_before_final_click(self):
        session, config, payment, total, submit = self.setup_flow()
        config['limit'] = 50000
        with patch('flashsale.shopee.checkout_controls', return_value=(total, submit)), patch('flashsale.shopee.Store') as store:
            with self.assertRaisesRegex(ValueError, 'batas harga'):
                session.checkout(config)
            store.assert_not_called()
        submit.click.assert_not_called()

    def test_readiness_rejects_old_extension_without_buying(self):
        session = ShopeeSession(bridge=MagicMock(client_protocol=2))
        session.page = MagicMock()
        with self.assertRaisesRegex(ValueError, '0.6.0'):
            session.preflight()
        session.page.get_by_role.assert_not_called()

    def test_guard_batches_normal_browser_state_into_one_read(self):
        session = ShopeeSession(bridge=MagicMock(client_protocol=3))
        session.page = MagicMock()
        session.page.browser_state.return_value = {'url': 'https://shopee.co.id/product/1/2', 'challenge': False}
        session.guard()
        session.page.browser_state.assert_called_once()
        session.page.locator.assert_not_called()

    def test_challenge_disappearance_resumes_without_continue_click(self):
        session = ShopeeSession(bridge=MagicMock(client_protocol=5))
        session.page = MagicMock()
        session.snapshot = MagicMock()
        session.stock_rejection = MagicMock(return_value=False)
        session.resume_event = MagicMock()
        session.page.browser_state.side_effect = [
            {'url': 'https://shopee.co.id/checkout', 'challenge': True},
            {'url': 'https://shopee.co.id/checkout', 'challenge': False},
        ]
        states = []
        session.status.connect(lambda state, message: states.append(state))
        session.guard()
        self.assertEqual(states, ['VERIFIKASI', 'MELANJUTKAN'])
        session.page.bring_to_front.assert_called_once()
        session.resume_event.wait.assert_called_once_with(.3)
        self.assertFalse(session.verification_only)

    def test_stock_retry_only_after_explicit_rejection(self):
        session, config, payment, total, submit=self.setup_flow()
        config['stock_attempts']=3
        session.submit_once=MagicMock(side_effect=[False,True])
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)):
            session.submit_order(config,submit)
        self.assertEqual(session.submit_once.call_count,2)

    def test_uncertain_result_is_never_retried(self):
        session, config, payment, total, submit=self.setup_flow()
        session.submit_once=MagicMock(side_effect=ValueError('Status belum pasti'))
        with self.assertRaisesRegex(ValueError,'belum pasti'):
            session.submit_order(config,submit)
        self.assertEqual(session.submit_once.call_count,1)

    def test_stock_retries_are_bounded(self):
        session, config, payment, total, submit=self.setup_flow()
        config['stock_attempts']=2
        session.submit_once=MagicMock(return_value=False)
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)):
            with self.assertRaisesRegex(ValueError,'2 percobaan'):
                session.submit_order(config,submit)
        self.assertEqual(session.submit_once.call_count,2)

    def test_scheduled_fast_mode_prepares_checkout_before_release(self):
        session,config,payment,total,submit=self.setup_flow()
        config.update(prepare_before_time=True,immediate=False,stop_before_submit=True)
        prepared=[]
        session.prepare_product=lambda c: (prepared.append('product'),setattr(session.page,'url','https://shopee.co.id/checkout'))
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)):
            session.checkout(config)
        self.assertEqual(prepared,['product'])
        session.await_checkout.assert_called_once()
        submit.click.assert_not_called()

    def test_explicit_stock_failure_is_recorded_without_uncertain_retry(self):
        session,config,payment,total,submit=self.setup_flow()
        session.stock_rejection.return_value=True
        with patch('flashsale.shopee.Store') as store:
            store.return_value.reserve.return_value=8
            self.assertFalse(session.submit_once(config,submit))
            store.return_value.finish.assert_called_once_with(8,'REJECTED_STOCK')
        submit.click.assert_called_once()
        self.assertIsNone(session.attempt)

    def test_payment_redirect_is_confirmed_from_recent_pending_order(self):
        session,config,payment,total,submit=self.setup_flow()
        session.bridge=MagicMock(client_protocol=8)
        session.data['name']='HMNS Alpha'
        session.guard.side_effect=[ValueError('Tab pilihan tidak lagi berada di Shopee Indonesia.'), None, None]
        session.page.open_pending_orders.side_effect=lambda:setattr(session.page,'url','https://shopee.co.id/user/purchase/list/?type=9')
        session.page.goto.side_effect=lambda url:setattr(session.page,'url',url)
        links=session.page.locator.return_value.filter.return_value
        links.count.return_value=1
        links.nth.return_value.is_visible.return_value=True
        links.nth.return_value.get_attribute.return_value='/user/purchase/checkout/246654450232149?orderIndex=0&type=9'
        marker=session.page.get_by_text.return_value
        marker.count.return_value=1
        marker.nth.return_value.is_visible.return_value=True
        marker.nth.return_value.inner_text.return_value='NO. PESANAN . 261026XYZ'
        with patch('flashsale.shopee.Store') as store:
            store.return_value.reserve.return_value=8
            self.assertTrue(session.submit_once(config,submit))
            store.return_value.finish.assert_called_once_with(8,'PENDING_PAYMENT','261026XYZ')
        submit.click.assert_called_once()

    def test_ready_checkout_does_not_reopen_product_or_cart(self):
        session,config,payment,total,submit=self.setup_flow()
        session.prepared_config=dict(config)
        session.prepared_payment=config['payment']
        session.page.url='https://shopee.co.id/checkout'
        session.prepare_product=MagicMock()
        config['stop_before_submit']=True
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)):
            session.checkout(config)
        session.prepare_product.assert_not_called()
        session.await_checkout.assert_not_called()
        session.select_payment.assert_not_called()
        submit.click.assert_not_called()

    def test_stage_checkout_never_reserves_or_submits(self):
        session,config,payment,total,submit=self.setup_flow()
        session.prepare_product=MagicMock()
        with patch('flashsale.shopee.Store') as store:
            session.stage_checkout(config)
        session.prepare_product.assert_called_once()
        session.await_checkout.assert_called_once()
        store.assert_not_called()
        self.assertEqual(session.prepared_config['quantity'],1)

    def test_unchanged_quote_does_not_submit_in_coin_mode(self):
        from decimal import Decimal
        session,config,payment,total,submit=self.setup_flow()
        config['refresh_with_coins']=True
        session.refresh_coins=MagicMock(return_value=Decimal('100000'))
        with patch('flashsale.shopee.time.monotonic',side_effect=[0,11]), patch('flashsale.shopee.Store') as store:
            with self.assertRaisesRegex(ValueError,'Harga checkout belum berubah'):
                session.checkout(config)
            store.assert_not_called()
        submit.click.assert_not_called()

    def test_changed_quote_within_budget_can_reach_inspection_ready(self):
        from decimal import Decimal
        session,config,payment,total,submit=self.setup_flow()
        config.update(refresh_with_coins=True,stop_before_submit=True)
        session.refresh_coins=MagicMock(return_value=Decimal('100005'))
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)), patch('flashsale.shopee.Store') as store:
            session.checkout(config)
            store.assert_not_called()
        submit.click.assert_not_called()

    def test_cart_resume_reaches_ready_checkout_without_rebuying_product(self):
        session,config,payment,total,submit=self.setup_flow()
        session.page.url='https://shopee.co.id/cart'
        session.prepare_product=MagicMock()
        session.await_checkout.side_effect=lambda c:setattr(session.page,'url','https://shopee.co.id/checkout')
        config['stop_before_submit']=True
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)),patch('flashsale.shopee.Store') as store:
            session.checkout(config)
            store.assert_not_called()
        session.prepare_product.assert_not_called()
        session.await_checkout.assert_called_once()

    def test_checkout_can_resume_after_preparation_validation_failed(self):
        session,config,payment,total,submit=self.setup_flow()
        session.page.url='https://shopee.co.id/checkout'
        session.preparation_request=dict(config)
        session.prepare_product=MagicMock()
        config['stop_before_submit']=True
        with patch('flashsale.shopee.checkout_controls',return_value=(total,submit)),patch('flashsale.shopee.Store') as store:
            session.checkout(config)
            store.assert_not_called()
        session.prepare_product.assert_not_called()
        session.await_checkout.assert_not_called()
        session.select_payment.assert_called_once_with(config['payment'])
        self.assertIsNotNone(session.prepared_config)

    def test_preflight_accepts_checkout_preparation_request(self):
        session=ShopeeSession()
        session.authenticated=True
        session.data={'url':'https://shopee.co.id/product/1/2'}
        session.page=MagicMock(url='https://shopee.co.id/checkout')
        session.preparation_request={'url':session.data['url'],'variants':[],'quantity':1}
        session.guard=MagicMock()
        session.verify_checkout_item=MagicMock()
        session.preflight()
        session.verify_checkout_item.assert_called_once_with(session.preparation_request)

    def test_checkout_loading_state_is_waited_out(self):
        session=ShopeeSession()
        session.page=MagicMock(url='https://shopee.co.id/checkout')
        session.guard=MagicMock()
        controls=(MagicMock(),MagicMock())
        with patch('flashsale.shopee.checkout_controls',side_effect=[ValueError('Struktur belum lengkap'),controls]):
            self.assertEqual(session.wait_checkout_ready(),controls)
        self.assertEqual(session.guard.call_count,2)
