import os, io, sqlite3
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ===== Konfigurasi via ENV (untuk hosting) =====
APP_DB = os.getenv("FINANCE_DB_PATH", os.path.join(os.path.dirname(__file__), "finance.db"))
os.makedirs(os.path.dirname(APP_DB), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")

# ---------- DB ----------
def db():
    conn = sqlite3.connect(APP_DB, timeout=5.0)  # tunggu sampai 5 detik kalau terkunci
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")   # cadangan
    return conn

def init_db():
    with db() as con, open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        con.executescript(f.read())

if not os.path.exists(APP_DB):
    init_db()

# -------- Auth ----------
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]

@login_manager.user_loader
def load_user(user_id):
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return User(row) if row else None

def seed_default_categories(user_id: int):
    defaults = {
        "income": ["Gaji","Bonus","Investasi","Freelance"],
        "expense": ["Makan","Transport","Belanja","Hiburan","Kesehatan","Tagihan","Lainnya"]
    }
    with db() as con:
        for t, names in defaults.items():
            for n in names:
                con.execute("INSERT OR IGNORE INTO categories(user_id,type,name) VALUES (?,?,?)",
                            (user_id, t, n))

# -------- Utilities ----------
def start_end_default():
    today = date.today()
    s = today.replace(day=1)
    e = (s + relativedelta(months=1) - relativedelta(days=1))
    return s.isoformat(), e.isoformat()

def money(x):
    return f"Rp {x:,.0f}".replace(",", ".")
app.jinja_env.filters["money"] = money

# -------- Public: auth pages ----------
@app.get("/register")
def register():
    return render_template("register.html", title="Daftar")

@app.post("/register")
def do_register():
    name  = request.form.get("name")
    email = request.form.get("email")
    password = request.form.get("password")
    if not all([name, email, password]):
        flash("Lengkapi nama, email, dan password.")
        return redirect(url_for("register"))

    # 1) Simpan user di satu koneksi
    try:
        with db() as con:
            cur = con.execute(
                "INSERT INTO users(name,email,password_hash) VALUES (?,?,?)",
                (name.strip(), email.lower().strip(), generate_password_hash(password))
            )
            user_id = cur.lastrowid   # <-- ambil id user baru
    except sqlite3.IntegrityError:
        flash("Email sudah terdaftar.")
        return redirect(url_for("register"))

    # 2) Setelah koneksi di atas komit & tertutup, baru seed kategori (koneksi baru)
    seed_default_categories(user_id)

    flash("Pendaftaran berhasil. Silakan login.")
    return redirect(url_for("login"))


@app.get("/login")
def login():
    return render_template("login.html", title="Masuk")

@app.post("/login")
def do_login():
    email, password = request.form.get("email"), request.form.get("password")
    with db() as con:
        u = con.execute("SELECT * FROM users WHERE email=?", (email.lower().strip(),)).fetchone()
    if not u or not check_password_hash(u["password_hash"], password or ""):
        flash("Email atau password salah.")
        return redirect(url_for("login"))
    login_user(User(u))
    return redirect(url_for("dashboard"))

