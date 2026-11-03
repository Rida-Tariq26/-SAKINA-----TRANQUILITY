"""
migrate_to_supabase.py — CLI script to migrate existing Sakina data from SQLite to Supabase.

Usage:
    python migrate_to_supabase.py

Prerequisites:
    1. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) in .env or environment.
    2. Run supabase_schema.sql in your Supabase SQL editor to create the tables.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

from database import is_supabase_configured, migrate_sqlite_to_supabase, DB_PATH


def main():
    print("=" * 65)
    print("        Sakina: SQLite to Supabase Migration Utility        ")
    print("=" * 65)

    if not is_supabase_configured():
        print("\n [ERROR] Supabase credentials not found in environment!")
        print(" Please ensure your .env contains:")
        print("   SUPABASE_URL=https://your-project.supabase.co")
        print("   SUPABASE_SERVICE_ROLE_KEY=your_service_role_secret\n")
        sys.exit(1)

    if not os.path.exists(DB_PATH):
        print(f"\n [NOTICE] No local SQLite database found at {DB_PATH}.")
        print(" Nothing to migrate. Your Supabase database is ready to receive new data.\n")
        return

    print(f"\n Found local SQLite database at: {DB_PATH}")
    print(" Connecting to Supabase and transferring records...\n")

    try:
        counts = migrate_sqlite_to_supabase()
        print(" [SUCCESS] Data migration completed successfully!")
        print("-" * 65)
        print(f"   Users Migrated            : {counts.get('users', 0)}")
        print(f"   Mood Logs Migrated        : {counts.get('mood_logs', 0)}")
        print(f"   Journal Entries Migrated  : {counts.get('journal_entries', 0)}")
        print(f"   Feedback/Reviews Migrated : {counts.get('feedback', 0)}")
        print("-" * 65)
        print("\n All existing records are now safely preserved in Supabase cloud storage.\n")
    except Exception as e:
        print(f"\n [ERROR] Migration encountered an error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
