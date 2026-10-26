# Peralihan ke Android — status sebenarnya

Target tetap login Shopee, membaca tautan dan varian, memilih jumlah/pembayaran, menjadwalkan, memonitor proses serta verifikasi manual, dan berhenti setelah pesanan menunggu pembayaran. Mengganti browser dengan emulator tidak membuktikan kompatibilitas atau stabilitas; semua tahap perlu diperiksa pada UI Android yang benar-benar terpasang.

BlueStacks dan adb tersedia pada Mac ini. Saat pemeriksaan, `adb devices -l` tidak menemukan perangkat. Android SDK standar belum ditemukan. Karena itu, adapter auto-buy Android **belum diimplementasikan dan belum diuji**. Aplikasi dashboard yang ada masih memakai backend browser; tidak ada perubahan label yang berpura-pura menjadi integrasi Android.

Appium dipasang secara lokal dalam `.tools/appium`, driver disimpan terpisah dalam `.tools/appium-home`, dan klien Python dipasang dalam virtual environment proyek. Dependensi tambahan tercatat dalam `requirements-android.txt`. Instalasi tool tidak menyelesaikan integrasi checkout.

Jalankan `.venv/bin/python -m flashsale.android_doctor` untuk melihat koneksi perangkat, SDK, server Appium, dan driver. Pemeriksaan ini membaca kesiapan, tidak melakukan login, menekan tombol produk, atau membentuk pesanan.

Buka BlueStacks, periksa apakah versinya menyediakan akses Android Debug Bridge, dan hubungkan endpoint lokal yang ditampilkan emulator ke adb. Jangan mengasumsikan port tertentu dan jangan membuka debugging ke jaringan publik. Jika memakai ponsel Android, otorisasi debugging dilakukan langsung oleh pemilik perangkat. Tidak ada upaya menyembunyikan emulator, menonaktifkan pengamanan Shopee, atau melewati verifikasi.

Android SDK yang sah beserta platform-tools/build-tools diperlukan untuk UiAutomator2. Lisensi Android SDK tidak diterima otomatis oleh proyek ini. Sesuaikan ANDROID_HOME dengan direktori SDK yang terpasang; JAVA_HOME tersedia melalui `/usr/libexec/java_home` pada Mac ini.

Server lokal dapat dijalankan dengan `APPIUM_HOME="$PWD/.tools/appium-home" .tools/appium/node_modules/.bin/appium --address 127.0.0.1 --port 4723`. Tidak menggunakan relaxed-security atau fitur insecure.

Setelah semua prasyarat siap, buka Shopee di Android dan jalankan `.venv/bin/python -m flashsale.android_probe --device SERIAL_ADB`. Probe membuat sesi UiAutomator2 dan membaca package aktif, ukuran layar, serta keberadaan hierarchy UI; tidak mencetak isi layar atau membuat pesanan. Appium dapat memasang komponen instrumentasi pengujiannya pada perangkat. Pembuatan sesi harus berhasil sebelum selector Android ditentukan dari halaman asli.
