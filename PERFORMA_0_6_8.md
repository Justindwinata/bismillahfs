# Penggabungan pembacaan final checkout

Pemeriksaan final sebelum submit sebelumnya meminta empat pembacaan bridge: identitas/kolom produk, struktur checkout, total, dan status tombol. Dashboard 0.6.8 menggunakan satu snapshot terbaru untuk memvalidasi seluruh data tersebut. Snapshot hanya berlaku dalam satu pemanggilan; tidak disimpan untuk penggunaan setelah perubahan halaman, harga, atau pembayaran. Guard CAPTCHA tetap dijalankan sebelum pemeriksaan final, dan pengiriman pesanan tetap tunggal dengan retry terbatas hanya pada penolakan stok yang terkonfirmasi.

Ekstensi tetap 0.6.3, protokol 8. Data total dan submit_enabled sudah tersedia dalam snapshot checkout sehingga tidak perlu menambah izin browser atau endpoint jaringan. Browser aplikasi tetap menggunakan alur locator sebelumnya.

Benchmark lokal 27 Oktober 2026, 30 sampel per jalur pada DOM Chromium terisolasi: median pemeriksaan final turun dari 5,851 ms menjadi 1,265 ms. Jumlah pembacaan bridge turun dari 4 menjadi 1. Ini mengukur tahap validasi final tanpa latensi jaringan Chrome/Shopee, bukan waktu transaksi atau jaminan checkout di bawah tiga detik.

Jalankan ulang dengan `PYTHONPATH=. .venv/bin/python tests/benchmark_checkout_reads.py`. Regresi mencakup total berubah di luar batas pada pembacaan berikutnya, varian/jumlah salah, tombol nonaktif, dan hadiah gratis. Tidak ada pengujian yang mengirim pesanan nyata.

Riset dokumentasi: https://playwright.dev/python/docs/actionability menjelaskan pemeriksaan kesiapan elemen sebelum aksi. Temuan yang diterapkan adalah mengurangi pembacaan berulang, sambil mempertahankan pemeriksaan kesiapan; tidak menggunakan force click atau menghilangkan validasi. Bridge ekstensi menjalankan operasi DOM sendiri sehingga auto-wait Playwright tidak otomatis berlaku pada jalur ini.
