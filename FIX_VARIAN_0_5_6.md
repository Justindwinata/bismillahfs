# Perbaikan varian dashboard 0.5.6

Pemeriksaan awal sebelumnya memakai read_labeled_variants dengan daftar nama heading terbatas untuk membebaskan syarat quantity.is_enabled. Sementara itu daftar varian dashboard memakai extract_product, yang pada ekstensi mengambil groups dari tombol modern/legacy. Dua sumber ini tidak konsisten. Heading model khusus, duplikat heading responsif, dan markup modern bisa terbaca oleh dashboard tetapi gagal memenuhi gerbang kesiapan sebelum pembacaan dashboard dilakukan.

Verifikasi sekarang membaca extract_product terlebih dahulu. Bila ada kelompok varian dari pembaca yang sama dengan dashboard, verifikasi dapat selesai meskipun jumlah belum aktif. Stok/jumlah aktif diperiksa sesudah semua varian diterapkan dalam prepare_product. Waktu menunggu CAPTCHA di tahap tersebut tidak menghabiskan timeout aktivasi jumlah. Kombinasi yang benar-benar tetap dinonaktifkan Shopee tetap ditolak dan tidak dibuatkan pesanan.

Tiga regresi baru menguji heading model di luar kosakata lama, heading ukuran tersembunyi yang terduplikasi, dan dua kelompok model+size yang baru mengaktifkan jumlah setelah keduanya dipilih. Pengaturan dashboard kini disimpan saat verifikasi dikirim agar tautan yang gagal tetap tersimpan saat aplikasi dimulai ulang.

Hasil: 83 tes Python dan 6 JavaScript lulus. Matriks tambahan kembali 110/110 dengan jumlah awal nonaktif pada produk beropsi. Harness sekarang memanggil verify() asli sebelum persiapan; pengaktifan jumlah disimulasikan setelah kelompok varian dipilih. Matriks memakai data kelompok dari lima produk yang diamati sebelumnya. Ini validasi lokal, tanpa transaksi server Shopee.

Produk yang sedang terbuka saat pemeriksaan adalah Redmi pada tab Chrome pengguna. Pembacaan DOM live gagal dengan Debugger unattached; pembacaan native Chrome timeout. Karena itu perubahan ini belum boleh disebut terbukti menyelesaikan transaksi produk tersebut di akun pengguna. Tidak ada pesanan baru dibuat agen dalam perbaikan ini.

Ekstensi tetap 0.5.0/protokol 7. Dashboard 0.5.6 perlu dijalankan dan tab dipasangkan menggunakan kode baru. Verifikasi produk harus menampilkan opsi model/ukuran walaupun jumlah di halaman Shopee awalnya disabled. Setelah semua opsi dipilih, bot menunggu jumlah aktif dan menyiapkan checkout tanpa menekan Buat Pesanan.