@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# -------- Main pages ----------
@app.get("/")
@app.get("/dashboard")  
@login_required
def dashboard():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        start, end = start_end_default()

    with db() as con:
        totals = con.execute("""
            SELECT
              SUM(CASE WHEN t.type='income'  THEN t.amount ELSE 0 END) AS income,
              SUM(CASE WHEN t.type='expense' THEN t.amount ELSE 0 END) AS expense
            FROM transactions t
            WHERE t.user_id=? AND t.date BETWEEN ? AND ?
        """, (current_user.id, start, end)).fetchone()

        spend = con.execute("""
            SELECT c.name AS category, c.id AS category_id, SUM(t.amount) AS total
            FROM transactions t
            JOIN categories c ON c.id=t.category_id
            WHERE t.user_id=? AND t.type='expense' AND t.date BETWEEN ? AND ?
            GROUP BY c.id, c.name
            ORDER BY total DESC
        """, (current_user.id, start, end)).fetchall()

        top_payee = con.execute("""
            SELECT COALESCE(source_or_payee,'(Tidak diisi)') AS payee,
                   SUM(amount) AS total, COUNT(*) AS cnt
            FROM transactions
            WHERE user_id=? AND type='expense' AND date BETWEEN ? AND ?
            GROUP BY COALESCE(source_or_payee,'(Tidak diisi)')
            ORDER BY total DESC LIMIT 1
        """, (current_user.id, start, end)).fetchone()

        # budgets (month of start)
        month = start[:7]
        budgets = con.execute("""
            SELECT b.id, c.name AS category, b.amount,
                   COALESCE( (SELECT SUM(amount) FROM transactions
                             WHERE user_id=b.user_id AND type='expense' AND category_id=b.category_id
                               AND substr(date,1,7)=b.month), 0) AS spent
            FROM budgets b
            JOIN categories c ON c.id=b.category_id
            WHERE b.user_id=? AND b.month=?
            ORDER BY c.name
        """, (current_user.id, month)).fetchall()

        latest = con.execute("""
            SELECT t.*, c.name AS category,
            t.source_or_payee AS keterangan,
            t.account AS payment_method
            FROM transactions t
            JOIN categories c ON c.id=t.category_id
            WHERE t.user_id=? AND t.date BETWEEN ? AND ?
            ORDER BY t.date DESC, t.id DESC
            LIMIT 10
        """, (current_user.id, start, end)).fetchall()


    summary = {
        "income": float(totals["income"] or 0),
        "expense": float(totals["expense"] or 0),
    }
    summary["net"] = summary["income"] - summary["expense"]

    return render_template(
        "dashboard.html",
        start=start, end=end, summary=summary,
        spend_by_cat=[dict(r) for r in spend],
        top_payee=dict(top_payee) if top_payee else None,
        budgets=[dict(b) for b in budgets],
        latest=[dict(r) for r in latest]
    )

@app.get("/add")
@login_required
def add_form():
    t = request.args.get("type", "expense")
    with db() as con:
        cats = con.execute(
            "SELECT id, name FROM categories WHERE user_id=? AND type=? ORDER BY name",
            (current_user.id, t)
        ).fetchall()
    return render_template("add.html", default_type=t, categories=cats, title="Tambah Transaksi")

