"""
database.py — Hybrid Persistence Layer for Sakina with Field-Level Encryption.

Supports:
  1. Supabase PostgreSQL via official Supabase client (when SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY are set).
  2. Local SQLite fallback (when Supabase credentials are not configured, ideal for local tests & offline dev).
  3. Field-Level AES/Fernet Encryption for sensitive data (journal content, prompts, mood notes).
  4. Complete GDPR/CCPA erasure (scrubbing user records and permanent IDs upon deletion).

Tables:
  users           — Google-authenticated user profiles (user_id = Google sub)
  mood_logs       — Per-user mood entries (isolated per user_id, encrypted notes)
  journal_entries — Per-user private journal reflections (encrypted title/content/prompt)
  feedback        — Public reviews and visitor feedback submissions
"""

import os
import sqlite3
import logging
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from cryptography.fernet import Fernet

logger = logging.getLogger("sakina.database")

# SQLite fallback path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sakina.db")

# Supabase configuration
_SUPABASE_CLIENT = None


# ─────────────────────────────────────────────
# FIELD ENCRYPTION HELPERS
# ─────────────────────────────────────────────
def get_fernet_key() -> bytes:
    """
    Derives or loads a 32-byte URL-safe base64 key for AES-128-CBC / Fernet encryption.
    Uses SAKINA_ENCRYPTION_KEY if provided, or derives from SAKINA_SESSION_SECRET / SECRET_KEY.
    """
    raw_key = os.environ.get("SAKINA_ENCRYPTION_KEY", "").strip()
    if raw_key:
        try:
            Fernet(raw_key.encode())
            return raw_key.encode()
        except Exception:
            pass
    secret = (
        os.environ.get("SAKINA_SESSION_SECRET")
        or os.environ.get("SECRET_KEY")
        or "sakina_default_field_encryption_seed_2026"
    ).encode("utf-8")
    derived = hashlib.sha256(secret + b"::sakina_field_encryption").digest()
    return base64.urlsafe_b64encode(derived)


def encrypt_field(plaintext: Optional[str]) -> str:
    """Encrypt a sensitive plaintext string with Fernet, prefixing with 'enc::'."""
    if plaintext is None:
        return ""
    text = str(plaintext)
    if not text:
        return ""
    try:
        f = Fernet(get_fernet_key())
        token = f.encrypt(text.encode("utf-8")).decode("utf-8")
        return f"enc::{token}"
    except Exception as e:
        logger.error(f"Field encryption error: {e}")
        return text


def decrypt_field(ciphertext: Optional[str]) -> str:
    """
    Decrypt a field if it starts with 'enc::'.
    Gracefully returns raw text if not encrypted, ensuring 100% backward compatibility
    with existing plaintext records.
    """
    if ciphertext is None:
        return ""
    text = str(ciphertext)
    if not text.startswith("enc::"):
        return text
    try:
        f = Fernet(get_fernet_key())
        raw_token = text[5:].encode("utf-8")
        return f.decrypt(raw_token).decode("utf-8")
    except Exception as e:
        logger.warning(f"Field decryption notice (returning legacy raw text): {e}")
        return text[5:]


