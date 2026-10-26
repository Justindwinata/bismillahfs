# Validasi dashboard 0.5.5

Perbaikan terakhir mengaktifkan kotak visual stardust-checkbox__box, bukan input transparan yang checked dan aria-checked dapat berbeda. Ini dipakai untuk koin dan pemilihan keranjang. Label koin sebelum/sesudah dipilih tetap dikenali. Pemilihan pembayaran menunggu kategori muncul meski heading sudah lebih dahulu tampil. Saat menunggu status pilihan, CAPTCHA tetap dipantau dan waktu penantian tantangan tidak dihitung sebagai timeout pilihan.

Jika koin tidak tersedia, bot tidak memuat ulang checkout; konteks produk tetap dipertahankan dan total diperiksa terhadap batas harga. Popup “informasi produk telah diperbarui” dapat dipulihkan satu kali dengan verifikasi dan persiapan ulang hanya sebelum ada permintaan pesanan. Setelah submission atau hasil ambigu, bot tidak mengulang pembentukan pesanan. Popup stok habis tetap memakai OK dan retry terbatas.

## Bukti pengujian

80 tes Python dan 6 tes JavaScript lulus pada kode terakhir. Dua putaran matriks lokal selesai masing-masing 110/110. Matriks memakai kelompok varian yang diamati pada lima halaman produk Shopee, jumlah 1–2, lima pengulangan per kombinasi, QRIS/Bank BCA, checkbox koin awal aktif/nonaktif, pembayaran terbuka/tertutup, dan popup stok habis. Setiap skenario mencapai CHECKOUT SIAP pada mode inspeksi, memastikan Store tidak dipanggil dan tombol final tidak ditekan, lalu menutup popup stok lokal. Ini tidak menguji server transaksi Shopee.

| Produk | Skenario lokal | Hasil |
|---|---:|---|
| WWC 8 - T-Shirt / Kaos / Baju Oversize Diego Maradona | 20 | Lulus |
| I13 Pro TWS Headset Bluetooth Bass 9D HiFi Stereo Sound Earphone Wireless Waterproof Headphone Sport | 60 | Lulus |
| Holder Tempel Dinding Remote TV AC / Rak Holder HP Polos | 10 | Lulus |
| HMNS Untitled Humans Aroma 01 Eau De Parfum 100 ml | 10 | Lulus |
| HMNS Alpha Blindbox | 10 | Lulus |

Pada browser Shopee asli, delapan pilihan ukuran/warna diuji: M/L pada WWC dan HITAM/PUTIH/PINK/KUNING/BIRU MUDA/HIJAU pada I13. Seluruhnya terlihat terpilih sesuai aksi, dan jumlah 1 tetap aktif. Ini pengujian UI melalui konektor browser, bukan bukti delapan transaksi otomatis. Tiga produk lain diperiksa struktur halamannya: varian bawaan Holder, HMNS Untitled tanpa tombol varian, dan HMNS Alpha Blindbox tanpa tombol varian. Pilihan awal pada tab pengujian dikembalikan setelah pemeriksaan.

![Bukti pilihan warna pada halaman asli](.local/variant-live-proof.png)

## Batas hasil

Tidak ada pesanan baru dibuat oleh agen pada pengujian ini. Keberhasilan transaksi nyata versi sebelumnya sudah tercatat di TESTING.md, tetapi versi 0.5.5 belum terbukti membentuk pesanan untuk semua produk di atas. Popup stok dan CAPTCHA diuji menggunakan fixture lokal; belum ada bukti flash sale asli dengan CAPTCHA dan stok berebut. Target transaksi live <=3 detik belum terverifikasi. Waktu fixture lokal tidak boleh dipakai sebagai klaim kecepatan transaksi Shopee.

Aksesibilitas jendela Python kembali timeout saat agen mencoba mengoperasikan dashboard. Karena itu pengujian bot lengkap pada akun tetap membutuhkan pairing dan pemicu dari dashboard oleh pengguna. Chrome profil Sfq telah dibuka kembali; konektor browser tersambung. Ekstensi tetap 0.5.0/protokol 7, tanpa perlu reload.

## Mengulang pengujian

Jalankan `.venv/bin/python -m unittest discover -s tests -q`, `node --test tests/extension.test.cjs`, dan `.venv/bin/python tests/run_product_matrix.py`. Fixture produk publik berada di tests/fixtures/product_matrix_observed.json. Hasil matriks terakhir berada di .local/product-matrix-results.json; hasil pilihan varian browser berada di .local/variant-live-results.json.
