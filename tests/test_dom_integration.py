"""Real DOM tests in isolated Chromium; no Shopee account or server involved."""
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from playwright.sync_api import sync_playwright

from flashsale.bridge import ChromePage
from flashsale.core import ROOT
from flashsale.shopee import ShopeeSession, checkout_controls, element_selected


class DomBridge:
    client_protocol = 8

    def __init__(self, page, source):
        self.page, self.source = page, source
        self.path = '/cart'

    def request(self, operation, **arguments):
        if operation == 'info':
            return {'url': 'https://shopee.co.id' + self.path, 'complete': True}
        if operation == 'focus': return True
        if operation in ('groups', 'checkout', 'state', 'promotion'):
            result = self.page.evaluate('(' + self.source + ')', {'operation': operation, 'expiresAt': 9999999999999})
            if operation in ('checkout', 'state', 'promotion'): result['url'] = 'https://shopee.co.id' + self.path
            return result
        if operation == 'dom':
            return self.page.evaluate('(' + self.source + ')', {'operation': operation, 'expiresAt': 9999999999999, **arguments})
        raise AssertionError(operation)


class NativeDomIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(headless=True)
        source = (ROOT / 'chrome-extension/background.js').read_text()
        cls.source = source[source.index('function executeDom('):source.index('\nasync function run(')]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.dom = self.browser.new_page()
        self.dom.set_content((ROOT / 'tests/fixtures/cart_checkout.html').read_text())
        self.bridge = DomBridge(self.dom, self.source)
        self.session = ShopeeSession()
        self.session.page = ChromePage(self.bridge)
        self.session.guard = MagicMock()
        self.session.data = {'name': 'HMNS Untitled Humans Aroma 01 Eau De Parfum 100 ml', 'url': 'https://shopee.co.id/product/190339326/22052904487', 'groups': []}
        self.config = {'url': self.session.data['url'], 'quantity': 2, 'variants': []}

    def tearDown(self):
        self.dom.close()

    def checkout(self):
        self.bridge.path = '/checkout'
        self.dom.evaluate("document.getElementById('cart').hidden=true;document.getElementById('checkout').style.display='block'")

    def test_promotion_preserves_official_campaign_identity_without_inventing_sku(self):
        # A real origin is supplied using a local isolated route, never Shopee's server.
        self.dom.route('https://shopee.co.id/**', lambda route: route.fulfill(body='<h1>Redmi</h1><a href="/flash_sale?fromItem=28340353844&amp;promotionId=511589778477216">Mulai pada 12:00, 26 Okt</a>'))
        self.dom.goto('https://shopee.co.id/product/1367937206/28340353844')
        result=self.bridge.request('promotion')
        self.assertEqual(result['campaigns'][0]['promotion_id'],'511589778477216')
        self.assertEqual(result['campaigns'][0]['item_id'],'28340353844')
        self.assertEqual(result['published'],[])

    def test_bootstrap_model_mapping_is_scoped_and_does_not_leak_account(self):
        import json
        data={'initialState':{'DOMAIN_PDP':{'data':{'PDP_BFF_DATA':{'cachedMap':{'1/2':{
            'account':{'token':'must-not-export'},
            'item':{'item_id':2,'shop_id':1,'tier_variations':[{'options':['Black']},{'options':['Phone']}],
                    'models':[{'model_id':123,'name':'Black,Phone','extinfo':{'tier_index':[0,0]},'promotion_id':None}]},
            'bottom_banner':{'flash_sale_preview':{'promotion_id':456,'start_time':1792990800}}
        }}}}}}}
        html='<h1>Phone</h1><script type="text/mfe-initial-data">'+json.dumps(data)+'</script>'
        self.dom.route('https://shopee.co.id/**',lambda route:route.fulfill(body=html))
        self.dom.goto('https://shopee.co.id/product/1/2')
        result=self.bridge.request('promotion')
        self.assertEqual(result['bootstrap']['models'][0]['labels'],['Black','Phone'])
        self.assertEqual(result['bootstrap']['models'][0]['model_id'],'123')
        self.assertEqual(result['bootstrap']['preview']['promotion_id'],'456')
        self.assertNotIn('must-not-export',json.dumps(result))
        self.assertEqual(result['published'],[])
        self.dom.goto('https://shopee.co.id/product/9/8')
        self.assertEqual(self.bridge.request('promotion')['bootstrap']['models'],[])

    def test_purchase_button_aliases_enter_checkout_after_two_variant_selections(self):
        from flashsale.shopee import extract_product
        self.bridge.path='/product/1/2'
        for label in ('Beli Sekarang','Beli Dengan Voucher','Beli Dengan Voucher Rp2.013.472','Beli Dengan Voucher\nRp 2.013.472'):
            with self.subTest(label=label):
                self.dom.set_content('<h1>Phone</h1><section><h2>VARIASI</h2><button class="selection-box-unselected">Black</button></section><section><h2>PAKET</h2><button class="selection-box-unselected">Phone</button></section><input role="spinbutton" value="1" disabled><button id="buy"></button><div id="result"></div>')
                self.dom.locator('#buy').evaluate('(e,label)=>e.textContent=label',label)
                self.dom.evaluate("""()=>{
                  document.querySelectorAll('section button').forEach(b=>b.onclick=()=>{
                    b.className='selection-box-selected';
                    document.querySelector('input').disabled=document.querySelectorAll('.selection-box-selected').length!==2;
                  });
                  document.querySelector('#buy').onclick=()=>document.querySelector('#result').textContent='checkout';
                }""")
                self.session.data=extract_product(self.session.page)
                self.session.purchase_panel_open=False
                self.session.prepare_product({'quantity':2,'variants':['Black','Phone']})
                self.assertEqual(self.dom.locator('#result').inner_text(),'checkout')
                self.assertEqual(self.dom.locator('input').input_value(),'2')

    def test_purchase_alias_rejects_ambiguous_and_disabled_buttons(self):
        self.dom.set_content('<button>Beli Dengan Voucher Rp100</button><button>Beli Sekarang</button>')
        with self.assertRaisesRegex(ValueError,'tidak ditemukan secara unik'):
            self.session.click('Beli Sekarang')
        self.dom.set_content('<button disabled>Beli Dengan Voucher Rp100</button>')
        with self.assertRaisesRegex(ValueError,'dinonaktifkan'):
            self.session.click('Beli Sekarang')

    def test_stock_release_refreshes_then_selects_same_target_when_enabled(self):
        from flashsale.shopee import extract_product
        self.bridge.path='/product/1/2'
        self.dom.set_content('<h1>Phone</h1><section><h2>VARIASI</h2><button class="selection-box-unselected" disabled>Promo Black</button></section><section><h2>PAKET</h2><button class="selection-box-unselected">Phone</button></section><input role="spinbutton" value="1" disabled>')
        self.dom.evaluate("""()=>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{
          b.className=b.className==='selection-box-selected'?'selection-box-unselected':'selection-box-selected';
          document.querySelector('input').disabled=document.querySelectorAll('.selection-box-selected').length!==2;
        })""")
        calls=[]
        def refresh(url):
            calls.append(url)
            if len(calls)==2:self.dom.locator('button').first.evaluate('e=>e.disabled=false')
            self.session.data=extract_product(self.session.page)
        self.session.verify=MagicMock(side_effect=refresh)
        self.session.refresh_released_stock({'url':'https://shopee.co.id/product/1/2','variants':['Promo Black','Phone']})
        self.assertEqual(len(calls),2)
        self.assertEqual(self.dom.locator('.selection-box-selected').count(),2)
        self.assertTrue(self.dom.locator('input').is_enabled())
        self.assertIsNone(self.session.prepared_config)

    def test_stock_release_is_bounded_and_never_selects_another_variant(self):
        self.session.verify=MagicMock()
        self.session.select_scan_choices=MagicMock(return_value=False)
        self.session.cancel_event.wait=MagicMock()
        config={'url':'https://shopee.co.id/product/1/2','variants':['Target','Phone']}
        with self.assertRaisesRegex(ValueError,'10 pemeriksaan'):
            self.session.refresh_released_stock(config)
        self.assertEqual(self.session.verify.call_count,10)
        self.assertTrue(all(call.args==(['Target','Phone'],) for call in self.session.select_scan_choices.call_args_list))

    def test_cart_isolates_target_and_replaces_accumulated_quantity(self):
        self.session.prepare_cart(self.config)
        self.assertEqual(self.dom.locator('#cart input[role=spinbutton]').first.input_value(), '2')
        selected = self.dom.locator('#cart input[role=checkbox][aria-checked=true]')
        self.assertEqual(selected.count(), 1)
        self.assertEqual(selected.locator('..').locator('a').inner_text(), self.session.data['name'])

    def test_bank_and_total_use_actual_radio_and_final_heading(self):
        self.checkout()
        self.session.select_payment('Bank BCA')
        bank = self.session.page.get_by_role('radio', name='Bank BCA', exact=True)
        self.assertTrue(element_selected(bank))
        total, submit = checkout_controls(self.session.page)
        self.assertEqual(total.locator('xpath=following-sibling::*[1]').inner_text(), 'Rp797.500')
        self.assertEqual(submit.inner_text(), 'Buat Pesanan')

    def test_checkout_quantity_is_verified_again(self):
        self.checkout()
        self.session.verify_checkout_item(self.config)
        self.dom.locator('#ordered-quantity').evaluate("e=>e.innerText='52'")
        with self.assertRaisesRegex(ValueError, 'Jumlah produk'):
            self.session.verify_checkout_item(self.config)

    def add_checkout_gift(self, badge='Hadiah', price='', subtotal='', quantity='1'):
        self.dom.locator('.ordered-row').evaluate('''(row, values) => {
          const gift=document.createElement('div');gift.className='gift-row';
          gift.innerHTML='<div><img alt="product image" width="40" height="40"><span class="badge"></span><span>[Gift Not For Sale] Bonus</span></div><div></div><div></div><div></div><div></div>';
          gift.querySelector('.badge').textContent=values[0];
          gift.children[2].textContent=values[1];gift.children[4].textContent=values[2];gift.children[3].textContent=values[3];
          row.after(gift);
        }''', [badge, price, subtotal, quantity])

    def test_checkout_accepts_explicit_free_gifts_and_keeps_target_validation(self):
        self.checkout()
        self.session.bridge=self.bridge
        self.add_checkout_gift()
        self.add_checkout_gift('Free Gift', 'Rp0', 'Rp0', '2')
        snapshot=self.session.page.checkout_snapshot()
        self.assertEqual((snapshot['paid_count'],snapshot['gift_count'],snapshot['unknown_count']),(1,2,0))
        self.session.verify_checkout_item(self.config)
        self.dom.locator('#ordered-quantity').evaluate("e=>e.innerText='3'")
        with self.assertRaisesRegex(ValueError,'Jumlah produk'):
            self.session.verify_checkout_item(self.config)

    def test_checkout_gift_badge_never_hides_charged_or_unmarked_extra_item(self):
        self.checkout()
        self.session.bridge=self.bridge
        for badge,price,subtotal,quantity in [('Hadiah','Rp1.000','Rp1.000','1'),
                                                ('Hadiah','','Rp1','1'),
                                                ('','','','1'),('Hadiah','','','0')]:
            with self.subTest(badge=badge,price=price,subtotal=subtotal,quantity=quantity):
                self.dom.locator('.gift-row').evaluate_all('rows=>rows.forEach(e=>e.remove())')
                self.add_checkout_gift(badge,price,subtotal,quantity)
                with self.assertRaisesRegex(ValueError,'Identitas satu produk'):
                    self.session.verify_checkout_item(self.config)

    def test_checkout_rejects_unrecognized_gift_structure_and_duplicate_target(self):
        self.checkout()
        self.session.bridge=self.bridge
        self.dom.locator('.ordered-row').evaluate("e=>e.after(e.cloneNode(true))")
        with self.assertRaisesRegex(ValueError,'Identitas satu produk'):
            self.session.verify_checkout_item(self.config)
        self.dom.locator('.ordered-row').last.evaluate('e=>e.remove()')
        self.dom.locator('#checkout').evaluate("e=>e.insertAdjacentHTML('beforeend','<div><img alt=\"product image\" width=40 height=40><span>Hadiah</span></div>')")
        with self.assertRaisesRegex(ValueError,'Identitas satu produk'):
            self.session.verify_checkout_item(self.config)

    def test_checkout_native_browser_accepts_gift_but_rejects_paid_extra(self):
        self.checkout()
        self.dom.route('https://shopee.co.id/checkout',lambda route:route.fulfill(body='<html></html>'))
        markup=self.dom.content()
        self.dom.goto('https://shopee.co.id/checkout')
        self.dom.set_content(markup)
        self.session.page=self.dom
        self.add_checkout_gift()
        self.session.verify_checkout_item(self.config)
        self.dom.locator('.gift-row > :nth-child(5)').evaluate("e=>e.innerText='Rp100'")
        with self.assertRaisesRegex(ValueError,'tepat satu baris'):
            self.session.verify_checkout_item(self.config)

    def challenge_state(self, markup):
        self.dom.set_content(markup)
        return self.dom.evaluate('(' + self.source + ')',
            {'operation': 'state', 'expiresAt': 9999999999999})['challenge']

    def test_empty_shopee_captcha_host_is_not_a_challenge(self):
        self.assertFalse(self.challenge_state('<div id="anti_fraud_captcha"></div><button>Buat Pesanan</button>'))
        self.assertFalse(self.challenge_state('<div id="anti_fraud_captcha" style="width:300px;height:100px"></div>'))

    def test_hidden_or_transparent_challenge_is_not_active(self):
        for style in ('display:none', 'visibility:hidden', 'opacity:0'):
            with self.subTest(style=style):
                self.assertFalse(self.challenge_state(
                    f'<div style="{style}"><div id="captcha"><button>Verifikasi</button></div></div>'))

    def test_active_challenge_with_zero_size_host_is_detected(self):
        self.assertTrue(self.challenge_state('<div id="anti_fraud_captcha" style="width:0;height:0">'
            '<div style="position:fixed;width:300px;height:200px"><button>Geser untuk verifikasi</button></div></div>'))

    def test_visible_challenge_text_and_frame_are_detected(self):
        self.assertTrue(self.challenge_state('<div class="captcha-panel">Pilih gambar yang sesuai</div>'))
        self.assertTrue(self.challenge_state('<iframe src="https://example.test/captcha" title="captcha"></iframe>'))

    def test_transparent_native_cart_checkbox_remains_interactive(self):
        # Shopee paints the checkbox through its wrapper; native input opacity is zero.
        self.dom.add_style_tag(content='input[role="checkbox"] {opacity:0}')
        self.session.prepare_cart(self.config)
        selected = self.dom.locator('#cart input[role=checkbox][aria-checked=true]')
        self.assertEqual(selected.count(), 1)
        self.assertEqual(selected.locator('..').locator('a').inner_text(), self.session.data['name'])
        self.assertEqual(self.dom.locator('#cart input[role=spinbutton]').first.input_value(), '2')

    def test_quantity_commit_waits_for_selection_reconciliation(self):
        self.dom.locator('#cart input[role=spinbutton]').first.evaluate("""e => {
          e.onblur = () => {
            const box=e.parentElement.querySelector('input[role=checkbox]');
            box.setAttribute('aria-checked','false');
            setTimeout(()=>box.setAttribute('aria-checked','true'),800);
          };
        }""")
        self.session.prepare_cart(self.config)
        self.assertEqual(self.dom.locator('#cart input[role=checkbox][aria-checked=true]').count(),1)

    def test_hidden_responsive_cart_copy_is_not_an_extra_selected_product(self):
        self.dom.evaluate("""() => {
          const duplicate=document.querySelector('.cart-row').cloneNode(true);
          duplicate.hidden=true;document.getElementById('cart').append(duplicate);
        }""")
        self.session.prepare_cart(self.config)
        visible = self.dom.locator('#cart input[role=checkbox][aria-checked=true]:visible')
        self.assertEqual(visible.count(),1)

    def test_discounted_checkout_ignores_crossed_out_list_price(self):
        self.checkout()
        self.dom.locator('.ordered-row > :nth-child(3)').evaluate(
            "e=>e.innerHTML='<div><span>Rp320.000</span></div><div style=\"text-decoration:line-through\">Rp345.000</div>'")
        self.dom.locator('.ordered-row > :nth-child(5)').evaluate("e=>e.innerText='Rp640.000'")
        self.session.verify_checkout_item(self.config)

    def test_discounted_checkout_still_rejects_wrong_subtotal(self):
        self.checkout()
        self.dom.locator('.ordered-row > :nth-child(3)').evaluate(
            "e=>e.innerHTML='<span>Rp320.000</span><div>Rp345.000</div>'")
        with self.assertRaisesRegex(ValueError, 'Subtotal produk'):
            self.session.verify_checkout_item(self.config)

    def test_discounted_checkout_rejects_ambiguous_price_order(self):
        self.checkout()
        self.dom.locator('.ordered-row > :nth-child(3)').evaluate(
            "e=>e.innerHTML='<div>Rp395.000</div><div>Rp320.000</div>'")
        with self.assertRaisesRegex(ValueError, 'Urutan harga diskon'):
            self.session.verify_checkout_item(self.config)

    def test_observed_megamiss_discounted_product_markup(self):
        self.checkout()
        markup = (ROOT / 'tests/fixtures/discounted_checkout_row.html').read_text()
        self.dom.locator('.ordered-row').evaluate('(e,markup)=>e.outerHTML=markup', markup)
        self.session.data['name'] = 'HMNS Parfum - ALPHA 100ml'
        self.config['quantity'] = 1
        self.session.verify_checkout_item(self.config)

    def test_modern_size_group_is_scoped_and_selected(self):
        from flashsale.shopee import extract_product, variant_scope
        self.dom.set_content('<h1>Kaos</h1>' + (ROOT / 'tests/fixtures/modern_size_group.html').read_text())
        self.bridge.path='/product/208904408/50408026398'
        data=extract_product(self.session.page)
        self.assertEqual([o['label'] for o in data['groups'][0]['options']], ['M','L'])
        scope=variant_scope(self.session.page,data['groups'][0])
        chosen=scope.locator('button').filter(has_text='L')
        self.assertTrue(element_selected(chosen))
        self.assertFalse(element_selected(scope.locator('button').filter(has_text='M')))

    def test_two_variant_groups_do_not_mix_duplicate_option_labels(self):
        from flashsale.shopee import extract_product, variant_scope
        self.dom.set_content('<h1>Produk</h1><section><h2>Warna</h2><button class="selection-box-unselected">S</button></section>'
            '<section><h2>Ukuran</h2><button class="selection-box-selected">S</button><button class="selection-box-unselected">M</button></section>')
        self.bridge.path='/product/1/2'
        data=extract_product(self.session.page)
        self.assertEqual(len(data['groups']),2)
        scope=variant_scope(self.session.page,data['groups'][1])
        self.assertTrue(element_selected(scope.locator('button').filter(has_text='S')))

    def test_batched_checkout_validates_and_rejects_wrong_quantity(self):
        self.checkout()
        self.session.bridge=self.bridge
        self.session.verify_checkout_item(self.config)
        self.dom.locator('#ordered-quantity').evaluate("e=>e.innerText='9'")
        with self.assertRaisesRegex(ValueError, 'Jumlah produk'):
            self.session.verify_checkout_item(self.config)

    def test_stock_dialog_accepts_only_its_own_ok_button(self):
        self.checkout()
        self.dom.evaluate("""() => {const d=document.createElement('div');d.innerHTML='<p>Beberapa barang habis terjual dalam proses pemesanan. Lihat keranjang belanja Anda, dan coba lagi.</p><button onclick="this.parentElement.remove()">OK</button>';document.body.append(d)}""")
        self.assertTrue(self.session.stock_rejection())
        self.assertFalse(self.session.stock_rejection())

    def test_coin_is_toggled_once_and_read_back(self):
        self.checkout()
        self.dom.evaluate("""() => {const d=document.createElement('input');d.type='checkbox';d.setAttribute('role','checkbox');d.setAttribute('aria-label','Click here to redeem Shopee Coins');d.setAttribute('aria-checked','false');d.onclick=()=>d.setAttribute('aria-checked',d.getAttribute('aria-checked')==='false');document.body.append(d)}""")
        self.session.refresh_coins()
        coin=self.dom.locator('input[aria-label="Click here to redeem Shopee Coins"]')
        self.assertEqual(coin.get_attribute('aria-checked'),'true')

    def test_disabled_quantity_does_not_block_variant_verification(self):
        self.dom.set_content('<h1>Kaos</h1>' + (ROOT / 'tests/fixtures/modern_size_group.html').read_text() + '<input role="spinbutton" value="1" disabled>')
        self.bridge.path='/product/208904408/50408026398'
        self.session.page.goto=MagicMock()
        self.session.authenticated=True
        self.session.verify('https://shopee.co.id/product/208904408/50408026398')
        self.assertEqual(len(self.session.data['groups']),1)

    def test_real_guard_pauses_for_fixture_challenge_then_resumes(self):
        self.session.bridge=self.bridge
        self.dom.set_content('<div id="anti_fraud_captcha"><button>Verifikasi</button></div>')
        states=[]
        self.session.status.connect(lambda state,message:states.append(state))
        # Simulate the human completing the local fixture; never solve a real CAPTCHA.
        self.session.snapshot=lambda:self.dom.locator('#anti_fraud_captcha').evaluate('e=>e.remove()')
        ShopeeSession.guard(self.session)
        self.assertEqual(states,['VERIFIKASI','MELANJUTKAN'])
        self.assertFalse(self.session.verification_only)

    def test_variant_preview_updates_dependent_options(self):
        from flashsale.shopee import extract_product
        self.dom.set_content('<h1>Kaos</h1><section><h2>Warna</h2><button class="selection-box-unselected">Hitam</button></section>'
            '<section><h2>Ukuran</h2><button id="size" class="selection-box-unselected" aria-disabled="true">L</button></section>')
        self.dom.locator('button').first.evaluate("e=>e.onclick=()=>{e.className='selection-box-selected';document.getElementById('size').setAttribute('aria-disabled','false')}")
        self.bridge.path='/product/1/2'
        self.session.data=extract_product(self.session.page)
        self.assertTrue(self.session.data['groups'][1]['options'][0]['disabled'])
        self.session.preview_variant({'index':0,'label':'Hitam'})
        self.assertFalse(self.session.data['groups'][1]['options'][0]['disabled'])

    def test_preselected_variant_is_not_toggled_off_during_preparation(self):
        from flashsale.shopee import extract_product
        self.dom.set_content('<h1>Kaos</h1><section><h2>Ukuran</h2><button class="selection-box-selected" onclick="this.className=\"selection-box-unselected\"">L</button></section><input role="spinbutton" value="1">')
        self.dom.locator('button').evaluate("e=>e.onclick=()=>{e.className='selection-box-unselected'}")
        self.bridge.path='/product/1/2'
        self.session.data=extract_product(self.session.page)
        self.session.click=MagicMock()
        self.session.prepare_product({'quantity':1,'variants':['L']})
        self.assertEqual(self.dom.locator('button').get_attribute('class'),'selection-box-selected')

    def test_fixed_cart_variants_are_carried_to_checkout_validation(self):
        self.dom.locator('.cart-row').first.evaluate("e=>{const b=document.createElement('button');b.disabled=true;b.innerText='Variasi: POLOS Rak Holder,WARNA RANDOM';e.append(b)}")
        self.session.prepare_cart(self.config)
        self.assertEqual(self.session.data['fixed_variants'],['polos rak holder','warna random'])
        self.checkout()
        self.dom.locator('.ordered-row > :nth-child(2)').evaluate("e=>e.innerText='POLOS Rak Holder,WARNA RANDOM'")
        self.session.verify_checkout_item(self.config)

    def test_fixed_variants_do_not_allow_ambiguous_product_rows(self):
        self.dom.locator('.cart-row').first.evaluate("e=>{const b=document.createElement('button');b.disabled=true;b.innerText='Variasi: Model A';e.append(b);const copy=e.cloneNode(true);copy.querySelector('button').innerText='Variasi: Model B';e.after(copy)}")
        with self.assertRaisesRegex(ValueError,'secara unik'):
            self.session.prepare_cart(self.config)

    def test_checkout_variation_prefix_matches_fixed_cart_labels(self):
        self.checkout()
        self.session.data['fixed_variants']=['polos rak holder','warna random']
        self.dom.locator('.ordered-row > :nth-child(2)').evaluate("e=>e.innerText='Variasi:  POLOS Rak Holder,WARNA RANDOM'")
        self.session.bridge=self.bridge
        self.session.verify_checkout_item(self.config)

    def test_collapsed_payment_opens_only_payment_change_button(self):
        self.checkout()
        self.dom.evaluate("""() => {
          const radio=document.querySelector('button[aria-label="Transfer Bank"]');radio.hidden=true;
          const heading=[...document.querySelectorAll('h2')].find(e=>e.innerText==='Metode Pembayaran');
          const wrapper=document.createElement('div');heading.before(wrapper);wrapper.append(heading);
          const change=document.createElement('button');change.innerText='UBAH';change.onclick=()=>radio.hidden=false;wrapper.append(change);
          const unrelated=document.createElement('button');unrelated.innerText='UBAH';unrelated.onclick=()=>{throw new Error('wrong change button')};document.body.append(unrelated);
        }""")
        self.session.select_payment('Bank BCA')
        self.assertTrue(element_selected(self.session.page.get_by_role('radio',name='Bank BCA',exact=True)))

    def test_coin_locator_survives_accessible_label_change_in_both_directions(self):
        self.checkout()
        self.dom.evaluate("""() => {
          const coin=document.createElement('input');coin.type='checkbox';coin.setAttribute('role','checkbox');
          coin.setAttribute('aria-label','Click here to redeem Shopee Coins');coin.setAttribute('aria-checked','false');
          coin.onclick=()=>{const checked=coin.getAttribute('aria-checked')!=='true';coin.setAttribute('aria-checked',checked);coin.setAttribute('aria-label',checked?'Coins redeemed':'Click here to redeem Shopee Coins')};
          document.body.append(coin);
        }""")
        self.session.refresh_coins()
        self.assertEqual(self.dom.locator('input[aria-label="Coins redeemed"]').get_attribute('aria-checked'),'true')
        self.session.refresh_coins()
        self.assertEqual(self.dom.locator('input[aria-label="Click here to redeem Shopee Coins"]').get_attribute('aria-checked'),'false')

    def test_prepared_checkout_coin_change_reaches_inspection_without_order(self):
        from datetime import datetime
        from unittest.mock import patch
        from flashsale.core import ZONE
        self.checkout()
        self.session.bridge=self.bridge
        self.session.authenticated=True
        config={**self.config,'payment':'Bank BCA','limit':1000000,'immediate':True,
                'time':datetime.now(ZONE).isoformat(),'refresh_with_coins':True,'stop_before_submit':True}
        self.session.stage_checkout(config)
        self.dom.evaluate("""() => {
          const coin=document.createElement('input');coin.type='checkbox';coin.setAttribute('role','checkbox');
          coin.setAttribute('aria-label','Click here to redeem Shopee Coins');coin.setAttribute('aria-checked','false');
          coin.onclick=()=>{coin.setAttribute('aria-label','Coins redeemed');coin.setAttribute('aria-checked','true');
            [...document.querySelectorAll('h3')].find(h=>h.innerText==='Total Pembayaran').nextElementSibling.innerText='Rp797.495'};
          document.body.append(coin);
        }""")
        states=[]
        self.session.status.connect(lambda state,message:states.append(state))
        with patch('flashsale.shopee.Store') as store:
            self.session.checkout(config)
            store.assert_not_called()
        self.assertEqual(states[-1],'CHECKOUT SIAP')
        self.assertEqual(self.dom.locator('input[aria-label="Coins redeemed"]').get_attribute('aria-checked'),'true')

    def test_released_stock_reaches_submit_without_changing_coins(self):
        from datetime import datetime
        from flashsale.core import ZONE
        self.bridge.path=self.session.data['url'].replace('https://shopee.co.id','')
        self.session.authenticated=True
        self.session.bridge=self.bridge
        self.session.refresh_released_stock=MagicMock()
        self.session.prepare_product=MagicMock()
        self.session.await_checkout=MagicMock(side_effect=lambda config:self.checkout())
        self.session.refresh_coins=MagicMock(side_effect=AssertionError('Coins must be skipped'))
        self.session.submit_order=MagicMock()
        config={**self.config,'payment':'Bank BCA','limit':1000000,'immediate':True,
                'time':datetime.now(ZONE).isoformat(),'wait_stock_release':True,
                'refresh_with_coins':True,'prepare_before_time':True,'stop_before_submit':False}
        self.session.checkout(config)
        self.session.refresh_released_stock.assert_called_once_with(config)
        self.session.prepare_product.assert_called_once_with(config)
        self.session.refresh_coins.assert_not_called()
        self.session.submit_order.assert_called_once()
        self.assertEqual(self.session.submit_order.call_args.args[0],config)

    def test_coin_painted_control_handles_native_and_aria_disagreement_repeatedly(self):
        self.checkout()
        self.dom.evaluate("""() => {
          const label=document.createElement('label');label.className='stardust-checkbox';
          label.innerHTML='<input role="checkbox" type="checkbox" aria-label="Coins redeemed" aria-checked="true" style="opacity:0"><div class="stardust-checkbox__box" style="width:18px;height:18px">x</div>';
          const coin=label.querySelector('input');
          coin.onclick=e=>{e.preventDefault();coin.setAttribute('aria-checked','true')};
          label.querySelector('div').onclick=e=>{e.preventDefault();const checked=coin.getAttribute('aria-checked')!=='true';coin.setAttribute('aria-checked',checked);coin.setAttribute('aria-label',checked?'Coins redeemed':'Click here to redeem Shopee Coins')};
          document.body.append(label);
        }""")
        for index in range(12):
            with self.subTest(index=index):
                self.session.refresh_coins()
                coin=self.dom.locator('input[aria-live],input[aria-label="Coins redeemed"],input[aria-label="Click here to redeem Shopee Coins"]')
                self.assertEqual(coin.get_attribute('aria-checked'),'false' if index%2==0 else 'true')

    def test_payment_category_can_appear_after_heading_without_change_button(self):
        self.checkout()
        self.dom.evaluate("""() => {const radio=document.querySelector('[aria-label="Transfer Bank"]');radio.hidden=true;setTimeout(()=>radio.hidden=false,250)}""")
        self.session.select_payment('Bank BCA')
        self.assertTrue(element_selected(self.session.page.get_by_role('radio',name='Bank BCA',exact=True)))

    def test_missing_coin_does_not_reload_checkout(self):
        self.checkout()
        self.session.page.goto=MagicMock()
        self.assertIsNone(self.session.refresh_coins())
        self.session.page.goto.assert_not_called()

    def test_updated_product_popup_rebuilds_only_before_order_submission(self):
        self.checkout()
        self.session.preparation_request={**self.config,'payment':'Bank BCA'}
        self.dom.evaluate("""() => {document.querySelector('#checkout h2').hidden=true;const d=document.createElement('div');d.id='stale';d.innerHTML='<p>Beberapa informasi produk pada pesananmu telah diperbarui. Mohon kembali ke halaman sebelumnya dan coba lagi.</p><button>OK</button>';d.querySelector('button').onclick=()=>d.remove();document.body.append(d)}""")
        self.session.verify=MagicMock()
        self.session.stage_checkout=MagicMock(side_effect=lambda c:self.dom.locator('#checkout h2').first.evaluate('e=>e.hidden=false'))
        self.session.wait_checkout_ready()
        self.session.verify.assert_called_once_with(self.config['url'])
        self.session.stage_checkout.assert_called_once()
        self.assertEqual(self.dom.locator('#stale').count(),0)

    def test_updated_product_popup_is_not_rebuilt_after_submit(self):
        self.checkout()
        self.session.attempt=9
        self.session.preparation_request={**self.config,'payment':'Bank BCA'}
        self.dom.locator('#checkout h2').first.evaluate('e=>e.hidden=true')
        self.session.verify=MagicMock()
        with self.assertRaisesRegex(ValueError,'belum selesai'):
            self.session.wait_checkout_ready(timeout=.2)
        self.session.verify.assert_not_called()

    def test_custom_model_heading_verifies_while_quantity_disabled(self):
        self.dom.set_content('<h1>Produk model</h1><section><h2>PILIH MODEL PRODUK</h2><button class="selection-box-unselected">Model A</button><button class="selection-box-unselected">Model B</button></section><input role="spinbutton" value="1" disabled>')
        self.bridge.path='/product/1/2'
        self.session.page.goto=MagicMock()
        self.session.authenticated=True
        self.session.verify('https://shopee.co.id/product/1/2')
        self.assertEqual(self.session.data['groups'][0]['name'],'PILIH MODEL PRODUK')
        self.assertEqual(len(self.session.data['groups'][0]['options']),2)
        self.assertFalse(self.dom.locator('input').is_enabled())

    def test_duplicate_hidden_size_heading_does_not_block_verification(self):
        self.dom.set_content('<h1>Kaos</h1><section hidden><h2>UKURAN</h2><button class="selection-box-unselected">S</button></section><section><h2>UKURAN</h2><button class="selection-box-unselected">M</button><button class="selection-box-unselected">L</button></section><input role="spinbutton" value="1" disabled>')
        self.bridge.path='/product/1/2'
        self.session.page.goto=MagicMock()
        self.session.authenticated=True
        self.session.verify('https://shopee.co.id/product/1/2')
        self.assertEqual(len(self.session.data['groups']),1)
        self.assertEqual([o['label'] for o in self.session.data['groups'][0]['options']],['M','L'])

    def test_two_variant_groups_enable_quantity_only_after_both_selections(self):
        self.dom.set_content('<h1>Produk</h1><section><h2>MODEL PILIHAN</h2><button class="selection-box-unselected">A</button><button class="selection-box-unselected">B</button></section><section><h2>SIZE PILIHAN</h2><button class="selection-box-unselected">M</button><button class="selection-box-unselected">L</button></section><input role="spinbutton" value="1" disabled>')
        self.dom.evaluate("""() => document.querySelectorAll('button').forEach(b=>b.onclick=()=>{
          b.parentElement.querySelectorAll('button').forEach(x=>x.className='selection-box-unselected');b.className='selection-box-selected';
          setTimeout(()=>document.querySelector('input').disabled=document.querySelectorAll('.selection-box-selected').length!==2,100);
        })""")
        self.bridge.path='/product/1/2'
        self.session.page.goto=MagicMock()
        self.session.authenticated=True
        self.session.verify('https://shopee.co.id/product/1/2')
        self.assertEqual(len(self.session.data['groups']),2)
        self.session.click=MagicMock()
        self.session.prepare_product({'quantity':2,'variants':['A','L']})
        self.assertTrue(self.dom.locator('input').is_enabled())
        self.assertEqual(self.dom.locator('input').input_value(),'2')
        self.session.click.assert_called_once_with('Beli Sekarang')

    def promo_fixture(self, published=True):
        import json
        from flashsale.shopee import extract_product
        self.dom.set_content('<h1>Redmi</h1><section><h2>Paket</h2><button class="selection-box-unselected">Unit</button><button class="selection-box-unselected">Bundel</button></section><input role="spinbutton" value="1"><div>Flash Sale Mulai 12:00</div><div>Rp950.000</div>')
        self.dom.locator('button').evaluate_all("buttons=>buttons.forEach(b=>b.onclick=()=>b.className=b.className==='selection-box-selected'?'selection-box-unselected':'selection-box-selected')")
        if published:
            data={'@type':'ProductGroup','name':'Redmi','url':'https://shopee.co.id/product/1/2','hasVariant':[
                {'@type':'Product','sku':'unit','model':'Unit','offers':{'name':'Flash Sale','price':'950000','priceCurrency':'IDR','validFrom':'2026-10-26T12:00:00+07:00','availability':'https://schema.org/InStock'}},
                {'@type':'Product','sku':'bundle','model':'Bundel','offers':{'name':'Flash Sale','price':'1100000','priceCurrency':'IDR','validFrom':'2026-10-26T12:00:00+07:00','availability':'https://schema.org/InStock'}}]}
            self.dom.evaluate("data=>{const s=document.createElement('script');s.type='application/ld+json';s.textContent=JSON.stringify(data);document.body.append(s)}",data)
        self.bridge.path='/product/1/2'
        self.session.bridge=self.bridge
        self.session.authenticated=True
        self.session.verify=MagicMock(side_effect=lambda url:setattr(self.session,'data',extract_product(self.session.page)))
        self.session.stage_checkout=MagicMock()
        return {'url':'https://shopee.co.id/product/1/2','quantity':1,'payment':'Bank BCA','target':'2026-10-26T12:00:00+07:00','limit':1000000,'max_combinations':64}

    def test_promo_scan_prepares_only_explicit_unique_sku(self):
        import tempfile
        from unittest.mock import patch
        config=self.promo_fixture()
        with tempfile.TemporaryDirectory() as folder,patch('flashsale.shopee.DATA',Path(folder)),patch('flashsale.shopee.Store') as store:
            self.session.scan_promotion(config)
            store.assert_not_called()
        self.session.stage_checkout.assert_called_once()
        self.assertEqual(self.session.stage_checkout.call_args.args[0]['variants'],['Unit'])

    def test_banner_only_or_incomplete_scan_never_prepares_a_random_sku(self):
        import tempfile
        from unittest.mock import patch
        for published,maximum in ((False,64),(True,1)):
            with self.subTest(published=published,maximum=maximum):
                config=self.promo_fixture(published);config['max_combinations']=maximum
                with tempfile.TemporaryDirectory() as folder,patch('flashsale.shopee.DATA',Path(folder)):
                    self.session.scan_promotion(config)
                self.session.stage_checkout.assert_not_called()
