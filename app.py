import os, io, sqlite3
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import datetime as dt


# =============================================================================
# Configuration
# =============================================================================

# Lokasi DB bisa dioverride via ENV (untuk deployment)
APP_DB = os.getenv("FINANCE_DB_PATH", os.path.join(os.path.dirname(__file__), "finance.db"))
os.makedirs(os.path.dirname(APP_DB), exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")


# =============================================================================
# Database helpers
# =============================================================================

def db():
    """Return sqlite3 connection with Row factory & timeout sane defaults."""
    conn = sqlite3.connect(APP_DB, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn

def init_db():
    """Initialize database schema from schema.sql if DB not exists."""
    with db() as con, open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8") as f:
        con.executescript(f.read())

if not os.path.exists(APP_DB):
    init_db()

# === Favorites bootstrap (tabel ringan untuk template transaksi) ===
def ensure_favorites_table():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                type TEXT NOT NULL CHECK(type IN ('income','expense')),
                category_id INTEGER NOT NULL,
                amount REAL,
                account TEXT,
                source_or_payee TEXT,
                notes TEXT,
                UNIQUE(user_id, name)
            )
        """)

# panggil saat startup
ensure_favorites_table()

# === Savings bootstrap (tabel untuk Tab Tabungan) ===
def ensure_savings_tables():
    with db() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_auto_transfers(
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                amount REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, month),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_goals(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                target_amount REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                achieved_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_allocations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                goal_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                date TEXT NOT NULL,
                note TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (goal_id) REFERENCES savings_goals(id)
            )
            """
        )

        # Pastikan kolom archived_at ada pada savings_goals (untuk arsip)
        try:
            cols = con.execute("PRAGMA table_info(savings_goals)").fetchall()
            col_names = {c[1] for c in cols}
            if "archived_at" not in col_names:
                con.execute("ALTER TABLE savings_goals ADD COLUMN archived_at TEXT")
        except Exception:
            pass

        # Tabel top-up manual
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_manual_topups(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Tambahkan kolom transaction_id jika belum ada (link ke tabel transactions)
        try:
            cols = con.execute("PRAGMA table_info(savings_manual_topups)").fetchall()
            col_names = {c[1] for c in cols}
            if "transaction_id" not in col_names:
                con.execute("ALTER TABLE savings_manual_topups ADD COLUMN transaction_id INTEGER")
        except Exception:
            pass

        # Tabel konsumsi tabungan permanen
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS savings_consumed(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

ensure_savings_tables()

# Pastikan kolom emoji pada categories ada (untuk ikon kategori)
def ensure_categories_emoji_column():
    with db() as con:
        try:
            cols = con.execute("PRAGMA table_info(categories)").fetchall()
            col_names = {c[1] for c in cols}
            if "emoji" not in col_names:
                con.execute("ALTER TABLE categories ADD COLUMN emoji TEXT")
        except Exception:
            pass

ensure_categories_emoji_column()

# Isi emoji default untuk kategori bawaan jika belum ada
DEFAULT_EMOJI = {
    ("income", "Gaji"): "💼",
    ("income", "Bonus"): "🎁",
    ("income", "Investasi"): "📈",
    ("income", "Freelance"): "🧑‍💻",
    ("expense", "Makan"): "🍽️",
    ("expense", "Transport"): "🚗",
    ("expense", "Belanja"): "🛍️",
    ("expense", "Hiburan"): "🎬",
    ("expense", "Kesehatan"): "🩺",
    ("expense", "Tagihan"): "🧾",
    ("expense", "Lainnya"): "✨",
}

def backfill_default_category_emojis():
    with db() as con:
        for (t, name), emo in DEFAULT_EMOJI.items():
            con.execute(
                "UPDATE categories SET emoji=? WHERE type=? AND name=? AND (emoji IS NULL OR emoji='')",
                (emo, t, name)
            )

backfill_default_category_emojis()

# =============================================================================
# Auth setup
# =============================================================================

login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(UserMixin):
    def __init__(self, row: sqlite3.Row):
        self.id = row["id"]
        self.name = row["name"]
        self.email = row["email"]

@login_manager.user_loader
def load_user(user_id):
    with db() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        return User(row) if row else None

def seed_default_categories(user_id: int):
    """Seed kategori default untuk user baru (idempotent)."""
    defaults = {
        "income":  ["Gaji", "Bonus", "Investasi", "Freelance"],
        "expense": ["Makan", "Transport", "Belanja", "Hiburan", "Kesehatan", "Tagihan", "Lainnya"],
    }
    with db() as con:
        for t, names in defaults.items():
            for n in names:
                con.execute(
                    "INSERT OR IGNORE INTO categories(user_id,type,name,emoji) VALUES (?,?,?,?)",
                    (user_id, t, n, DEFAULT_EMOJI.get((t, n)))
                )
                # update emoji jika baris sudah ada namun emoji kosong
                con.execute(
                    "UPDATE categories SET emoji=? WHERE user_id=? AND type=? AND name=? AND (emoji IS NULL OR emoji='')",
                    (DEFAULT_EMOJI.get((t, n)), user_id, t, n)
                )


# =============================================================================
# Utilities & constants
# =============================================================================

def start_end_default():
    """Return (start_iso, end_iso) for current month."""
    today = date.today()
    s = today.replace(day=1)
    e = (s + relativedelta(months=1) - relativedelta(days=1))
    return s.isoformat(), e.isoformat()

def money(x):
    """Format angka sebagai Rupiah sederhana (tanpa symbol lokal)."""
    return f"Rp {x:,.0f}".replace(",", ".")
app.jinja_env.filters["money"] = money

# Format "YYYY-MM" menjadi "NamaBulan YYYY" (Indonesia)
_MONTHS_ID = [
    None,
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

def month_indo(ym: str) -> str:
    try:
        if not ym or len(ym) < 7 or "-" not in ym:
            return ym
        y, m = ym.split("-")[:2]
        mi = int(m)
        name = _MONTHS_ID[mi] if 1 <= mi <= 12 else m
        return f"{name} {y}"
    except Exception:
        return ym

app.jinja_env.filters["month_indo"] = month_indo

# Label jenis transaksi dalam Bahasa Indonesia
def type_label(val: str) -> str:
    if val == 'income':
        return 'Pemasukan'
    if val == 'expense':
        return 'Pengeluaran'
    return val or ''

app.jinja_env.filters["type_label"] = type_label

VALID_PAYMENTS = {"Transfer", "E-Wallet", "Tunai"}

def valid_iso_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except Exception:
        return False

def normalize_date_range(start: str | None, end: str | None):
    """Jika kosong/invalid, fallback ke default bulan berjalan. Pastikan start <= end."""
    s_def, e_def = start_end_default()
    s = start if start and valid_iso_date(start) else s_def
    e = end   if end   and valid_iso_date(end)   else e_def
    if s > e:
        s, e = e, s
    return s, e


# =============================================================================
# Public: auth pages
# =============================================================================

@app.get("/register")
def register():
    return render_template("register.html", title="Daftar")

@app.post("/register")
def do_register():
    name  = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if not all([name, email, password]):
        flash("Lengkapi nama, email, dan password.")
        return redirect(url_for("register"))

    try:
        with db() as con:
            cur = con.execute(
                "INSERT INTO users(name,email,password_hash) VALUES (?,?,?)",
                (name, email, generate_password_hash(password))
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        flash("Email sudah terdaftar.")
        return redirect(url_for("register"))

    seed_default_categories(user_id)
    flash("Pendaftaran berhasil. Silakan login.")
    return redirect(url_for("login"))

@app.get("/login")
def login():
    return render_template("login.html", title="Masuk")

@app.post("/login")
def do_login():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    with db() as con:
        u = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not u or not check_password_hash(u["password_hash"], password):
        flash("Email atau password salah.")
        return redirect(url_for("login"))
    login_user(User(u))
    return redirect(url_for("dashboard"))

@app.get("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# =============================================================================
# Main pages
# =============================================================================

@app.get("/")
@app.get("/dashboard")
@login_required
def dashboard():
    # range tanggal aman
    start, end = normalize_date_range(request.args.get("start"), request.args.get("end"))

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

        # budgets (berdasarkan bulan dari start)
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

        # latest transaksi (LEFT JOIN agar tanpa kategori tetap tampil)
        latest = con.execute("""
            SELECT t.*,
                   COALESCE(c.name, '-') AS category,
                   c.emoji AS category_emoji,
                   t.source_or_payee AS keterangan,
                   t.account AS payment_method
            FROM transactions t
            LEFT JOIN categories c ON c.id=t.category_id
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
        latest=[dict(r) for r in latest],
    )


# =============================================================================
# Import/Export page (UI)
# =============================================================================

@app.get("/import-export")
@login_required
def import_export():
    # default range: bulan berjalan
    today = date.today()
    start_default = today.replace(day=1).isoformat()
    end_default = today.isoformat()
    start = request.args.get("start", start_default)
    end = request.args.get("end", end_default)
    return render_template("import_export.html", title="Import & Export", start=start, end=end)


# =============================================================================
# CRUD Transaksi
# =============================================================================

@app.get("/add")
@login_required
def add_form():
    # tidak ada default; kalau ada ?type=income|expense tetap didukung
    t_raw = (request.args.get("type") or "").strip().lower()
    t = t_raw if t_raw in ("income", "expense") else None

    with db() as con:
        if t:
            cats = con.execute(
                "SELECT id, name FROM categories WHERE user_id=? AND type=? ORDER BY name",
                (current_user.id, t)
            ).fetchall()
        else:
            cats = []

        favs = con.execute("""
            SELECT f.id, f.name, f.type, f.category_id, COALESCE(c.name,'-') AS category,
                   f.amount, f.account, f.source_or_payee, f.notes
            FROM favorites f
            LEFT JOIN categories c ON c.id=f.category_id
            WHERE f.user_id=?
            ORDER BY f.type, f.name
        """, (current_user.id,)).fetchall()

    return render_template(
        "add.html",
        default_type=t or "",
        categories=cats,
        favorites=[dict(x) for x in favs],
        title="Tambah Transaksi"
    )

@app.post("/add")
@login_required
def add_submit():
    date_ = request.form.get("date")
    type_ = request.form.get("type")
    category_id = request.form.get("category_id")
    amount = request.form.get("amount")
    keterangan = request.form.get("keterangan")
    payment = request.form.get("payment_method")
    notes = request.form.get("notes")

    # wajib isi
    if not all([date_, type_, category_id, amount]):
        flash("Tanggal, jenis, kategori, dan nominal wajib diisi.")
        return redirect(url_for("add_form", type=type_ or "expense"))
    
    # metode pembayaran wajib & harus valid
    if payment not in VALID_PAYMENTS:
        flash("Pilih metode pembayaran terlebih dahulu.")
        return redirect(url_for("add_form", type=type_ or "expense"))

    # validasi ringan
    if type_ not in ("income", "expense"):
        flash("Jenis transaksi tidak valid.")
        return redirect(url_for("add_form", type="expense"))
    if not valid_iso_date(date_):
        flash("Tanggal tidak valid (format YYYY-MM-DD).")
        return redirect(url_for("add_form", type=type_))

    # tidak boleh di masa depan
    today_iso = date.today().isoformat()
    if date_ > today_iso:
        flash("Tanggal tidak boleh di masa depan.")
        return redirect(url_for("add_form", type=type_))

    try:
        cat_id_int = int(category_id)
    except:
        flash("Kategori tidak valid.")
        return redirect(url_for("add_form", type=type_))

    try:
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except:
        flash("Nominal harus angka positif.")
        return redirect(url_for("add_form", type=type_))

    # pastikan kategori milik user & sesuai type
    with db() as con:
        cat = con.execute(
            "SELECT 1 FROM categories WHERE id=? AND user_id=? AND type=?",
            (cat_id_int, current_user.id, type_),
        ).fetchone()
        if not cat:
            flash("Kategori tidak ditemukan / tidak sesuai jenis.")
            return redirect(url_for("add_form", type=type_))

        con.execute("""
            INSERT INTO transactions(user_id,date,type,category_id,amount,source_or_payee,account,notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (current_user.id, date_, type_, cat_id_int, amt, keterangan, payment, notes))

    flash("Transaksi tersimpan.")
    return redirect(url_for("history"))

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
        if not trx:
            abort(404)
        cats = con.execute("""
            SELECT id, name FROM categories WHERE user_id=? AND type=? ORDER BY name
        """, (current_user.id, trx["type"])).fetchall()
    return render_template("edit.html", trx=dict(trx), categories=[dict(c) for c in cats], title="Edit Transaksi")

@app.post("/edit/<int:trx_id>")
@login_required
def edit_submit(trx_id):
    date_ = request.form.get("date")
    category_id = request.form.get("category_id")
    amount = request.form.get("amount")
    keterangan = request.form.get("keterangan")
    payment = request.form.get("payment_method")
    notes = request.form.get("notes")

    # metode pembayaran wajib valid
    if payment not in VALID_PAYMENTS:
        flash("Pilih metode pembayaran terlebih dahulu.")
        return redirect(url_for("edit_form", trx_id=trx_id))
    
    # validasi ringan
    if not valid_iso_date(date_):
        flash("Tanggal tidak valid (format YYYY-MM-DD).")
        return redirect(url_for("edit_form", trx_id=trx_id))

    # tidak boleh di masa depan
    today_iso = date.today().isoformat()
    if date_ > today_iso:
        flash("Tanggal tidak boleh di masa depan.")
        return redirect(url_for("edit_form", trx_id=trx_id))

    try:
        cat_id_int = int(category_id)
    except:
        flash("Kategori tidak valid.")
        return redirect(url_for("edit_form", trx_id=trx_id))

    try:
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except:
        flash("Nominal harus angka positif.")
        return redirect(url_for("edit_form", trx_id=trx_id))

    with db() as con:
        # pastikan transaksi milik user
        tx = con.execute("SELECT * FROM transactions WHERE id=? AND user_id=?", (trx_id, current_user.id)).fetchone()
        if not tx:
            abort(404)

        # pastikan kategori milik user
        cat = con.execute(
            "SELECT 1 FROM categories WHERE id=? AND user_id=?",
            (cat_id_int, current_user.id)
        ).fetchone()
        if not cat:
            flash("Kategori tidak ditemukan.")
            return redirect(url_for("edit_form", trx_id=trx_id))

        con.execute("""
            UPDATE transactions
               SET date=?, category_id=?, amount=?, source_or_payee=?, account=?, notes=?
             WHERE id=? AND user_id=?
        """, (date_, cat_id_int, amt, keterangan, payment, notes, trx_id, current_user.id))

    flash("Perubahan disimpan.")
    return redirect(url_for("history"))

@app.post("/delete/<int:trx_id>")
@login_required
def delete_trx(trx_id):
    with db() as con:
        cur = con.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (trx_id, current_user.id))
    if getattr(cur, "rowcount", 0):
        flash("Transaksi dihapus.")
    else:
        flash("Transaksi tidak ditemukan.", "warning")
    return redirect(url_for("history"))


# =============================================================================
# Riwayat
# =============================================================================

@app.get("/history")
@login_required
def history():
    q_type = (request.args.get("type") or "").strip()
    q_cat  = (request.args.get("category_id") or "").strip()
    # --- SORTING ---
    # ambil raw tanpa default; biarkan kosong jika tidak ada
    q_sort_raw = (request.args.get("sort") or "").strip()

    order_map = {
        "date_desc":        "t.date DESC, t.id DESC",
        "date_asc":         "t.date ASC, t.id ASC",
        "amount_desc":      "t.amount DESC, t.id DESC",
        "amount_asc":       "t.amount ASC, t.id ASC",
        "category_asc":     "c.name ASC, t.date DESC, t.id DESC",
        "category_desc":    "c.name DESC, t.date DESC, t.id DESC",
        "payment_asc":      "t.account ASC, t.date DESC, t.id DESC",
        "payment_desc":     "t.account DESC, t.date DESC, t.id DESC",
        "type_income_first":  "CASE WHEN t.type='income' THEN 0 ELSE 1 END, t.date DESC, t.id DESC",
        "type_expense_first": "CASE WHEN t.type='expense' THEN 0 ELSE 1 END, t.date DESC, t.id DESC",
    }

    # q_sort untuk template: validasi whitelist; kalau invalid/kosong -> ""
    q_sort = q_sort_raw if q_sort_raw in order_map else ""

    # ORDER BY untuk query: kalau q_sort kosong -> pakai default date_desc
    order_sql = order_map.get(q_sort or "date_desc")

    if q_type not in ("income", "expense"):
        q_type = ""
    if q_cat and not str(q_cat).isdigit():
        q_cat = ""

    # paging
    per = 20
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    page = max(1, page)

    where = ["t.user_id=?"]
    params = [current_user.id]
    if q_type:
        where.append("t.type=?"); params.append(q_type)
    if q_cat:
        where.append("t.category_id=?"); params.append(int(q_cat))
    where_clause = " AND ".join(where)

    with db() as con:
        total = con.execute(
            f"SELECT COUNT(*) AS n FROM transactions t WHERE {where_clause}",
            params
        ).fetchone()["n"]

    pages = max(1, (total + per - 1) // per)
    if page > pages:
        page = pages
    offset = (page - 1) * per

    with db() as con:
        cats = con.execute(
            "SELECT id, type, name FROM categories WHERE user_id=? ORDER BY type, name",
            (current_user.id,)
        ).fetchall()

        rows = con.execute(
            f"""
            SELECT
                t.*,
                COALESCE(c.name, '-') AS category,
                c.emoji AS category_emoji,
                t.source_or_payee AS keterangan,
                t.account AS payment_method
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE {where_clause}
            ORDER BY {order_sql}
            LIMIT ? OFFSET ?
            """,
            (*params, per, offset)
        ).fetchall()

    return render_template(
        "history.html",
        rows=[dict(r) for r in rows],
        categories=[dict(c) for c in cats],
        q_type=q_type,
        q_cat=q_cat,
        q_sort=q_sort, 
        page=page,
        pages=pages,
        title="Riwayat",
    )


# =============================================================================
# Categories management
# =============================================================================

@app.get("/categories")
@login_required
def categories_page():
    with db() as con:
        inc = con.execute(
            "SELECT * FROM categories WHERE user_id=? AND type='income' ORDER BY name",
            (current_user.id,)
        ).fetchall()
        exp = con.execute(
            "SELECT * FROM categories WHERE user_id=? AND type='expense' ORDER BY name",
            (current_user.id,)
        ).fetchall()
    return render_template(
        "categories.html",
        income=[dict(i) for i in inc],
        expense=[dict(e) for e in exp],
        title="Kategori",
    )

@app.post("/categories")
@login_required
def categories_add():
    type_ = request.form.get("type")
    name = (request.form.get("name") or "").strip()
    emoji = (request.form.get("emoji") or "").strip()
    if not name or type_ not in ("income", "expense"):
        flash("Isi nama kategori dengan benar.")
        return redirect(url_for("categories_page"))
    with db() as con:
        try:
            con.execute("INSERT INTO categories(user_id,type,name,emoji) VALUES (?,?,?,?)", (current_user.id, type_, name, emoji or None))
            flash("Kategori ditambahkan.")
        except sqlite3.IntegrityError:
            flash("Kategori sudah ada.")
    return redirect(url_for("categories_page"))


@app.post("/categories/edit/<int:cat_id>")
@login_required
def categories_edit(cat_id):
    name = (request.form.get("name") or "").strip()
    emoji = (request.form.get("emoji") or "").strip()
    if not name:
        flash("Nama kategori tidak boleh kosong.")
        return redirect(url_for("categories_page"))
    with db() as con:
        row = con.execute("SELECT * FROM categories WHERE id=? AND user_id=?", (cat_id, current_user.id)).fetchone()
        if not row:
            flash("Kategori tidak ditemukan.")
            return redirect(url_for("categories_page"))
        try:
            con.execute(
                "UPDATE categories SET name=?, emoji=? WHERE id=? AND user_id=?",
                (name, emoji or None, cat_id, current_user.id)
            )
            flash("Kategori diperbarui.")
        except sqlite3.IntegrityError:
            flash("Kategori dengan nama tersebut sudah ada.")
    return redirect(url_for("categories_page"))


# =============================================================================
# Budgets
# =============================================================================

@app.get("/budgets")
@login_required
def budgets_page():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    with db() as con:
        cats = con.execute(
            "SELECT id,name FROM categories WHERE user_id=? AND type='expense' ORDER BY name",
            (current_user.id,)
        ).fetchall()
        rows = con.execute("""
            SELECT b.id, c.name AS category, b.category_id, b.month, b.amount
            FROM budgets b
            JOIN categories c ON c.id=b.category_id
            WHERE b.user_id=? AND b.month=?
            ORDER BY c.name
        """, (current_user.id, month)).fetchall()
    return render_template(
        "budgets.html",
        month=month,
        categories=[dict(c) for c in cats],
        rows=[dict(r) for r in rows],
        title="Budget",
    )

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


# =============================================================================
# Savings (Tab Tabungan)
# =============================================================================

def ensure_autosavings_up_to_prev_month(user_id: int):
    today = date.today()
    prev_month = (today.replace(day=1) - relativedelta(days=1)).strftime("%Y-%m")

    with db() as con:
        row = con.execute(
            "SELECT MIN(substr(date,1,7)) AS m FROM transactions WHERE user_id=?",
            (user_id,)
        ).fetchone()
        first_trx_month = row["m"] if row else None
        if not first_trx_month:
            return

        ym = datetime.strptime(first_trx_month + "-01", "%Y-%m-%d").date()
        stop = datetime.strptime(prev_month + "-01", "%Y-%m-%d").date()

        while ym <= stop:
            ym_str = ym.strftime("%Y-%m")
            totals = con.execute(
                """
                SELECT
                  SUM(CASE WHEN type='income'  THEN amount ELSE 0 END) AS inc,
                  SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
                FROM transactions
                WHERE user_id=? AND substr(date,1,7)=?
                """,
                (user_id, ym_str)
            ).fetchone()

            inc = float(totals["inc"] or 0)
            exp = float(totals["exp"] or 0)
            net = inc - exp

            if net > 0:
                con.execute(
                    """
                    INSERT INTO savings_auto_transfers(user_id, month, amount)
                    VALUES (?,?,?)
                    ON CONFLICT(user_id, month) DO UPDATE SET amount=excluded.amount
                    """,
                    (user_id, ym_str, net)
                )
            else:
                con.execute(
                    "DELETE FROM savings_auto_transfers WHERE user_id=? AND month=?",
                    (user_id, ym_str)
                )

            ym = (ym.replace(day=1) + relativedelta(months=1))


@app.get("/savings")
@login_required
def savings_page():
    ensure_autosavings_up_to_prev_month(current_user.id)
    with db() as con:
        total_auto = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_auto_transfers WHERE user_id=?",
            (current_user.id,)
        ).fetchone()["t"]
        total_manual = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_manual_topups WHERE user_id=?",
            (current_user.id,)
        ).fetchone()["t"]

        rows = con.execute(
            """
            SELECT g.id, g.name, g.target_amount, g.created_at, g.achieved_at, g.archived_at,
                   COALESCE(SUM(a.amount),0) AS allocated
            FROM savings_goals g
            LEFT JOIN savings_allocations a ON a.goal_id=g.id AND a.user_id=g.user_id
            WHERE g.user_id=?
            GROUP BY g.id
            ORDER BY g.created_at DESC
            """,
            (current_user.id,)
        ).fetchall()

        goals = [dict(r) for r in rows]
        total_alloc = sum(float(r["allocated"]) for r in goals)
        # konsumsi permanen (goal yang dihapus, dsb.)
        total_consumed = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_consumed WHERE user_id=?",
            (current_user.id,)
        ).fetchone()["t"]

        # total masuk tabungan = auto + manual
        total_in = float(total_auto) + float(total_manual)
        # saldo tersedia = total in - (alokasi aktif/arsip + konsumsi permanen)
        pot_available = total_in - (float(total_alloc) + float(total_consumed))

        # Tandai achieved_at bila terpenuhi namun belum ditandai
        achieved_ids = [g["id"] for g in goals if not g.get("achieved_at") and float(g["allocated"]) >= float(g["target_amount"]) ]
        if achieved_ids:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for gid in achieved_ids:
                con.execute(
                    "UPDATE savings_goals SET achieved_at=? WHERE id=? AND user_id=?",
                    (now, gid, current_user.id)
                )

        autosave_history = con.execute(
            "SELECT month, amount FROM savings_auto_transfers WHERE user_id=? ORDER BY month DESC LIMIT 12",
            (current_user.id,)
        ).fetchall()

        # Sisa income bulan berjalan yang tersedia (income - expense)
        curr_month = date.today().strftime("%Y-%m")
        month_totals = con.execute(
            """
            SELECT
              SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
              SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
            FROM transactions
            WHERE user_id=? AND substr(date,1,7)=?
            """,
            (current_user.id, curr_month)
        ).fetchone()
        inc_m = float(month_totals["inc"] or 0)
        exp_m = float(month_totals["exp"] or 0)
        avail_current = max(0.0, inc_m - exp_m)

        # Daftar top-up manual bulan berjalan
        topups_current = con.execute(
            "SELECT id, date, amount, note FROM savings_manual_topups WHERE user_id=? AND month=? ORDER BY date DESC, id DESC",
            (current_user.id, curr_month)
        ).fetchall()

    # Kelompokkan goals
    active_goals = []
    archived_goals = []
    for g in goals:
        g["remaining"] = max(0.0, float(g["target_amount"]) - float(g["allocated"]))
        if g.get("archived_at"):
            archived_goals.append(g)
        else:
            active_goals.append(g)

    any_achieved_active = any((float(g["allocated"]) >= float(g["target_amount"])) and (not g.get("archived_at")) for g in goals)
    return render_template(
        "savings.html",
        pot_available=pot_available,
        total_auto=total_in,
        total_manual=total_manual,
        total_alloc=(float(total_alloc) + float(total_consumed)),
        active_goals=active_goals,
        archived_goals=archived_goals,
        any_achieved=any_achieved_active,
        autosave_history=[dict(r) for r in autosave_history],
        avail_current=avail_current,
        topups_current=[dict(r) for r in topups_current],
        title="Tabungan",
        user_name=current_user.name,
    )


@app.post("/savings/topup")
@login_required
def savings_topup():
    amount = request.form.get("amount")
    note = (request.form.get("note") or "").strip()
    try:
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except Exception:
        flash("Nominal top up tidak valid.")
        return redirect(url_for("savings_page"))

    today = date.today()
    month = today.strftime("%Y-%m")
    with db() as con:
        # Hitung sisa income bulan berjalan dan tolak jika melebihi
        month_totals = con.execute(
            """
            SELECT
              SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
              SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
            FROM transactions
            WHERE user_id=? AND substr(date,1,7)=?
            """,
            (current_user.id, month)
        ).fetchone()
        inc_m = float(month_totals["inc"] or 0); exp_m = float(month_totals["exp"] or 0)
        avail_current = max(0.0, inc_m - exp_m)
        if amt > avail_current + 1e-6:
            flash(f"Nominal melebihi sisa income bulan ini: {money(avail_current)}")
            return redirect(url_for("savings_page"))

        # Pastikan kategori 'Tabungan' (expense) ada
        con.execute(
            "INSERT OR IGNORE INTO categories(user_id,type,name) VALUES (?,?,?)",
            (current_user.id, 'expense', 'Tabungan')
        )
        cat_id = con.execute(
            "SELECT id FROM categories WHERE user_id=? AND type='expense' AND name=?",
            (current_user.id, 'Tabungan')
        ).fetchone()["id"]

        # Catat transaksi expense yang mengurangi income bulan ini
        cur_tx = con.execute(
            """
            INSERT INTO transactions(user_id,date,type,category_id,amount,source_or_payee,account,notes)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (current_user.id, today.isoformat(), 'expense', cat_id, amt, 'Top-up Tabungan', 'Transfer', note or None)
        )
        tx_id = cur_tx.lastrowid

        con.execute(
            "INSERT INTO savings_manual_topups(user_id,month,date,amount,note,transaction_id) VALUES (?,?,?,?,?,?)",
            (current_user.id, month, today.isoformat(), amt, note or None, tx_id)
        )
    flash("Top up tabungan bulan ini disimpan.")
    return redirect(url_for("savings_page"))


@app.post("/savings/topup/delete/<int:topup_id>")
@login_required
def savings_topup_delete(topup_id):
    today = date.today()
    curr_month = today.strftime("%Y-%m")
    with db() as con:
        row = con.execute(
            "SELECT id, user_id, month, amount, transaction_id FROM savings_manual_topups WHERE id=? AND user_id=?",
            (topup_id, current_user.id)
        ).fetchone()
        if not row:
            flash("Top-up tidak ditemukan.")
            return redirect(url_for("savings_page"))
        if row["month"] != curr_month:
            flash("Hanya top-up bulan ini yang dapat dihapus.")
            return redirect(url_for("savings_page"))

        tx_id = row["transaction_id"]
        if tx_id:
            con.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, current_user.id))
        con.execute("DELETE FROM savings_manual_topups WHERE id=? AND user_id=?", (topup_id, current_user.id))

    flash("Top-up bulan ini dibatalkan dan dana dikembalikan ke sisa income bulan ini.")
    return redirect(url_for("savings_page"))


@app.post("/savings/goals")
@login_required
def savings_create_goal():
    name = (request.form.get("name") or "").strip()
    target = (request.form.get("target_amount") or "").strip()
    try:
        target_val = float(target)
        if target_val <= 0:
            raise ValueError
    except Exception:
        flash("Target harus angka > 0.")
        return redirect(url_for("savings_page"))
    if not name:
        flash("Nama goal wajib diisi.")
        return redirect(url_for("savings_page"))

    with db() as con:
        con.execute(
            "INSERT INTO savings_goals(user_id,name,target_amount) VALUES (?,?,?)",
            (current_user.id, name, target_val)
        )
    flash("Goal tabungan ditambahkan.")
    return redirect(url_for("savings_page"))


@app.post("/savings/allocate")
@login_required
def savings_allocate():
    goal_id = request.form.get("goal_id")
    amount = request.form.get("amount")
    note = (request.form.get("note") or "").strip()

    try:
        gid = int(goal_id)
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except Exception:
        flash("Alokasi tidak valid.")
        return redirect(url_for("savings_page"))

    with db() as con:
        total_auto = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_auto_transfers WHERE user_id=?",
            (current_user.id,)
        ).fetchone()["t"]
        total_alloc = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_allocations WHERE user_id=?",
            (current_user.id,)
        ).fetchone()["t"]
        pot_available = float(total_auto) - float(total_alloc)

        row = con.execute(
            """
            SELECT target_amount, archived_at,
                   COALESCE((SELECT SUM(amount) FROM savings_allocations WHERE user_id=? AND goal_id=?),0) AS allocated
            FROM savings_goals WHERE id=? AND user_id=?
            """,
            (current_user.id, gid, gid, current_user.id)
        ).fetchone()
        if not row:
            flash("Goal tidak ditemukan.")
            return redirect(url_for("savings_page"))
        if row["archived_at"]:
            flash("Goal sudah diarsipkan, tidak bisa dialokasikan.")
            return redirect(url_for("savings_page"))

        remaining = max(0.0, float(row["target_amount"]) - float(row["allocated"]))
        allowed = min(pot_available, remaining)
        if amt > allowed + 1e-6:
            flash(f"Maksimal alokasi yang diperbolehkan: Rp {allowed:,.0f}".replace(',', '.'))
            return redirect(url_for("savings_page"))

        today_iso = date.today().isoformat()
        con.execute(
            "INSERT INTO savings_allocations(user_id,goal_id,amount,date,note) VALUES (?,?,?,?,?)",
            (current_user.id, gid, amt, today_iso, note or None)
        )

    flash("Alokasi tersimpan.")
    return redirect(url_for("savings_page"))


@app.post("/savings/goals/<int:goal_id>/archive")
@login_required
def savings_archive(goal_id):
    with db() as con:
        ok = con.execute("SELECT 1 FROM savings_goals WHERE id=? AND user_id=?", (goal_id, current_user.id)).fetchone()
        if not ok:
            flash("Goal tidak ditemukan.")
            return redirect(url_for("savings_page"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        con.execute("UPDATE savings_goals SET archived_at=? WHERE id=? AND user_id=?", (now, goal_id, current_user.id))
    flash("Goal diarsipkan.")
    return redirect(url_for("savings_page"))


@app.post("/savings/goals/<int:goal_id>/unarchive")
@login_required
def savings_unarchive(goal_id):
    with db() as con:
        ok = con.execute("SELECT 1 FROM savings_goals WHERE id=? AND user_id=?", (goal_id, current_user.id)).fetchone()
        if not ok:
            flash("Goal tidak ditemukan.")
            return redirect(url_for("savings_page"))
        con.execute("UPDATE savings_goals SET archived_at=NULL WHERE id=? AND user_id=?", (goal_id, current_user.id))
    flash("Goal dikembalikan ke daftar aktif.")
    return redirect(url_for("savings_page"))


@app.post("/savings/release")
@login_required
def savings_release():
    goal_id = request.form.get("goal_id")
    amount = request.form.get("amount")
    note = (request.form.get("note") or "").strip()

    try:
        gid = int(goal_id)
        amt = float(amount)
        if amt <= 0:
            raise ValueError
    except Exception:
        flash("Nominal pelepasan tidak valid.")
        return redirect(url_for("savings_page"))

    with db() as con:
        ok = con.execute("SELECT 1 FROM savings_goals WHERE id=? AND user_id=?", (gid, current_user.id)).fetchone()
        if not ok:
            flash("Goal tidak ditemukan.")
            return redirect(url_for("savings_page"))
        row = con.execute(
            "SELECT COALESCE((SELECT SUM(amount) FROM savings_allocations WHERE user_id=? AND goal_id=?),0) AS allocated",
            (current_user.id, gid)
        ).fetchone()
        allocated = float(row["allocated"]) if row else 0.0
        if amt > allocated + 1e-6:
            flash("Tidak bisa melepas dana melebihi yang sudah dialokasikan.")
            return redirect(url_for("savings_page"))

        today_iso = date.today().isoformat()
        con.execute(
            "INSERT INTO savings_allocations(user_id,goal_id,amount,date,note) VALUES (?,?,?,?,?)",
            (current_user.id, gid, -amt, today_iso, note or "Release dana")
        )

    flash("Dana dilepas kembali ke saldo tabungan.")
    return redirect(url_for("savings_page"))


@app.post("/savings/goals/<int:goal_id>/delete")
@login_required
def savings_goal_delete(goal_id):
    with db() as con:
        g = con.execute(
            "SELECT id, name, archived_at FROM savings_goals WHERE id=? AND user_id=?",
            (goal_id, current_user.id)
        ).fetchone()
        if not g:
            flash("Goal tidak ditemukan.")
            return redirect(url_for("savings_page"))
        if not g["archived_at"]:
            flash("Hanya goal yang sudah diarsipkan yang bisa dihapus.")
            return redirect(url_for("savings_page"))
        # Hitung total alokasi pada goal ini, lalu tandai sebagai konsumsi permanen
        row = con.execute(
            "SELECT COALESCE(SUM(amount),0) AS t FROM savings_allocations WHERE user_id=? AND goal_id=?",
            (current_user.id, goal_id)
        ).fetchone()
        consumed = float(row["t"] or 0)
        if consumed > 0:
            note = f"Hapus goal: {g['name']}"
            con.execute(
                "INSERT INTO savings_consumed(user_id,amount,note) VALUES (?,?,?)",
                (current_user.id, consumed, note)
            )
        # Hapus alokasi dan goal
        con.execute("DELETE FROM savings_allocations WHERE user_id=? AND goal_id=?", (current_user.id, goal_id))
        con.execute("DELETE FROM savings_goals WHERE id=? AND user_id=?", (goal_id, current_user.id))

    flash("Goal dihapus. Dana yang telah dialokasikan dianggap terpakai.")
    return redirect(url_for("savings_page"))

# Export (Excel / PDF)
# =============================================================================

@app.get("/export/excel")
@login_required
def export_excel():
    start, end = normalize_date_range(request.args.get("start"), request.args.get("end"))
    with db() as con:
        rows = con.execute("""
            SELECT t.date, t.type, COALESCE(c.name,'-') AS category,
                   t.amount, t.source_or_payee, t.account, t.notes
            FROM transactions t
            LEFT JOIN categories c ON c.id=t.category_id
            WHERE t.user_id=? AND t.date BETWEEN ? AND ?
            ORDER BY t.date, t.id
        """, (current_user.id, start, end)).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    bio = io.BytesIO()
    df.to_excel(bio, index=False, sheet_name="Laporan")
    bio.seek(0)
    return send_file(
        bio,
        as_attachment=True,
        download_name=f"laporan_{start}_sampai_{end}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/export/pdf")
@login_required
def export_pdf():
    start, end = normalize_date_range(request.args.get("start"), request.args.get("end"))

    # ringkas totals
    with db() as con:
        totals = con.execute("""
           SELECT
            SUM(CASE WHEN type='income' THEN amount ELSE 0 END) AS inc,
            SUM(CASE WHEN type='expense' THEN amount ELSE 0 END) AS exp
           FROM transactions WHERE user_id=? AND date BETWEEN ? AND ?
        """, (current_user.id, start, end)).fetchone()

        rows = con.execute("""
          SELECT t.date, t.type, COALESCE(c.name,'-') AS category,
                 t.amount, COALESCE(t.source_or_payee,'') AS payee, COALESCE(t.account,'') AS acc
          FROM transactions t
          LEFT JOIN categories c ON c.id = t.category_id
          WHERE t.user_id=? AND t.date BETWEEN ? AND ?
          ORDER BY t.date, t.id
        """, (current_user.id, start, end)).fetchall()

    # Siapkan canvas
    bio = io.BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    w, h = A4
    margin_l, margin_r, margin_t, margin_b = 32, 32, 36, 36

    def page_header():
        # banner hijau di header
        c.setFillColorRGB(0.082, 0.451, 0.278)  # ~ #157347
        c.rect(0, h-28, w, 28, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin_l, h-20, "Temanku — Laporan Keuangan")

        c.setFillColor(colors.black)
        y0 = h - 48
        c.setFont("Helvetica", 9)
        c.drawString(margin_l, y0, f"Periode: {start} s.d. {end}")
        c.drawRightString(w - margin_r, y0, f"Dicetak: {datetime.now():%d/%m/%Y %H:%M}")

        # Ringkasan angka
        inc = float(totals['inc'] or 0); exp = float(totals['exp'] or 0); net = inc - exp
        y1 = y0 - 16
        c.setFont("Helvetica-Bold", 10); c.drawString(margin_l, y1, f"Pendapatan: {money(inc)}")
        y1 -= 14; c.setFont("Helvetica", 10); c.drawString(margin_l, y1, f"Pengeluaran: {money(exp)}")
        y1 -= 14; c.drawString(margin_l, y1, f"Saldo Bersih: {money(net)}")
        return y1 - 18

    def table_header(y):
        cols = ["Tanggal", "Jenis", "Kategori", "Nominal", "Keterangan", "Metode"]
        # Pastikan total <= area konten (w - margin_l - margin_r = ~531pt)
        widths = [66, 76, 110, 78, 156, 45]  # total = 531
        x = margin_l
        c.setFillColorRGB(0.94, 0.96, 0.99)
        c.rect(margin_l, y-3, sum(widths), 16, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 9)
        for col, wcol in zip(cols, widths):
            c.drawString(x, y, col)
            x += wcol
        return y - 14, widths

    def table_row(y, widths, r, idx):
        # garis latar selang-seling
        if idx % 2 == 1:
            c.setFillColorRGB(0.98, 0.98, 0.985)
            c.rect(margin_l, y-2, sum(widths), 12, fill=1, stroke=0)
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 9)
        x = margin_l
        c.drawString(x, y, r["date"]); x += widths[0]
        tipe = 'Pemasukan' if r["type"] == 'income' else ('Pengeluaran' if r["type"] == 'expense' else (r["type"] or ''))
        c.drawString(x, y, tipe); x += widths[1]
        c.drawString(x, y, (r["category"] or '')[:20]); x += widths[2]
        # Nominal rata kiri
        c.drawString(x, y, money(r["amount"]))
        x += widths[3]
        c.drawString(x, y, (r["payee"] or "")[:28]); x += widths[4]
        c.drawString(x, y, (r["acc"] or "")[:10])
        return y - 12

    def page_footer():
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.grey)
        c.drawRightString(w - margin_r, margin_b - 10, f"Halaman {c.getPageNumber()}")
        c.setFillColor(colors.black)

    # Gambar header pertama
    y = page_header()
    c.setFont("Helvetica-Bold", 11); c.drawString(margin_l, y, "Detail Transaksi"); y -= 14
    y, widths = table_header(y)

    # Render baris
    for idx, r in enumerate(rows):
        if y < margin_b + 24:
            page_footer(); c.showPage()
            y = page_header()
            c.setFont("Helvetica-Bold", 11); c.drawString(margin_l, y, "Detail Transaksi"); y -= 14
            y, widths = table_header(y)
        y = table_row(y, widths, r, idx)

    page_footer()
    c.save(); bio.seek(0)
    return send_file(
        bio,
        as_attachment=True,
        download_name=f"laporan_{start}_{end}.pdf",
        mimetype="application/pdf"
    )


# =============================================================================
# API kecil
# =============================================================================

@app.get("/api/categories")
@login_required
def api_categories():
    t = (request.args.get("type") or "expense").strip()
    if t not in ("income", "expense"):
        t = "expense"
    with db() as con:
        rows = con.execute(
            "SELECT id, name, emoji FROM categories WHERE user_id=? AND type=? ORDER BY name",
            (current_user.id, t)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# =============================================================================
# CSV Template & Upload
# =============================================================================

CSV_COLUMNS = ["date", "type", "amount", "category", "source_or_payee", "account", "notes"]

# alias dari file export → kolom internal
COLUMN_ALIASES = {
    "keterangan": "source_or_payee",
    "payment_method": "account",
}

@app.get("/template.csv")
@login_required
def template_csv():
    sample = pd.DataFrame([
        {"date": "2025-01-25", "type": "income",  "amount": 8500000, "category": "Gaji",  "source_or_payee": "PT Maju", "account": "BCA",  "notes": "Gaji bulanan"},
        {"date": "2025-01-27", "type": "expense", "amount":   45000, "category": "Makan", "source_or_payee": "Warung",  "account": "Tunai","notes": "Nasi Padang"},
    ], columns=CSV_COLUMNS)
    buf = io.StringIO()
    sample.to_csv(buf, index=False); buf.seek(0)
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="template_transaksi.csv"
    )

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

    # isi kolom opsional agar sesuai target internal
    if "notes" not in df.columns: df["notes"] = ""
    if "source_or_payee" not in df.columns: df["source_or_payee"] = ""
    if "account" not in df.columns: df["account"] = ""

    required = ["date", "type", "amount", "category"]
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
        if not set(df["type"].dropna().unique()).issubset({"income", "expense"}):
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
    
    # tolak baris dengan tanggal di masa depan
    today_iso = date.today().isoformat()
    future_mask = df["date"] > today_iso
    if future_mask.any():
        n = int(future_mask.sum())
        contoh = df.loc[future_mask, "date"].iloc[0]
        flash(f"Terdapat {n} baris dengan tanggal di masa depan (contoh: {contoh}). Perbaiki lalu unggah ulang.")
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

# ---- Favorites API ----
@app.get("/api/favorites")
@login_required
def api_favorites_list():
    with db() as con:
        rows = con.execute("""
            SELECT f.id, f.name, f.type, f.category_id, COALESCE(c.name,'-') AS category,
                   f.amount, f.account, f.source_or_payee, f.notes
            FROM favorites f
            LEFT JOIN categories c ON c.id=f.category_id
            WHERE f.user_id=?
            ORDER BY f.type, f.name
        """, (current_user.id,)).fetchall()
    return jsonify([dict(r) for r in rows])

# =============================================================================
# Favorites CRUD API
# =============================================================================

@app.post("/api/favorites")
@login_required
def api_favorites_create():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    type_ = (data.get("type") or "").strip().lower()
    category_id = (data.get("category_id") or "").strip()
    amount = (data.get("amount") or "").strip()
    account = (data.get("account") or "").strip()
    source = (data.get("source_or_payee") or "").strip()
    notes  = (data.get("notes") or "").strip()

    if not name:
        return jsonify({"ok": False, "msg": "Nama favorit wajib diisi."}), 400
    if type_ not in ("income", "expense"):
        return jsonify({"ok": False, "msg": "Jenis favorit tidak valid."}), 400
    try:
        cat_id_int = int(category_id)
    except:
        return jsonify({"ok": False, "msg": "Kategori favorit tidak valid."}), 400

    # amount opsional; jika kosong, simpan NULL
    amt_val = None
    if amount:
        try:
            amt_val = float(amount)
            if amt_val <= 0:
                return jsonify({"ok": False, "msg": "Nominal favorit harus > 0."}), 400
        except:
            return jsonify({"ok": False, "msg": "Nominal favorit tidak valid."}), 400

    # validasi kepemilikan kategori
    with db() as con:
        ok = con.execute(
            "SELECT 1 FROM categories WHERE id=? AND user_id=? AND type=?",
            (cat_id_int, current_user.id, type_)
        ).fetchone()
        if not ok:
            return jsonify({"ok": False, "msg": "Kategori tidak ditemukan / tidak sesuai jenis."}), 400

        try:
            cur = con.execute("""
                INSERT INTO favorites(user_id,name,type,category_id,amount,account,source_or_payee,notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (current_user.id, name, type_, cat_id_int, amt_val, account or None, source or None, notes or None))
            fav_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "msg": "Nama favorit sudah ada."}), 409

        row = con.execute("""
            SELECT f.id, f.name, f.type, f.category_id, COALESCE(c.name,'-') AS category,
                   f.amount, f.account, f.source_or_payee, f.notes
            FROM favorites f LEFT JOIN categories c ON c.id=f.category_id
            WHERE f.id=? AND f.user_id=?
        """, (fav_id, current_user.id)).fetchone()

    return jsonify({"ok": True, "data": dict(row)}), 201

@app.post("/api/favorites/delete/<int:fav_id>")
@login_required
def api_favorites_delete(fav_id):
    with db() as con:
        con.execute("DELETE FROM favorites WHERE id=? AND user_id=?", (fav_id, current_user.id))
    return jsonify({"ok": True})


# =============================================================================
# Entrypoint (dev)
# =============================================================================

if __name__ == "__main__":
    app.run(debug=True)
