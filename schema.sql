-- Users
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Categories milik user (income/expense)
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT CHECK(type IN ('income','expense')) NOT NULL,
  name TEXT NOT NULL,
  UNIQUE(user_id, type, name),
  FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Transactions milik user
CREATE TABLE IF NOT EXISTS transactions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  date TEXT NOT NULL,                      -- YYYY-MM-DD
  type TEXT CHECK(type IN ('income','expense')) NOT NULL,
  category_id INTEGER NOT NULL,
  amount REAL NOT NULL,
  source_or_payee TEXT,
  account TEXT,
  notes TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (category_id) REFERENCES categories(id)
);
CREATE INDEX IF NOT EXISTS idx_trx_user_date ON transactions(user_id, date);
CREATE INDEX IF NOT EXISTS idx_trx_user_type ON transactions(user_id, type);

-- Budget bulanan per kategori (YYYY-MM)
CREATE TABLE IF NOT EXISTS budgets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  category_id INTEGER NOT NULL,
  month TEXT NOT NULL,                     -- 2025-09
  amount REAL NOT NULL,
  UNIQUE(user_id, category_id, month),
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (category_id) REFERENCES categories(id)
);