# ─────────────────────────────────────────────
# SUPABASE CLIENT HELPERS
# ─────────────────────────────────────────────
def is_supabase_configured() -> bool:
    """Check if valid Supabase environment variables are present."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
        or os.environ.get("SUPABASE_ANON_KEY", "").strip()
    )
    return bool(url and key and url.startswith("http"))


def get_supabase_client():
    """Lazily initialize and return the Supabase client singleton."""
    global _SUPABASE_CLIENT
    if _SUPABASE_CLIENT is not None:
        return _SUPABASE_CLIENT

    if not is_supabase_configured():
        return None

    try:
        from supabase import create_client, Client
        url = os.environ.get("SUPABASE_URL", "").strip()
        key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
            or os.environ.get("SUPABASE_ANON_KEY", "").strip()
        )
        _SUPABASE_CLIENT = create_client(url, key)
        logger.info("Connected to Supabase successfully at %s", url)
        return _SUPABASE_CLIENT
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None


# ─────────────────────────────────────────────
# SQLITE CONNECTION HELPER (Fallback & Tests)
# ─────────────────────────────────────────────
def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ─────────────────────────────────────────────
# SCHEMA INIT & HEALTH
# ─────────────────────────────────────────────
def init_db() -> None:
    """Initializes schemas for SQLite or ensures default records exist in Supabase."""
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            try:
                now = datetime.now(timezone.utc).isoformat()
                client.table("users").upsert({
                    "user_id": "default_user",
                    "email": "guest@sakina.local",
                    "name": "Guest User",
                    "picture": "",
                    "created_at": now
                }, on_conflict="user_id", ignore_duplicates=True).execute()
                logger.info("Supabase database verified.")
            except Exception as e:
                logger.warning(f"Notice during Supabase database verification: {e}")
            return

    # Fallback: SQLite schema initialization
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
            is_approved   INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type);
        CREATE INDEX IF NOT EXISTS idx_feedback_ip_created ON feedback(ip_hash, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_feedback_approved ON feedback(is_approved, created_at DESC);
    """)

    # Ensure schema backward compatibility for existing databases
    cols_cursor = conn.execute("PRAGMA table_info(feedback)")
    cols = {row["name"] for row in cols_cursor.fetchall()}
    if "name" not in cols:
        conn.execute("ALTER TABLE feedback ADD COLUMN name TEXT DEFAULT 'Anonymous'")
    if "is_approved" not in cols:
        conn.execute("ALTER TABLE feedback ADD COLUMN is_approved INTEGER NOT NULL DEFAULT 1")

    # Ensure existing submitted feedback/reviews are marked active and published
    conn.execute("UPDATE feedback SET is_approved = 1 WHERE is_approved = 0")

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
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            client.table("users").upsert({
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "created_at": now,
                "deleted_at": None,
            }, on_conflict="user_id").execute()
            return

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
    """Return user dict or None if not found / deleted."""
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("users").select("*").eq("user_id", user_id).is_("deleted_at", "null").execute()
            return dict(res.data[0]) if res.data else None

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE user_id = ? AND deleted_at IS NULL",
        (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─────────────────────────────────────────────
# MOOD LOG OPERATIONS (With Note Encryption)
# ─────────────────────────────────────────────
def add_mood_log(user_id: str, state: str, intensity: int, note: str = "") -> dict:
    """Append a new mood entry for this user with encrypted note and return the record dict."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    encrypted_note = encrypt_field(note)

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            client.table("users").upsert({
                "user_id": user_id,
                "email": "guest@sakina.local",
                "name": "User",
                "picture": "",
                "created_at": now
            }, on_conflict="user_id", ignore_duplicates=True).execute()

            res = client.table("mood_logs").insert({
                "user_id": user_id,
                "timestamp": now,
                "state": state,
                "intensity": intensity,
                "note": encrypted_note
            }).execute()
            row = res.data[0]
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "timestamp": row["timestamp"],
                "state": row["state"],
                "intensity": row["intensity"],
                "note": decrypt_field(row.get("note", "")),
            }

    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, email, name, picture, created_at)
        VALUES (?, 'guest@sakina.local', 'User', '', ?)
    """, (user_id, now))
    cursor = conn.execute("""
        INSERT INTO mood_logs (user_id, timestamp, state, intensity, note)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, now, state, intensity, encrypted_note))
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
    """Return the N most recent mood entries for this user in chronological order (decrypted notes)."""
    user_id = user_id or "default_user"
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("mood_logs").select("*").eq("user_id", user_id).order("timestamp", desc=True).limit(limit).execute()
            data = list(res.data or [])
            data.reverse()
            for r in data:
                r["note"] = decrypt_field(r.get("note", ""))
            return data

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
    result = []
    for r in rows:
        d = dict(r)
        d["note"] = decrypt_field(d.get("note", ""))
        result.append(d)
    return result


def get_all_mood_logs(user_id: str) -> list[dict]:
    """Return all mood entries for this user, oldest first (decrypted notes)."""
    user_id = user_id or "default_user"
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("mood_logs").select("*").eq("user_id", user_id).order("timestamp", desc=False).execute()
            data = list(res.data or [])
            for r in data:
                r["note"] = decrypt_field(r.get("note", ""))
            return data

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mood_logs WHERE user_id = ? ORDER BY timestamp",
        (user_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["note"] = decrypt_field(d.get("note", ""))
        result.append(d)
    return result


def get_mood_logs_since(user_id: str, since_iso: str) -> list[dict]:
    """Return mood entries for this user since a given ISO timestamp/date (decrypted notes)."""
    user_id = user_id or "default_user"
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("mood_logs").select("*").eq("user_id", user_id).gte("timestamp", since_iso).order("timestamp", desc=False).execute()
            data = list(res.data or [])
            for r in data:
                r["note"] = decrypt_field(r.get("note", ""))
            return data

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM mood_logs WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp ASC",
        (user_id, since_iso)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["note"] = decrypt_field(d.get("note", ""))
        result.append(d)
    return result


# ─────────────────────────────────────────────
# JOURNAL OPERATIONS (With Field-Level Encryption)
# ─────────────────────────────────────────────
def add_journal_entry(
    user_id: str,
    title: str,
    content: str,
    mood: str = "",
    prompt: str = ""
) -> dict:
    """Insert a new journal entry with encrypted content, title, and prompt."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    enc_title = encrypt_field(title)
    enc_content = encrypt_field(content)
    enc_prompt = encrypt_field(prompt)

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            client.table("users").upsert({
                "user_id": user_id,
                "email": "guest@sakina.local",
                "name": "User",
                "picture": "",
                "created_at": now
            }, on_conflict="user_id", ignore_duplicates=True).execute()

            res = client.table("journal_entries").insert({
                "user_id": user_id,
                "title": enc_title,
                "content": enc_content,
                "mood": mood,
                "prompt": enc_prompt,
                "created_at": now,
                "updated_at": now,
            }).execute()
            row = res.data[0]
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "title": title,
                "content": content,
                "mood": row.get("mood", ""),
                "prompt": prompt,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    conn = get_db()
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, email, name, picture, created_at)
        VALUES (?, 'guest@sakina.local', 'User', '', ?)
    """, (user_id, now))
    cursor = conn.execute("""
        INSERT INTO journal_entries (user_id, title, content, mood, prompt, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, enc_title, enc_content, mood, enc_prompt, now, now))
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
    """Retrieve and decrypt journal entries with optional search and mood filters."""
    user_id = user_id or "default_user"

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            query = client.table("journal_entries").select("*").eq("user_id", user_id)
            if mood and mood.strip():
                query = query.eq("mood", mood.strip())
            query = query.order("created_at", desc=True)
            res = query.execute()
            raw_entries = list(res.data or [])

            decrypted = []
            for r in raw_entries:
                item = dict(r)
                item["title"] = decrypt_field(item.get("title", ""))
                item["content"] = decrypt_field(item.get("content", ""))
                item["prompt"] = decrypt_field(item.get("prompt", ""))
                if search and search.strip():
                    term = search.strip().lower()
                    if (
                        term not in item["title"].lower()
                        and term not in item["content"].lower()
                        and term not in item["prompt"].lower()
                    ):
                        continue
                decrypted.append(item)
            return decrypted[offset : offset + limit]

    conn = get_db()
    query = "SELECT * FROM journal_entries WHERE user_id = ?"
    params: list[Any] = [user_id]
    if mood and mood.strip():
        query += " AND mood = ?"
        params.append(mood.strip())
    query += " ORDER BY created_at DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    decrypted = []
    for r in rows:
        item = dict(r)
        item["title"] = decrypt_field(item.get("title", ""))
        item["content"] = decrypt_field(item.get("content", ""))
        item["prompt"] = decrypt_field(item.get("prompt", ""))
        if search and search.strip():
            term = search.strip().lower()
            if (
                term not in item["title"].lower()
                and term not in item["content"].lower()
                and term not in item["prompt"].lower()
            ):
                continue
        decrypted.append(item)

    return decrypted[offset : offset + limit]


