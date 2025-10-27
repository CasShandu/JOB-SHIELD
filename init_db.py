import sqlite3

DB = "jobshield.db"

schema = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    searches_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    min_experience INTEGER NOT NULL,
    skills TEXT NOT NULL,
    location TEXT
);

CREATE TABLE IF NOT EXISTS seekers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT NOT NULL,
    qualification TEXT,
    experience INTEGER,
    skills TEXT,
    location TEXT
);
"""

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.executescript(schema)
    conn.commit()
    conn.close()
    print("Initialized DB:", DB)

if __name__ == "__main__":
    init_db()
