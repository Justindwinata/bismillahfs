# Checkout dengan hadiah gratis — 0.6.7

Pemeriksaan lama menolak checkout ketika jumlah gambar produk bukan satu. Checkout dengan satu produk utama dan bonus Hadiah ikut ditolak.

Ekstensi 0.6.3 mengembalikan jumlah baris berbayar, baris hadiah, dan gambar dengan struktur yang belum dikenali. Hadiah harus mempunyai label Hadiah, Free Gift, atau Gift yang terlihat pada kolom produk, jumlah positif, serta harga satuan dan subtotal kosong, nol, atau berlabel Gratis/Free. Judul yang sekadar memuat kata gift tidak cukup. Nama, varian, jumlah, dan konsistensi subtotal produk utama tetap diperiksa. Total akhir dan metode pembayaran tetap menggunakan validasi yang ada.

Satu produk berbayar target boleh disertai beberapa hadiah gratis. Produk tambahan berbayar, duplikat produk target, hadiah dengan biaya, dan struktur gambar tambahan yang tidak dikenali tetap menghentikan pemesanan. Browser aplikasi juga menerapkan pemeriksaan hadiah yang sama melalui locator.

Mulai ulang dashboard ke 0.6.7, muat ulang ekstensi ke 0.6.3, lalu pasangkan tab kembali. Protokol tetap 8; ekstensi lama tetap memakai pemeriksaan satu gambar sehingga perlu dimuat ulang untuk mendapatkan dukungan hadiah.

Pengujian lokal mencakup beberapa hadiah, harga nol/kosong, hadiah berbayar, item tanpa label hadiah, jumlah hadiah nol, duplikat produk, struktur tidak dikenali, kesalahan jumlah target, dan browser aplikasi. Simulasi DOM tidak membuktikan transaksi pada checkout asli yang ada di screenshot; pengujian akun berikutnya tetap diperlukan.
