# Pengujian manual versi 0.3.0

Dashboard dijalankan melalui `.venv/bin/python -m flashsale.app`. Muat ulang ekstensi Flashsale Lokal yang sudah terpasang dari pengelola ekstensi Chrome dan pastikan versi 0.3.0, lalu hubungkan tab Shopee menggunakan kode pairing dashboard. Backend menolak tugas dengan protokol lama sehingga aplikasi tidak diam-diam menggunakan fitur yang tidak tersedia.

Klik Periksa login, verifikasi tautan produk, pilih seluruh varian yang terbaca, isi jumlah, metode pembayaran, dan batas total termasuk ongkir. Tombol Periksa kesiapan hanya memeriksa koneksi, sesi yang telah dideteksi, serta kesesuaian halaman produk; tombol ini tidak menguji transaksi atau menjamin stok tersedia. Jika panel mobile baru memunculkan varian, pilihannya dikembalikan ke dashboard untuk dilengkapi.

Pilihan Pengujian: berhenti sebelum tombol Buat Pesanan bersifat opsional dan secara default tidak dicentang. Saat dicentang, tugas hanya dapat berakhir dengan CHECKOUT SIAP setelah pembayaran dan total terverifikasi, tanpa membuat catatan pemesanan atau menekan tombol final. Untuk pengujian alur sampai pesanan menunggu pembayaran, lepaskan centang tersebut sebelum menjalankan tugas. Pembayaran tetap dilakukan pengguna sendiri.

Gunakan Jalankan sekarang untuk menguji tanpa menunggu jadwal. Gunakan jadwal WIB mendatang untuk menguji penjadwalan. Tugas kedaluwarsa lebih dari 30 detik tidak dijalankan. Laptop harus tetap aktif. Dua detik terakhir sebelum jadwal tidak dipakai untuk screenshot berkala; ini mengurangi pekerjaan monitoring saat mendekati target, bukan jaminan waktu penerimaan server.

Ketika CAPTCHA atau verifikasi muncul, selesaikan pada tab browser asli lalu klik Lanjutkan. Aplikasi tidak menyelesaikan tantangan itu. Interaksi browser yang sedang berlangsung mungkin perlu selesai sebelum penghentian diproses. Jangan menekan tombol pemesanan manual bersamaan dengan worker.

Buka laporan pengujian terakhir setelah tugas selesai atau berhenti. `.local/latest-run.json` mencatat status tahap dan durasi sejak tugas dimulai, serta waktu respons maksimal 100 panggilan bridge terakhir. Durasi bridge dapat mencakup panggilan sebelum tugas; ini data diagnostik lokal, bukan benchmark checkout Shopee. Tidak menyimpan cookie, kode pairing, screenshot, atau isi lengkap halaman. Hasil `inspection_complete_no_order` berarti tidak ada pesanan dikirim; `pending_payment_confirmed` berarti status dan ID pesanan ditemukan. Error atau status UNKNOWN tidak berarti pesanan gagal terbentuk: periksa riwayat sebelum mengulang.

Ekstensi hanya menjalankan permintaan yang belum kedaluwarsa. Navigasi versi ini menunggu event load selesai sehingga halaman lama tidak langsung dianggap sebagai tujuan yang sudah terbuka. Pembacaan status normal menggabungkan URL dan deteksi verifikasi dalam satu permintaan. Tidak ada retry otomatis tombol Buat Pesanan atau pengiriman pembelian paralel.

Batas saat ini: selector pembayaran masih membutuhkan elemen radio yang dapat diverifikasi. Markup pembayaran, varian, total, dan bukti pesanan yang tidak dikenali menghentikan tugas. Alur checkout live Shopee belum dibuktikan end-to-end. Pengujian lokal memakai stub/fake untuk menguji logika; hasilnya tidak boleh dilaporkan sebagai transaksi Shopee nyata.

# Perubahan 0.4.0

