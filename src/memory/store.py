import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "memory.db"

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db.commit()

def save_message(role, content):
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
        db.commit()

def get_recent_messages(limit=20):
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [{"role": r, "content": c} for r, c in reversed(rows)]

def remember_fact(fact):
    fact = fact.strip()
    if not fact:
        return
    with sqlite3.connect(DB_PATH) as db:
        db.execute("INSERT OR IGNORE INTO facts (fact) VALUES (?)", (fact,))
        db.commit()

def get_facts(limit=50):
    with sqlite3.connect(DB_PATH) as db:
        return [r[0] for r in db.execute(
            "SELECT fact FROM facts ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]

def clear_memory():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM messages")
        db.execute("DELETE FROM facts")
        db.commit()
