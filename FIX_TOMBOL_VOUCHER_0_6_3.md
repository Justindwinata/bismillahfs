# Perbaikan tombol pembelian 0.6.3

Rekaman pengguna menunjukkan varian dan jumlah sudah diterapkan, tetapi pencarian tombol gagal karena hanya menerima nama persis Beli Sekarang.

Backend sekarang memakai satu pola untuk Beli Sekarang, Beli Dengan Voucher, serta kedua label dengan harga Rp pada nama tombol. Spasi dan baris baru ditangani. Pola yang sama digunakan untuk membuka panel mobile dan mengonfirmasi panel tersebut. Pemilihan harus unik dan tombol harus aktif; tombol Buat Pesanan tetap memakai penanganan terpisah.

Uji DOM lokal menjalankan persiapan produk dengan dua kelompok varian, jumlah dua, dan empat variasi label tombol. Uji tambahan memastikan dua tombol pembelian yang sama-sama terlihat tidak dipilih secara acak dan tombol nonaktif tidak ditekan. Uji ini bukan bukti pesanan nyata dibuat. Tidak ada pesanan nyata yang dibuat dalam revisi ini.

Ekstensi tetap 0.6.2 karena perubahan hanya di backend. Dashboard 0.6.3 memerlukan pemasangan kode baru setelah dijalankan ulang.
