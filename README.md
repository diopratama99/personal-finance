# Temanku — Personal Finance Web App

Aplikasi web untuk mencatat pemasukan/pengeluaran, kelola kategori dan budget, lihat statistik, serta import/export data. Desain responsif, nyaman dipakai di mobile/iPad/desktop.

---

## Fitur Utama

- Multi-user + login (Flask-Login)
- CRUD transaksi (income/expense), keterangan, dan metode pembayaran (Transfer/Rekening, Tunai, E-Wallet)
- Kategori pemasukan & pengeluaran
- Budget per kategori + progress bar
- Dashboard: ringkasan periode dan grafik pengeluaran per kategori
- Import dari CSV/Excel dan export ke Excel/PDF
- Dark mode sederhana
- Off-canvas menu (burger) yang ramah mobile

### Baru (Oktober 2025)
- Halaman Saldo Akun (`/accounts`):
  - Top Up E-Wallet, Tarik Tunai, dan Top Up Rekening (semua dengan opsi biaya admin)
  - Validasi saldo: mutasi ditolak jika saldo sumber bulan tersebut tidak cukup
  - Riwayat mutasi + tombol hapus (ikut menghapus transaksi biaya admin terkait)
- Layout mobile/iPad:
  - Riwayat menjadi kartu (mobile 1 kolom, iPad 2 kolom)
  - Dashboard mobile menampilkan mini card Goals & Budget berdampingan
  - Grafik dipindah sebelum Ringkasan Periode
- Tabungan: bisa hapus Goal aktif (alokasi kembali ke saldo tabungan)

Lihat ringkasan lengkap di NOTES.md.

---

## Teknologi

- Backend: Flask (Python 3.11), Flask-Login
- Database: SQLite (persisten)
- Frontend: Bootstrap 5.3, Jinja2, Chart.js, Google Font (Montserrat)
- Laporan/Impor: pandas, openpyxl, ReportLab

---

## Struktur Direktori Singkat

```text
.
+- app.py
+- requirements.txt
+- schema.sql
+- templates/
¦  +- base.html
¦  +- dashboard.html
¦  +- history.html
¦  +- accounts.html
¦  +- savings.html
¦  +- ...
+- static/
¦  +- style.css
¦  +- app.js
+- NOTES.md
```

---

## Menjalankan di Lokal

### 0) Prasyarat
- Python 3.11+ (disarankan)
- Git (opsional)

### 1) Clone repo
```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>
```

### 2) Buat & aktifkan virtual env
- Windows (PowerShell)
```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
```
- macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```
Jika perlu (ekspor/impor):
```bash
pip install openpyxl reportlab
```

### 4) (Opsional) Konfigurasi .env
```dotenv
SECRET_KEY=ubah-ke-string-acak
FINANCE_DB_PATH=finance.db
```

### 5) Jalankan
```bash
python app.py
# atau
export FLASK_APP=app.py && flask run
```
Buka http://127.0.0.1:5000. Daftar di `/register`, lalu login.

---

## Import & Export
- Masuk ke menu Import/Export
- Export: pilih periode ? Export Excel / Export PDF
- Import: unggah CSV/Excel (format mengikuti hasil export Excel aplikasi ini)

---

## Deploy Singkat (contoh: Azure App Service)
1. Buat Web App Linux
2. Tambah App Settings:
   - `SECRET_KEY=string_acak`
   - `FINANCE_DB_PATH=/home/data/finance.db` (lokasi persisten)
3. Gunakan GitHub Actions atau deploy manual
4. Startup (jika perlu): `gunicorn --bind=0.0.0.0:8000 app:app`

---

## Troubleshooting
- `ModuleNotFoundError: openpyxl/reportlab` ? `pip install openpyxl reportlab`
- Grafik tidak muncul ? pastikan ada data dalam periode, Chart.js termuat, dan `#expenseChart` berada di wrapper yang punya tinggi (`.chart-box{height:360px}`)
- SQLite `database is locked` ? gunakan `PRAGMA busy_timeout` dan mode WAL (lihat `app.py`)

---

## Roadmap Singkat
- FAB + pencarian/penyaring riwayat + ikon kategori
- Tren 12 bulan + alert budget
- PWA + recurring transactions
- Import wizard (mapping bebas) + attachment struk
- Backup otomatis + onboarding mini

---

## Kontribusi
PR & issue sangat welcome. Untuk perubahan UI, sertakan screenshot sebelum/sesudah. Jika mengubah skema DB, sertakan migrasi idempotent.