def get_journal_entry(entry_id: int, user_id: str) -> dict | None:
    """Fetch and decrypt a single journal entry belonging to user_id."""
    user_id = user_id or "default_user"
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("journal_entries").select("*").eq("id", entry_id).eq("user_id", user_id).execute()
            if not res.data:
                return None
            item = dict(res.data[0])
            item["title"] = decrypt_field(item.get("title", ""))
            item["content"] = decrypt_field(item.get("content", ""))
            item["prompt"] = decrypt_field(item.get("prompt", ""))
            return item

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM journal_entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    ).fetchone()
    conn.close()
    if not row:
        return None
    item = dict(row)
    item["title"] = decrypt_field(item.get("title", ""))
    item["content"] = decrypt_field(item.get("content", ""))
    item["prompt"] = decrypt_field(item.get("prompt", ""))
    return item


def update_journal_entry(
    entry_id: int,
    user_id: str,
    title: str,
    content: str,
    mood: str = "",
    prompt: str = ""
) -> dict | None:
    """Update and re-encrypt an existing journal entry for user_id."""
    user_id = user_id or "default_user"
    now = datetime.now(timezone.utc).isoformat()
    enc_title = encrypt_field(title)
    enc_content = encrypt_field(content)
    enc_prompt = encrypt_field(prompt)

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("journal_entries").update({
                "title": enc_title,
                "content": enc_content,
                "mood": mood,
                "prompt": enc_prompt,
                "updated_at": now,
            }).eq("id", entry_id).eq("user_id", user_id).execute()
            if not res.data:
                return None
            return get_journal_entry(entry_id, user_id)

    conn = get_db()
    cursor = conn.execute("""
        UPDATE journal_entries
        SET title = ?, content = ?, mood = ?, prompt = ?, updated_at = ?
        WHERE id = ? AND user_id = ?
    """, (enc_title, enc_content, mood, enc_prompt, now, entry_id, user_id))
    conn.commit()
    rows_affected = cursor.rowcount
    conn.close()
    if rows_affected == 0:
        return None
    return get_journal_entry(entry_id, user_id)


