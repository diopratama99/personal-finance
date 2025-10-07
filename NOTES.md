Temanku — Catatan Perubahan & Catatan Dev (Oktober 2025)

Halo! Ini catatan singkat agar yang nge‑clone repo ini paham apa saja yang berubah dan kenapa dibuat begitu. Bahasa santai saja biar enak dibaca.

Apa yang baru
- Saldo Akun: halaman khusus untuk mengelola saldo per metode (Rekening/Transfer, Tunai, E‑Wallet) — route: `/accounts`.
  - Top Up E‑Wallet, Tarik Tunai, dan Top Up Rekening.
  - Opsi biaya admin (opsional). Kalau diisi, otomatis tercatat sebagai transaksi Pengeluaran kategori “Biaya Admin”.
  - Validasi saldo: mutasi akan ditolak kalau saldo sumber tidak cukup (ikut memperhitungkan biaya admin) untuk bulan yang sedang dilihat.
  - Riwayat mutasi + tombol Hapus. Menghapus mutasi otomatis menghapus transaksi biaya admin terkait (kalau ada) dan saldo kembali.

- Dashboard (mobile):
  - Kartu mini “Goals Aktif” dan “Budget Oktober” ditampilkan berdampingan (2 kolom), isi ringkas + progress bar lebih tebal.
  - Ringkasan Periode disederhanakan jadi 2 angka: Pendapatan (hijau) dan Pengeluaran (merah). Saldo disembunyikan.
  - Grafik Pengeluaran dipindah ke atas Ringkasan sesuai urutan yang lebih enak dibaca.

- Riwayat (mobile & iPad):
  - Mode “kartu” untuk mobile (1 kolom) dan iPad (2 kolom). Di iPad tampil ringkas: Tanggal, Jenis, Kategori, Nominal. Tombol Detail tetap ada.

- Tabungan:
  - Bisa hapus Goal aktif. Kalau dihapus saat masih aktif, dana alokasi dikembalikan ke saldo tabungan (pot) — tidak dianggap “terpakai”. Kalau goal sudah diarsipkan, perilaku lama tetap: dana dianggap terpakai permanen.

- Offcanvas (burger menu):
  - Lebar menyesuaikan perangkat. Mobile pakai 75% lebar layar (bisa diubah di CSS).
  - Opacity panel 50% dan warna hijau mengikuti warna navbar.
  - Tombol “Logout” dibuat merah semi‑transparan dengan teks putih.
  - Greeting sederhana di bagian atas: “Halo, (Nama User) — Semangat cari uangnya ya!”.

Perubahan teknis (ringkas)
- DB: tabel baru `account_transfers` + kolom `fee_transaction_id` untuk mengaitkan biaya admin dengan mutasi (dipakai saat delete).
- Helper `account_balances_month(user_id, ym)` untuk hitung saldo bulanan per metode.
- Filter Jinja baru `month_name_indo` (ambil nama bulan dari `YYYY-MM`).
- Beberapa CSS dirapikan: konsolidasi rules chips, layout kartu mobile/iPad, offcanvas width, progress bar, dan spacing.

Catatan gaya & rapih‑rapih
- Beberapa rules CSS lama yang dobel/kurang terpakai sudah dibersihkan (mis. definisi chips yang ganda). Sisanya sengaja dibiarkan minimal agar tidak mengganggu layout lain yang belum disentuh.
- Nama class yang ditambah:
  - `table-stacked stack-compact` → untuk mode kartu 2 kolom di iPad (menyembunyikan kolom non-esensial).
  - `greet-box`/`greet-title` → styling sapaan di menu.
  - Mini card di dashboard mobile tetap memanfaatkan komponen dan warna yang sudah ada (minim CSS baru).

Cara jalanin lokal
1) Python 3.10+ dan pip siap.
2) `pip install -r requirements.txt`
3) `python app.py`
4) Buka `http://127.0.0.1:5000`

Catatan Dev
- Perhitungan saldo akun memakai data transaksi + mutasi internal. Karena saldo yang ditampilkan bersifat per‑bulan (filter di halaman akun), validasi “saldo cukup” juga mengikuti bulan yang dipilih.
- Deskripsi biaya admin sengaja dibedakan: “Top Up E‑Wallet”, “Tarik Tunai”, “Top Up Rekening” supaya mudah dilacak di Riwayat.
- Tampilan mobile/iPad mengandalkan CSS grid + media queries. Kalau ada komponen yang masih “jeda” atau kurang fit, tinggal atur `--bs-gutter-x`/`--bs-gutter-y` atau padding container.

Ide lanjutan (kalau sempat)
- Transfer bebas antar akun dengan dropdown sumber/tujuan dalam satu form.
- Export PDF/Excel yang sudah include breakdown per metode pembayaran.
- Dark mode yang lebih komprehensif untuk semua komponen baru.

Kalau ada bagian yang kurang sreg, feel free untuk tweak—struktur templating-nya mudah diikuti kok. Happy hacking!

