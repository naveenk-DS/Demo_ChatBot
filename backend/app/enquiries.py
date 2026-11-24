import sqlite3
from typing import Optional
from .config import env

def save_enquiry(data: Optional[dict] = None, **kwargs) -> int:
    payload = dict(data or {})
    payload.update(kwargs)
    path = env("ENQUIRY_DB_PATH", "./enquiries.db")
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            phone TEXT NOT NULL, property_id TEXT, message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cur = conn.execute(
            "INSERT INTO enquiries (name, phone, property_id, message) VALUES (?, ?, ?, ?)",
            (payload.get("name", ""), payload.get("phone", ""), payload.get("property_id"), payload.get("message", "")),
        )
        return int(cur.lastrowid)
