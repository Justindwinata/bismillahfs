"""Visible-browser Shopee workflow. No private API or challenge bypass."""
from __future__ import annotations

import queue
import json
import re
import threading
import time
import itertools
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import urlparse, urlunparse, urljoin

from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright

from .core import DATA, Job, Store, ZONE, rupiah
from .bridge import ChromePage


def unique_visible(locator):
    found = [locator.nth(i) for i in range(min(locator.count(), 100)) if locator.nth(i).is_visible()]
    return found[0] if len(found) == 1 else None


def is_checkout_url(url):
    parsed = urlparse(url)
    return parsed.scheme == 'https' and parsed.hostname == 'shopee.co.id' and bool(re.match(r'^/checkout(?:/|$)', parsed.path))


def element_selected(element):
    for name in ('aria-checked', 'aria-selected', 'aria-pressed'):
        value = element.get_attribute(name)
        if value in ('true', 'false'):
            return value == 'true'
    classes = element.get_attribute('class') or ''
    return bool(re.search(r'(?:^|\s)(?:[\w-]+--(?:selected|checked)|selection-box-selected)(?:\s|$)', classes))


# Shopee renders the optional price inside the accessible button name.
BUY_BUTTON_PATTERN = re.compile(r'^\s*Beli\s+(?:Sekarang|Dengan\s+Voucher)(?:\s+Rp\s*[0-9][0-9.,]*)?\s*$', re.I)


def payment_category(label):
    if label in ('Bank BCA', 'Bank BNI', 'Bank BRI', 'Bank Mandiri'):
        return 'Transfer Bank'
    if label in ('Alfamart', 'Indomaret'):
        return 'Bayar Tunai di Mitra/Agen'
    if label == 'QRIS':
        return 'QRIS'
    raise ValueError('Metode pembayaran belum didukung secara spesifik. Pilih bank atau QRIS yang tersedia pada dashboard.')


def validate_checkout_columns(columns, config):
    quantity_text = columns[3].strip()
    if not re.fullmatch(r'\d+', quantity_text):
        raise ValueError('Kolom jumlah produk checkout belum terbaca sebagai bilangan bulat.')
    if int(quantity_text) != config['quantity']:
        raise ValueError('Jumlah produk pada checkout berbeda dari dashboard.')
    variant_text = re.sub(r'^(?:Variasi|Variation)\s*:\s*', '', columns[1].strip(), flags=re.I)
    labels = [s.strip().casefold() for s in variant_text.split(',') if s.strip()]
    if sorted(labels) != sorted(str(s).strip().casefold() for s in config['variants']):
        raise ValueError('Varian pada ringkasan checkout berbeda dari dashboard.')
    unit_text = columns[2].strip()
    pattern = r'Rp\s*[\d.]+(?:,\d{1,2})?'
    amounts = re.findall(pattern, unit_text)
    if len(amounts) not in (1, 2) or re.sub(pattern, '', unit_text).strip():
        raise ValueError('Kolom harga satuan checkout belum terbaca secara tegas.')
    unit = rupiah(amounts[0])
    if len(amounts) == 2 and rupiah(amounts[1]) < unit:
        raise ValueError('Urutan harga diskon dan harga awal checkout belum dapat dipastikan.')
    if unit <= 0 or unit * config['quantity'] != rupiah(columns[4].strip()):
        raise ValueError('Subtotal produk checkout tidak konsisten dengan harga dan jumlah.')


def checkout_controls(page):
    if isinstance(page, ChromePage) and page.bridge.client_protocol >= 7:
        state = page.checkout_snapshot()
        if not is_checkout_url(state.get('url', '')) or not state.get('complete'):
            raise ValueError('Struktur checkout belum lengkap atau tab bukan checkout.')
        return (page.locator('h3').filter(has_text=re.compile(r'^Total Pembayaran$', re.I)),
                page.get_by_role('button', name=re.compile(r'^Buat Pesanan$', re.I)))
    if not is_checkout_url(page.url):
        raise ValueError('Tab tidak berada pada halaman checkout. Tidak ada metode pembayaran yang diubah.')
    ordered = unique_visible(page.locator('h2,h3').filter(has_text=re.compile(r'^Produk Dipesan$', re.I)))
    payment = unique_visible(page.locator('h2,h3').filter(has_text=re.compile(r'^Metode Pembayaran$', re.I)))
    total = unique_visible(page.locator('h3').filter(has_text=re.compile(r'^Total Pembayaran$', re.I)))
    submit = unique_visible(page.get_by_role('button', name=re.compile(r'^Buat Pesanan$', re.I)))
    if any(value is None for value in (ordered, payment, total, submit)):
        raise ValueError('Struktur checkout belum lengkap: produk, pembayaran, total final, atau tombol pemesanan belum terbaca.')
    return total, submit


def quantity_field(page):
    for locator in (page.get_by_role('spinbutton'), page.locator('input[role="spinbutton"], input.shopee-input-quantity__input, .shopee-input-quantity input')):
        field = unique_visible(locator)
        if field is not None:
            return field
    for label in ('Kuantitas', 'Jumlah', 'Quantity'):
        heading = unique_visible(page.get_by_text(label, exact=True))
        if heading is not None:
            scope = heading
            for _ in range(3):
                scope = scope.locator('..')
                field = unique_visible(scope.locator('input:not([type="hidden"]):not([type="password"])'))
                if field is not None:
                    return field
    return None


def shared_url(value):
    match = re.search(r'https://[^\s<>]+', value.strip())
    if not match:
        raise ValueError('Tempel tautan produk atau teks Bagikan dari aplikasi Shopee.')
    url = match[0].rstrip(').,')
    parsed = urlparse(url)
    if parsed.username or parsed.password or parsed.hostname not in ('shopee.co.id', 'id.shp.ee', 'shope.ee'):
        raise ValueError('Tautan harus berasal dari Shopee Indonesia atau tautan Bagikan Shopee.')
    if parsed.hostname == 'shopee.co.id':
        return product_url(url)
    return url


def product_url(value):
    parsed = urlparse(value.strip())
    if parsed.scheme != 'https' or parsed.hostname != 'shopee.co.id' or parsed.username or parsed.password:
        raise ValueError('Masukkan tautan HTTPS lengkap dari shopee.co.id, bukan tautan pendek.')
    if not (re.search(r'-i\.\d+\.\d+', parsed.path) or re.fullmatch(r'/product/\d+/\d+/?', parsed.path)):
        raise ValueError('Tautan harus menunjuk satu produk Shopee.')
    match = re.search(r'-i\.(\d+)\.(\d+)', parsed.path) or re.search(r'/product/(\d+)/(\d+)', parsed.path)
    return f'https://shopee.co.id/product/{match[1]}/{match[2]}'


def variant_scope(page, group):
    if 'button_index' in group:
        scope = page.locator('button.product-variation, button[class*="selection-box-"]').nth(group['button_index'])
        for _ in range(group['levels']):
            scope = scope.locator('..')
        return scope
    scope = page.get_by_text(re.compile('^' + re.escape(group['anchor']) + '$', re.I), exact=True).first
    for _ in range(group['levels']):
        scope = scope.locator('..')
    return scope