Versi ini memeriksa pathname checkout secara tepat, bukan mencari substring checkout di seluruh URL. Checkout baru diterima ketika heading Produk Dipesan dan Metode Pembayaran, h3 Total Pembayaran, serta tombol Buat Pesanan ditemukan. Beranda atau URL redirect yang sekadar memuat kata checkout tidak dianggap checkout.

Jika Beli Sekarang membawa ke keranjang, bot memilih satu baris produk berdasarkan shop/item ID, nama, dan varian. Pilihan item lain dilepas tanpa menghapus isi keranjang. Jumlah target ditetapkan tepat, tidak ditambahkan pada jumlah lama, lalu diverifikasi kembali setelah stabil. Ringkasan checkout harus berisi satu baris dengan nama, jumlah, varian, dan subtotal yang sesuai sebelum pemesanan. Kontrol yang tidak dikenali menghentikan proses, bukan ditebak.

Bank BCA/BNI/BRI/Mandiri dipilih melalui kategori Transfer Bank, lalu radio bank spesifik dan status aria-checked dibaca kembali. QRIS dipilih melalui radio QRIS. Pembayaran yang tidak tersedia menghasilkan error; tidak ada instruksi memilih pembayaran secara manual. CAPTCHA/verifikasi keamanan tetap membutuhkan pengguna. Varian yang diberikan juga diperiksa status pilihannya setelah diklik.

Gambar monitoring kini hanya dikirim ketika status VERIFIKASI; status teks/log tetap berjalan. Pengambilan gambar rutin saat alur normal dihentikan. Ekstensi yang diperlukan adalah versi 0.4.0/protokol 4. Muat ulang ekstensi yang terpasang lalu lakukan pairing ulang.

Bukti pemeriksaan langsung: halaman produk membawa ke keranjang dan jumlah lama terakumulasi. Pada pemeriksaan browser, jumlah telah diperbaiki menjadi dua dan halaman checkout asli berhasil dibuka dengan subtotal Rp790.000, Bank BCA terpilih, serta total akhir Rp797.500. Ini bukti pemeriksaan browser sampai checkout, **bukan bukti bot versi 0.4.0 telah membentuk pesanan otomatis**. Tombol Buat Pesanan tidak ditekan selama pemeriksaan ini.

Pengujian terbaru: 34 tes Python dan 4 tes JavaScript lulus. Sebagian tes memakai DOM lokal yang disusun dari struktur yang diamati; tidak melakukan transaksi di server Shopee. Tahap pembentukan pesanan dan pembacaan ID/status menunggu pembayaran masih perlu diuji pada versi baru yang sudah dimuat ke Chrome.


# Perbaikan 0.4.1

Pada checkout asli, host `div#anti_fraud_captcha` kosong memiliki DOMRect berukuran 0×0. Detektor lama memakai `getClientRects().length`, sehingga host dianggap tantangan aktif dan alur berhenti sebelum pemesanan. Detektor baru memerlukan luas tampilan positif, memeriksa visibilitas leluhur, dan memerlukan isi tantangan yang benar-benar tampil. Isi tantangan yang diposisikan di luar host 0×0 tetap terdeteksi. Container kosong, display:none, visibility:hidden, dan opacity:0 tidak mengaktifkan monitoring.

Guard memeriksa ulang tantangan setiap 300 ms dan melanjutkan otomatis setelah tantangan selesai; tombol Lanjutkan tidak wajib. Verifikasi keamanan aktif tetap diserahkan kepada pengguna. Pemeriksaan batas total, kesesuaian produk, sesi login, dan pencegahan pesanan duplikat tetap berlaku.

Ekstensi 0.4.1 menggunakan protokol 5 agar backend menolak skrip deteksi lama. Muat ulang ekstensi dan pairing ulang setelah dashboard baru berjalan. Validasi read-only pada checkout Shopee tanggal 26 Oktober 2026 menunjukkan challenge=false dan tombol Buat Pesanan aktif. Belum ada tombol final ditekan dalam pemeriksaan ini. 39 tes Python dan 4 tes JavaScript lulus; keberhasilan pembentukan pesanan nyata belum dikonfirmasi.


