Temanku — Personal Finance Web App

Aplikasi web pencatatan keuangan pribadi: catat pemasukan/pengeluaran, kategori & budget, lihat statistik, ekspor laporan ke PDF/Excel, dan impor data. Tampilan minimalis-modern, responsif, dan mendukung dark mode.

✨ Fitur Utama

🔐 Multi-user + login

➕ CRUD transaksi (income/expense), keterangan & metode pembayaran (tunai / e-wallet / transfer)

🏷️ Kategori pemasukan & pengeluaran

📊 Dashboard: ringkasan periode & grafik pengeluaran per kategori

💰 Budget per kategori + progress bar

⬇️ Export laporan ke PDF & Excel

⬆️ Import dari CSV/Excel (menu Import/Export)

🌙 Dark mode (toggle)

📱 UI mobile dengan offcanvas menu & desain glassy

🧰 Teknologi

Backend: Flask (Python 3.11), Flask-Login

DB: SQLite (persisten)

Frontend: Bootstrap 5.3, Jinja2, Chart.js, Google Font (Montserrat)

Laporan/Impor: pandas, openpyxl, ReportLab

Optimasi: Flask-Compress (gzip), WAL mode (SQLite)

📁 Struktur Folder Singkat
app.py
requirements.txt
templates/
  base.html
  dashboard.html
  history.html
  categories.html
  budgets.html
  import_export.html
static/
  style.css
  app.js

🚀 Cara Menjalankan di Lokal
0) Prasyarat

Python 3.11 (disarankan)

Git (opsional, untuk clone)

(Windows) Microsoft C++ Build Tools terkadang dibutuhkan saat install paket tertentu

1) Clone & masuk folder
git clone https://github.com/<username>/<repo>.git
cd <repo>

2) Buat virtual env & aktifkan

Windows (PowerShell)

python -m venv .venv
.venv\Scripts\Activate.ps1


macOS / Linux

python3 -m venv .venv
source .venv/bin/activate

3) Install dependencies
pip install -r requirements.txt


Jika gagal saat export Excel/PDF:

Excel: pip install openpyxl

PDF: pip install reportlab

4) (Opsional) Buat file .env lokal

Buat file .env (tidak wajib; variabel juga bisa di-setup dari shell):

SECRET_KEY=ubah-ke-string-acak
FINANCE_DB_PATH=finance.db


Default DB akan dibuat otomatis. Untuk lokasi persisten lain, isi FINANCE_DB_PATH sesuai keinginan (mis. instance/finance.db).

5) Jalankan aplikasi

Opsi A — Flask

set FLASK_APP=app.py & flask run          # Windows
# atau
export FLASK_APP=app.py && flask run      # macOS/Linux


Opsi B — Python langsung

python app.py


Buka browser: http://127.0.0.1:5000

Daftar user pertama di /register, lalu login.

📦 Import & Export Data

Buka menu 🔁 Import/Export.

Export: pilih rentang tanggal → Export Excel atau Export PDF.

Import: unggah file CSV/Excel (format kolom mengikuti export Excel aplikasi ini).

☁️ Deploy (ringkas)

Azure App Service (Linux F1) untuk testing:

SECRET_KEY dan FINANCE_DB_PATH=/home/data/finance.db di Environment variables

Startup command:

gunicorn --bind=0.0.0.0:8000 app:app


Gunakan GitHub Actions untuk deploy.

Catatan: F1 tidak mendukung custom domain. Untuk custom domain + SSL gratis, scale ke B1.

🛠️ Troubleshooting

1) “ModuleNotFoundError: openpyxl / reportlab”
→ pip install openpyxl reportlab

2) “database is locked” (SQLite)

Pastikan koneksi DB set WAL mode & busy timeout. Di db():

conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")


Tutup app lain yang mengunci file DB.

3) Export Excel/PDF gagal

Pastikan paket terpasang: openpyxl (Excel), reportlab (PDF).

4) Grafik kosong

Pastikan ada data pada periode dipilih.

Pastikan Chart.js dimuat (CDN) & elemen <canvas id="expenseChart"> ada.

Pastikan wrapper .chart-box{height:360px} dan opsi Chart: maintainAspectRatio:false.

5) UI mobile (burger) tidak bisa diklik / menutup sendiri

Pastikan memakai Bootstrap bundle (bukan JS non-bundle).

Jangan panggil Offcanvas.toggle() manual—biarkan data-API Bootstrap yang handle.

🔐 Environment Variables

SECRET_KEY — string acak untuk session Flask (wajib di production)

FINANCE_DB_PATH — path SQLite (contoh: finance.db atau /home/data/finance.db di Azure)

🗺️ Roadmap Singkat (opsional)

FAB + search/filter riwayat + warna/ikon kategori

Tren 12 bulan + alert budget

PWA + recurring transactions

Import wizard (mapping bebas) + attachment struk

Backup otomatis + onboarding mini

🤝 Kontribusi

PR & issue dipersilakan. Saat mengajukan perubahan:

Jelaskan perubahan (UI/DB/route) & alasan

Sertakan screenshot sebelum/sesudah untuk perubahan UI

Jika ubah skema DB, sertakan migrasi idempotent