def delete_journal_entry(entry_id: int, user_id: str) -> bool:
    """Delete a journal entry belonging to user_id."""
    user_id = user_id or "default_user"
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("journal_entries").delete().eq("id", entry_id).eq("user_id", user_id).execute()
            return len(res.data) > 0 if res.data else False

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
# DATA EXPORT (GDPR / CCPA)
# ─────────────────────────────────────────────
def export_user_data(user_id: str) -> dict:
    """Return all user data as a decrypted, human-readable serialisable dict."""
    user_row = get_user(user_id)
    log_rows = get_all_mood_logs(user_id)
    journal_rows = get_journal_entries(user_id, limit=1000)
    return {
        "exported_at":     datetime.now(timezone.utc).isoformat(),
        "user":            user_row,
        "mood_logs":       log_rows,
        "journal_entries": journal_rows,
    }


# ─────────────────────────────────────────────
# DATA DELETION (Complete Right to Erasure)
# ─────────────────────────────────────────────
def delete_user_data(user_id: str) -> None:
    """
    Permanently delete the user's mood logs, journal entries, and remove the
    user record and Google sub identifier completely from the system.
    """
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            user = get_user(user_id)
            user_email = user.get("email") if user and user.get("email") and not user.get("email", "").startswith("[deleted]") else None

            client.table("mood_logs").delete().eq("user_id", user_id).execute()
            client.table("journal_entries").delete().eq("user_id", user_id).execute()
            if user_email:
                client.table("feedback").update({"email": "[redacted]"}).ilike("email", user_email).execute()

            # Permanent erasure: Remove user record completely
            client.table("users").delete().eq("user_id", user_id).execute()
            return

    conn = get_db()
    user_row = conn.execute("SELECT email FROM users WHERE user_id = ?", (user_id,)).fetchone()
    user_email = user_row["email"] if user_row and user_row["email"] and not user_row["email"].startswith("[deleted]") else None

    conn.execute("DELETE FROM mood_logs WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM journal_entries WHERE user_id = ?", (user_id,))
    if user_email:
        conn.execute("UPDATE feedback SET email = '[redacted]' WHERE lower(email) = lower(?)", (user_email,))
    
    # Permanent erasure: Remove user record completely
    conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# VISITOR FEEDBACK & REVIEWS OPERATIONS
