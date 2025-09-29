-- Kategori terpisah (biar fleksibel)
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT CHECK(type IN ('income','expense')) NOT NULL,
  name TEXT NOT NULL,
  UNIQUE(type, name)
);

-- Transaksi refer ke category_id
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,                      -- YYYY-MM-DD
  type TEXT CHECK(type IN ('income','expense')) NOT NULL,
  category_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  source_or_payee TEXT,
  account TEXT,
  notes TEXT,
  FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE INDEX IF NOT EXISTS idx_trx_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_trx_type ON transactions(type);
CREATE INDEX IF NOT EXISTS idx_trx_cat ON transactions(category_id);

-- Seed kategori default
INSERT OR IGNORE INTO categories(type,name) VALUES
('income','Gaji'),('income','Bonus'),('income','Investasi'),('income','Freelance'),
('expense','Makan'),('expense','Transport'),('expense','Belanja'),
('expense','Hiburan'),('expense','Kesehatan'),('expense','Tagihan'),('expense','Lainnya');