# Perbaikan 0.4.2

Pemeriksaan DOM keranjang asli menemukan `input.stardust-checkbox__input` berukuran 13×13 dan opacity:0. Shopee menggambar checkbox melalui pembungkus; input tersebut tetap interaktif. Versi 0.4.1 tanpa sengaja menerapkan syarat opacity CAPTCHA ke semua kontrol, sehingga prepare_cart menolak checkbox dan tidak menemukan kandidat baris.

Versi 0.4.2 memisahkan visibilitas layout kontrol dari visibilitas isi tantangan. Kontrol transparan tetap bisa dikenali dan diklik; tantangan opacity:0/aria-hidden tetap diabaikan. Host CAPTCHA 0×0 kosong tetap tidak aktif. Tes regresi keranjang memakai input opacity:0 dan memverifikasi pemilihan satu produk serta penggantian jumlah tepat. Hasil: 40 tes Python dan 4 tes JavaScript lulus.

Ekstensi memakai protokol 6. Dashboard 0.4.1 yang sudah berjalan menerima protokol ini, sehingga perbaikan dapat dipakai cukup dengan reload ekstensi dan pairing ulang memakai kode yang sama, tanpa memulai ulang dashboard atau mengubah konfigurasi pembelian. Backend yang dimulai berikutnya memerlukan 0.4.2 untuk menolak ekstensi 0.4.1 yang bermasalah. Belum ada pembentukan pesanan nyata yang dikonfirmasi oleh pengujian agen ini.


# Perbaikan stabilisasi keranjang backend

Run 02:03:41 berhenti sebelum checkout dengan pesan pilihan keranjang bukan satu produk. Pemeriksaan DOM sesudah kegagalan menunjukkan satu checkbox produk target aria-checked=true; ini menunjukkan pemeriksaan akhir sebelumnya tidak cukup menghadapi perubahan status saat rekonsiliasi UI. Backend kini menghitung hanya checkbox produk yang tampil dan menunggu jumlah, enabled, satu pilihan, serta checkbox target bersama-sama stabil selama 500 ms, maksimal 8 detik. Jika gagal, laporan menyertakan hitungan dan keadaan target/jumlah, bukan pesan umum.

Tes regresi mereproduksi perubahan aria-checked selama 800 ms setelah blur jumlah, serta salinan baris responsif tersembunyi yang terpilih. Keduanya lulus bersama 42 tes Python. Pengaturan disimpan saat tugas dikirim, bukan hanya saat jendela ditutup; laporan berikutnya mencatat nama, URL, dan varian produk. Ekstensi tetap 0.4.2/protokol 6; perubahan ini memerlukan mulai ulang dashboard, tanpa reload berkas ekstensi.


# Bukti transaksi nyata 26 Oktober 2026, 02:07 WIB

Pengguna menjalankan bot hingga membentuk pesanan HMNS Alpha Eau de Parfum 100ml ×1, Bank BCA, total Rp327.500. Tahap MEMBENTUK PESANAN tercatat pada elapsed 4115,9 ms. Pengguna mengonfirmasi menunggu pembayaran; agen memeriksa halaman detail asli dan status MENUNGGU PEMBAYARAN. Identitas pesanan dan checkout tidak disertakan dalam dokumentasi publik. Tidak ada pembayaran dilakukan oleh agen.

Keterbatasan tersisa: bot menandai outcome ValueError/UNKNOWN setelah redirect ke pay.shopee.co.id yang ditolak bridge. Catatan SQLite percobaan #1 telah direkonsiliasi menjadi PENDING_PAYMENT berdasarkan bukti UI; laporan mempertahankan outcome otomatis asli dan menambahkan independent_verification. Ini bukti pembentukan pesanan otomatis nyata, tetapi pencatatan sukses otomatis setelah redirect masih belum selesai. Jangan mengulang produk ini untuk menguji konfirmasi; gunakan bukti pesanan yang sudah ada.


