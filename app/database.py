"""Record every exchange in a small SQLite file. Only redacted text is stored."""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    request_type TEXT NOT NULL,
    department TEXT,
    suburb TEXT NOT NULL,
    street TEXT,
    expected_band TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);    
    
"""


def _connect():
    conn = sqlite3.connect(config.DB_FILE, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the table if it does not exist yet. Safe to run every time the app starts."""
    with closing(_connect()) as conn:
        conn.executescript(SCHEMA)


def save_message(conversation_id, channel, role, content):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as conn:
        with conn:
            conn.execute(
                "INSERT INTO messages (conversation_id, channel, role, content, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (conversation_id, channel, role, content, now),
            )

def save_draft(conversation_id, channel, request_type, department, suburb, street, band):
    """Save a draft service request and return its draft number."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect()) as conn:
        with conn:
            cursor = conn.execute(
                "INSERT INTO drafts (conversation_id, channel, request_type, department, "
                "suburb, street, expected_band, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (conversation_id, channel, request_type, department, suburb, street, band, now),
            )
            return cursor.lastrowid