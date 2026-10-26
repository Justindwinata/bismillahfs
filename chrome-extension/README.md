# Hubungkan tab Chrome yang sudah login

Buka dashboard dengan `.venv/bin/python -m flashsale.app`, gunakan sumber **Chrome saya — tab yang sudah login**. Dashboard menyiapkan koneksi WebSocket hanya di `127.0.0.1:8765` dan membuat kode pairing acak yang berubah setiap sesi. Tombol **Salin kode** menyalin kode ke clipboard atas tindakan pengguna.

Di Chrome yang berisi login Shopee, buka `chrome://extensions`, aktifkan Mode developer, pilih **Muat yang belum dibuka / Load unpacked**, lalu pilih folder `/Users/justindwinata/Downloads/fsb/chrome-extension`. Ini pemasangan ekstensi lokal; Chrome dapat menampilkan peringatan ekstensi developer.

Aktifkan tab `https://shopee.co.id` yang sudah login. Buka ekstensi **Flashsale Lokal — Shopee Bridge**, tempel kode pairing, dan tekan **Hubungkan tab ini**. Ekstensi hanya memasangkan tab tersebut. Kembali ke dashboard dan tekan **Periksa login**. Tidak perlu mengekspor cookie atau membuka browser lain.

Izin scripting dan host Shopee memungkinkan membaca serta mengoperasikan halaman Shopee. Izin activeTab memungkinkan gambar monitoring setelah kamu membuka ekstensi pada tab yang dipilih. Tidak ada izin cookies, debugger, seluruh situs, atau pembacaan riwayat browser. Kode pairing dikirim hanya ke dashboard loopback; jangan membagikannya. Koneksi tidak dipulihkan otomatis setelah worker browser, Chrome, atau dashboard berhenti.

Tetap aktifkan tab Shopee selama monitoring gambar. Ekstensi menolak mengambil gambar jika tab lain aktif dan memeriksa kembali tab setelah pengambilan. Saat dashboard ditutup, koneksi dilepas dan tab Chrome dibiarkan terbuka. Tombol **Putuskan koneksi** pada ekstensi juga menghentikan akses aplikasi.

Login, CAPTCHA, dan OTP tetap kamu kerjakan langsung di Chrome. Ekstensi tidak menggunakan cookies API, tidak memecahkan CAPTCHA, dan menolak pengisian kolom keamanan melalui aksi fill. Jadwal, pemilihan produk, pembelian, dan deteksi status masih memakai pemeriksaan konservatif pada halaman asli; instalasi bridge bukan bukti checkout telah berhasil.