# ─────────────────────────────────────────────
def add_feedback(
    feedback_type: str = "review",
    message: str = "",
    rating: Optional[int] = None,
    name: Optional[str] = "Anonymous",
    email: Optional[str] = None,
    ip_hash: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_approved: int = 1,
) -> dict:
    """Insert a visitor feedback or review record and return the created record metadata."""
    now = datetime.now(timezone.utc).isoformat()
    cleaned_name = (name or "Anonymous").strip() or "Anonymous"

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("feedback").insert({
                "feedback_type": feedback_type,
                "rating": rating,
                "message": message,
                "name": cleaned_name,
                "email": email,
                "ip_hash": ip_hash,
                "user_agent": user_agent,
                "is_approved": is_approved,
                "created_at": now,
            }).execute()
            row = res.data[0] if res.data else {}
            return {
                "id": row.get("id"),
                "feedback_type": feedback_type,
                "rating": rating,
                "name": cleaned_name,
                "is_approved": is_approved,
                "created_at": now,
            }

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
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=window_seconds)).isoformat()

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("feedback").select("id", count="exact").eq("ip_hash", ip_hash).gte("created_at", cutoff).execute()
            return res.count or 0

    conn = get_db()
    row = conn.execute("""
        SELECT COUNT(*) AS count FROM feedback
        WHERE ip_hash = ? AND created_at >= ?
    """, (ip_hash, cutoff)).fetchone()
    conn.close()
    return int(row["count"]) if row else 0


