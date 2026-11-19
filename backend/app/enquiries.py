import sqlite3
from .config import env

def save_enquiry(data: dict) -> int:
    path = env("ENQUIRY_DB_PATH", "./enquiries.db")
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS enquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            phone TEXT NOT NULL, property_id TEXT, message TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        cur = conn.execute(
            "INSERT INTO enquiries (name, phone, property_id, message) VALUES (?, ?, ?, ?)",
            (data["name"], data["phone"], data.get("property_id"), data["message"]),
        )
        return int(cur.lastrowid)
