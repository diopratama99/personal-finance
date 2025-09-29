import io, os, sqlite3
from datetime import date
from dateutil.relativedelta import relativedelta

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, flash

APP_DB = os.path.join(os.path.dirname(__file__), "finance.db")
app = Flask(__name__)
app.secret_key = "change-this-in-production"

# ---------- DB ----------
def db():
    conn = sqlite3.connect(APP_DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as con, open(os.path.join(os.path.dirname(__file__), "schema.sql")) as f:
        con.executescript(f.read())

if not os.path.exists(APP_DB):
    init_db()

# ---------- Helpers ----------
def start_end_default():
    today = date.today()
    s = today.replace(day=1)
    e = (s + relativedelta(months=1) - relativedelta(days=1))
    return s.isoformat(), e.isoformat()

def money(x):
    return f"Rp {x:,.0f}".replace(",", ".")

app.jinja_env.filters["money"] = money

# ---------- Pages ----------
@app.get("/")
def dashboard():
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        start, end = start_end_default()

    with db() as con:
        totals = con.execute("""
            SELECT
              SUM(CASE WHEN t.type='income' THEN t.amount ELSE 0 END) AS income,
              SUM(CASE WHEN t.type='expense' THEN t.amount ELSE 0 END) AS expense
            FROM transactions t
            WHERE t.date BETWEEN ? AND ?
        """, (start, end)).fetchone()

        spend = con.execute("""
            SELECT c.name AS category, SUM(t.amount) AS total
            FROM transactions t
            JOIN categories c ON c.id=t.category_id
            WHERE t.type='expense' AND t.date BETWEEN ? AND ?
            GROUP BY c.name
            ORDER BY total DESC
        """, (start, end)).fetchall()

        top_payee = con.execute("""
            SELECT COALESCE(source_or_payee,'(Tidak diisi)') AS payee,
                   SUM(amount) AS total, COUNT(*) AS cnt
            FROM transactions
            WHERE type='expense' AND date BETWEEN ? AND ?
            GROUP BY COALESCE(source_or_payee,'(Tidak diisi)')
            ORDER BY total DESC LIMIT 1
        """, (start, end)).fetchone()

        latest = con.execute("""
            SELECT t.*, c.name AS category
            FROM transactions t
            JOIN categories c ON c.id=t.category_id
            WHERE t.date BETWEEN ? AND ?
            ORDER BY t.date DESC, t.id DESC
            LIMIT 10
        """, (start, end)).fetchall()

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
        latest=[dict(r) for r in latest]
    )

@app.get("/add")
def add_form():
    t = request.args.get("type", "expense")
    with db() as con:
        cats = con.execute("SELECT id, name FROM categories WHERE type=? ORDER BY name", (t,)).fetchall()
    return render_template("add.html", default_type=t, categories=cats)

@app.post("/add")
def add_submit():
    date_ = request.form.get("date")
    type_ = request.form.get("type")
    category_id = request.form.get("category_id")
    amount = request.form.get("amount")
    source = request.form.get("source_or_payee")
    account = request.form.get("account")
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
            INSERT INTO transactions(date,type,category_id,amount,source_or_payee,account,notes)
            VALUES (?,?,?,?,?,?,?)
        """, (date_, type_, int(category_id), amt, source, account, notes))
    flash("Transaksi berhasil ditambahkan.")
    return redirect(url_for("history"))

@app.get("/history")
def history():
    # filter sederhana + pagination
    q_type = request.args.get("type", "")
    q_cat = request.args.get("category_id", "")
    page = int(request.args.get("page", 1))
    per = 20
    where = ["1=1"]
    params = []
    if q_type in ("income", "expense"):
        where.append("t.type=?"); params.append(q_type)
    if q_cat:
        where.append("t.category_id=?"); params.append(q_cat)
    where_clause = " AND ".join(where)

    with db() as con:
        cats = con.execute("SELECT id, type, name FROM categories ORDER BY type, name").fetchall()
        total = con.execute(f"SELECT COUNT(*) AS n FROM transactions t WHERE {where_clause}", params).fetchone()["n"]
        rows = con.execute(f"""
            SELECT t.*, c.name AS category
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
                           q_type=q_type, q_cat=q_cat, page=page, pages=pages)

