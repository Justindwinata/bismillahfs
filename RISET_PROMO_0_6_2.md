# Pemeriksaan varian flash sale, 26 Oktober 2026

Target: produk 1367937206/28340353844, kampanye 511589778477216, pukul 12.00 WIB. Batas total pengguna Rp1.000.000.

## Bukti langsung dari sesi pengguna

Halaman kampanye mencantumkan produk Redmi pada sesi 12.00. Harga kartu disamarkan sebagai ?1.000. JSON-LD SaleEvent menggunakan AggregateOffer dengan price bernilai string `p`; identitas model tidak dicantumkan. Nilai aksesibilitas Rp0 tidak boleh dianggap sebagai harga nyata.

Halaman produk menyertakan JSON dalam script `text/mfe-initial-data`. Jalur yang diamati adalah initialState.DOMAIN_PDP.data.PDP_BFF_DATA.cachedMap[shop/item]. Data item memuat 27 model dengan model_id, nama, dan extinfo.tier_index. bottom_banner.flash_sale_preview memuat promotion_id 511589778477216 dan start_time 1792990800. Seluruh promotion_id model bernilai null saat diperiksa. Bukti tersanitasi tersimpan di .local/redmi-catalog-observed.json; data akun tidak disimpan di artefak itu.

## Perubahan

Ekstensi 0.6.2 membaca subtree produk yang cocok dengan shop/item URL, memetakan tier_index ke label varian, serta mengekspor ID model dan preview kampanye. Parser memakai JSON.parse, tidak mengeksekusi script halaman, tidak menyalin cookie atau subtree akun. Laporan membedakan jumlah model yang diketahui dari model yang terikat eksplisit ke kampanye. Tidak ada perubahan yang menganggap model berlabel CAMPAIGN otomatis sebagai target promo.

## Riset eksternal

Implementasi sumber terbuka Shopee SDK memperlihatkan model_id sebagai konfigurasi promo pada API Shop Flash Sale:
https://github.com/congminh1254/shopee-sdk/blob/main/docs/managers/shop-flash-sale.md
Ini API pengelolaan toko, bukan bukti bahwa pembeli dapat membaca konfigurasi kampanye platform milik toko lain.

Daftar endpoint lama ditemukan pada https://gist.github.com/arugaz/1e9fedad55082aaf9e07d9c1ba81e9ef . Daftar tersebut tidak membuktikan endpoint masih berfungsi, respons memuat model promo mendatang, atau cookie pembeli memberikan akses ke data seller. Endpoint itu tidak diintegrasikan berdasarkan asumsi.

## Batas hasil

Penemuan SKU promo belum tercapai. Katalog model dan preview produk tersedia, hubungan model-kampanye serta harga promo belum ditemukan dalam sumber yang diperiksa. Tidak ada pesanan atau pengujian pembelian yang dilakukan pada revisi ini. Pengujian lokal memvalidasi parser dan pembatasan data, bukan membuktikan hasil flash sale.