# Perbaikan produk diskon pada checkout

Run 02:13:22 gagal membaca ringkasan HMNS Parfum - ALPHA 100ml dari Megamiss Official. Baris produk asli menampilkan harga aktif Rp320.000, harga awal Rp345.000, jumlah 1, dan subtotal Rp320.000. Parser lama meminta tepat dua string rupiah pada keseluruhan baris, sehingga tiga string rupiah menyebabkan kegagalan.

Parser baru mencari struktur lima kolom produk (identitas, varian, harga satuan, jumlah, subtotal). Harga aktif diambil dari awal kolom harga satuan; harga awal opsional harus tidak lebih kecil dari harga aktif. Jumlah, varian, perkalian harga aktif × jumlah, dan subtotal tetap diverifikasi. Total akhir tetap dibaca dari Total Pembayaran sehingga diskon Rp25.000 tidak ditambahkan/dikurangi dua kali. Tidak ada perubahan pada izin/versi ekstensi.

Tes: 46 Python dan 4 JavaScript lulus, termasuk markup baris diskon asli yang disimpan tanpa data akun/alamat di tests/fixtures/discounted_checkout_row.html; kasus subtotal salah dan urutan harga ambigu tetap ditolak. Belum ada tombol Buat Pesanan ditekan agen selama perbaikan ini. Keterbatasan konfirmasi otomatis setelah redirect pay.shopee.co.id yang sudah dicatat sebelumnya masih berlaku.


# Pembaruan 0.5.0

Rincian implementasi, batas pengujian, dan metrik tersedia di UPGRADE_0_5.md. Hasil 60 tes Python dan 6 JavaScript lulus; belum ada transaksi live versi 0.5.0 yang dijalankan agen.


# Dashboard 0.5.1

Rekaman layar 03:39 ditinjau; alur baru dan perbaikan klik ulang varian dijelaskan di UPGRADE_0_5_1.md. Ekstensi tetap 0.5.0/protokol 7. Belum ada transaksi baru yang dibuat agen selama revisi ini.


# Dashboard 0.5.2 — varian bawaan dan melanjutkan keranjang

Kegagalan 03:52:31 menampilkan Tautan harus menunjuk satu produk Shopee karena persiapan sebelumnya masih di /cart. Pemeriksaan DOM produk Holder Tempel Dinding Remote TV AC / Rak Holder HP Polos menunjukkan keranjang berisi satu baris target dengan tombol varian disabled: POLOS Rak Holder,WARNA RANDOM, sedangkan konfigurasi tanpa pilihan varian.

Backend kini menerima label bawaan hanya bila produk tidak mempunyai kelompok pilihan, konfigurasi varian kosong, tombol varian keranjang disabled, serta tepat satu baris cocok berdasarkan identitas/nama produk. Label tersebut dibawa ke pemeriksaan checkout. Dua baris kandidat tetap ditolak. Label varian yang dipilih pengguna tidak ditimpa.

Persiapan checkout dapat dilanjutkan dari keranjang tanpa menekan Beli Sekarang lagi. Jalankan sekarang mencoba menyelesaikan persiapan tersebut sebelum preflight, sehingga URL /cart tidak lagi salah diproses sebagai tautan produk. Tahap persiapan dan pemilihan varian kini mempunyai laporan latest-preparation.json terpisah; tombol laporan membuka berkas terbaru. Riwayat transaksi latest-run.json tetap terpisah.

68 tes Python dan 6 tes JavaScript lulus, termasuk varian bawaan sampai validasi checkout, penolakan dua baris kandidat, dan melanjutkan keranjang tanpa pembelian/reservasi baru. Versi ekstensi tetap 0.5.0/protokol 7. Belum ada pesanan baru yang dibuat agen untuk membuktikan transaksi live versi 0.5.2.


# Dashboard 0.5.3 — label variasi dan pembayaran ringkas

