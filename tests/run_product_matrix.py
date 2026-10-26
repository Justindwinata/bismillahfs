"""Repeat actual backend flows against local DOM based on observed public products.
No Shopee network requests, order creation, or CAPTCHA solving.
"""
import html
import itertools
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from flashsale.bridge import ChromePage
from flashsale.core import ROOT, ZONE
from flashsale.shopee import ShopeeSession, extract_product

class MatrixBridge:
    client_protocol=8
    def __init__(self,page,source): self.page,self.source=page,source
    def request(self,operation,**kwargs):
        route=self.page.evaluate('document.body.dataset.route')
        if operation=='info': return {'url':'https://shopee.co.id'+route,'complete':True}
        if operation=='focus': return True
        if operation in ('dom','state','groups','checkout'):
            result=self.page.evaluate('('+self.source+')',{'operation':operation,'expiresAt':9999999999999,**kwargs})
            if operation in ('state','checkout'): result['url']='https://shopee.co.id'+route
            return result
        raise AssertionError(operation)

def content(product,choices,coin_checked,collapsed):
    name=html.escape(product['name'])
    path=product['url'].replace('https://shopee.co.id','')
    groups=''.join(re.sub(r'\s(?:src|srcset)="[^"]*"','',g['html']) for g in product['groups'])
    fixed=['POLOS Rak Holder','WARNA RANDOM'] if '/774489951/' in path else []
    labels=choices or fixed
    variants=html.escape(','.join(labels))
    variant_button=f'<button {"disabled" if fixed else ""}>Variasi: {variants}</button>' if labels else ''
    return f'''<body data-route="{path}">
    <section id="product"><h1>{name}</h1>{groups}<input id="pqty" role="spinbutton" value="1"><button id="buy">Beli Sekarang</button></section>
    <section id="cart" hidden><div id="target"><label><input role="checkbox" type="checkbox" aria-label="Click here to select this product" aria-checked="true" style="opacity:0"><div class="stardust-checkbox__box" style="width:18px;height:18px">x</div></label><a href="{path}">{name}</a>{variant_button}<input id="cqty" role="spinbutton" value="5"></div></section>
    <section id="checkout" hidden><h2>Produk Dipesan</h2><div><div><img alt="product image" width="40" height="40"><span>{name}</span></div><div>{'Variasi: '+variants if variants else ''}</div><div>Rp10.000</div><div id="ordered">1</div><div id="subtotal">Rp10.000</div></div>
    <div><h2>Metode Pembayaran</h2><button id="change" {'' if collapsed else 'hidden'}>Ubah</button></div>
    <button id="transfer" role="radio" aria-label="Transfer Bank" aria-checked="false" {'hidden' if collapsed else ''}>Transfer Bank</button>
    <button id="qris" role="radio" aria-label="QRIS" aria-checked="false" {'hidden' if collapsed else ''}>QRIS</button>
    <div id="banks" hidden><div role="radio" aria-checked="false">Bank BCA</div></div>
    <label><input id="coins" role="checkbox" type="checkbox" aria-label="{'Coins redeemed' if coin_checked else 'Click here to redeem Shopee Coins'}" aria-checked="{str(coin_checked).lower()}" style="opacity:0"><div class="stardust-checkbox__box" style="width:18px;height:18px">x</div></label>
    <h3>Total Pembayaran</h3><div id="total">Rp15.000</div><button id="submit">Buat Pesanan</button></section></body>'''

