# Dashboard 0.5.1 — checkout disiapkan saat verifikasi

Verifikasi & siapkan checkout membaca produk, lalu langsung menyiapkan checkout bila tidak ada varian. Bila ada varian, pengguna memilih semua kelompok pada dashboard; pemilihan terakhir memperbarui pilihan ke Shopee dan menyiapkan checkout. Tidak ada tombol Buat Pesanan ditekan pada tahap ini. Jumlah dan pembayaran dapat diatur sebelum verifikasi. Bila pembayaran belum dipilih saat persiapan, pemilihan dilakukan saat mulai.

Produk yang sudah disiapkan disimpan bersama URL kanonis, jumlah, dan varian. Jalankan sekarang menerima halaman checkout yang cocok tanpa kembali ke produk atau keranjang. Perubahan jumlah/varian setelah persiapan membuat bot menyiapkan ulang, sehingga waktu proses bertambah. Pilihan varian yang sudah aktif tidak diklik ulang agar tidak terlepas; jumlah yang sudah benar tidak ditulis ulang.

Mode koin aktif secara default pada dashboard baru. Bot membaca total awal, mengubah pilihan koin satu kali, lalu menunggu total berbeda dan memenuhi batas total, maksimal 10 detik. Bila koin tidak tersedia, checkout dimuat ulang satu kali. Bila total tidak berubah atau tetap terlalu mahal, bot tidak membuat pesanan. Perubahan total akibat koin bukan bukti bahwa diskon flash sale diberikan; batas total harus disetel sesuai harga yang diterima pengguna.

Penolakan stok yang eksplisit ditangani melalui OK dan percobaan ulang terbatas sesuai konfigurasi. Bot tidak menekan Pelajari lebih lanjut. Timeout/hasil transaksi ambigu tidak memicu pengulangan. CAPTCHA/verifikasi diserahkan kepada manusia; bot melanjutkan setelah tantangan hilang.

Dashboard memerlukan restart; ekstensi tetap 0.5.0/protokol 7 dan tidak memerlukan reload bila sudah versi tersebut. Pasangkan tab dengan kode dashboard baru. Verifikasi endpoint live serta waktu <=3 detik pada alur baru masih memerlukan pengujian langsung. Tes otomatis mencakup persiapan tanpa reservasi pesanan, checkout siap tanpa kembali ke produk/keranjang, varian aktif tidak terlepas, dan penolakan harga yang belum berubah.
