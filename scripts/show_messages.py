"""Print the recorded conversations, newest last. For checking and for Part E."""
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "data" / "conversations.db"

conn = sqlite3.connect(DB_FILE)
rows = conn.execute(
    "SELECT conversation_id, role, content, created_at FROM messages ORDER BY id"
).fetchall()
conn.close()

print(f"{len(rows)} messages\n")
for conversation_id, role, content, created_at in rows:
    print(f"{created_at}  {conversation_id[:8]}  {role:9}  {content[:70]!r}")