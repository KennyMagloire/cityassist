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