def read_labeled_variants(page):
    groups = []
    for label in ('Ukuran', 'Warna', 'Variasi', 'Model', 'Size', 'Color', 'Jenis', 'Motif', 'Paket'):
        heading = page.get_by_text(re.compile('^' + label + '$', re.I), exact=True)
        if heading.count() != 1 or not heading.first.is_visible():
            continue
        for level in range(1, 4):
            group = {'name': label, 'anchor': label, 'levels': level}
            buttons = variant_scope(page, group).locator('button, [role="button"]')
            count = buttons.count()
            if count > 100:
                break
            options = []
            for i in range(count):
                item = buttons.nth(i)
                if not item.is_visible():
                    continue
                text = item.inner_text().strip()
                if text and len(text) <= 50:
                    options.append({'label': text, 'disabled': not item.is_enabled()})
            if options and len({item['label'] for item in options}) == len(options):
                group['options'] = options
                groups.append(group)
                break
    return groups


def extract_product(page):
    title = page.locator('h1').first
    title.wait_for(state='visible', timeout=15000)
    name = title.inner_text().strip()
    if not name:
        raise ValueError('Nama produk tidak terbaca. Periksa browser.')
    # Only visible UI is inspected. Group discovery is conservative: unsupported
    # markup produces an explicit manual-review state rather than invented data.
    groups = page.evaluate('''() => {
      const visible = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
      const buttons = [...document.querySelectorAll('button.product-variation')].filter(visible);
      const map = new Map();
      for (const b of buttons) {
        let root = b.parentElement;
        while (root.parentElement && root.parentElement.querySelectorAll('button.product-variation').length === root.querySelectorAll('button.product-variation').length && root.parentElement.tagName !== 'MAIN') {
          if (root.parentElement.querySelectorAll('button').length > buttons.length + 3) break;
          root = root.parentElement;
        }
        const options = [...root.querySelectorAll('button.product-variation')].filter(visible).map(x => ({label:x.innerText.trim(), disabled:x.disabled || x.getAttribute('aria-disabled') === 'true'}));
        const key = options.map(x=>x.label).join('|');
        if (!map.has(key)) map.set(key, {name:(root.innerText.split('\\n')[0] || 'Varian').trim(), options});
      }
      return [...map.values()];
    }''')
    if not groups:
        groups = read_labeled_variants(page)
    return {'name': name, 'groups': groups, 'url': product_url(page.url)}


