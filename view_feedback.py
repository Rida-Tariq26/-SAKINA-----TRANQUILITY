"""
view_feedback.py — Secure Administrative CLI tool to view, approve, and manage feedback & public reviews.

Usage:
    python view_feedback.py [--limit N] [--type TYPE] [--status {all,pending,approved}]
    python view_feedback.py --approve <ID>
    python view_feedback.py --reject <ID>
"""

import sys
import argparse
from datetime import datetime
from database import get_feedback_submissions, get_db, approve_feedback

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

    conn = get_db()
    
    # Summary statistics
    total_count = conn.execute("SELECT COUNT(*) AS total FROM feedback").fetchone()["total"]
    approved_count = conn.execute("SELECT COUNT(*) AS approved FROM feedback WHERE is_approved = 1").fetchone()["approved"]
    pending_count = conn.execute("SELECT COUNT(*) AS pending FROM feedback WHERE is_approved = 0").fetchone()["pending"]
    avg_rating_row = conn.execute("SELECT AVG(rating) AS avg_r FROM feedback WHERE rating IS NOT NULL AND is_approved = 1").fetchone()
    avg_rating = round(avg_rating_row["avg_r"], 2) if avg_rating_row["avg_r"] is not None else "N/A"
    
    type_counts = conn.execute(
        "SELECT feedback_type, COUNT(*) AS c FROM feedback GROUP BY feedback_type"
    ).fetchall()

    print("\n" + "=" * 65)
    print("        Sakina Administrative Feedback & Review Dashboard        ")
    print("=" * 65)
    print(f" Total Submissions     : {total_count}")
    print(f" Approved (Public)     : {approved_count}")
    print(f" Pending Moderation    : {pending_count}")
    print(f" Approved Avg Rating   : {avg_rating} / 5")
    print(" Breakdown by Type     :")
    for row in type_counts:
        print(f"   - {row['feedback_type'].capitalize():14}: {row['c']}")
    print("-" * 65)

    if total_count == 0:
        print(" No feedback or review records found.\n")
        conn.close()
        return

    # Fetch records
    query = "SELECT id, feedback_type, rating, message, name, email, is_approved, created_at FROM feedback WHERE 1=1"
    params = []
    if args.type:
        query += " AND feedback_type = ?"
        params.append(args.type.lower())
    if args.status == "approved":
        query += " AND is_approved = 1"
    elif args.status == "pending":
        query += " AND is_approved = 0"
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([args.limit, args.offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    print(f"\n Displaying {len(rows)} record(s) [Filter: status={args.status}]:\n")
    for r in rows:
        rating_display = f"{r['rating']}/5" if r['rating'] else "Not rated"
        author_display = r['name'] if r['name'] else "Anonymous"
        email_display = r['email'] if r['email'] else "(None)"
        mod_status = "[APPROVED - PUBLIC]" if r['is_approved'] == 1 else "[PENDING APPROVAL]"
        
        print(f" [ID #{r['id']}] {r['created_at']} | {mod_status}")
        print(f" Type: {r['feedback_type'].upper()} | Rating: {rating_display} | Author: {author_display}")
        print(f" Email: {email_display}")
        print(f" Message:\n   {r['message']}")
        print("-" * 65)
    print("\nTip: To publish a review, run: python view_feedback.py --approve <ID>")
    print("Tip: To unpublish/reject, run: python view_feedback.py --reject <ID>\n")

if __name__ == "__main__":
    main()