@app.post("/add")
@login_required
def add_submit():
    date_ = request.form.get("date")
    type_ = request.form.get("type")
    category_id = request.form.get("category_id")
    amount = request.form.get("amount")
    keterangan = request.form.get("keterangan")
    payment = request.form.get("payment_method")
    VALID_PAYMENTS = {"Transfer","E-Wallet","Tunai"}
    if payment not in VALID_PAYMENTS: payment = "Tunai"
    notes = request.form.get("notes")

    if not all([date_, type_, category_id, amount]):
        flash("Tanggal, jenis, kategori, dan nominal wajib diisi.")
        return redirect(url_for("add_form", type=type_ or "expense"))

    try:
        amt = float(amount)
        if amt <= 0: raise ValueError
    except:
        flash("Nominal harus angka positif.")
        return redirect(url_for("add_form", type=type_ or "expense"))

    with db() as con:
        con.execute("""
            INSERT INTO transactions(user_id,date,type,category_id,amount,source_or_payee,account,notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (current_user.id, date_, type_, int(category_id), amt, keterangan, payment, notes))
    flash("Transaksi tersimpan.")
    return redirect(url_for("history"))

# ---- CRUD: edit & delete
@app.get("/edit/<int:trx_id>")
@login_required
def edit_form(trx_id):
    with db() as con:
        trx = con.execute("""
            SELECT t.*,
            t.source_or_payee AS keterangan,
            t.account AS payment_method
            FROM transactions t
            WHERE t.id=? AND t.user_id=?
        """, (trx_id, current_user.id)).fetchone()

        if not trx: abort(404)
        cats = con.execute("""
            SELECT id, name FROM categories WHERE user_id=? AND type=? ORDER BY name
        """, (current_user.id, trx["type"])).fetchall()
    return render_template("edit.html", trx=dict(trx), categories=[dict(c) for c in cats], title="Edit Transaksi")

@app.post("/edit/<int:trx_id>")
@login_required
def edit_submit(trx_id):
    date_ = request.form.get("date")
    category_id = int(request.form.get("category_id"))
    amount = float(request.form.get("amount"))
    keterangan = request.form.get("keterangan")
    payment = request.form.get("payment_method")
    VALID_PAYMENTS = {"Transfer","E-Wallet","Tunai"}
    if payment not in VALID_PAYMENTS: payment = "Tunai"
    notes = request.form.get("notes")
    with db() as con:
        con.execute("""
            UPDATE transactions SET date=?, category_id=?, amount=?, source_or_payee=?, account=?, notes=?
             WHERE id=? AND user_id=?
        """, (date_, category_id, amount, keterangan, payment, notes, trx_id, current_user.id))
    flash("Perubahan disimpan.")
    return redirect(url_for("history"))

@app.post("/delete/<int:trx_id>")
@login_required
def delete_trx(trx_id):
    with db() as con:
        con.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (trx_id, current_user.id))
    flash("Transaksi dihapus.")
    return redirect(url_for("history"))

# ---- Riwayat
@app.get("/history")
@login_required
def history():
    q_type = request.args.get("type", "")
    q_cat = request.args.get("category_id", "")
    page = int(request.args.get("page", 1))
    per = 20
    where = ["t.user_id=?"]; params = [current_user.id]
    if q_type in ("income", "expense"):
        where.append("t.type=?"); params.append(q_type)
    if q_cat:
        where.append("t.category_id=?"); params.append(q_cat)
    where_clause = " AND ".join(where)

    with db() as con:
        cats = con.execute("SELECT id, type, name FROM categories WHERE user_id=? ORDER BY type,name",
                           (current_user.id,)).fetchall()
        total = con.execute(f"SELECT COUNT(*) AS n FROM transactions t WHERE {where_clause}", params).fetchone()["n"]
        rows = con.execute(f"""
            SELECT t.*, c.name AS category,
            t.source_or_payee AS keterangan,
            t.account AS payment_method
            FROM transactions t
            JOIN categories c ON c.id=t.category_id
            WHERE {where_clause}
            ORDER BY t.date DESC, t.id DESC
            LIMIT ? OFFSET ?
        """, (*params, per, (page-1)*per)).fetchall()


    pages = (total + per - 1)//per
    return render_template("history.html",
                           rows=[dict(r) for r in rows],
                           categories=[dict(c) for c in cats],
                           q_type=q_type, q_cat=q_cat, page=page, pages=pages, title="Riwayat")

# ---- Categories management
@app.get("/categories")
@login_required
def categories_page():
    with db() as con:
        inc = con.execute("SELECT * FROM categories WHERE user_id=? AND type='income' ORDER BY name",
                          (current_user.id,)).fetchall()
        exp = con.execute("SELECT * FROM categories WHERE user_id=? AND type='expense' ORDER BY name",
                          (current_user.id,)).fetchall()
    return render_template("categories.html", income=[dict(i) for i in inc], expense=[dict(e) for e in exp], title="Kategori")

@app.post("/categories")
@login_required
def categories_add():
    type_ = request.form.get("type")
    name = request.form.get("name","").strip()
    if not name or type_ not in ("income", "expense"):
        flash("Isi nama kategori dengan benar.")
        return redirect(url_for("categories_page"))
    with db() as con:
        try:
            con.execute("INSERT INTO categories(user_id,type,name) VALUES (?,?,?)", (current_user.id, type_, name))
            flash("Kategori ditambahkan.")
        except sqlite3.IntegrityError:
            flash("Kategori sudah ada.")
    return redirect(url_for("categories_page"))

# ---- Budgets
@app.get("/budgets")
@login_required
def budgets_page():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    with db() as con:
        cats = con.execute("SELECT id,name FROM categories WHERE user_id=? AND type='expense' ORDER BY name",
                           (current_user.id,)).fetchall()
        rows = con.execute("""
            SELECT b.id, c.name AS category, b.category_id, b.month, b.amount
            FROM budgets b JOIN categories c ON c.id=b.category_id
            WHERE b.user_id=? AND b.month=?
            ORDER BY c.name
        """, (current_user.id, month)).fetchall()
    return render_template("budgets.html", month=month, categories=[dict(c) for c in cats], rows=[dict(r) for r in rows], title="Budget")

@app.post("/budgets")
@login_required
def budgets_set():
    month = request.form.get("month")
    category_id = int(request.form.get("category_id"))
    amount = float(request.form.get("amount"))
    with db() as con:
        con.execute("""
            INSERT INTO budgets(user_id,category_id,month,amount)
            VALUES (?,?,?,?)
            ON CONFLICT(user_id,category_id,month) DO UPDATE SET amount=excluded.amount
        """, (current_user.id, category_id, month, amount))
    flash("Budget disimpan.")
    return redirect(url_for("budgets_page", month=month))

# ---- Export
@app.get("/export/excel")
@login_required
def export_excel():
    start = request.args.get("start") or start_end_default()[0]
    end = request.args.get("end") or start_end_default()[1]
    with db() as con:
        rows = con.execute("""
            SELECT t.date, t.type, c.name AS category, t.amount, t.source_or_payee, t.account, t.notes
            FROM transactions t JOIN categories c ON c.id=t.category_id
            WHERE t.user_id=? AND t.date BETWEEN ? AND ?
            ORDER BY t.date
        """, (current_user.id, start, end)).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    bio = io.BytesIO()
    df.to_excel(bio, index=False, sheet_name="Laporan"); bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"laporan_{start}_sampai_{end}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/export/pdf")
@login_required
def export_pdf():
    start = request.args.get("start") or start_end_default()[0]
    end = request.args.get("end") or start_end_default()[1]
    # ringkas totals
    with db() as con:
        totals = con.execute("""
           SELECT
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
           FROM transactions WHERE user_id=? AND date BETWEEN ? AND ?
        """, (current_user.id, start, end)).fetchone()
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    w, h = A4
    y = h - 50
    c.setFont("Helvetica-Bold", 16); c.drawString(40, y, "Laporan Keuangan"); y -= 18
    c.setFont("Helvetica", 10); c.drawString(40, y, f"Periode: {start} s.d. {end}   |   Dicetak: {datetime.now():%d/%m/%Y %H:%M}"); y -= 20
    c.setFont("Helvetica-Bold", 12); c.drawString(40, y, f"Pendapatan: {money(totals['inc'] or 0)}"); y -= 16
    c.drawString(40, y, f"Pengeluaran: {money(totals['exp'] or 0)}"); y -= 16
    c.drawString(40, y, f"Saldo Bersih: {money((totals['inc'] or 0)-(totals['exp'] or 0))}"); y -= 24
    c.setFont("Helvetica-Bold", 11); c.drawString(40, y, "Detail Transaksi"); y -= 14
    c.setFont("Helvetica", 9)
    with db() as con:
        rows = con.execute("""
          SELECT date, type, (SELECT name FROM categories WHERE id=t.category_id) AS category,
                 amount, COALESCE(source_or_payee,'') AS payee, COALESCE(account,'') AS acc
          FROM transactions t
          WHERE user_id=? AND date BETWEEN ? AND ? ORDER BY date
        """, (current_user.id, start, end)).fetchall()
    # header
    cols = ["Tanggal","Jenis","Kategori","Nominal","Payee","Akun"]
    xs = [40, 100, 150, 300, 380, 480]
    c.setFont("Helvetica-Bold", 9)
    for x, col in zip(xs, cols): c.drawString(x, y, col)
    y -= 12; c.setFont("Helvetica", 9)
    for r in rows:
        if y < 60: c.showPage(); y = h-40; c.setFont("Helvetica",9)
        c.drawString(xs[0], y, r["date"])
        c.drawString(xs[1], y, r["type"])
        c.drawString(xs[2], y, r["category"])
        c.drawRightString(xs[3], y, money(r["amount"]))
        c.drawString(xs[4], y, r["payee"][:24])
        c.drawString(xs[5], y, r["acc"][:18])
        y -= 12
    c.showPage(); c.save(); bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=f"laporan_{start}_{end}.pdf", mimetype="application/pdf")

# ---- API kecil
@app.get("/api/categories")
@login_required
def api_categories():
    t = request.args.get("type","expense")
    with db() as con:
        rows = con.execute("SELECT id, name FROM categories WHERE user_id=? AND type=? ORDER BY name",
                           (current_user.id, t)).fetchall()
    return jsonify([dict(r) for r in rows])

# format standar internal (target setelah normalisasi)
CSV_COLUMNS = ["date","type","amount","category","source_or_payee","account","notes"]

# alias dari file export → kolom internal
COLUMN_ALIASES = {
    "keterangan": "source_or_payee",
    "payment_method": "account"
}
@app.get("/template.csv")
@login_required
def template_csv():
    sample = pd.DataFrame([
        {"date":"2025-01-25","type":"income","amount":8500000,"category":"Gaji","source_or_payee":"PT Maju","account":"BCA","notes":"Gaji bulanan"},
        {"date":"2025-01-27","type":"expense","amount":45000,"category":"Makan","source_or_payee":"Warung","account":"Tunai","notes":"Nasi Padang"},
    ], columns=CSV_COLUMNS)
    buf = io.StringIO(); sample.to_csv(buf, index=False); buf.seek(0)
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8")),
                     mimetype="text/csv", as_attachment=True, download_name="template_transaksi.csv")

@app.post("/upload")
@login_required
def upload_csv():
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("Pilih file terlebih dahulu (.csv / .xlsx).")
        return redirect(url_for("dashboard"))

    ext = os.path.splitext(f.filename)[1].lower()
    try:
        if ext in [".xlsx", ".xls"]:
            df = pd.read_excel(f)
        elif ext == ".csv":
            df = pd.read_csv(f)
        else:
            flash("Format tidak didukung. Gunakan .csv atau .xlsx")
            return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"Gagal membaca file: {e}")
        return redirect(url_for("dashboard"))

    # normalisasi nama kolom → huruf kecil
    df.columns = [c.strip().lower() for c in df.columns]

    # mapping alias (export: keterangan/payment_method) → internal
    for src, dst in COLUMN_ALIASES.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]

    # isi kolom yang belum ada (opsional) agar sesuai target internal
    if "notes" not in df.columns: df["notes"] = ""
    if "source_or_payee" not in df.columns: df["source_or_payee"] = ""
    if "account" not in df.columns: df["account"] = ""

    required = ["date","type","amount","category"]
    missing_req = [c for c in required if c not in df.columns]
    if missing_req:
        flash(f"Kolom wajib hilang: {', '.join(missing_req)}")
        return redirect(url_for("dashboard"))

    # hanya ambil kolom target (yang pasti ada)
    keep = [c for c in CSV_COLUMNS if c in df.columns]
    df = df[keep].copy()

    # validasi & normalisasi nilai
    try:
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
        df["type"] = df["type"].str.lower().str.strip()
        if not set(df["type"].dropna().unique()).issubset({"income","expense"}):
            raise ValueError("Kolom 'type' harus 'income' atau 'expense'.")

        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if df["amount"].isna().any():
            raise ValueError("Beberapa 'amount' tidak valid.")
        df["category"] = df["category"].fillna("Lainnya").astype(str)
        df["source_or_payee"] = df.get("source_or_payee", "").fillna("").astype(str)
        df["account"] = df.get("account", "").fillna("").astype(str)
        df["notes"] = df.get("notes", "").fillna("").astype(str)
    except Exception as e:
        flash(f"Validasi data gagal: {e}")
        return redirect(url_for("dashboard"))

    # tulis ke DB
    with db() as con:
        # pastikan kategori ada
        for _, r in df.iterrows():
            con.execute("""
              INSERT OR IGNORE INTO categories(user_id,type,name) VALUES (?,?,?)
            """, (current_user.id, r["type"], r["category"]))
        con.commit()

        # masukkan transaksi
        for _, r in df.iterrows():
            cat_id = con.execute("""
              SELECT id FROM categories WHERE user_id=? AND type=? AND name=?
            """, (current_user.id, r["type"], r["category"])).fetchone()["id"]
            con.execute("""
              INSERT INTO transactions(user_id,date,type,category_id,amount,source_or_payee,account,notes)
              VALUES (?,?,?,?,?,?,?,?)
            """, (current_user.id, r["date"], r["type"], cat_id,
                  float(r["amount"]), r["source_or_payee"], r["account"], r["notes"]))

    flash(f"Impor {len(df)} baris berhasil.")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