def approve_feedback(feedback_id: int, is_approved: int = 1) -> bool:
    """Approve or reject a review for public display."""
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("feedback").update({
                "is_approved": 1 if is_approved else 0
            }).eq("id", feedback_id).execute()
            return len(res.data) > 0 if res.data else False

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
    Retrieve reviews for public display.
    Excludes private data (email, ip_hash, user_agent).
    Calculates overall average rating and total count of published reviews.
    """
    limit = min(max(1, limit), 50)
    offset = max(0, offset)

    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res_stats = client.table("feedback").select("rating", count="exact").eq("is_approved", 1).not_.is_("rating", "null").execute()
            total_reviews = res_stats.count or 0
            ratings = [r["rating"] for r in (res_stats.data or []) if r.get("rating") is not None]
            avg_rating = round(float(sum(ratings) / len(ratings)), 1) if ratings else 0.0

            res_rows = client.table("feedback").select("id, name, rating, message, created_at")\
                .eq("is_approved", 1).not_.is_("rating", "null")\
                .order("created_at", desc=True).order("id", desc=True)\
                .range(offset, offset + limit - 1).execute()

            reviews = []
            for r in (res_rows.data or []):
                reviews.append({
                    "id": r["id"],
                    "name": r.get("name") or "Anonymous",
                    "rating": r.get("rating"),
                    "message": r.get("message"),
                    "created_at": r.get("created_at"),
                })

            return {
                "average_rating": avg_rating,
                "total_reviews": total_reviews,
                "reviews": reviews,
            }

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
        WHERE is_approved = 1 AND rating IS NOT NULL
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
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            query = client.table("feedback").select("id, feedback_type, rating, message, name, email, is_approved, created_at")
            if status == "approved":
                query = query.eq("is_approved", 1)
            elif status == "pending":
                query = query.eq("is_approved", 0)
            query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
            res = query.execute()
            return list(res.data or [])

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
    if is_supabase_configured():
        client = get_supabase_client()
        if client:
            res = client.table("feedback").select("id", count="exact").eq("is_approved", 1).limit(1).execute()
            count = res.count or 0
            if count == 0:
                samples = [
                    ("review", 5, "Sakina brings a soothing rhythm of dhikr and mindfulness into my busy day. Truly calming.", "Amina K.", 1),
                    ("review", 5, "The grounding exercises and Ilm al-Nafs perspectives provide clarity during moments of overwhelm.", "Tariq S.", 1),
                    ("review", 5, "Beautifully designed, minimalist, and serene. It feels like a quiet sanctuary.", "Anonymous", 1),
                ]
                now = datetime.now(timezone.utc).isoformat()
                for fb_type, rating, msg, name, apprv in samples:
                    client.table("feedback").insert({
                        "feedback_type": fb_type,
                        "rating": rating,
                        "message": msg,
                        "name": name,
                        "is_approved": apprv,
                        "created_at": now,
                    }).execute()
            return

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


# ─────────────────────────────────────────────
# MIGRATION UTILITY: SQLITE -> SUPABASE
# ─────────────────────────────────────────────
def migrate_sqlite_to_supabase() -> dict:
    """
    Reads existing records from local SQLite (sakina.db) and safely
    migrates them into Supabase, preserving all existing user data.
    """
    if not is_supabase_configured():
        raise RuntimeError("Supabase credentials not configured in environment (SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY).")

    if not os.path.exists(DB_PATH):
        return {"users": 0, "mood_logs": 0, "journal_entries": 0, "feedback": 0, "status": "No local sakina.db found"}

    client = get_supabase_client()
    if not client:
        raise RuntimeError("Failed to obtain Supabase client.")

    conn = get_db()
    counts = {"users": 0, "mood_logs": 0, "journal_entries": 0, "feedback": 0}

    # 1. Users
    user_rows = conn.execute("SELECT * FROM users").fetchall()
    for u in user_rows:
        client.table("users").upsert({
            "user_id": u["user_id"],
            "email": u["email"],
            "name": u["name"],
            "picture": u["picture"],
            "created_at": u["created_at"],
            "deleted_at": u["deleted_at"],
        }, on_conflict="user_id").execute()
        counts["users"] += 1

    # 2. Mood Logs
    mood_rows = conn.execute("SELECT * FROM mood_logs").fetchall()
    for m in mood_rows:
        # Preserve encrypted note or encrypt if legacy plaintext
        note = m["note"] or ""
        enc_note = note if note.startswith("enc::") else encrypt_field(note)
        client.table("mood_logs").insert({
            "user_id": m["user_id"],
            "timestamp": m["timestamp"],
            "state": m["state"],
            "intensity": m["intensity"],
            "note": enc_note,
        }).execute()
        counts["mood_logs"] += 1

    # 3. Journal Entries
    journal_rows = conn.execute("SELECT * FROM journal_entries").fetchall()
    for j in journal_rows:
        title = j["title"] or ""
        content = j["content"] or ""
        prompt = j["prompt"] or ""
        enc_title = title if title.startswith("enc::") else encrypt_field(title)
        enc_content = content if content.startswith("enc::") else encrypt_field(content)
        enc_prompt = prompt if prompt.startswith("enc::") else encrypt_field(prompt)
        client.table("journal_entries").insert({
            "user_id": j["user_id"],
            "title": enc_title,
            "content": enc_content,
            "mood": j["mood"] or "",
            "prompt": enc_prompt,
            "created_at": j["created_at"],
            "updated_at": j["updated_at"],
        }).execute()
        counts["journal_entries"] += 1

    # 4. Feedback / Reviews
    feedback_rows = conn.execute("SELECT * FROM feedback").fetchall()
    for f in feedback_rows:
        client.table("feedback").insert({
            "feedback_type": f["feedback_type"],
            "rating": f["rating"],
            "message": f["message"],
            "name": f["name"] or "Anonymous",
            "email": f["email"],
            "ip_hash": f["ip_hash"],
            "user_agent": f["user_agent"],
            "is_approved": f["is_approved"],
            "created_at": f["created_at"],
        }).execute()
        counts["feedback"] += 1

    conn.close()
    return counts
