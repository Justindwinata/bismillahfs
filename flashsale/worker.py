from __future__ import annotations

import threading
import time
from datetime import datetime

from PySide6.QtCore import QThread, Signal
from playwright.sync_api import sync_playwright

from .core import DATA, Job, Store, ZONE, rupiah


class Stopped(Exception):
    pass


class Worker(QThread):
    status = Signal(str)
    verification = Signal(str)
    result = Signal(str)

    def __init__(self, job: Job, login_only=False):
        super().__init__()
        self.job = job
        self.login_only = login_only
        self.stop_event = threading.Event()
        self.resume_event = threading.Event()

    def check(self):
        if self.stop_event.is_set():
            raise Stopped()

    def pause(self, seconds):
        if self.stop_event.wait(max(0, seconds)):
            raise Stopped()

    def manual(self, message):
        self.resume_event.clear()
        self.verification.emit(message)
        self.status.emit('MENUNGGU PENGGUNA — browser tetap terbuka')
        while not self.resume_event.wait(.2):
            self.check()
        self.check()

    def guard(self, page):
        self.check()
        from urllib.parse import urlparse
        if urlparse(page.url).hostname not in self.job.adapter['hosts']:
            raise ValueError('Navigasi keluar dari hostname adapter. Proses dihentikan.')
        selectors = self.job.adapter.get('challenge_selectors', [])
        while any(page.locator(s).first.is_visible() for s in selectors):
            self.manual('Selesaikan verifikasi pada browser, lalu klik Lanjutkan.')

    def run(self):
        attempt = None
        store = Store()
        try:
            profile = DATA / 'profiles' / self.job.profile
            profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(str(profile), headless=False)
                context.set_default_timeout(12000)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    self.status.emit('MEMBUKA BROWSER')
                    page.goto(self.job.url, wait_until='domcontentloaded', timeout=45000)
                    if self.login_only:
                        self.status.emit('LOGIN MANUAL — klik Hentikan setelah selesai; sesi tersimpan lokal')
                        while True:
                            self.pause(.3)
                    self.manual('Periksa akun pada browser dan selesaikan login jika diperlukan. Klik Lanjutkan untuk mengaktifkan jadwal.')
                    target = datetime.fromisoformat(self.job.starts_at)
                    remaining = (target - datetime.now(ZONE)).total_seconds()
                    if remaining < -30:
                        raise ValueError('Jadwal terlewat lebih dari 30 detik. Atur jadwal baru.')
                    self.status.emit('TERJADWAL — browser harus tetap terbuka dan komputer tetap aktif')
                    while (target - datetime.now(ZONE)).total_seconds() > 0:
                        self.pause(min(.2, (target - datetime.now(ZONE)).total_seconds()))
                    if (datetime.now(ZONE) - target).total_seconds() > 30:
                        raise ValueError('Eksekusi terlambat; pembelian dibatalkan.')
                    adapter = self.job.adapter
                    self.guard(page)
                    page.locator(adapter['ready_selector']).wait_for(state='visible')
                    for step in adapter.get('steps', []):
                        self.guard(page)
                        self.status.emit('MENYIAPKAN CHECKOUT')
                        locator = page.locator(step['selector'])
                        if step['action'] == 'click':
                            locator.click()
                        elif step['action'] == 'fill':
                            locator.fill(str(step.get('value', '')))
                        else:
                            locator.select_option(label=str(step['value']))
                    self.guard(page)
                    total = rupiah(page.locator(adapter['total_selector']).inner_text())
                    from decimal import Decimal
                    if total <= 0 or total > Decimal(self.job.max_total):
                        raise ValueError(f'Total Rp{total} berada di luar batas pembelian.')
                    button = page.locator(adapter['submit_selector'])
                    if button.count() != 1 or not button.is_visible() or not button.is_enabled():
                        raise ValueError('Tombol pemesanan tidak unik atau belum siap.')
                    self.check()
                    attempt = store.reserve(self.job)
                    self.status.emit('MEMBENTUK PESANAN — tidak ada pengulangan otomatis')
                    button.click()
                    deadline = time.monotonic() + 60
                    while time.monotonic() < deadline:
                        self.guard(page)
                        if page.locator(adapter['pending_selector']).first.is_visible():
                            order_id = page.locator(adapter['order_id_selector']).inner_text().strip()
                            if order_id:
                                store.finish(attempt, 'PENDING_PAYMENT', order_id)
                                self.result.emit(f'Pesanan {order_id} menunggu pembayaran. Bot selesai; bayar secara manual.')
                                return
                        self.pause(.3)
                    raise ValueError('Status pesanan belum terkonfirmasi. Periksa riwayat pesanan di platform; jangan langsung mengulang.')
                finally:
                    context.close()
        except Stopped:
            if attempt is not None:
                store.finish(attempt, 'UNKNOWN')
            self.result.emit('Dihentikan.' + (' Hasil checkout belum pasti; periksa riwayat pesanan.' if attempt is not None else ''))
        except Exception as exc:
            if attempt is not None:
                store.finish(attempt, 'UNKNOWN')
            # Do not log exception text: browser errors may contain session-bearing URLs.
            detail = str(exc) if isinstance(exc, ValueError) else f'Periksa browser dan adapter ({type(exc).__name__}).'
            self.result.emit(f'Proses berhenti. {detail} ' +
                             ('Status UNKNOWN: periksa riwayat pesanan sebelum mengulang.' if attempt is not None else
                              'Periksa konfigurasi adapter, sesi, jadwal, total, dan keadaan halaman.'))