class ShopeeSession(QThread):
    status = Signal(str, str)
    log = Signal(str)
    frame = Signal(bytes)
    account = Signal(bool, str)
    product = Signal(dict)
    finished_order = Signal(str)
    busy = Signal(bool)
    verification_view = Signal(bool)
    promotion = Signal(dict)

    def __init__(self, profile='shopee_utama', bridge=None):
        super().__init__()
        self.profile = profile
        self.commands = queue.Queue()
        self.stop_event = threading.Event()
        self.cancel_event = threading.Event()
        self.resume_event = threading.Event()
        self.data = None
        self.authenticated = False
        self.attempt = None
        self.bridge = bridge
        self.last_snapshot = 0
        self.purchase_panel_open = False
        self.report = None
        self.run_started = None
        self.verification_only = False
        self.prepared_config = None
        self.prepared_payment = None
        self.preparation_request = None

    def send(self, command, value=None):
        self.commands.put((command, value))

    def emit_status(self, state, message):
        self.verification_only = state == 'VERIFIKASI'
        self.verification_view.emit(self.verification_only)
        if self.report is not None:
            self.report['stages'].append({'state': state, 'elapsed_ms': round((time.monotonic() - self.run_started) * 1000, 1)})
        self.status.emit(state, message)
        self.log.emit(message)

    def snapshot(self):
        if not self.verification_only:
            return
        if time.monotonic() - self.last_snapshot < .7:
            return
        self.last_snapshot = time.monotonic()
        try:
            self.frame.emit(self.page.screenshot(type='jpeg', quality=65, timeout=2500))
        except Exception:
            pass

    def check(self):
        if self.stop_event.is_set() or self.cancel_event.is_set():
            raise InterruptedError('Tugas dihentikan pengguna.')

    def challenge(self):
        if self.bridge and self.bridge.client_protocol >= 3:
            return bool(self.page.browser_state()['challenge'])
        path = urlparse(self.page.url).path.lower()
        loc = self.page.locator('[class*="captcha"], [id*="captcha"], iframe[src*="captcha"]')
        return ('captcha' in path or '/verify' in path or
                any(loc.nth(i).is_visible() for i in range(min(loc.count(), 20))))

    def guard(self):
        self.check()
        state = self.page.browser_state() if self.bridge and self.bridge.client_protocol >= 3 else None
        url = state['url'] if state is not None else self.page.url
        if urlparse(url).hostname != 'shopee.co.id':
            raise ValueError('Browser keluar dari Shopee Indonesia; periksa halaman secara manual.')
        challenged = bool(state['challenge']) if state is not None else self.challenge()
        was_challenged = challenged
        if challenged:
            self.resume_event.clear()
            self.emit_status('VERIFIKASI', 'Selesaikan CAPTCHA/verifikasi di browser. Bot melanjutkan otomatis setelah tantangan hilang.')
            self.page.bring_to_front()
        while challenged:
            self.check()
            self.snapshot()
            self.resume_event.wait(.3)
            self.resume_event.clear()
            state = self.page.browser_state() if state is not None else None
            url = state['url'] if state is not None else self.page.url
            challenged = bool(state['challenge']) if state is not None else self.challenge()
        if was_challenged:
            self.emit_status('MELANJUTKAN', 'Verifikasi keamanan selesai. Bot melanjutkan tugas otomatis.')
        if '/buyer/login' in url:
            self.authenticated = False
            self.account.emit(False, 'Sesi kedaluwarsa. Login kembali.')
            raise ValueError('Shopee meminta login kembali.')

    def preflight(self):
        self.check()
        if self.bridge and self.bridge.client_protocol < 8:
            raise ValueError('Muat ulang ekstensi ke versi 0.6.0 lalu hubungkan ulang sebelum menjalankan tugas.')
        if not self.authenticated or not self.data:
            raise ValueError('Login dan produk harus diperiksa terlebih dahulu.')
        self.guard()
        if is_checkout_url(self.page.url):
            prepared = self.prepared_config or self.preparation_request
            if prepared is None:
                raise ValueError('Checkout belum terhubung dengan produk dan jumlah yang diverifikasi.')
            self.verify_checkout_item(prepared)
        elif product_url(self.page.url) != self.data['url']:
            raise ValueError('Tab telah berpindah dari produk terverifikasi. Periksa tautan kembali.')
        self.emit_status('PEMERIKSAAN LULUS', 'Koneksi, sesi, dan halaman produk siap. Pemeriksaan ini tidak menekan tombol pembelian atau membuktikan checkout.')

    def save_report(self, outcome):
        if self.report is None:
            return
        if outcome == 'finished' and self.report['stages']:
            last_state = self.report['stages'][-1]['state']
            outcome = {'SELESAI': 'pending_payment_confirmed', 'CHECKOUT SIAP': 'inspection_complete_no_order',
                       'CHECKOUT DISIAPKAN': 'checkout_prepared_no_order', 'PROMO BELUM PASTI': 'promotion_unconfirmed'}.get(last_state, outcome)
        self.report['outcome'] = outcome
        if self.bridge:
            self.report['bridge_calls'] = list(self.bridge.metrics)[-100:]
        try:
            DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
            name = 'latest-preparation' if self.report.get('kind') == 'preparation' else 'latest-run'
            temporary = DATA / (name + '.tmp')
            temporary.write_text(json.dumps(self.report, indent=2, ensure_ascii=False))
            temporary.replace(DATA / (name + '.json'))
        except OSError:
            self.log.emit('Laporan pengujian tidak dapat disimpan; periksa izin folder .local.')
        self.report = None

    def login_check(self):
        self.guard()
        # Native querySelectorAll in the Chrome extension cannot parse
        # Playwright's nonstandard :has-text() pseudo-class.
        marker = self.page.locator('.navbar__username, a[href*="/user/account"]')
        visible = any(marker.nth(i).is_visible() for i in range(min(marker.count(), 10)))
        if not visible:
            logout = self.page.get_by_role('button', name='Log Out', exact=True)
            visible = any(logout.nth(i).is_visible() for i in range(min(logout.count(), 10)))
        if not visible:
            raise ValueError('Login belum terbukti dari halaman. Selesaikan login, buka beranda Shopee, lalu periksa lagi.')
        self.authenticated = True
        username = self.page.locator('.navbar__username')
        name = username.first.inner_text().strip() if username.count() and username.first.is_visible() else 'Akun Shopee'
        self.account.emit(True, name)
        self.emit_status('AKUN SIAP', 'Login terdeteksi. Masukkan tautan produk untuk diperiksa.')

    def click(self, label):
        self.guard()
        pattern = BUY_BUTTON_PATTERN if label == 'Beli Sekarang' else re.compile('^' + re.escape(label) + '$', re.I)
        button = unique_visible(self.page.get_by_role('button', name=pattern, exact=True))
        if button is None:
            button = unique_visible(self.page.get_by_text(pattern, exact=True))
        if button is None:
            display_label = 'Beli Sekarang / Beli Dengan Voucher' if label == 'Beli Sekarang' else label
            raise ValueError(f'Tombol “{display_label}” tidak ditemukan secara unik. Periksa halaman browser.')
        if not button.is_enabled():
            raise ValueError(f'Tombol pembelian masih dinonaktifkan Shopee. Periksa kelengkapan varian dan stok.')
        button.click(timeout=12000)

    def prepare_product(self, config):
        self.emit_status('MENYIAPKAN PRODUK', 'Mencari pilihan jumlah pada halaman produk atau panel pembelian mobile.')
        qty = quantity_field(self.page)
        opened_panel = qty is None
        if opened_panel:
            self.click('Beli Sekarang')
            self.purchase_panel_open = True
            self.emit_status('PILIHAN MOBILE', 'Menunggu panel varian/jumlah setelah tombol pembelian.')
            deadline = time.monotonic() + 12
            while qty is None and time.monotonic() < deadline:
                self.guard()
                qty = quantity_field(self.page)
                self.snapshot()
                if qty is None:
                    self.cancel_event.wait(.25)
        if qty is None:
            raise ValueError('Panel pembelian belum menampilkan kolom jumlah yang dapat diverifikasi. Belum ada pesanan yang dikirim.')
        in_mobile_panel = opened_panel or self.purchase_panel_open
        groups = read_labeled_variants(self.page) if in_mobile_panel else self.data['groups']
        if len(groups) != len(config['variants']):
            self.data['groups'] = groups
            self.product.emit(self.data)
            raise ValueError('Pilihan varian baru ditemukan pada panel mobile. Pilih varian pada dashboard, lalu aktifkan tugas kembali.')
        for group, label in zip(groups, config['variants']):
            scope = variant_scope(self.page, group).locator('button, [role="button"]') if group.get('anchor') or 'button_index' in group else self.page.locator('button.product-variation, button[class*="selection-box-"]')
            item = unique_visible(scope.filter(has_text=re.compile('^' + re.escape(label) + '$')))
            if item is None:
                raise ValueError('Pilihan varian tidak unik atau markup produk berubah.')
            if not element_selected(item):
                item.click()
            self.wait_selected(item)
        if not qty.is_enabled():
            deadline = time.monotonic() + 12
            while not qty.is_enabled():
                checked_at = time.monotonic()
                self.guard()
                deadline += time.monotonic() - checked_at
                if time.monotonic() >= deadline:
                    raise ValueError('Varian sudah dipilih, tetapi jumlah masih dinonaktifkan Shopee. Periksa ketersediaan kombinasi stok tersebut.')
                self.cancel_event.wait(.1)
        if qty.input_value().strip() != str(config['quantity']):
            qty.fill(str(config['quantity']))
        # A successful fill call doesn't prove the requested quantity was applied.
        deadline = time.monotonic() + 3
        while qty.input_value().strip() != str(config['quantity']):
            self.check()
            if time.monotonic() >= deadline:
                raise ValueError('Jumlah pada halaman tidak sama dengan dashboard; pemesanan dihentikan.')
            self.cancel_event.wait(.15)
        self.emit_status('JUMLAH TERVERIFIKASI', f'Jumlah {config["quantity"]} sudah terbaca kembali dari kolom produk.')
        if in_mobile_panel:
            scope = qty
            confirm = None
            for _ in range(7):
                scope = scope.locator('..')
                confirm = unique_visible(scope.locator('button, [role="button"], a').filter(has_text=BUY_BUTTON_PATTERN))
                if confirm is not None:
                    break
            if confirm is None:
                raise ValueError('Tombol konfirmasi panel mobile belum dikenali secara unik; proses dihentikan.')
            self.guard()
            if not confirm.is_enabled():
                raise ValueError('Tombol konfirmasi pembelian masih dinonaktifkan Shopee.')
            confirm.click()
            self.purchase_panel_open = False
        else:
            self.click('Beli Sekarang')

    def wait_selected(self, element, expected=True):
        deadline = time.monotonic() + 4
        while element_selected(element) != expected:
            checked_at = time.monotonic()
            self.guard()
            deadline += time.monotonic() - checked_at
            if time.monotonic() >= deadline:
                raise ValueError('Pilihan pada halaman tidak sesuai konfigurasi dashboard.')
            self.cancel_event.wait(.1)

    def click_checkbox(self, checkbox):
        skin = unique_visible(checkbox.locator('..').locator('.stardust-checkbox__box'))
        # Shopee can expose checked=false on the invisible native input even when
        # aria-checked=true. Activate the same painted control a person clicks.
        (skin if skin is not None else checkbox).click()

    def preview_variant(self, value):
        self.guard()
        if self.data and self.prepared_config is not None and is_checkout_url(self.page.url):
            self.page.goto(self.data['url'])
            self.prepared_config = None
        if not self.data or product_url(self.page.url) != self.data['url']:
            raise ValueError('Buka kembali produk yang diverifikasi sebelum mengubah varian.')
        group = self.data['groups'][value['index']]
        scope = (variant_scope(self.page, group).locator('button,[role="button"]')
                 if group.get('anchor') or 'button_index' in group else self.page.locator('button.product-variation'))
        option = unique_visible(scope.filter(has_text=re.compile('^' + re.escape(value['label']) + '$')))
        if option is None or not option.is_enabled():
            raise ValueError('Kombinasi varian ini tidak tersedia.')
        if not element_selected(option):
            option.click()
        self.wait_selected(option)
        self.data = extract_product(self.page)
        self.product.emit(self.data)
        self.emit_status('VARIAN DIPERBARUI', 'Pilihan dan ketersediaan kombinasi varian diperbarui dari Shopee.')

    @staticmethod
    def selection_key(config):
        return config['url'], int(config['quantity']), tuple(config['variants'])

    def stage_checkout(self, config):
        if not self.data:
            raise ValueError('Produk belum diverifikasi.')
        config = {**config, 'url': self.data['url']}
        self.preparation_request = dict(config)
        self.prepared_config = None
        if urlparse(self.page.url).path.rstrip('/') == '/cart':
            self.await_checkout(config)
        elif not is_checkout_url(self.page.url):
            self.prepare_product(config)
            self.await_checkout(config)
        self.verify_checkout_item(config)
        self.prepared_payment = None
        if config.get('payment') in ('QRIS','Bank BCA','Bank BNI','Bank BRI','Bank Mandiri','Alfamart','Indomaret'):
            self.select_payment(config['payment'])
            self.prepared_payment = config['payment']
        self.prepared_config = dict(config)
        self.emit_status('CHECKOUT DISIAPKAN', 'Checkout siap. Jalankan sekarang memperbarui koin dan memesan setelah harga memenuhi batas; belum ada pesanan dikirim.')

    def prepare_cart(self, config):
        if urlparse(self.page.url).path.rstrip('/') != '/cart':
            raise ValueError('Pemilihan produk keranjang hanya dilakukan di halaman keranjang.')
        self.emit_status('MEMERIKSA KERANJANG', 'Memilih hanya produk target dan menetapkan jumlah tepat sesuai dashboard.')
        _, shop, item = urlparse(config['url']).path.rstrip('/').rsplit('/', 2)
        links = self.page.locator(f'a[href*="-i.{shop}.{item}"], a[href*="/product/{shop}/{item}"]').filter(has_text=re.compile('^' + re.escape(self.data['name']) + '$', re.I))
        links.first.wait_for(state='visible', timeout=12000)
        candidates = []
        fixed_labels = []
        for i in range(min(links.count(), 30)):
            link = links.nth(i)
            if not link.is_visible():
                continue
            scope = link
            for _ in range(7):
                scope = scope.locator('..')
                qty = unique_visible(scope.locator('input[role="spinbutton"], input[type="number"]'))
                box = unique_visible(scope.locator('input[role="checkbox"][aria-label="Click here to select this product"]'))
                if qty is not None and box is not None:
                    variant = unique_visible(scope.locator('button').filter(has_text=re.compile(r'^Variasi:', re.I)))
                    row_labels = [] if variant is None else [s.strip().casefold() for s in re.sub(r'^Variasi:\s*', '', variant.inner_text(), flags=re.I).split(',')]
                    fixed = (not config['variants'] and not self.data.get('groups') and variant is not None
                             and not variant.is_enabled() and bool(row_labels))
                    if fixed or sorted(row_labels) == sorted(str(s).strip().casefold() for s in config['variants']):
                        candidates.append((scope, qty, box, row_labels if fixed else []))
                    break
        if len(candidates) != 1:
            raise ValueError('Baris produk/varian target tidak dapat dipastikan secara unik di keranjang.')
        row, qty, box, fixed_labels = candidates[0]
        self.data['fixed_variants'] = fixed_labels
        if fixed_labels:
            self.log.emit('Varian bawaan produk yang tidak dapat diubah: ' + ', '.join(fixed_labels))
        selected = self.page.locator('input[role="checkbox"][aria-label="Click here to select this product"][aria-checked="true"]')
        def visible_selected():
            return [selected.nth(i) for i in range(min(selected.count(), 100)) if selected.nth(i).is_visible()]
        # Re-query after each click; indexes shift as aria-checked changes.
        for _ in range(100):
            checked = visible_selected()
            if not checked:
                break
            before = len(checked)
            self.click_checkbox(checked[0])
            deadline = time.monotonic() + 4
            while len(visible_selected()) >= before:
                self.check()
                if time.monotonic() >= deadline:
                    raise ValueError('Pilihan keranjang tidak berubah setelah dilepas.')
                self.cancel_event.wait(.1)
        if visible_selected():
            raise ValueError('Pilihan keranjang lain belum berhasil dilepas.')
        if not element_selected(box):
            self.click_checkbox(box)
        self.wait_selected(box)
        qty.fill(str(config['quantity']))
        deadline = time.monotonic() + 8
        stable = None
        selected_count = 0
        target_selected = False
        while True:
            self.guard()
            selected_count = len(visible_selected())
            target_selected = element_selected(box)
            if (qty.input_value().strip() == str(config['quantity']) and qty.is_enabled()
                    and selected_count == 1 and target_selected):
                stable = time.monotonic() if stable is None else stable
                if time.monotonic() - stable >= .2:
                    break
            else:
                stable = None
            if time.monotonic() >= deadline:
                raise ValueError(f'Keranjang belum stabil: {selected_count} baris produk terpilih yang tampil; '
                                 f'target terpilih={target_selected}; jumlah={qty.input_value().strip()}. Checkout dibatalkan.')
            self.cancel_event.wait(.1)
        self.emit_status('KERANJANG TERVERIFIKASI', f'Produk target dipilih sendiri, jumlah {config["quantity"]} terkonfirmasi.')

    def verify_checkout_item(self, config, checkout_state=None):
        if not config['variants'] and self.data.get('fixed_variants'):
            config = {**config, 'variants': self.data['fixed_variants']}
        if self.bridge and self.bridge.client_protocol >= 7:
            state = self.page.checkout_snapshot() if checkout_state is None else checkout_state
            columns = state.get('columns')
            paid_count = state.get('paid_count', state.get('image_count'))
            if (not is_checkout_url(state.get('url', '')) or not state.get('complete') or paid_count != 1
                    or state.get('unknown_count', 0) != 0
                    or not isinstance(columns, list) or len(columns) != 5 or columns[0] != self.data['name']):
                raise ValueError('Identitas satu produk target pada checkout belum terkonfirmasi.')
            validate_checkout_columns(columns, config)
            return
        checkout_controls(self.page)
        images = self.page.locator('img[alt="product image"]')
        paid_images = []
        for i in range(images.count()):
            image = images.nth(i)
            if not image.is_visible():
                continue
            row = image
            for _ in range(10):
                row = row.locator('..')
                cols = row.locator(':scope > *')
                if cols.count() == 5 and cols.nth(0).locator('img[alt="product image"]').count() == 1:
                    badge = cols.nth(0).locator('span,label').filter(has_text=re.compile(r'^(?:Hadiah|Free Gift|Gift)$', re.I))
                    explicit = any(badge.nth(j).is_visible() for j in range(badge.count()))
                    free = lambda text: not text or re.fullmatch(r'(?:Rp\s*)?0(?:[,.]0{1,2})?|Gratis|Free', text, re.I)
                    if not (explicit and free(cols.nth(2).inner_text().strip()) and free(cols.nth(4).inner_text().strip())
                            and re.fullmatch(r'[1-9]\d*', cols.nth(3).inner_text().strip())):
                        paid_images.append(image)
                    break
            else:
                raise ValueError('Baris tambahan pada checkout belum dikenali sebagai hadiah gratis.')
        if len(paid_images) != 1:
            raise ValueError('Checkout harus berisi tepat satu baris produk target berbayar.')
        leaf = unique_visible(self.page.get_by_text(self.data['name'], exact=True))
        if leaf is None:
            raise ValueError('Nama produk target tidak ditemukan secara unik pada checkout.')
        row = leaf
        for _ in range(6):
            row = row.locator('..')
            # Match the five product columns, not all currency strings in the row.
            # A discounted unit-price cell also contains the crossed-out list price.
            columns = row.locator(':scope > *')
            if columns.count() == 5 and columns.nth(0).locator('img[alt="product image"]').count() == 1:
                validate_checkout_columns([columns.nth(i).inner_text().strip() for i in range(5)], config)
                return
        raise ValueError('Ringkasan jumlah dan subtotal produk checkout belum terbaca secara tegas.')

    def verified_checkout_quote(self, config):
        """Read one fresh checkout snapshot; never cache a quote across actions."""
        if isinstance(self.page, ChromePage) and self.bridge and self.bridge.client_protocol >= 7:
            state = self.page.checkout_snapshot()
            self.verify_checkout_item(config, checkout_state=state)
            total = rupiah(state.get('total') or '')
            enabled = state.get('submit_enabled') is True
            submit = self.page.get_by_role('button', name=re.compile(r'^Buat Pesanan$', re.I))
        else:
            self.verify_checkout_item(config)
            total_label, submit = checkout_controls(self.page)
            total = rupiah(total_label.locator('xpath=following-sibling::*[1]').inner_text().strip())
            enabled = submit.is_enabled()
        if not Decimal('0') < total <= Decimal(str(config['limit'])):
            raise ValueError('Total akhir di luar batas harga yang kamu tetapkan.')
        if not enabled:
            raise ValueError('Tombol Buat Pesanan belum siap.')
        return total, submit

    def select_payment(self, label):
        checkout_controls(self.page)
        category = payment_category(label)
        self.emit_status('MEMILIH PEMBAYARAN', f'Memilih {label} secara otomatis pada halaman checkout.')
        primary = None
        opened = False
        deadline = time.monotonic() + 8
        while primary is None and time.monotonic() < deadline:
            self.guard()
            primary = unique_visible(self.page.get_by_role('radio', name=re.compile('^' + re.escape(category) + '$', re.I), exact=True))
            if primary is not None:
                break
            heading = unique_visible(self.page.locator('h2,h3').filter(has_text=re.compile(r'^Metode Pembayaran$', re.I)))
            change = None if heading is None else unique_visible(heading.locator('..').locator('button,[role="button"]').filter(has_text=re.compile(r'^ubah$', re.I)))
            if change is not None and not opened:
                change.click()
                opened = True
            self.cancel_event.wait(.1)
        if primary is None:
            raise ValueError(f'Kategori pembayaran {category} tidak tersedia; tidak mengganti metode atau meminta pemilihan manual.')
        if not element_selected(primary):
            primary.click()
        self.wait_selected(primary)
        if label != category:
            deadline = time.monotonic() + 8
            chosen = None
            while chosen is None:
                self.guard()
                chosen = unique_visible(self.page.get_by_role('radio', name=re.compile('^' + re.escape(label) + '$', re.I), exact=True))
                if time.monotonic() >= deadline:
                    raise ValueError(f'{label} tidak tersedia pada kategori {category}.')
                if chosen is None:
                    self.cancel_event.wait(.1)
            if not element_selected(chosen):
                chosen.click()
            self.wait_selected(chosen)
        self.emit_status('PEMBAYARAN TERVERIFIKASI', f'{label} terkonfirmasi terpilih pada checkout.')

    def await_checkout(self, config):
        deadline = time.monotonic() + 30
        cart_clicked = False
        while time.monotonic() < deadline:
            checked_at = time.monotonic()
            self.guard()
            deadline += time.monotonic() - checked_at
            path = urlparse(self.page.url).path.rstrip('/')
            if path == '':
                raise ValueError('Shopee mengalihkan tab ke beranda. Halaman ini bukan checkout; tidak ada pesanan dikirim.')
            if path == '/cart' and not cart_clicked:
                self.prepare_cart(config)
                self.click('Checkout')
                cart_clicked = True
            if is_checkout_url(self.page.url):
                try:
                    checkout_controls(self.page)
                except ValueError:
                    pass  # UI may still be loading after the route changes.
                else:
                    self.verify_checkout_item(config)
                    return
            self.cancel_event.wait(.1)
        raise ValueError('Halaman checkout beserta rincian produk belum terkonfirmasi dalam 30 detik.')

    def verify(self, url):
        if not self.authenticated:
            raise ValueError('Periksa login terlebih dahulu.')
        self.data = None
        self.prepared_config = None
        self.prepared_payment = None
        self.preparation_request = None
        self.purchase_panel_open = False
        self.emit_status('MEMERIKSA PRODUK', 'Membuka tautan dan membaca nama serta varian dari halaman Shopee.')
        self.page.goto(shared_url(url), wait_until='domcontentloaded', timeout=45000)
        self.guard()
        deadline = time.monotonic() + 12
        while True:
            self.guard()
            candidate = extract_product(self.page)
            qty = quantity_field(self.page)
            # Read the same groups that populate the dashboard, including modern
            # classes and seller-defined labels. Quantity may stay disabled until
            # every model/size is selected; it is not a verification prerequisite.
            if candidate['groups'] or qty is None or qty.is_enabled():
                self.data = candidate
                break
            if time.monotonic() >= deadline:
                raise ValueError('Halaman produk belum selesai menyiapkan stok dan jumlah.')
            self.cancel_event.wait(.15)
        if self.report is not None:
            self.report.update(product_name=self.data['name'], product_url=self.data['url'],
                               variant_groups=[g['name'] for g in self.data['groups']])
        self.product.emit(self.data)
        self.emit_status('PRODUK TERBACA', 'Pilih varian, pembayaran, dan jadwal. Cocokkan detail dengan browser.')

    def select_scan_choices(self, choices):
        # Clear prior combination first, so dependent options do not remain locked
        # by the previous colour/model while enumerating the next combination.
        for group in self.data['groups']:
            scope = variant_scope(self.page, group).locator('button,[role="button"]')
            for option in group['options']:
                item = unique_visible(scope.filter(has_text=re.compile('^'+re.escape(option['label'])+'$')))
                if item is not None and element_selected(item):
                    item.click()
                    self.wait_selected(item, False)
        self.data = extract_product(self.page)
        for index, label in enumerate(choices):
            if index >= len(self.data['groups']):
                return False
            group = self.data['groups'][index]
            scope = variant_scope(self.page, group).locator('button,[role="button"]')
            item = unique_visible(scope.filter(has_text=re.compile('^'+re.escape(label)+'$')))
            if item is None or not item.is_enabled():
                return False
            if not element_selected(item):
                item.click()
            self.wait_selected(item)
            self.data = extract_product(self.page)
        return True

    def scan_promotion(self, config):
        from .promotions import matching_offers, scan_summary, schedule_conflicts, catalog_summary
        if not self.bridge or self.bridge.client_protocol < 8:
            raise ValueError('Pemindaian promo memerlukan ekstensi 0.6.0 dan Chrome yang dipasangkan.')
        self.verify(config['url'])
        url = self.data['url']
        initial_snapshot = self.page.promotion_snapshot()
        choices = [[o['label'] for o in group['options']] for group in self.data['groups']]
        total = 1
        for labels in choices:
            total *= len(labels)
        maximum = min(128, max(1, int(config.get('max_combinations',64))))
        rows = []
        for index, combination in enumerate(itertools.islice(itertools.product(*choices),maximum)):
            self.guard()
            self.emit_status('MEMINDAI PROMO', f'Memeriksa kombinasi {index+1}/{min(total,maximum)} tanpa memasukkan pesanan.')
            if not self.select_scan_choices(combination):
                rows.append({'choices':list(combination),'available':False,'offers':[],
                             'reason':'Pilihan tidak tersedia atau dinonaktifkan oleh halaman setelah pilihan sebelumnya diterapkan.'})
                continue
            self.cancel_event.wait(.3)
            snapshot = self.page.promotion_snapshot()
            offers = matching_offers(snapshot,combination,config['target'],config['limit'])
            offers = list({(o['sku'],o['price'],o['starts_at']):o for o in offers}.values())
            rows.append({'choices':list(combination),'available':True,'evidence':snapshot.get('evidence',[]),'campaigns':snapshot.get('campaigns',[]),'offers':offers})
        candidates = [row for row in rows if row['available'] and len(row['offers'])==1]
        confirmed = len(candidates)==1 and total<=maximum and all(len(row['offers'])<=1 for row in rows)
        result = {'product_url':url,'product_name':self.data['name'],'checked_at':datetime.now(ZONE).isoformat(),
                  'target':config['target'],'max_total':config['limit'],'total_combinations':total,
                  'truncated':total>maximum,'rows':rows,'confirmed_unique':confirmed,
                  'candidate':candidates[0] if confirmed else None,
                  'summary':scan_summary(rows),
                  'product_catalog':initial_snapshot.get('bootstrap',{}),
                  'campaigns':initial_snapshot.get('campaigns',[]),
                  'note':'SKU hanya dipastikan dari penawaran publik yang mengikat varian, flash sale, jadwal, dan harga; banner/harga termurah tidak cukup.'}
        result['summary']['catalog'] = catalog_summary(result['product_catalog'])
        catalog = result['summary']['catalog']
        if catalog['model_count'] and not catalog['linked_model_ids']:
            result['summary']['reason'] += f" Data awal memuat {catalog['model_count']} ID model, tetapi belum mengikat model mana pun ke kampanye {catalog['campaign_id'] or 'yang dicari'}."
        result['summary']['schedule_conflicts'] = schedule_conflicts(result['summary']['announcements'], config['target'])
        if result['summary']['schedule_conflicts']:
            result['summary']['reason'] = 'Jadwal pencarian berbeda dari pengumuman halaman: ' + '; '.join(result['summary']['schedule_conflicts']) + '. Cocokkan tanggal dan jam promo.'
        DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
        (DATA/'latest-promotion.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
        self.promotion.emit(result)
        self.verify(url)
        if confirmed:
            labels = result['candidate']['choices']
            if not self.select_scan_choices(labels):
                raise ValueError('Ketersediaan varian promo berubah setelah pemindaian; checkout belum disiapkan.')
            self.product.emit(self.data)
            self.stage_checkout({**config,'url':url,'variants':labels})
        else:
            self.emit_status('PROMO BELUM PASTI', result['summary']['reason'] +
                             f" {result['summary']['available_combinations']}/{len(rows)} kombinasi tersedia. Buka hasil pemindaian untuk rinciannya.")

    def refresh_released_stock(self, config):
        """Refresh at release, selecting the same labels; never replace an unavailable SKU."""
        self.prepared_config = None
        self.prepared_payment = None
        for attempt in range(10):
            self.guard()
            self.emit_status('MENUNGGU STOK', f'Memuat ulang stok target, pemeriksaan {attempt+1}/10.')
            self.verify(config['url'])
            if self.select_scan_choices(config['variants']):
                quantity = quantity_field(self.page)
                if quantity is not None and quantity.is_enabled():
                    self.emit_status('STOK TARGET AKTIF', 'Varian target terpilih kembali dan kolom jumlah aktif. Melanjutkan checkout.')
                    return
            if attempt < 9:
                self.cancel_event.wait(1)
        raise ValueError('Stok kombinasi target belum dibuka setelah 10 pemeriksaan. Tidak memilih varian pengganti atau mengirim pesanan.')

    def checkout(self, config):
        release_stock = bool(config.get('wait_stock_release'))
        refresh_with_coins = bool(config.get('refresh_with_coins')) and not release_stock
        if release_stock and is_checkout_url(self.page.url):
            self.verify(config['url'])
        if not release_stock and self.data and (urlparse(self.page.url).path.rstrip('/') == '/cart' or
                          (is_checkout_url(self.page.url) and self.prepared_config is None)):
            self.stage_checkout(config)
        self.preflight()
        if not self.authenticated or not self.data or config['url'] != self.data['url']:
            raise ValueError('Akun dan produk harus diverifikasi sebelum menjalankan jadwal.')
        target = datetime.fromisoformat(config['time'])
        staged = not release_stock and self.prepared_config is not None and is_checkout_url(self.page.url)
        if staged and self.selection_key(self.prepared_config) != self.selection_key(config):
            self.page.goto(config['url'])
            self.prepared_config = None
            staged = False
        prepared = not release_stock and (staged or bool(config.get('prepare_before_time') and not config.get('immediate')))
        if prepared and not staged:
            self.prepare_product(config)
            self.await_checkout(config)
            self.select_payment(config['payment'])
            self.verify_checkout_item(config)
            self.emit_status('CHECKOUT DISIAPKAN', 'Checkout siap sebelum jadwal. Bot belum menekan Buat Pesanan.')
        elif staged and self.prepared_payment != config['payment']:
            self.select_payment(config['payment'])
            self.prepared_payment = config['payment']
        self.emit_status('MEMULAI' if config.get('immediate') else 'TERJADWAL',
                         'Menjalankan pembelian sekarang.' if config.get('immediate') else f'Menunggu {target.strftime("%d %b %Y, %H:%M:%S WIB")}. Komputer harus tetap aktif.')
        next_housekeeping = 0
        coin_refreshed = False
        previous_total = None
        while datetime.now(ZONE) < target:
            self.check()
            seconds = max(0, int((target - datetime.now(ZONE)).total_seconds()))
            self.status.emit('TERJADWAL', f'Mulai dalam {seconds//60} menit {seconds%60} detik. Browser tetap aktif.')
            remaining = (target - datetime.now(ZONE)).total_seconds()
            if prepared and refresh_with_coins and not coin_refreshed and remaining <= 1:
                previous_total = self.refresh_coins()
                coin_refreshed = True
            if remaining > 2 and time.monotonic() >= next_housekeeping:
                self.guard()
                self.snapshot()
                next_housekeeping = time.monotonic() + 2
            self.cancel_event.wait(min(.1, max(.001, remaining)))
        if (datetime.now(ZONE) - target).total_seconds() > 30:
            raise ValueError('Jadwal terlewat lebih dari 30 detik. Atur ulang waktu.')
        self.guard()
        if self.report is not None:
            self.report['release_monotonic'] = time.monotonic()
        if not prepared and product_url(self.page.url) != config['url']:
            raise ValueError('Halaman produk berubah. Periksa tautan kembali.')
        if not prepared:
            if release_stock:
                self.refresh_released_stock(config)
            self.prepare_product(config)
            self.emit_status('CHECKOUT', 'Menunggu halaman checkout dan memeriksa metode pembayaran.')
            self.await_checkout(config)
            self.select_payment(config['payment'])
        if release_stock:
            self.emit_status('STOK RILIS TERVERIFIKASI', 'Checkout setelah refresh stok: melewati perubahan koin dan memeriksa total akhir sebelum pemesanan.')
        if refresh_with_coins:
            if not coin_refreshed:
                previous_total = self.refresh_coins()
            price_deadline = time.monotonic() + 10
            price_ready = False
            while time.monotonic() < price_deadline:
                self.guard()
                try:
                    heading, _ = self.wait_checkout_ready(timeout=3)
                    quote = rupiah(heading.locator('xpath=following-sibling::*[1]').inner_text().strip())
                except ValueError:
                    if not is_checkout_url(self.page.url):
                        raise
                    self.cancel_event.wait(.1)
                    continue
                if (previous_total is None or quote != previous_total) and Decimal('0') < quote <= Decimal(str(config['limit'])):
                    price_ready = True
                    break
                self.cancel_event.wait(.1)
            if not price_ready:
                raise ValueError('Harga checkout belum berubah sesuai batas total dalam 10 detik; pesanan belum dikirim.')
        self.guard()
        total, submit = self.verified_checkout_quote(config)
        if config.get('stop_before_submit'):
            self.emit_status('CHECKOUT SIAP', 'Mode pengujian berhenti sebelum Buat Pesanan. Total dan pilihan pembayaran sudah diperiksa; pesanan belum dikirim.')
            return
        self.submit_order(config, submit)

    def refresh_coins(self):
        self.guard()
        heading, _ = self.wait_checkout_ready()
        previous_total = rupiah(heading.locator('xpath=following-sibling::*[1]').inner_text().strip())
        coin = unique_visible(self.page.get_by_role('checkbox', name=re.compile(
            r'^(Click here to redeem Shopee Coins|Coins redeemed)$', re.I), exact=True))
        if coin is None or not coin.is_enabled():
            self.log.emit('Koin tidak tersedia; mempertahankan konteks checkout dan memeriksa total yang tampil sesuai batas harga.')
            return None
        expected = not element_selected(coin)
        self.emit_status('MEMPERBARUI HARGA', 'Mengubah pilihan koin satu kali dan menunggu perhitungan harga checkout.')
        self.click_checkbox(coin)
        self.wait_selected(coin, expected)
        # A price change is not proof of a flash-sale allocation. Re-read final total below.
        self.cancel_event.wait(.2)
        self.wait_checkout_ready()
        return previous_total

    def wait_checkout_ready(self, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            started = time.monotonic()
            self.guard()
            deadline += time.monotonic() - started
            if not is_checkout_url(self.page.url):
                raise ValueError('Halaman berpindah dari checkout saat memperbarui harga; tidak mengirim pesanan.')
            try:
                controls = checkout_controls(self.page)
                if controls[1].is_enabled():
                    return controls
            except ValueError:
                saved = self.prepared_config or self.preparation_request
                if self.attempt is None and saved is not None and not getattr(self, '_recovering_checkout', False):
                    message = unique_visible(self.page.get_by_text(re.compile(
                        r'^Beberapa informasi produk pada pesananmu telah diperbarui\..*', re.I)))
                    if message is not None and saved is not None:
                        scope = message
                        for _ in range(5):
                            scope = scope.locator('..')
                            ok = unique_visible(scope.locator('button,[role="button"]').filter(has_text=re.compile(r'^OK$', re.I)))
                            if ok is not None:
                                ok.click()
                                self._recovering_checkout = True
                                try:
                                    self.emit_status('MEMULIHKAN CHECKOUT', 'Informasi produk berubah. Menyiapkan ulang satu kali tanpa mengirim pesanan.')
                                    self.verify(saved['url'])
                                    self.stage_checkout(saved)
                                    return checkout_controls(self.page)
                                finally:
                                    self._recovering_checkout = False
            self.cancel_event.wait(.1)
        raise ValueError('Checkout belum selesai memuat rincian produk, pembayaran, total, dan tombol pesanan dalam 12 detik.')

    def stock_rejection(self):
        message = unique_visible(self.page.get_by_text(re.compile(
            r'^Beberapa barang habis terjual dalam proses pemesanan\..*', re.I)))
        if message is None:
            return False
        scope = message
        for _ in range(5):
            scope = scope.locator('..')
            ok = unique_visible(scope.locator('button,[role="button"]').filter(has_text=re.compile(r'^OK$', re.I)))
            if ok is not None:
                ok.click()
                return True
        raise ValueError('Penolakan stok terlihat, tetapi tombol OK dialog belum dikenali secara unik.')

    def submit_order(self, config, submit):
        attempts = max(1, min(10, int(config.get('stock_attempts', 3))))
        for index in range(attempts):
            if index:
                self.guard()
                self.verify_checkout_item(config)
                self.select_payment(config['payment'])
                total_label, submit = checkout_controls(self.page)
                total = rupiah(total_label.locator('xpath=following-sibling::*[1]').inner_text().strip())
                if not Decimal('0') < total <= Decimal(str(config['limit'])) or not submit.is_enabled():
                    raise ValueError('Total/metode/produk belum aman untuk pengulangan setelah penolakan stok.')
            if self.submit_once(config, submit):
                return
            if index + 1 == attempts:
                raise ValueError(f'Shopee menolak stok pada {attempts} percobaan. Tidak ada pengulangan tanpa batas.')
            self.emit_status('MENCOBA STOK KEMBALI', f'Penolakan stok terkonfirmasi. Percobaan {index + 2}/{attempts} setelah jeda.')
            self.cancel_event.wait(.5)

    def submit_once(self, config, submit):
        job = Job(config['url'], config['time'], self.profile, str(config['limit']), {})
        self.attempt = Store().reserve(job)
        self.emit_status('MEMBENTUK PESANAN', 'Mengirim satu permintaan pesanan. Pengulangan hanya setelah penolakan stok terkonfirmasi.')
        if self.report is not None:
            now = time.monotonic()
            self.report.setdefault('click_to_submit_ms', round((now - self.run_started) * 1000, 1))
            self.report.setdefault('release_to_submit_ms', round((now - self.report.get('release_monotonic', now)) * 1000, 1))
        submitted_at = datetime.now(ZONE)
        submit.click()
        deadline = time.monotonic() + 60
        recovered = False
        def recover_redirect(exc):
            nonlocal recovered
            if self.bridge and not recovered and 'Tab pilihan tidak lagi berada di Shopee' in str(exc):
                self.page.open_pending_orders()
                recovered = True
                return True
            return False
        while time.monotonic() < deadline:
            checked_at = time.monotonic()
            try:
                self.guard()
            except ValueError as exc:
                if recover_redirect(exc):
                    continue
                raise
            deadline += time.monotonic() - checked_at
            self.snapshot()
            if recovered:
                path = urlparse(self.page.url).path
                if path.rstrip('/') == '/user/purchase/list':
                    pattern = re.compile(re.escape(self.data['name']) + r'\s*x\s*' + str(config['quantity']) + r'\s*Rp', re.I)
                    link = unique_visible(self.page.locator('a[href*="/user/purchase/checkout/"]').filter(has_text=pattern))
                    if link is not None:
                        url = urljoin('https://shopee.co.id', link.get_attribute('href') or '')
                        if urlparse(url).hostname == 'shopee.co.id' and re.fullmatch(r'/user/purchase/checkout/\d+', urlparse(url).path):
                            self.page.goto(url)
                    self.cancel_event.wait(.1)
                    continue
                if re.fullmatch(r'/user/purchase/checkout/\d+', path):
                    marker = unique_visible(self.page.get_by_text(re.compile(r'^MENUNGGU PEMBAYARAN$', re.I)))
                    number = unique_visible(self.page.get_by_text(re.compile(r'^NO\. PESANAN\s*\.\s*[A-Z0-9]+$', re.I)))
                    recent = any(unique_visible(self.page.get_by_text((submitted_at + timedelta(minutes=n)).strftime('%d-%m-%Y %H:%M'), exact=True)) is not None for n in (0, 1))
                    if marker is not None and number is not None and recent:
                        order_id = re.search(r'([A-Z0-9]+)$', number.inner_text().strip(), re.I)[1]
                        self.finish_pending(order_id)
                        return True
            try:
                rejected = self.stock_rejection()
                result_url = self.page.url
            except ValueError as exc:
                if recover_redirect(exc):
                    continue
                raise
            if rejected:
                Store().finish(self.attempt, 'REJECTED_STOCK')
                self.attempt = None
                return False
            pending = self.page.get_by_text(re.compile(r'^(Menunggu Pembayaran|Belum Bayar)$', re.I))
            order = re.search(r'/(?:order|purchase)/order/(\d+)', result_url)
            if order and any(pending.nth(i).is_visible() for i in range(pending.count())):
                self.finish_pending(order[1])
                return True
            self.cancel_event.wait(.5)
        raise ValueError('Status dan ID pesanan belum terkonfirmasi. Periksa riwayat pesanan; jangan langsung mengulang.')

    def finish_pending(self, order_id):
        Store().finish(self.attempt, 'PENDING_PAYMENT', order_id)
        self.attempt = None
        if self.report is not None:
            self.report['order_id'] = order_id
            self.report['confirmation_elapsed_ms'] = round((time.monotonic() - self.run_started) * 1000, 1)
        self.finished_order.emit(order_id)
        self.emit_status('SELESAI', 'Pesanan terkonfirmasi menunggu pembayaran. Bot berhenti; pembayaran kamu lakukan sendiri.')

    def run(self):
        try:
            with sync_playwright() as p:
                if self.bridge:
                    from .bridge import ChromePage
                    self.emit_status('MENUNGGU CHROME', 'Hubungkan tab Shopee dari ekstensi menggunakan kode pairing dashboard.')
                    while not self.bridge.connected.wait(.3):
                        if self.stop_event.is_set():
                            return
                    self.page = ChromePage(self.bridge)
                    self.emit_status('CHROME TERHUBUNG', 'Menggunakan tab Shopee yang kamu pilih. Klik Periksa login untuk melanjutkan.')
                    if self.bridge.client_protocol < 8:
                        self.emit_status('PERBARUI EKSTENSI', 'Muat ulang ekstensi Flashsale Lokal versi 0.6.0 dan hubungkan kembali sebelum pengujian.')
                else:
                    path = DATA / 'profiles' / self.profile
                    path.mkdir(parents=True, exist_ok=True, mode=0o700)
                    self.context = p.chromium.launch_persistent_context(str(path), headless=False, viewport={'width':1100,'height':780})
                    self.context.set_default_timeout(12000)
                    self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                    self.page.goto('https://shopee.co.id/buyer/login', wait_until='domcontentloaded', timeout=45000)
                    self.emit_status('LOGIN', 'Browser Shopee terbuka. Login langsung di browser, lalu klik Periksa login.')
                idle_challenge = False
                while not self.stop_event.is_set():
                    self.snapshot()
                    detected = self.challenge()
                    if detected and not idle_challenge:
                        self.emit_status('VERIFIKASI', 'Shopee meminta CAPTCHA/verifikasi. Kerjakan di browser, lalu klik Periksa login setelah selesai.')
                    elif idle_challenge and not detected:
                        self.emit_status('LOGIN', 'Verifikasi tidak lagi terlihat. Selesaikan login dan klik Periksa login.')
                    idle_challenge = detected
                    try:
                        command, value = self.commands.get(timeout=.5)
                    except queue.Empty:
                        continue
                    self.cancel_event.clear()
                    self.busy.emit(True)
                    outcome = 'finished'
                    try:
                        if command in ('verify_prepare', 'variant', 'scan_promotion'):
                            self.run_started = time.monotonic()
                            self.report = {'kind': 'preparation', 'command': command, 'stages': [],
                                           'started_at': datetime.now(ZONE).isoformat()}
                        if command == 'login':
                            self.login_check()
                        elif command == 'verify':
                            self.verify(value)
                        elif command == 'scan_promotion':
                            self.scan_promotion(value)
                        elif command == 'verify_prepare':
                            self.verify(value['url'])
                            if not self.data['groups']:
                                self.stage_checkout({**value, 'url': self.data['url'], 'variants': []})
                        elif command == 'variant':
                            self.preview_variant(value)
                            configured = value.get('config')
                            if configured and len(configured['variants']) == len(self.data['groups']) and all(configured['variants']):
                                self.stage_checkout(configured)
                        elif command == 'schedule':
                            self.run_started = time.monotonic()
                            self.report = {'started_at': datetime.now(ZONE).isoformat(), 'stages': [],
                                           'quantity': value['quantity'], 'payment': value['payment'],
                                           'product_url': value['url'], 'variants': value['variants'],
                                           'product_name': (self.data or {}).get('name'),
                                           'wait_stock_release': bool(value.get('wait_stock_release')),
                                           'prepare_before_time': bool(value.get('prepare_before_time')),
                                           'refresh_with_coins': bool(value.get('refresh_with_coins')),
                                           'stock_attempts': value.get('stock_attempts', 3)}
                            self.checkout(value)
                        elif command == 'preflight':
                            self.preflight()
                        elif command == 'focus':
                            self.page.bring_to_front()
                    except Exception as exc:
                        outcome = type(exc).__name__
                        if self.attempt is not None:
                            Store().finish(self.attempt, 'UNKNOWN')
                            self.attempt = None
                            suffix = ' Hasil checkout belum pasti; periksa riwayat pesanan.'
                        else:
                            suffix = ''
                        detail = str(exc) if isinstance(exc, (ValueError, InterruptedError)) else f'Halaman belum dapat diproses ({type(exc).__name__}). Periksa browser.'
                        if self.report is not None:
                            self.report['error'] = {'type': type(exc).__name__, 'message': detail}
                        self.emit_status('DIHENTIKAN' if isinstance(exc, InterruptedError) else 'PERLU DIPERIKSA', detail + suffix)
                    finally:
                        self.save_report(outcome)
                        self.busy.emit(False)
                if not self.bridge:
                    self.context.close()
        except Exception as exc:
            if self.attempt is not None:
                Store().finish(self.attempt, 'UNKNOWN')
            self.emit_status('BROWSER BERHENTI', f'Browser tidak tersedia ({type(exc).__name__}). Tutup sesi Shopee lain dan buka kembali.')
