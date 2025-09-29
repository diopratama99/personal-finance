# Temanku — Personal Finance Web App

Aplikasi web pencatatan keuangan pribadi: catat pemasukan/pengeluaran, kelola kategori & budget, lihat statistik, serta **import/export** data. Desain **minimalis–modern**, responsif, dan mendukung **dark mode**.

---

## ✨ Fitur

- 🔐 Multi-user + login (Flask-Login)  
- ➕ CRUD transaksi (income/expense), keterangan & metode pembayaran (tunai / e-wallet / transfer)  
- 🏷️ Kategori pemasukan & pengeluaran  
- 💰 Budget per kategori + progress bar  
- 📊 Dashboard: ringkasan periode & grafik pengeluaran per kategori  
- ⬇️ Export laporan ke **Excel** & **PDF**  
- ⬆️ Import dari **CSV/Excel** (menu **Import/Export**)  
- 🌙 Dark mode toggle  
- 📱 UI mobile dengan off-canvas menu & gaya glass

---

## 🧰 Teknologi

- **Backend:** Flask (Python 3.11), Flask-Login  
- **Database:** SQLite (persisten)  
- **Frontend:** Bootstrap 5.3, Jinja2, Chart.js, Google Font (Montserrat)  
- **Laporan & impor:** pandas, openpyxl, ReportLab  
- **Optimasi:** Flask-Compress (gzip), SQLite WAL mode

---

## 📂 Struktur Direktori Singkat



app.py
requirements.txt
schema.sql
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


---

## 🚀 Menjalankan di Lokal

### 0) Prasyarat
- **Python 3.11** (disarankan)
- Git (opsional, untuk clone)
- (Windows) Microsoft C++ Build Tools kadang diperlukan untuk beberapa paket

### 1) Clone repo
```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>

2) Buat & aktifkan virtual environment

Windows (PowerShell)

python -m venv .venv
. .venv\Scripts\Activate.ps1


macOS / Linux

python3 -m venv .venv
source .venv/bin/activate

3) Install dependencies
pip install -r requirements.txt


Jika perlu:

pip install openpyxl reportlab

4) (Opsional) File .env

Buat file .env di root (atau set dari shell):

SECRET_KEY=ubah-ke-string-acak
FINANCE_DB_PATH=finance.db

5) Jalankan aplikasi

Opsi A – Flask

# Windows
set FLASK_APP=app.py & flask run
# macOS/Linux
export FLASK_APP=app.py && flask run


Opsi B – Python

python app.py


Buka: http://127.0.0.1:5000

Daftar akun di /register, lalu login.

🔁 Import & Export

Buka menu 🔁 Import/Export.

Export: pilih rentang tanggal → Export Excel / Export PDF.

Import: unggah CSV/Excel (format kolom mengikuti hasil export Excel aplikasi ini).

☁️ Deploy Singkat (Azure App Service)

Buat Web App Linux (F1 untuk testing).

Set Configuration → Application settings:

SECRET_KEY = string acak

FINANCE_DB_PATH = /home/data/finance.db (lokasi persisten)

Gunakan GitHub Actions (Deployment Center) untuk auto-deploy.

Startup command (jika perlu):

gunicorn --bind=0.0.0.0:8000 app:app


Catatan: F1 punya cold start & tidak mendukung custom domain. Untuk custom domain, scale ke B1.

🧪 Troubleshooting

ModuleNotFoundError: openpyxl/reportlab
Jalankan pip install openpyxl reportlab.

database is locked (SQLite)
Pastikan koneksi mengaktifkan:

conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")


Grafik tidak muncul
Cek ada data pada periode, Chart.js ter-load, dan elemen <canvas id="expenseChart"> ada.
Di CSS, pastikan wrapper grafik memiliki tinggi (mis. .chart-box{height:360px}) dan opsi Chart maintainAspectRatio:false.

🗺️ Roadmap Singkat

FAB + search/filter riwayat + warna/ikon kategori

Tren 12 bulan + alert budget

PWA + recurring transactions

Import wizard (mapping bebas) + attachment struk

Backup otomatis + onboarding mini

🤝 Kontribusi

PR & issue dipersilakan.
Untuk perubahan UI, sertakan screenshot sebelum/sesudah.
Jika mengubah skema DB, sertakan migrasi idempotent.

