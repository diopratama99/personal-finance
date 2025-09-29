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

📄 Lisensi

Tentukan sesuai preferensi (mis. MIT). Tambahkan file LICENSE bila diperlukan.

Butuh bantuan cepat? Buka issue atau kirim “Lanjutan Temanku” (format ringkas task + link repo) biar perbaikan/fitur baru langsung dikerjakan.

You said:
btw klo saya commit nanti web yang dari azure itu otomatis update kan?
ChatGPT said:
Thought for 16s

Iya—kalau kamu sudah pakai GitHub Actions ke Azure (yang OIDC tadi), maka setiap commit ke branch yang dipantau (biasanya main) akan auto build & deploy ke App Service-mu.

Cara cek cepat

Di GitHub → tab Actions: setiap kali push harus muncul workflow “Deploy Temanku…” → sukses (✅).

Di Azure → App Service → Deployment Center: sumber GitHub Actions aktif (jangan ada pipeline lain yang masih nyangkut).

Setelah deploy, Overview → Browse atau buka URL kamu; first load bisa agak lambat di F1 (cold start).

Kalau ternyata tidak auto-update, cek ini:

Branch salah – Pastikan workflow-mu trigger ke branch yang kamu push:

on:
  push: { branches: ["main"] }
  workflow_dispatch:


Job fail – Lihat log di GitHub Actions (module tidak terpasang, app-name salah, dsb).

app-name keliru – Di step azure/webapps-deploy@v2, app-name: harus sama persis dengan nama Web App di Azure.

Pipeline ganda – Jangan aktifkan Oryx/OneDeploy dan Actions bersamaan. Pilih salah satu (rekomendasi: Actions).

Tips praktis

Mau redeploy manual tanpa commit? Di Actions ada tombol “Run workflow” (karena kita pakai workflow_dispatch), atau push empty commit:

git commit --allow-empty -m "redeploy" && git push


DB aman: file kamu di /home/data/finance.db → tidak terhapus saat redeploy/update kode.

Ubah requirements.txt → workflow akan install ulang pip deps secara otomatis.

Kalau kamu kirim link workflow file-mu (.github/workflows/azure-webapp.yml), aku bisa double-check trigger & app-name-nya biar 100% auto-deploy.

You said:
kok tampilan readme nya jelek ya
ChatGPT said:
Thought for 7s

siap—yang tadi kelihatan “gepeng” karena pakai simbol/indentasi yang GitHub nggak render bagus. Ini versi Markdown rapi (GitHub-flavored), tinggal paste sebagai README.md.

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
