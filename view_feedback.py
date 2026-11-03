"""
view_feedback.py — Secure Administrative CLI tool to view, approve, and manage feedback & public reviews.

Supports both Supabase cloud database and local SQLite storage.

Usage:
    python view_feedback.py [--limit N] [--type TYPE] [--status {all,pending,approved}]
    python view_feedback.py --approve <ID>
    python view_feedback.py --reject <ID>
"""

import sys
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from database import (
    get_feedback_submissions, get_db, approve_feedback,
    is_supabase_configured, get_supabase_client
)


def main():
    parser = argparse.ArgumentParser(description="Sakina Secure Feedback & Review Manager (Admin CLI)")
    parser.add_argument("--limit", type=int, default=50, help="Number of records to display (default: 50)")
    parser.add_argument("--offset", type=int, default=0, help="Offset for pagination (default: 0)")
    parser.add_argument("--type", type=str, default="", help="Filter by feedback type (general, feature, bug, experience, review)")
    parser.add_argument("--status", type=str, default="all", choices=["all", "pending", "approved"], help="Filter by moderation status")
    parser.add_argument("--approve", type=int, default=None, help="Approve feedback/review ID for public display")
    parser.add_argument("--reject", type=int, default=None, help="Reject / hide feedback/review ID from public display")
    args = parser.parse_args()

    # Handle single action: approve
    if args.approve is not None:
        success = approve_feedback(args.approve, is_approved=1)
        if success:
            print(f"\n [SUCCESS] Review #{args.approve} has been APPROVED and is now publicly visible on the landing page.\n")
        else:
            print(f"\n [ERROR] Record #{args.approve} not found.\n")
        return

    # Handle single action: reject
    if args.reject is not None:
        success = approve_feedback(args.reject, is_approved=0)
        if success:
            print(f"\n [SUCCESS] Review #{args.reject} has been REJECTED / hidden from public display.\n")
        else:
            print(f"\n [ERROR] Record #{args.reject} not found.\n")
        return

    # Statistics & reporting
    backend_mode = "Supabase Cloud" if is_supabase_configured() else "Local SQLite"

    if is_supabase_configured():
        client = get_supabase_client()
        res_total = client.table("feedback").select("id", count="exact").execute()
        total_count = res_total.count or 0

        res_approved = client.table("feedback").select("id", count="exact").eq("is_approved", 1).execute()
        approved_count = res_approved.count or 0

        res_pending = client.table("feedback").select("id", count="exact").eq("is_approved", 0).execute()
        pending_count = res_pending.count or 0

        res_ratings = client.table("feedback").select("rating").eq("is_approved", 1).not_.is_("rating", "null").execute()
        ratings = [r["rating"] for r in (res_ratings.data or []) if r.get("rating") is not None]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else "N/A"

        res_all_types = client.table("feedback").select("feedback_type").execute()
        type_counts = {}
        for r in (res_all_types.data or []):
            ft = r.get("feedback_type", "other")
            type_counts[ft] = type_counts.get(ft, 0) + 1
        type_summary = [{"feedback_type": k, "c": v} for k, v in type_counts.items()]
    else:
        conn = get_db()
        total_count = conn.execute("SELECT COUNT(*) AS total FROM feedback").fetchone()["total"]
        approved_count = conn.execute("SELECT COUNT(*) AS approved FROM feedback WHERE is_approved = 1").fetchone()["approved"]
        pending_count = conn.execute("SELECT COUNT(*) AS pending FROM feedback WHERE is_approved = 0").fetchone()["pending"]
        avg_rating_row = conn.execute("SELECT AVG(rating) AS avg_r FROM feedback WHERE rating IS NOT NULL AND is_approved = 1").fetchone()
        avg_rating = round(avg_rating_row["avg_r"], 2) if avg_rating_row["avg_r"] is not None else "N/A"
        type_counts_rows = conn.execute(
            "SELECT feedback_type, COUNT(*) AS c FROM feedback GROUP BY feedback_type"
        ).fetchall()
        type_summary = [dict(r) for r in type_counts_rows]
        conn.close()

    print("\n" + "=" * 65)
    print(f"   Sakina Feedback & Review Dashboard ({backend_mode})   ")
    print("=" * 65)
    print(f" Storage Backend       : {backend_mode}")
    print(f" Total Submissions     : {total_count}")
    print(f" Public Reviews        : {approved_count}")
    print(f" Hidden Submissions    : {pending_count}")
    print(f" Public Avg Rating     : {avg_rating} / 5")
    print(" Breakdown by Type     :")
    for row in type_summary:
        print(f"   - {row['feedback_type'].capitalize():14}: {row['c']}")
    print("-" * 65)

    if total_count == 0:
        print(" No feedback or review records found.\n")
        return

    # Fetch records
    status_filter = None if args.status == "all" else args.status
    records = get_feedback_submissions(limit=args.limit, offset=args.offset, status=status_filter)
    if args.type:
        records = [r for r in records if r.get("feedback_type", "").lower() == args.type.lower()]

    print(f"\n Displaying {len(records)} record(s) [Filter: status={args.status}]:\n")
    for r in records:
        rating_display = f"{r['rating']}/5" if r.get('rating') else "Not rated"
        author_display = r['name'] if r.get('name') else "Anonymous"
        email_display = r['email'] if r.get('email') else "(None)"
        mod_status = "[PUBLIC]" if r.get('is_approved') == 1 else "[HIDDEN]"

        print(f" [ID #{r['id']}] {r['created_at']} | {mod_status}")
        print(f" Type: {r['feedback_type'].upper()} | Rating: {rating_display} | Author: {author_display}")
        print(f" Email: {email_display}")
        print(f" Message:\n   {r['message']}")
        print("-" * 65)


if __name__ == "__main__":
    main()