def attach(page):
    page.evaluate('''() => {
      window.submissions=0;
      const money=v=>'Rp'+v.toLocaleString('id-ID');
      const recalc=()=>{const q=Number(document.getElementById('cqty').value);document.getElementById('ordered').innerText=q;document.getElementById('subtotal').innerText=money(q*10000);document.getElementById('total').innerText=money(q*10000+5000-(document.getElementById('coins').getAttribute('aria-checked')==='true'?5:0))};
      const variantButtons=[...document.querySelectorAll('#product button.product-variation,#product button[class*="selection-box-"]')];
      if(variantButtons.length)document.getElementById('pqty').disabled=true;
      variantButtons.forEach(b=>{b.className='selection-box-unselected';b.onclick=()=>{const root=b.closest('section,[role="group"]')||b.parentElement;root.querySelectorAll('button.product-variation,button[class*="selection-box-"]').forEach(x=>x.className='selection-box-unselected');b.className='selection-box-selected';const groups=[...new Set(variantButtons.map(x=>x.closest('section,[role=group]')||x.parentElement))];document.getElementById('pqty').disabled=!groups.every(g=>g.querySelector('.selection-box-selected'))}});
      document.getElementById('buy').onclick=()=>{document.getElementById('product').hidden=true;document.getElementById('cart').hidden=false;document.body.dataset.route='/cart'};
      document.getElementById('cqty').onblur=recalc;
      document.querySelectorAll('.stardust-checkbox__box').forEach(s=>s.onclick=e=>{e.preventDefault();const input=s.parentElement.querySelector('input');const checked=input.getAttribute('aria-checked')!=='true';input.setAttribute('aria-checked',checked);if(input.id==='coins'){input.setAttribute('aria-label',checked?'Coins redeemed':'Click here to redeem Shopee Coins');recalc()}});
      const next=document.createElement('button');next.innerText='Checkout';document.getElementById('cart').append(next);next.onclick=()=>{document.getElementById('cart').hidden=true;document.getElementById('checkout').hidden=false;document.body.dataset.route='/checkout';recalc()};
      document.getElementById('change').onclick=()=>{document.getElementById('transfer').hidden=false;document.getElementById('qris').hidden=false};
      document.getElementById('transfer').onclick=e=>{e.currentTarget.setAttribute('aria-checked','true');document.getElementById('banks').hidden=false};
      document.getElementById('qris').onclick=e=>e.currentTarget.setAttribute('aria-checked','true');
      document.querySelector('#banks [role=radio]').onclick=e=>e.currentTarget.setAttribute('aria-checked','true');
      document.getElementById('submit').onclick=()=>window.submissions++;
    }''')

def main():
    products=json.loads((ROOT/'tests/fixtures/product_matrix_observed.json').read_text())
    source=(ROOT/'chrome-extension/background.js').read_text();source=source[source.index('function executeDom('):source.index('\nasync function run(')]
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for product in products:
            options=[[o['label'] for o in g['options'] if not o['disabled']] for g in product['groups']]
            combinations=list(itertools.product(*options)) if options else [()]
            for choices in combinations:
                for repeat in range(5):
                    for quantity in (1,2):
                        page=browser.new_page();page.route('**/*',lambda route:route.abort())
                        page.set_content(content(product,choices,repeat%2==0,repeat%2==1));attach(page)
                        bridge=MatrixBridge(page,source);session=ShopeeSession(bridge=bridge);session.page=ChromePage(bridge);session.authenticated=True
                        session.page.goto=lambda *args,**kwargs:None
                        session.verify(product['url'])
                        config={'url':product['url'],'variants':list(choices),'quantity':quantity,'payment':'Bank BCA' if repeat%2 else 'QRIS','limit':100000,'time':datetime.now(ZONE).isoformat(),'immediate':True,'refresh_with_coins':True,'stop_before_submit':True}
                        begin=time.perf_counter()
                        try:
                            with patch('flashsale.shopee.Store') as store:
                                session.stage_checkout(config);session.checkout(config);store.assert_not_called()
                            assert page.evaluate('window.submissions')==0
                            page.evaluate("""() => {const d=document.createElement('div');d.innerHTML='<p>Beberapa barang habis terjual dalam proses pemesanan. Lihat keranjang belanja Anda, dan coba lagi.</p><button>OK</button>';d.querySelector('button').onclick=()=>d.remove();document.body.append(d)}""")
                            assert session.stock_rejection() is True
                            outcome='pass'
                        except Exception as exc: outcome=f'{type(exc).__name__}: {exc}'
                        results.append({'product':product['name'],'variants':list(choices),'quantity':quantity,'repeat':repeat,'payment':config['payment'],'initial_coin_checked':repeat%2==0,'result':outcome,'local_elapsed_ms':round((time.perf_counter()-begin)*1000,1)})
                        page.close()
            print(product['name'],sum(r['product']==product['name'] for r in results),'cases',flush=True)
        browser.close()
    report={'scope':'Local DOM simulation using observed public product groups; no live server order verification','cases':results,'passed':sum(r['result']=='pass' for r in results),'total':len(results)}
    (ROOT/'.local').mkdir(parents=True, exist_ok=True, mode=0o700)
    (ROOT/'.local/product-matrix-results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({k:v for k,v in report.items() if k!='cases'}))
    if report['passed']!=report['total']:
        print([r for r in results if r['result']!='pass'][:3]);raise SystemExit(1)
if __name__=='__main__':main()
