# Flashsale Lokal — dashboard Shopee

Aplikasi desktop Python/PySide6 dengan browser Chromium terlihat. Jalankan `.venv/bin/python -m flashsale.app` dari folder proyek. Dependensi tersedia pada `requirements.txt`; browser dipasang dengan `.venv/bin/python -m playwright install chromium`.

## Alur aplikasi

Sumber default adalah **Chrome saya — tab yang sudah login**. Hubungkan ekstensi lokal mengikuti `chrome-extension/README.md`; dashboard menunggu pairing tanpa membuka browser baru. Tab dan sesi tetap berada di Chrome milik pengguna. Pilihan **Browser aplikasi — sesi terpisah** masih tersedia. Login dan selesaikan CAPTCHA/OTP langsung di browser. Klik **Periksa login**; aplikasi mencari bukti login pada antarmuka Shopee, bukan menganggap login berhasil hanya karena cookie tersedia. Tahap produk terkunci sampai pemeriksaan itu berhasil.

Tempel tautan produk lengkap, tautan pendek `id.shp.ee`/`shope.ee`, atau teks Bagikan dari aplikasi Shopee. Klik **Verifikasi tautan & baca produk**. Nama produk dibaca dari h1 halaman; varian dibaca dari tombol product-variation yang terlihat. Dropdown hanya berisi data yang ditemukan. Jika markup tidak sesuai, proses berhenti atau menampilkan bahwa tidak ada varian terbaca; periksa halaman asli. Tidak ada data produk contoh.

Pilih varian, jumlah, preferensi pembayaran, batas total termasuk ongkir, dan jadwal WIB menggunakan pemilih tanggal/jam. Tombol **Aktifkan auto-buy** menjalankan pemilihan varian, pengisian jumlah, Beli Sekarang, dan Checkout bila melalui keranjang. Aplikasi memeriksa metode pembayaran yang dipilih, total akhir, dan tombol Buat Pesanan sebelum mengirim satu kali. Metode yang tidak dapat diverifikasi menghentikan proses; tidak ada penggantian metode diam-diam. Tidak ada langkah pembayaran otomatis.

Monitoring menampilkan screenshot browser secara berkala, status proses, dan log. Screenshot bersifat lihat saja, bukan browser interaktif. Tombol **Tampilkan browser** membawa halaman asli ke depan. Ketika verifikasi terdeteksi, kerjakan langsung di browser lalu gunakan **Lanjutkan**. Deteksi berdasarkan URL/elemen CAPTCHA tidak menjamin semua jenis tantangan dikenali. Status akhir sukses hanya ditetapkan setelah status belum dibayar dan ID pesanan terdeteksi bersama.

## Status pengujian dan batas nyata

Dashboard, penguncian tahap, browser persisten, parser rupiah, validasi tautan, normalisasi identitas produk, dan pencatatan percobaan telah diuji. Akses beranda Shopee berhasil. Sesi login yang dibuka untuk pengujian mencapai halaman CAPTCHA. Login akun, pembacaan produk nyata, pemilihan pembayaran, dan pembentukan pesanan **belum dibuktikan pada akun pengguna**. Implementasi selector checkout bersifat konservatif dan perlu disesuaikan dari halaman nyata setelah login. Daftar pembayaran dashboard adalah preferensi, bukan hasil konfirmasi ketersediaan dari Shopee.

Tugas dibatalkan jika jadwal terlewat lebih dari 30 detik. Komputer harus aktif, browser terbuka, dan jaringan tersedia. Tidak ada jaminan stok atau kemenangan flash sale. Ketentuan Shopee tetap berlaku; aplikasi tidak menyembunyikan otomasi atau melewati keamanan.

## Penyimpanan dan pengulangan

Untuk mode browser aplikasi, sesi berada dalam `.local/profiles/shopee_utama`. Untuk mode Chrome, sesi tetap berada dalam Chrome pengguna dan tidak diekspor. Database percobaan berada dalam `.local/orders.sqlite3`. Jangan bagikan direktori `.local`. Tidak ada enkripsi tambahan terhadap profil browser. Screenshot monitoring tidak ditulis ke disk oleh worker. Jangan menggunakan profil yang sama pada dua proses.

Catatan SUBMITTING dibuat sebelum klik final. Hasil belum pasti menjadi UNKNOWN; keduanya memblokir percobaan produk yang sama. Produk dinormalisasi berdasarkan shop ID dan item ID agar tautan pelacakan berbeda tidak menghindari blokir. PENDING_PAYMENT juga memblokir pemesanan ulang. Dashboard Shopee belum menyediakan pembukaan blokir; jika ada hasil tidak pasti, periksa riwayat pesanan terlebih dahulu. Jangan menghapus database untuk memaksa pengulangan.

`flashsale/shopee.py` berisi sesi dan alur khusus Shopee; `flashsale/app.py` dashboard; `flashsale/core.py` parsing, validasi, dan database. Worker generik lama dan adapter JSON tetap berada dalam repositori untuk referensi, tetapi tidak dipakai oleh dashboard Shopee.

Jalankan pengujian dengan `.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -v`. Pengujian unit tidak membuktikan transaksi marketplace.

Penghubung Chrome memakai WebSocket loopback dengan kode pairing acak dan pemeriksaan Origin ekstensi. Sembilan pengujian unit/transport lulus; pemasangan ekstensi, pairing Chrome nyata, dan alur setelah login belum terverifikasi sebelum pengguna memuat ekstensi. Detail tersedia dalam `chrome-extension/README.md`.

## Perbaikan alur mobile web (ekstensi 0.2.0)

Tampilan Device Mode Chrome tetap merupakan halaman web. Mesin pembelian kini memeriksa kolom jumlah yang terlihat; jika belum tersedia, ia menekan Beli Sekarang sekali untuk membuka panel dan menunggu kolom jumlah. Jika varian baru ditemukan di panel, pilihan dikembalikan ke dashboard dan tugas dihentikan sampai pengguna memilihnya. Nilai jumlah dibaca kembali setelah pengisian sebelum konfirmasi panel. Jumlah tidak cocok menghentikan proses. Tombol Checkout pada keranjang tidak diklik berulang selama menunggu navigasi.

Ekstensi perlu dimuat ulang oleh pengguna dari pengelola ekstensi Chrome. Versi 0.2.0 menambahkan pembacaan nilai input dan melaporkan protokolnya saat pairing. Versi lama ditolak saat verifikasi jumlah diperlukan. Pengujian tahap persiapan menggunakan objek tiruan untuk urutan panel/kuantitas dan bukan bukti checkout Shopee nyata. Pemeriksaan live masih terhambat akses inspeksi tab.

## Persiapan pengujian 0.3.0

Lihat `TESTING.md` untuk pembaruan ekstensi, pemeriksaan kesiapan, mode inspeksi checkout opsional, laporan tahap, serta batas pembuktian. Versi ini menggabungkan pembacaan status browser, menolak permintaan kedaluwarsa, dan menunggu event selesai navigasi. Hasil pengujian terbaru: 25 tes Python dan 3 tes JavaScript lulus; bukan bukti transaksi Shopee nyata.
