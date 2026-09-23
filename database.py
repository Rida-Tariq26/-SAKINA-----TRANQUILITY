"""
database.py — SQLite persistence layer for Sakina.

Tables:
  users      — Google-authenticated user profiles (user_id = Google sub)
  mood_logs  — Per-user mood entries (replaces mood_log.json for data management)

The MCP server's mood_log.json is kept for AI agent memory.
This DB is authoritative for user data export / deletion (GDPR / CCPA).
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Any

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sakina.db")


# ─────────────────────────────────────────────
# CONNECTION HELPER
# ─────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# SCHEMA INIT (called once on app startup)
# ─────────────────────────────────────────────
def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    TEXT PRIMARY KEY,
            email      TEXT NOT NULL,
            name       TEXT,
            picture    TEXT,
            created_at TEXT NOT NULL,
            deleted_at TEXT
        );

        CREATE TABLE IF NOT EXISTS mood_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT    NOT NULL,
            timestamp  TEXT    NOT NULL,
            state      TEXT    NOT NULL,
            intensity  INTEGER NOT NULL,
            note       TEXT    DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT    NOT NULL,
            title      TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            mood       TEXT    DEFAULT '',
            prompt     TEXT    DEFAULT '',
            created_at TEXT    NOT NULL,
            updated_at TEXT    NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_mood_user ON mood_logs(user_id);
        CREATE INDEX IF NOT EXISTS idx_mood_user_timestamp ON mood_logs(user_id, timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_journal_user ON journal_entries(user_id);
        CREATE INDEX IF NOT EXISTS idx_journal_user_created ON journal_entries(user_id, created_at DESC);
    """)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, email, name, picture, created_at)
        VALUES ('default_user', 'guest@sakina.local', 'Guest User', '', ?)
    """, (now,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# USER OPERATIONS
# ─────────────────────────────────────────────
def upsert_user(user_id: str, email: str, name: str, picture: str) -> None:
    """Insert a new user or update profile info on re-login."""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("""
        INSERT INTO users (user_id, email, name, picture, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            email      = excluded.email,
            name       = excluded.name,
            picture    = excluded.picture,
            deleted_at = NULL
    """, (user_id, email, name, picture, now))
    conn.commit()
    conn.close()


def get_user(user_id: str) -> dict | None:
    """Return user dict or None if not found / already deleted."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE user_id = ? AND deleted_at IS NULL",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# MOOD LOG OPERATIONS
# ─────────────────────────────────────────────
def add_mood_log(user_id: str, state: str, intensity: int, note: str = "") -> dict:
    """Append a new mood entry for this user and return the record dict."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, email, name, picture, created_at)
        VALUES (?, 'guest@sakina.local', 'User', '', ?)
    """, (user_id, now))
    cursor = conn.execute("""
        INSERT INTO mood_logs (user_id, timestamp, state, intensity, note)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, now, state, intensity, note))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": entry_id,
        "user_id": user_id,
        "timestamp": now,
        "state": state,
        "intensity": intensity,
        "note": note,
    }


def get_recent_mood_logs(user_id: str, limit: int = 7) -> list[dict]:
    """Return the N most recent mood entries for this user in chronological order."""
    user_id = user_id or "default_user"
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM (
            SELECT * FROM mood_logs
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ) ORDER BY timestamp ASC
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_mood_logs(user_id: str) -> list[dict]:
    """Return all mood entries for this user, oldest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mood_logs WHERE user_id = ? ORDER BY timestamp",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_mood_logs_since(user_id: str, since_iso: str) -> list[dict]:
    """Return mood entries for this user since a given ISO timestamp/date, ordered chronologically."""
    user_id = user_id or "default_user"
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mood_logs WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
        (user_id, since_iso)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# JOURNAL OPERATIONS
# ─────────────────────────────────────────────
def add_journal_entry(
    user_id: str,
    title: str,
    content: str,
    mood: str = "",
    prompt: str = ""
) -> dict:
    """Insert a new journal entry for the user and return the full dict."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, email, name, picture, created_at)
        VALUES (?, 'guest@sakina.local', 'User', '', ?)
    """, (user_id, now))
    cursor = conn.execute("""
        INSERT INTO journal_entries (user_id, title, content, mood, prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, title, content, mood, prompt, now, now))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": entry_id,
        "user_id": user_id,
        "title": title,
        "content": content,
        "mood": mood,
        "prompt": prompt,
        "created_at": now,
        "updated_at": now,
    }


def get_journal_entries(
    user_id: str,
    search: str = "",
    mood: str = "",
    limit: int = 100,
    offset: int = 0
) -> list[dict]:
    """Retrieve journal entries with optional search and mood filters, newest first."""
    user_id = user_id or "default_user"
    conn = get_db()
    query = "SELECT * FROM journal_entries WHERE user_id = ?"
    params: list[Any] = [user_id]

    if mood and mood.strip():
        query += " AND mood = ?"
        params.append(mood.strip())

    if search and search.strip():
        query += " AND (title LIKE ? OR content LIKE ? OR prompt LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_journal_entry(entry_id: int, user_id: str) -> dict | None:
    """Fetch a single journal entry belonging to user_id."""
    user_id = user_id or "default_user"
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_journal_entry(
    entry_id: int,
    user_id: str,
    title: str,
    content: str,
    mood: str = "",
    prompt: str = ""
) -> dict | None:
    """Update an existing journal entry for user_id."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cursor = conn.execute("""
        UPDATE journal_entries
        SET title = ?, content = ?, mood = ?, prompt = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
    """, (title, content, mood, prompt, now, entry_id, user_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    if rows_affected == 0:
        return None
    return get_journal_entry(entry_id, user_id)


def delete_journal_entry(entry_id: int, user_id: str) -> bool:
    """Delete a journal entry belonging to user_id."""
    user_id = user_id or "default_user"
    conn = get_db()
    cursor = conn.execute(
        "DELETE FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted


# ─────────────────────────────────────────────
# DATA EXPORT (GDPR / CCPA — right to portability)
# ─────────────────────────────────────────────
def export_user_data(user_id: str) -> dict:
    """Return all user data as a serialisable dict."""
    conn = get_db()
    user_row = conn.execute(
        "SELECT * FROM users WHERE user_id = ?", (user_id,)
    ).fetchone()
    log_rows = conn.execute(
        "SELECT * FROM mood_logs WHERE user_id = ? ORDER BY timestamp",
        (user_id,)
    ).fetchall()
    journal_rows = conn.execute(
        "SELECT * FROM journal_entries WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()

    return {
        "exported_at":     datetime.now(timezone.utc).isoformat(),
        "user":            dict(user_row) if user_row else None,
        "mood_logs":       [dict(r) for r in log_rows],
        "journal_entries": [dict(r) for r in journal_rows],
    }


# ─────────────────────────────────────────────
# DATA DELETION (GDPR / CCPA — right to erasure)
# ─────────────────────────────────────────────
def delete_user_data(user_id: str) -> None:
    """
    Permanently delete the user's mood logs and journal entries,
    and anonymise the user record.
    """
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    conn.execute("DELETE FROM mood_logs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM journal_entries WHERE user_id = ?", (user_id,))
    conn.execute("""
        UPDATE users
        SET email      = '[deleted]',
            name       = '[deleted]',
            picture    = NULL,
            deleted_at = ?
        WHERE user_id  = ?
    """, (now, user_id))
    conn.commit()
    conn.close()

