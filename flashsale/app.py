import sys
import json
from datetime import datetime

from PySide6.QtCore import QDateTime, QTime, QTimeZone, Qt, QTimer, QUrl
from PySide6.QtGui import QPixmap, QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox,
    QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter, QVBoxLayout, QWidget)

from .core import ZONE, ROOT, DATA
from .shopee import ShopeeSession, shared_url

STYLE = '''
QMainWindow, QWidget#root { background:#f4f3ef; color:#252a30; }
QWidget { font-family:"Avenir Next"; font-size:13px; }
QLabel#title { font-size:28px; font-weight:700; }
QLabel#subtitle { color:#68717b; }
QFrame#section { background:#ffffff; border-radius:12px; }
QLabel#sectionTitle { font-size:17px; font-weight:600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateTimeEdit {
 background:#fafaf8; border:1px solid #d8dcd9; border-radius:6px;
 padding:9px; color:#252a30; min-height:18px;
}
QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus { border:1px solid #d85b35; }
QPushButton { background:#e7e9e5; color:#303a42; border:0; border-radius:6px; padding:11px 15px; font-weight:600; }
QPushButton:hover { background:#dce0da; }
QPushButton#primary { background:#c74e2b; color:white; }
QPushButton#primary:hover { background:#b34324; }
QPushButton:disabled { color:#919993; background:#eceeea; }
QPushButton#primary:disabled { color:#919993; background:#eceeea; }
QLabel#status { background:#f6e8de; border-radius:6px; padding:9px; color:#8c3d22; font-weight:600; }
QLabel#preview { background:#202830; color:#b7c3cc; border-radius:8px; }
QPlainTextEdit { background:#202830; color:#dbe3e8; border:0; border-radius:8px; padding:10px; font-family:Menlo; font-size:11px; }
QScrollArea { border:0; background:transparent; }
QSplitter::handle { background:#f4f3ef; width:18px; }
'''


def section(title, description):
    frame = QFrame()
    frame.setObjectName('section')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 20)
    layout.setSpacing(12)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    label = QLabel(description)
    label.setWordWrap(True)
    label.setObjectName('subtitle')
    layout.addWidget(label)
    return frame, layout


