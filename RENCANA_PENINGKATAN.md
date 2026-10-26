# Baseline dan pengembangan terpisah

Branch main dan tag v0.6.5-stable mempertahankan backend yang disetujui pengguna. Branch feat/gui-refresh hanya memperbarui presentasi dashboard: navigasi antartahap, jam WIB, hierarki visual, warna tombol, scrollbar, dan placeholder log. Tidak mengubah selector, jadwal, retry, batas harga, atau pengiriman pesanan.

## Temuan riset, 26 Oktober 2026

Dokumentasi Playwright menjelaskan auto-waiting berdasarkan visibility, stability, menerima event, dan enabled. Mengurangi waktu tunggu tetap dapat dilakukan hanya setelah bukti kesiapan tersedia. Bridge ekstensi aplikasi ini bukan Playwright penuh; fitur auto-wait Playwright tidak otomatis berlaku pada bridge. Pengoptimalan selanjutnya perlu mengukur waktu setiap RPC, navigasi, dan kesiapan DOM sebelum mengganti polling.

Sumber: https://playwright.dev/python/docs/actionability

Chrome menerapkan throttling timer pada tab latar belakang. Karena itu waktu respons tab tersembunyi perlu dibandingkan dengan tab aktif dalam pengujian; memperkecil interval saja tidak membuktikan waktu checkout membaik. Jam UI adalah jam komputer, bukan jam server Shopee.

Sumber: https://developer.chrome.com/blog/background_tabs/

Dokumentasi Cloudflare menjelaskan challenge sebagai pemeriksaan klien yang diputuskan layanan, dan menyediakan test keys untuk pengujian pada situs sendiri. Test keys tidak dapat dipakai untuk meniadakan CAPTCHA pada Shopee. Sumber ini menjelaskan prinsip challenge, bukan bukti bahwa Shopee menggunakan Turnstile. Memblokir script CAPTCHA tidak membuktikan server menerima pesanan dan dapat membuat verifikasi gagal.

Sumber: https://developers.cloudflare.com/turnstile/ dan https://developers.cloudflare.com/turnstile/troubleshooting/testing/

## Pengembangan berikutnya yang dapat diuji

Ukur p50/p95 waktu persiapan, perubahan harga, submit, dan konfirmasi secara terpisah. Pertahankan pengiriman tunggal saat hasil pesanan ambigu. Pengujian CAPTCHA lokal harus meliputi challenge muncul/hilang, pembatalan, navigasi, dan pemulihan konfigurasi setelah pengguna menyelesaikannya. Jangan mengklaim hasil fixture sebagai hasil flash sale nyata atau menjanjikan bot kebal pembatasan. Perubahan backend tersebut belum diterapkan agar baseline tetap sama; pratinjau ini hanya mengubah GUI.