@app.get("/categories")
def categories_page():
    with db() as con:
        inc = con.execute("SELECT * FROM categories WHERE type='income' ORDER BY name").fetchall()
        exp = con.execute("SELECT * FROM categories WHERE type='expense' ORDER BY name").fetchall()
    return render_template("categories.html", income=[dict(i) for i in inc], expense=[dict(e) for e in exp])

@app.post("/categories")
def categories_add():
    type_ = request.form.get("type")
    name = request.form.get("name")
    if not name or type_ not in ("income", "expense"):
        flash("Isi nama kategori dengan benar.")
        return redirect(url_for("categories_page"))
    with db() as con:
        try:
            con.execute("INSERT INTO categories(type,name) VALUES (?,?)", (type_, name.strip()))
            flash("Kategori ditambahkan.")
        except sqlite3.IntegrityError:
            flash("Kategori sudah ada.")
    return redirect(url_for("categories_page"))

# ---------- CSV template & upload (opsional, tetap ada) ----------
CSV_COLUMNS = ["date","type","amount","category","source_or_payee","account","notes"]

@app.get("/template.csv")
def template_csv():
    sample = pd.DataFrame([
        {"date":"2025-01-25","type":"income","amount":8500000,"category":"Gaji","source_or_payee":"PT Maju","account":"BCA","notes":"Gaji bulanan"},
        {"date":"2025-01-27","type":"expense","amount":45000,"category":"Makan","source_or_payee":"Warung","account":"Tunai","notes":"Nasi Padang"},
    ], columns=CSV_COLUMNS)
    buf = io.StringIO(); sample.to_csv(buf, index=False); buf.seek(0)
    return send_file(io.BytesIO(buf.getvalue().encode("utf-8")),
                     mimetype="text/csv", as_attachment=True, download_name="template_transaksi.csv")

@app.post("/upload")
def upload_csv():
    f = request.files.get("file")
    if not f or f.filename == "":
        flash("Pilih file CSV.")
        return redirect(url_for("dashboard"))

    try:
        df = pd.read_csv(f)
    except Exception as e:
        flash(f"Gagal membaca CSV: {e}")
        return redirect(url_for("dashboard"))

    missing = [c for c in CSV_COLUMNS if c not in df.columns]
    if missing:
        flash(f"Kolom wajib hilang: {', '.join(missing)}")
        return redirect(url_for("dashboard"))

    df = df[CSV_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    df["type"] = df["type"].str.lower().str.strip()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["category"] = df["category"].fillna("Lainnya")
    df["source_or_payee"] = df["source_or_payee"].fillna("")
    df["account"] = df["account"].fillna("")
    df["notes"] = df["notes"].fillna("")

    # Map kategori teks -> id (otomatis buat kalau belum ada)
    with db() as con:
        for _, r in df.iterrows():
            cat = con.execute("SELECT id FROM categories WHERE type=? AND name=?", (r["type"], r["category"])).fetchone()
            if not cat:
                con.execute("INSERT INTO categories(type,name) VALUES (?,?)", (r["type"], r["category"]))
        con.commit()

        # insert
        for _, r in df.iterrows():
            cat_id = con.execute("SELECT id FROM categories WHERE type=? AND name=?", (r["type"], r["category"])).fetchone()["id"]
            con.execute("""
              INSERT INTO transactions(date,type,category_id,amount,source_or_payee,account,notes)
              VALUES (?,?,?,?,?,?,?)
            """, (r["date"], r["type"], cat_id, float(r["amount"]), r["source_or_payee"], r["account"], r["notes"]))

    flash(f"Impor {len(df)} baris berhasil.")
    return redirect(url_for("dashboard"))

# ---------- API kecil untuk dropdown dinamis ----------
@app.get("/api/categories")
def api_categories():
    t = request.args.get("type","expense")
    with db() as con:
        rows = con.execute("SELECT id, name FROM categories WHERE type=? ORDER BY name", (t,)).fetchall()
    return jsonify([dict(r) for r in rows])

if __name__ == "__main__":
    app.run(debug=True)
