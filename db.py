"""
SQLite persistence for the IS 6403 RAG dashboard.

Stores conversations and messages in a local file (chat.db). Good for the
single-user prototype; the schema migrates cleanly to PostgreSQL when you're
ready for the website.

Schema:
    conversations(id, title, created_at, updated_at)
    messages(id, conversation_id, role, content, debug_json, created_at)

A conversation is a list of messages in chronological order. The first user
message in a conversation auto-becomes the title (truncated to ~60 chars).
"""

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "chat.db"


def init_db():
    """Create tables if they don't exist. Idempotent — safe to call on every startup."""
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                created_at  REAL NOT NULL,
                updated_at  REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                debug_json      TEXT,
                created_at      REAL NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                    ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conv
                ON messages(conversation_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_conv_updated
                ON conversations(updated_at DESC);
        """)


@contextmanager
def _conn():
    """Open a connection with foreign keys + row factory enabled."""
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys = ON")
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------
def create_conversation(title: str = "New chat") -> int:
    """Create a new empty conversation and return its id."""
    now = time.time()
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO conversations (title, created_at, updated_at) "
            "VALUES (?, ?, ?)",
            (title, now, now),
        )
        return cur.lastrowid


def list_conversations(limit: int = 50) -> list[dict]:
    """Return [{id, title, updated_at}, ...] ordered by most recent."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, title, created_at, updated_at FROM conversations "
            "ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_conversation(conv_id: int) -> Optional[dict]:
    """Return {id, title, ...} or None."""
    with _conn() as c:
        row = c.execute(
            "SELECT id, title, created_at, updated_at FROM conversations "
            "WHERE id = ?",
            (conv_id,),
        ).fetchone()
        return dict(row) if row else None


def rename_conversation(conv_id: int, new_title: str):
    with _conn() as c:
        c.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (new_title, time.time(), conv_id),
        )


def delete_conversation(conv_id: int):
    """Cascade-deletes messages because of the FK."""
    with _conn() as c:
        c.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))


def conversation_message_count(conv_id: int) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
            (conv_id,),
        ).fetchone()
        return row["n"] if row else 0


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
def add_message(conv_id: int, role: str, content: str,
                debug: Optional[dict] = None) -> int:
    """
    Append a message to a conversation. Updates the conversation's updated_at.
    If this is the first user message in a brand-new conversation titled "New chat",
    auto-rename the conversation using the message content.
    """
    now = time.time()
    debug_str = json.dumps(debug) if debug else None
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO messages "
            "(conversation_id, role, content, debug_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (conv_id, role, content, debug_str, now),
        )
        msg_id = cur.lastrowid

        c.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conv_id),
        )

        # Auto-title
        if role == "user":
            row = c.execute(
                "SELECT title FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            if row and row["title"] == "New chat":
                title = content.strip().replace("\n", " ")
                if len(title) > 60:
                    title = title[:57] + "..."
                c.execute(
                    "UPDATE conversations SET title = ? WHERE id = ?",
                    (title, conv_id),
                )

        return msg_id


def get_messages(conv_id: int) -> list[dict]:
    """Return all messages in a conversation, oldest first."""
    with _conn() as c:
        rows = c.execute(
            "SELECT id, role, content, debug_json, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("debug_json"):
                try:
                    d["debug"] = json.loads(d["debug_json"])
                except (TypeError, ValueError):
                    d["debug"] = None
            else:
                d["debug"] = None
            out.append(d)
        return out


def get_messages_for_llm(conv_id: int, limit_pairs: int = 8) -> list[dict]:
    """
    Return the last N pairs of (user, assistant) messages in OpenAI format,
    suitable for sending as conversation history to the LLM.

    `limit_pairs` controls how much history goes back — keeps prompts short.
    Default 8 pairs ≈ 16 messages, which is plenty for follow-up coherence
    without bloating tokens.
    """
    msgs = get_messages(conv_id)
    if limit_pairs:
        # Keep last 2 * limit_pairs messages (a "pair" is user + assistant)
        msgs = msgs[-(2 * limit_pairs):]
    return [{"role": m["role"], "content": m["content"]} for m in msgs]