Checkout Holder menampilkan kolom kedua "Variasi: POLOS Rak Holder,WARNA RANDOM", sedangkan label keranjang tersimpan tanpa awalan. Parser kini membuang hanya awalan tampilan Variasi:/Variation: sebelum membandingkan label. Identitas produk, jumlah, varian, subtotal dan total tetap diverifikasi.

Jika persiapan sebelumnya gagal setelah mencapai /checkout, Jalankan sekarang menyelesaikan stage_checkout menggunakan konfigurasi yang dipilih sebelum preflight; URL checkout tidak diproses sebagai URL produk. Permintaan persiapan juga disimpan untuk pemeriksaan kesiapan tanpa mengirim pesanan.

Pemeriksaan UI asli menemukan metode pembayaran ringkas COD dan tombol Ubah. Bot kini mencari Ubah dalam parent heading Metode Pembayaran saja, membuka daftar kategori, menunggu kategori tersedia, lalu memilih bank sesuai konfigurasi. Tombol Ubah alamat/pengiriman tidak disentuh. Agen membuka kontrol metode pembayaran untuk memeriksa markup; tidak menekan Buat Pesanan.

72 tes Python dan 6 tes JavaScript lulus. Ekstensi tetap 0.5.0/protokol 7. Transaksi live versi ini belum dikonfirmasi. CAPTCHA dan retry stok tetap seperti 0.5.0: hanya penolakan eksplisit yang boleh memicu pengulangan final terbatas.


# Dashboard 0.5.4 — label koin berubah dan hidrasi checkout

Pemeriksaan DOM checkout asli menemukan checkbox koin yang sudah terpilih menggunakan aria-label="Coins redeemed", aria-checked="true", dan properti checked=false. Label saat belum dipilih adalah "Click here to redeem Shopee Coins". Locator lama hanya mengenali label pertama, sehingga wait_selected kehilangan elemen sesudah klik dan percobaan berikutnya salah menyimpulkan koin tidak tersedia.

Locator sekarang mengenali kedua label dan tetap membaca aria-checked sebagai status utama. Sesudah perubahan koin atau reload, wait_checkout_ready menunggu heading, total, kontrol pembayaran, dan tombol pesanan yang aktif. Selama penantian harga, struktur yang sementara belum lengkap dicoba kembali alih-alih langsung menghasilkan error. Navigasi keluar checkout tetap menolak pemesanan.

75 tes Python dan 6 tes JavaScript lulus. Tes baru memeriksa toggle dua arah dengan perubahan aria-label, struktur checkout yang muncul terlambat, dan alur checkout siap sampai koin/harga diperbarui pada mode berhenti sebelum pesanan. Agen tidak membuat pesanan baru dalam perbaikan ini. Ekstensi tetap 0.5.0/protokol 7; dashboard 0.5.4 memerlukan restart dan pairing ulang.


# Dashboard 0.5.5

Perbaikan checkbox visual, pembayaran terlambat, dan pemulihan popup pra-submission dirinci di VALIDASI_0_5_5.md. 80 tes Python, 6 JavaScript, dan dua putaran 110/110 skenario lokal lulus. Delapan pilihan varian diuji di browser asli; tidak ada pesanan baru yang dibuat agen. Pengujian transaksi live versi ini belum terkonfirmasi.


# Dashboard 0.5.6

Gerbang verifikasi produk ber­varian disamakan dengan pembaca varian dashboard; jumlah aktif baru diwajibkan sesudah pilihan diterapkan. 83 tes Python, 6 JavaScript, dan 110/110 skenario lokal lulus. Rincian serta batas bukti tersedia di FIX_VARIAN_0_5_6.md.


# Versi 0.6.0 — pencarian bukti promo

Pemindaian kombinasi varian dan bukti penawaran publik ditambahkan; rincian serta batas kemampuan tersedia di PEMINDAIAN_PROMO_0_6_0.md. 90 tes Python, 6 JavaScript, dan 110/110 regresi lokal lulus. SKU Redmi pukul 12.00 belum terkonfirmasi dari halaman asli; tidak ada pesanan baru dibuat agen.