class Window(QMainWindow):
    def __init__(self, auto_open=True):
        super().__init__()
        self.session = None
        self.persist_settings = auto_open
        self.bridge = None
        self.authenticated = False
        self.product_data = None
        self.variant_fields = []
        self.promo_choices = None
        self.last_frame = None
        self.active = False
        self.closing = False
        self.setWindowTitle('Flashsale Lokal | Shopee 0.6.5')
        self.resize(1240, 900)
        root = QWidget()
        root.setObjectName('root')
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(18)
        title = QLabel('Shopee / Checkout terjadwal')
        title.setObjectName('title')
        layout.addWidget(title)
        sub = QLabel('Login → periksa produk → atur pembelian → pantau proses. Pembayaran kamu lakukan sendiri.')
        sub.setObjectName('subtitle')
        layout.addWidget(sub)
        split = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(split, 1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(left)
        split.addWidget(scroll)
        scroll.setMinimumWidth(470)

        frame, box = section('01  Akun Shopee', 'Gunakan tab Shopee yang sudah login di Chrome milikmu. Koneksi dipasangkan secara lokal melalui ekstensi.')
        self.source = QComboBox()
        self.source.addItems(['Chrome saya — tab yang sudah login', 'Browser aplikasi — sesi terpisah'])
        box.addWidget(self.source)
        pairing = QHBoxLayout()
        self.pair_code = QLineEdit()
        self.pair_code.setReadOnly(True)
        self.pair_code.setEchoMode(QLineEdit.EchoMode.Password)
        self.pair_code.setPlaceholderText('Kode pairing tersedia setelah koneksi dibuka')
        copy = QPushButton('Salin kode')
        copy.clicked.connect(lambda: QApplication.clipboard().setText(self.bridge.token) if self.bridge else None)
        pairing.addWidget(self.pair_code)
        pairing.addWidget(copy)
        box.addLayout(pairing)
        instructions = QLabel('Pasang folder ekstensi lewat chrome://extensions → Mode developer → Muat yang belum dibuka. Pada tab Shopee, klik ekstensi lalu tempel kode pairing.')
        instructions.setWordWrap(True)
        box.addWidget(instructions)
        folder = QPushButton('Buka folder ekstensi Chrome')
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT / 'chrome-extension'))))
        box.addWidget(folder)
        self.account_label = QLabel('Belum login')
        box.addWidget(self.account_label)
        row = QHBoxLayout()
        self.login = QPushButton('Hubungkan browser')
        self.login.setObjectName('primary')
        self.check_login = QPushButton('Periksa login')
        self.check_login.setEnabled(False)
        row.addWidget(self.login)
        row.addWidget(self.check_login)
        box.addLayout(row)
        left_layout.addWidget(frame)
        self.login.clicked.connect(self.open_session)
        self.check_login.clicked.connect(lambda: self.send('login'))

        self.product_section, box = section('02  Tautan & detail produk', 'Tempel tautan produk shopee.co.id. Nama dan pilihan varian dibaca dari halaman asli.')
        self.url = QLineEdit()
        self.url.setPlaceholderText('https://shopee.co.id/nama-produk-i.…')
        box.addWidget(self.url)
        self.verify = QPushButton('Verifikasi & siapkan checkout')
        box.addWidget(self.verify)
        self.promo_time = QDateTimeEdit()
        self.promo_time.setTimeZone(QTimeZone(b'Asia/Jakarta'))
        promo_date = QDateTime.currentDateTime().toTimeZone(QTimeZone(b'Asia/Jakarta'))
        promo_date.setTime(QTime(12,0))
        self.promo_time.setDateTime(promo_date)
        self.promo_time.setDisplayFormat('dd MMM yyyy HH:mm:ss')
        self.promo_time.setCalendarPopup(True)
        box.addWidget(QLabel('Jadwal promo yang dicari (WIB)'))
        box.addWidget(self.promo_time)
        scan = QPushButton('Cari varian & paket flash sale — tanpa membeli')
        scan.clicked.connect(self.scan_promotion)
        box.addWidget(scan)
        self.promo_result = QLabel('Belum ada bukti varian promo. Banner produk saja tidak menentukan paket yang ikut flash sale.')
        self.promo_result.setWordWrap(True)
        box.addWidget(self.promo_result)
        promo_report = QPushButton('Buka informasi promo yang ditemukan')
        promo_report.clicked.connect(self.open_promotion_report)
        box.addWidget(promo_report)
        self.product_name = QLabel('Belum ada produk yang diperiksa.')
        self.product_name.setWordWrap(True)
        box.addWidget(self.product_name)
        readiness = QPushButton('Periksa kesiapan — tanpa membeli')
        readiness.clicked.connect(lambda: self.send('preflight'))
        box.addWidget(readiness)
        self.variants_layout = QFormLayout()
        box.addLayout(self.variants_layout)
        left_layout.addWidget(self.product_section)
        self.product_section.setEnabled(False)
        self.verify.clicked.connect(self.verify_link)
        self.url.textEdited.connect(self.invalidate_product)

        self.purchase_section, box = section('03  Pembayaran & waktu', 'Pilih preferensi pembayaran yang menghasilkan pesanan belum dibayar. Pilihan diverifikasi kembali di checkout.')
        form = QFormLayout()
        self.payment = QComboBox()
        self.payment.addItems(['Pilih metode pembayaran', 'QRIS', 'Bank BCA', 'Bank BNI', 'Bank BRI', 'Bank Mandiri', 'Alfamart', 'Indomaret'])
        self.quantity = QSpinBox()
        self.quantity.setRange(1, 100)
        self.quantity.setValue(1)
        self.limit = QDoubleSpinBox()
        self.limit.setRange(1, 1_000_000_000)
        self.limit.setDecimals(0)
        self.limit.setPrefix('Rp ')
        self.limit.setValue(100000)
        self.schedule = QDateTimeEdit()
        self.schedule.setTimeZone(QTimeZone(b'Asia/Jakarta'))
        self.schedule.setDateTime(QDateTime.currentDateTime().toTimeZone(QTimeZone(b'Asia/Jakarta')).addSecs(300))
        self.schedule.setDisplayFormat('dd MMM yyyy  HH:mm:ss')
        self.schedule.setCalendarPopup(True)
        self.execution = QComboBox()
        self.execution.addItems(['Jadwalkan pada waktu WIB', 'Jalankan sekarang'])
        self.execution.currentIndexChanged.connect(self.execution_changed)
        form.addRow('Jumlah', self.quantity)
        form.addRow('Metode pembayaran', self.payment)
        form.addRow('Batas total + ongkir', self.limit)
        form.addRow('Waktu eksekusi', self.execution)
        form.addRow('Jadwal (WIB)', self.schedule)
        box.addLayout(form)
        self.stock_release = QCheckBox('Stok dibuka saat jadwal: refresh lalu pilih ulang varian target')
        self.stock_release.setToolTip('Memungkinkan memilih varian yang saat ini nonaktif. Saat jadwal dimulai, halaman dimuat ulang maksimal 10 kali dengan jeda 1 detik; checkout dilanjutkan hanya jika kombinasi target aktif.')
        box.addWidget(self.stock_release)
        self.stock_release.toggled.connect(lambda _: self.product_changed(self.product_data) if self.product_data else None)
        self.prepare_early = QCheckBox('Siapkan checkout sebelum jadwal (jalur cepat)')
        self.prepare_early.setChecked(True)
        box.addWidget(self.prepare_early)
        self.refresh_coins = QCheckBox('Perbarui koin sekali: 1 detik sebelum jadwal / saat mulai langsung')
        box.addWidget(self.refresh_coins)
        self.stock_release.toggled.connect(lambda enabled: self.refresh_coins.setEnabled(not enabled))
        self.refresh_coins.setToolTip('Dilewati otomatis pada mode stok dibuka saat jadwal; pilihan koin hanya digunakan untuk alur biasa.')
        retry_form = QFormLayout()
        self.stock_attempts = QSpinBox()
        self.stock_attempts.setRange(1, 10)
        self.stock_attempts.setValue(3)
        retry_form.addRow('Maks. percobaan jika stok ditolak', self.stock_attempts)
        box.addLayout(retry_form)
        self.inspect_checkout = QCheckBox('Pengujian: berhenti sebelum tombol Buat Pesanan')
        box.addWidget(self.inspect_checkout)
        self.time_hint = QLabel()
        self.time_hint.setWordWrap(True)
        box.addWidget(self.time_hint)
        reset_time = QPushButton('Atur 5 menit dari sekarang')
        reset_time.clicked.connect(lambda: self.schedule.setDateTime(QDateTime.currentDateTime().toTimeZone(QTimeZone(b'Asia/Jakarta')).addSecs(300)))
        box.addWidget(reset_time)
        self.start = QPushButton('Jadwalkan auto-buy')
        self.start.setObjectName('primary')
        box.addWidget(self.start)
        self.start.clicked.connect(self.start_job)
        left_layout.addWidget(self.purchase_section)
        self.purchase_section.setEnabled(False)
        left_layout.addStretch()

        right, box = section('Status proses', 'Alur berjalan otomatis. Tampilan browser muncul hanya saat CAPTCHA atau verifikasi keamanan membutuhkan tindakanmu.')
        split.addWidget(right)
        self.state = QLabel('SIAP MEMULAI')
        self.state.setObjectName('status')
        box.addWidget(self.state)
        self.message = QLabel('Buka login Shopee untuk memulai.')
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        self.preview = QLabel('Tampilan browser muncul di sini setelah sesi dibuka.')
        self.preview.setObjectName('preview')
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(270)
        self.preview.setMinimumWidth(380)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.preview.setWordWrap(True)
        self.preview.setVisible(False)
        box.addWidget(self.preview, 2)
        row = QHBoxLayout()
        self.browser = QPushButton('Tampilkan browser')
        self.resume = QPushButton('Lanjutkan')
        self.resume.setEnabled(False)
        self.stop = QPushButton('Hentikan tugas')
        row.addWidget(self.browser)
        row.addWidget(self.resume)
        row.addWidget(self.stop)
        box.addLayout(row)
        self.browser.clicked.connect(lambda: self.send('focus'))
        self.resume.clicked.connect(self.continue_job)
        self.stop.clicked.connect(self.cancel_job)
        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setMaximumBlockCount(300)
        self.logs.setMinimumHeight(160)
        box.addWidget(self.logs, 1)
        report_button = QPushButton('Buka laporan pengujian terakhir')
        report_button.clicked.connect(self.open_report)
        box.addWidget(report_button)
        warning = QLabel('Integrasi checkout belum terbukti pada akunmu. Status sukses hanya muncul setelah ID pesanan dan status belum dibayar terdeteksi.')
        warning.setWordWrap(True)
        warning.setObjectName('subtitle')
        box.addWidget(warning)
        split.setSizes([530, 610])
        self.setCentralWidget(root)
        self.setStyleSheet(STYLE)
        try:
            settings = json.loads((DATA / 'gui-settings.json').read_text())
            self.url.setText(settings.get('url', ''))
            self.quantity.setValue(int(settings.get('quantity', 1)))
            self.limit.setValue(float(settings.get('limit', 100000)))
            self.payment.setCurrentText(settings.get('payment', 'Pilih metode pembayaran'))
            self.prepare_early.setChecked(bool(settings.get('prepare_before_time', True)))
            self.refresh_coins.setChecked(True)
            self.stock_attempts.setValue(int(settings.get('stock_attempts', 3)))
        except (OSError, ValueError, TypeError):
            pass
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_time_hint)
        self.clock_timer.start(1000)
        self.update_time_hint()
        if auto_open:
            QTimer.singleShot(600, self.open_session)

    def open_session(self):
        if self.session and self.session.isRunning():
            self.send('focus')
            return
        if self.source.currentIndex() == 0:
            try:
                from .bridge import ChromeBridge
                self.bridge = ChromeBridge()
                self.pair_code.setText(self.bridge.token)
            except Exception:
                self.show_status('KONEKSI BELUM TERSEDIA', 'Port lokal 8765 sedang digunakan atau library bridge belum terpasang. Tutup dashboard lain lalu coba lagi.')
                return
        self.session = ShopeeSession(profile='chrome_pilihan' if self.bridge else 'shopee_utama', bridge=self.bridge)
        self.session.status.connect(self.show_status)
        self.session.log.connect(self.append_log)
        self.session.frame.connect(self.show_frame)
        self.session.verification_view.connect(self.preview.setVisible)
        self.session.account.connect(self.account_changed)
        self.session.product.connect(self.product_changed)
        self.session.promotion.connect(self.promotion_changed)
        self.session.busy.connect(self.set_busy)
        self.session.finished_order.connect(lambda oid: self.show_status('SELESAI', f'Pesanan {oid} menunggu pembayaran.'))
        self.session.finished.connect(self.session_finished)
        self.session.start()
        self.source.setEnabled(False)
        self.login.setEnabled(False)
        self.check_login.setEnabled(True)
        self.check_login.setFocus()
        self.show_status('MENYIAPKAN KONEKSI', 'Menyiapkan akses tab Shopee lokal…')

    def send(self, command, value=None):
        if self.session and self.session.isRunning():
            self.session.send(command, value)
        else:
            if command == 'schedule':
                self.set_busy(False)
            self.show_status('SESI BELUM TERBUKA', 'Buka login Shopee terlebih dahulu.')

    def append_log(self, message):
        self.logs.appendPlainText(f'{datetime.now(ZONE):%H:%M:%S}  {message}')

    def open_report(self):
        reports = [p for p in (DATA / 'latest-run.json', DATA / 'latest-preparation.json') if p.exists()]
        if reports:
            path = max(reports, key=lambda p: p.stat().st_mtime_ns)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self.show_status('BELUM ADA LAPORAN', 'Laporan dibuat setelah tugas pembelian atau pengujian checkout selesai/berhenti.')

    def show_status(self, state, message):
        self.state.setText(state)
        self.message.setText(message)
        self.resume.setEnabled(state == 'VERIFIKASI')
        if state == 'VERIFIKASI':
            QApplication.alert(self)

    def show_frame(self, data):
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.last_frame = pixmap
            self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def account_changed(self, ready, name):
        self.authenticated = ready
        self.account_label.setText(f'Terhubung: {name}' if ready else name)
        self.product_section.setEnabled(ready and not self.active)
        if not ready:
            self.invalidate_product()
        else:
            self.purchase_section.setEnabled(not self.active)

    def invalidate_product(self):
        self.product_data = None
        self.product_name.setText('Tautan belum diverifikasi.')
        self.purchase_section.setEnabled(False)

    def verify_link(self):
        try:
            url = shared_url(self.url.text())
        except ValueError as exc:
            self.show_status('TAUTAN BELUM VALID', str(exc))
            return
        self.save_settings()
        self.invalidate_product()
        self.send('verify_prepare', {'url': url, 'quantity': self.quantity.value(),
            'variants': [], 'payment': self.payment.currentText()})

    def product_changed(self, data):
        previous = [field.currentData() for field in self.variant_fields] if self.product_data and self.product_data['url'] == data['url'] else []
        if self.promo_choices and self.promo_choices['url'] == data['url']:
            previous = self.promo_choices['choices']
            self.promo_choices = None
        self.product_data = data
        self.product_name.setText(data['name'])
        self.variant_fields = []
        while self.variants_layout.rowCount():
            self.variants_layout.removeRow(0)
        for index, group in enumerate(data['groups']):
            combo = QComboBox()
            combo.addItem('Pilih varian…', None)
            for option in group['options']:
                combo.addItem(option['label'], option['label'])
                if option['disabled'] and not self.stock_release.isChecked():
                    combo.model().item(combo.count() - 1).setEnabled(False)
            if index < len(previous):
                selected = combo.findData(previous[index])
                if selected >= 0 and combo.model().item(selected).isEnabled():
                    combo.setCurrentIndex(selected)
            combo.currentIndexChanged.connect(lambda _, i=index, c=combo: self.preview_choice(i, c))
            self.variants_layout.addRow(group['name'][:50], combo)
            self.variant_fields.append(combo)
        if not data['groups']:
            self.variants_layout.addRow(QLabel('Tidak ada tombol varian yang terbaca. Cocokkan dengan halaman produk.'))
        self.purchase_section.setEnabled(self.authenticated and not self.active)

    def scan_promotion(self):
        try:
            url = shared_url(self.url.text())
        except ValueError as exc:
            self.show_status('TAUTAN BELUM VALID', str(exc))
            return
        self.save_settings()
        self.promo_choices = None
        self.promo_result.setText('Memindai bukti varian/paket, harga, dan jadwal. Hasil sebelumnya belum digunakan untuk pemindaian ini.')
        self.send('scan_promotion', {'url':url,'target':datetime.fromtimestamp(self.promo_time.dateTime().toSecsSinceEpoch(),ZONE).isoformat(),
            'limit':self.limit.value(),'quantity':self.quantity.value(),'payment':self.payment.currentText(),'max_combinations':64})

    def promotion_changed(self, result):
        candidate = result.get('candidate')
        self.promo_choices = {'url':result['product_url'],'choices':candidate['choices']} if candidate else None
        if candidate:
            if result.get('target'):
                moment = datetime.fromisoformat(result['target'])
                self.schedule.setDateTime(QDateTime.fromSecsSinceEpoch(int(moment.timestamp())).toTimeZone(QTimeZone(b'Asia/Jakarta')))
            self.promo_result.setText('Bukti promo satu SKU ditemukan: '+', '.join(candidate['choices'])+
                '. Harga produk Rp'+candidate['offers'][0]['price']+'. Total checkout tetap diperiksa terhadap batas Anda.')
        else:
            self.promo_result.setText(result.get("summary", {}).get("reason", "SKU/paket flash sale belum dapat dipastikan dari data publik.") + f" {len(result['rows'])} kombinasi diperiksa. "
                + ('Pemindaian dibatasi 64 kombinasi. ' if result.get('truncated') else '')
                + 'Buka hasil untuk melihat bukti; bot tidak menebak paket termurah.')

    def open_promotion_report(self):
        path = DATA/'latest-promotion.json'
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            self.show_status('BELUM ADA PEMINDAIAN', 'Jalankan pencarian varian/paket promo terlebih dahulu.')

    def preview_choice(self, index, combo):
        if self.stock_release.isChecked():
            self.show_status('TARGET STOK DISIMPAN', 'Pilihan target disimpan. Bot akan refresh dan memilih ulang saat jadwal dijalankan.')
            return
        if not self.active and combo.currentData() is not None:
            self.send('variant', {'index': index, 'label': combo.currentData(), 'config': {
                'url': self.product_data['url'], 'quantity': self.quantity.value(),
                'payment': self.payment.currentText(), 'variants': [f.currentData() for f in self.variant_fields]}})

    def set_busy(self, busy):
        self.active = busy
        self.check_login.setEnabled(not busy)
        self.product_section.setEnabled(self.authenticated and not busy)
        self.purchase_section.setEnabled(self.authenticated and not busy)
        self.start.setEnabled(bool(self.product_data) and not busy)

    def execution_changed(self):
        immediate = self.execution.currentIndex() == 1
        self.schedule.setEnabled(not immediate)
        self.start.setText('Jalankan auto-buy sekarang' if immediate else 'Jadwalkan auto-buy')
        self.update_time_hint()

    def update_time_hint(self):
        if self.execution.currentIndex() == 1:
            self.time_hint.setText('Tugas dimulai segera setelah kamu menekan tombol di bawah.')
            return
        target = datetime.fromtimestamp(self.schedule.dateTime().toSecsSinceEpoch(), ZONE)
        remaining = (target - datetime.now(ZONE)).total_seconds()
        self.time_hint.setText(f'Mulai dalam {int(remaining)//60} menit {int(remaining)%60} detik.' if remaining > 0 else
                               'Jadwal sudah lewat. Ubah waktunya atau pilih Jalankan sekarang.')

    def start_job(self):
        if self.active:
            return
        if not self.product_data:
            return
        if self.payment.currentIndex() == 0:
            self.show_status('PILIH PEMBAYARAN', 'Pilih metode pembayaran sebelum mengaktifkan jadwal.')
            return
        if any(field.currentData() is None for field in self.variant_fields):
            self.show_status('PILIH VARIAN', 'Lengkapi setiap pilihan varian terlebih dahulu.')
            return
        immediate = self.execution.currentIndex() == 1
        target = datetime.now(ZONE) if immediate else datetime.fromtimestamp(self.schedule.dateTime().toSecsSinceEpoch(), ZONE)
        if not immediate and target <= datetime.now(ZONE):
            self.show_status('PERIKSA JADWAL', 'Jadwal sudah lewat. Ubah waktunya atau pilih Jalankan sekarang pada Waktu eksekusi.')
            self.append_log('Tugas tidak dikirim: jadwal sudah lewat. Pilih waktu mendatang atau Jalankan sekarang.')
            return
        self.save_settings()
        self.set_busy(True)
        self.show_status('MENGIRIM TUGAS', 'Mengaktifkan tugas pembelian sekarang.' if immediate else 'Mengaktifkan jadwal pembelian.')
        self.send('schedule', {'url': self.product_data['url'], 'variants': [f.currentData() for f in self.variant_fields],
            'quantity': self.quantity.value(), 'payment': self.payment.currentText(), 'limit': self.limit.value(), 'time': target.isoformat(),
            'wait_stock_release': self.stock_release.isChecked(),
            'immediate': immediate, 'stop_before_submit': self.inspect_checkout.isChecked(),
            'prepare_before_time': self.prepare_early.isChecked(), 'refresh_with_coins': self.refresh_coins.isChecked(),
            'stock_attempts': self.stock_attempts.value()})

    def continue_job(self):
        if self.session:
            self.session.resume_event.set()
        self.resume.setEnabled(False)

    def cancel_job(self):
        if self.session:
            self.session.cancel_event.set()
        self.show_status('MENGHENTIKAN', 'Menunggu operasi browser selesai. Jangan menekan tombol pesanan secara manual bersamaan.')

    def session_finished(self):
        if self.bridge:
            self.bridge.close()
            self.bridge = None
            self.pair_code.clear()
        self.source.setEnabled(True)
        self.login.setEnabled(True)
        self.check_login.setEnabled(False)
        self.account_changed(False, 'Sesi browser tertutup')
        if self.closing:
            QTimer.singleShot(0, self.close)

    def save_settings(self):
        if self.persist_settings:
            try:
                DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
                (DATA / 'gui-settings.json').write_text(json.dumps({'url': self.url.text(), 'quantity': self.quantity.value(),
                    'payment': self.payment.currentText(), 'limit': self.limit.value(),
                    'prepare_before_time': self.prepare_early.isChecked(), 'refresh_with_coins': self.refresh_coins.isChecked(),
                    'stock_attempts': self.stock_attempts.value()}))
            except OSError:
                pass

    def closeEvent(self, event):
        self.save_settings()
        if self.session and self.session.isRunning():
            self.closing = True
            self.session.stop_event.set()
            self.session.cancel_event.set()
            self.show_status('MENUTUP', 'Menutup browser dan menyimpan sesi. Tutup dashboard sekali lagi setelah selesai.')
            event.ignore()
            return
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
