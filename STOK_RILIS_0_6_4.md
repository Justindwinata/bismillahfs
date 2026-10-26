# Stok varian dibuka saat jadwal

Dashboard 0.6.4 menambahkan mode “Stok dibuka saat jadwal: refresh lalu pilih ulang varian target”. Mode ini harus diaktifkan sebelum memilih varian promo yang saat ini nonaktif. Pilihan tetap memakai label asli, tanpa menekan tombol varian nonaktif di Shopee. Pemilihan dashboard tidak memulai persiapan checkout pada mode ini.

Saat jadwal dimulai, backend memuat ulang URL produk terverifikasi, membaca kelompok varian baru, dan memilih kembali kombinasi target yang sama. Checkout hanya dimulai setelah seluruh pilihan berhasil diterapkan dan kolom jumlah aktif. Jika target belum tersedia, pemeriksaan diulang maksimal 10 kali, dengan jeda satu detik setelah setiap pemeriksaan gagal. Waktu pemuatan halaman dan CAPTCHA dapat membuat durasi keseluruhan lebih dari 10 detik. Pembatalan tetap tersedia. Mode ini mengabaikan persiapan checkout sebelum jadwal karena stok memang belum terbuka.

Bot tidak memilih pengganti jika target belum tersedia. Identitas produk, varian, jumlah, pembayaran dan batas total tetap diperiksa melalui alur checkout yang ada. Stok di server tetap dapat habis setelah tampilan menjadi aktif.

Pengujian lokal mencakup varian yang aktif setelah pemuatan kedua, batas 10 pemeriksaan, tidak mengganti target, serta pemilihan varian nonaktif pada dashboard tanpa mengirim aksi preview. Ini bukan pembuktian pembelian flash sale nyata.

Ekstensi tetap 0.6.2. Setelah dashboard dimulai ulang, pasangkan kode dashboard baru, verifikasi produk, aktifkan mode stok rilis, pilih seluruh varian target, lalu tentukan jadwal dan jalankan.

## Revisi 0.6.5

Pada mode stok rilis, perubahan koin dan penantian perubahan harga akibat koin dilewati seluruhnya, sekalipun pengaturan refresh_with_coins masih true. Setelah stok aktif, bot memilih target, membuka checkout, memilih pembayaran, memvalidasi total dan kemudian masuk ke submit_order. Mode pengujian tetap berhenti sebelum submit, jika dicentang. Kontrol koin pada dashboard dinonaktifkan saat mode stok rilis aktif, tanpa menghapus preferensi alur biasa.
