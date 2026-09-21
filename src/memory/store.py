import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "memory.db"

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        db.commit()

def save_message(role: str, content: str):
    with sqlite3.connect(DB_PATH) as db:
        db.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content),
        )
        db.commit()

def get_recent_messages(limit: int = 20):
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]

def clear_memory():
    with sqlite3.connect(DB_PATH) as db:
        db.execute("DELETE FROM messages")
        db.commit()
