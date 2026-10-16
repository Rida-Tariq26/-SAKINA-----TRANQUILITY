"""
database.py — SQLite persistence layer for Sakina.

Tables:
  users      — Google-authenticated user profiles (user_id = Google sub)
  mood_logs  — Per-user mood entries (replaces mood_log.json for data management)

The SQLite database is authoritative for both MCP agent tools and user data management,
ensuring strict per-user session and data isolation across all operations.
This DB is authoritative for user data export / deletion (GDPR / CCPA).
"""

import sqlite3
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

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

        CREATE TABLE IF NOT EXISTS feedback (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            feedback_type TEXT    NOT NULL DEFAULT 'review',
            rating        INTEGER,
            message       TEXT    NOT NULL,
            name          TEXT    DEFAULT 'Anonymous',
            email         TEXT,
            ip_hash       TEXT,
            user_agent    TEXT,
            is_approved   INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);
        CREATE INDEX IF NOT EXISTS idx_feedback_ip_created ON feedback(ip_hash, created_at DESC);
    """)

    # Ensure schema backward compatibility for existing databases
    cols_cursor = conn.execute("PRAGMA table_info(feedback)")
    cols = {row["name"] for row in cols_cursor.fetchall()}
    if "name" not in cols:
        conn.execute("ALTER TABLE feedback ADD COLUMN name TEXT DEFAULT 'Anonymous'")
    if "is_approved" not in cols:
        conn.execute("ALTER TABLE feedback ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 0")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_approved ON feedback(is_approved, created_at DESC)")

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
    # Fetch user's email before redaction to scrub any matching feedback emails
    user_row = conn.execute("SELECT email FROM users WHERE user_id = ?", (user_id,)).fetchone()
    user_email = user_row["email"] if user_row and user_row["email"] and not user_row["email"].startswith("[deleted]") else None

    conn.execute("DELETE FROM mood_logs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM journal_entries WHERE user_id = ?", (user_id,))
    if user_email:
        conn.execute("UPDATE feedback SET email = '[redacted]' WHERE lower(email) = lower(?)", (user_email,))
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


# ─────────────────────────────────────────────
# VISITOR FEEDBACK OPERATIONS
# ─────────────────────────────────────────────
def add_feedback(
    feedback_type: str = "review",
    message: str = "",
    rating: Optional[int] = None,
    name: Optional[str] = "Anonymous",
    email: Optional[str] = None,
    ip_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_approved: int = 0,
) -> dict:
    """Insert a visitor feedback or review record and return the created record metadata."""
    now = datetime.now(timezone.utc).isoformat()
    cleaned_name = (name or "Anonymous").strip() or "Anonymous"
    conn = get_db()
    cursor = conn.execute("""
        INSERT INTO feedback (feedback_type, rating, message, name, email, ip_hash, user_agent, is_approved, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (feedback_type, rating, message, cleaned_name, email, ip_hash, user_agent, is_approved, now))
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": entry_id,
        "feedback_type": feedback_type,
        "rating": rating,
        "name": cleaned_name,
        "is_approved": is_approved,
        "created_at": now,
    }


def count_recent_feedback_by_ip(ip_hash: str, window_seconds: int = 3600) -> int:
    """Count feedback entries created by ip_hash within the specified window in seconds."""
    if not ip_hash:
        return 0
    conn = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()
    row = conn.execute("""
        SELECT COUNT(*) AS count FROM feedback
        WHERE ip_hash = ? AND created_at >= ?
    """, (ip_hash, cutoff)).fetchone()
    conn.close()
    return int(row["count"]) if row else 0


def approve_feedback(feedback_id: int, is_approved: int = 1) -> bool:
    """Approve or reject a review for public display."""
    conn = get_db()
    cursor = conn.execute("""
        UPDATE feedback
        SET is_approved = ?
        WHERE id = ?
    """, (1 if is_approved else 0, feedback_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def get_public_reviews(limit: int = 10, offset: int = 0) -> dict:
    """
    Retrieve only approved reviews for public display.
    Excludes private data (email, ip_hash, user_agent).
    Calculates overall average rating and total count of published reviews.
    """
    limit = min(max(1, limit), 50)
    offset = max(0, offset)
    conn = get_db()

    stats = conn.execute("""
        SELECT 
            COUNT(*) AS total_reviews,
            AVG(rating) AS avg_rating
        FROM feedback
        WHERE is_approved = 1 AND rating IS NOT NULL
    """).fetchone()

    total_reviews = int(stats["total_reviews"]) if stats and stats["total_reviews"] else 0
    raw_avg = stats["avg_rating"] if stats and stats["avg_rating"] is not None else 0.0
    avg_rating = round(float(raw_avg), 1)

    rows = conn.execute("""
        SELECT id, name, rating, message, created_at
        FROM feedback
        WHERE is_approved = 1
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()

    conn.close()

    reviews = []
    for r in rows:
        reviews.append({
            "id": r["id"],
            "name": r["name"] or "Anonymous",
            "rating": r["rating"],
            "message": r["message"],
            "created_at": r["created_at"],
        })

    return {
        "average_rating": avg_rating,
        "total_reviews": total_reviews,
        "reviews": reviews,
    }


def get_feedback_submissions(limit: int = 50, offset: int = 0, status: Optional[str] = None) -> list[dict]:
    """Return recent feedback entries for secure internal / admin auditing."""
    conn = get_db()
    query = """
        SELECT id, feedback_type, rating, message, name, email, is_approved, created_at
        FROM feedback
    """
    params = []
    if status == "approved":
        query += " WHERE is_approved = 1"
    elif status == "pending":
        query += " WHERE is_approved = 0"
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def seed_sample_reviews_if_empty():
    """Seed peaceful initial reviews if the feedback table has no approved reviews."""
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) AS c FROM feedback WHERE is_approved = 1").fetchone()["c"]
    if count == 0:
        samples = [
            ("review", 5, "Sakina brings a soothing rhythm of dhikr and mindfulness into my busy day. Truly calming.", "Amina K.", 1),
            ("review", 5, "The grounding exercises and Ilm al-Nafs perspectives provide clarity during moments of overwhelm.", "Tariq S.", 1),
            ("review", 5, "Beautifully designed, minimalist, and serene. It feels like a quiet sanctuary.", "Anonymous", 1),
        ]
        now = datetime.now(timezone.utc).isoformat()
        for fb_type, rating, msg, name, apprv in samples:
            conn.execute("""
                INSERT INTO feedback (feedback_type, rating, message, name, is_approved, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fb_type, rating, msg, name, apprv, now))
        conn.commit()
    conn.close()


