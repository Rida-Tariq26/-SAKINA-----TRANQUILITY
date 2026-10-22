"""
test_feedback.py

Comprehensive test suite verifying Sakina's feedback system:
1. SQLite persistent data storage and querying
2. Input validation (required fields, bounds, allowed types)
3. Optional fields (rating, email)
4. Honeypot spam defense
5. Rate limiting per IP hash
6. Privacy & unauthorized public retrieval prevention
7. Administrative retrieval authorization
8. CORS headers and deployment compatibility
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import pytest
import sqlite3
import hashlib
from httpx import AsyncClient, ASGITransport

from database import (
    init_db, get_db,
    add_feedback, count_recent_feedback_by_ip, get_feedback_submissions,
    upsert_user, delete_user_data,
)
from FrontendAPI import app


@pytest.fixture(autouse=True)
def setup_clean_db():
    """Ensure database schema is fresh and clean before each test run."""
    init_db()
    conn = get_db()
    conn.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()
    yield
    conn = get_db()
    conn.execute("DELETE FROM feedback")
    conn.commit()
    conn.close()


class TestFeedbackPersistence:
    """Tests for direct database operations in database.py"""

    def test_add_and_retrieve_feedback(self):
        result = add_feedback(
            feedback_type="general",
            message="Sakina has been deeply calming and helpful for my daily reflections.",
            rating=5,
            email="visitor@example.com",
            ip_hash="testhash12345",
            user_agent="pytest-client",
        )
        assert result["id"] is not None
        assert result["feedback_type"] == "general"
        assert result["rating"] == 5

        submissions = get_feedback_submissions(limit=10)
        assert len(submissions) == 1
        sub = submissions[0]
        assert sub["feedback_type"] == "general"
        assert sub["rating"] == 5
        assert "calming and helpful" in sub["message"]
        assert sub["email"] == "visitor@example.com"

    def test_optional_fields_allow_null(self):
        result = add_feedback(
            feedback_type="feature",
            message="Please consider adding an audio recitation speed control.",
            rating=None,
            email=None,
            ip_hash=None,
            user_agent=None,
        )
        assert result["id"] is not None
        submissions = get_feedback_submissions(limit=10)
        assert len(submissions) == 1
        sub = submissions[0]
        assert sub["rating"] is None
        assert sub["email"] is None

    def test_rate_limiting_ip_count(self):
        ip_hash = "rate_limit_ip_hash_abc"
        # Initially 0
        assert count_recent_feedback_by_ip(ip_hash, window_seconds=3600) == 0

        # Add 3 entries
        for i in range(3):
            add_feedback(
                feedback_type="bug",
                message=f"Found bug number {i} in the timer screen.",
                ip_hash=ip_hash,
            )

        assert count_recent_feedback_by_ip(ip_hash, window_seconds=3600) == 3
        # Different IP hash should remain 0
        assert count_recent_feedback_by_ip("other_hash", window_seconds=3600) == 0

    def test_user_data_erasure_anonymizes_matching_feedback_email(self):
        user_id = "test_user_privacy"
        user_email = "privacy_user@sakina.local"
        upsert_user(user_id=user_id, email=user_email, name="Privacy Test", picture="")

        # User submits feedback with their email
        add_feedback(
            feedback_type="experience",
            message="Sharing feedback while using Sakina regularly.",
            email=user_email,
        )

        # Confirm email is saved
        entries = get_feedback_submissions(limit=5)
        assert entries[0]["email"] == user_email

        # User invokes GDPR erasure
        delete_user_data(user_id)

        # Check feedback table: email must be scrubbed / redacted
        updated_entries = get_feedback_submissions(limit=5)
        assert updated_entries[0]["email"] == "[redacted]"


class TestFeedbackAPIEndpoints:
    """Tests for FastAPI HTTP endpoints: /api/feedback and /api/admin/feedback"""

    @pytest.mark.asyncio
    async def test_valid_feedback_submission(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "experience",
                "message": "The dhikr grounding exercises brought genuine peace to my afternoon.",
                "rating": 5,
                "email": "user@sakina.org",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert "Thank you" in data["message"]

            # Verify in persistent DB
            submissions = get_feedback_submissions(limit=10)
            assert len(submissions) == 1
            assert submissions[0]["feedback_type"] == "experience"
            assert submissions[0]["rating"] == 5

    @pytest.mark.asyncio
    async def test_anonymous_feedback_without_email_or_rating(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "general",
                "message": "A peaceful design with great typography and celestial tones.",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 200
            submissions = get_feedback_submissions(limit=10)
            assert len(submissions) == 1
            assert submissions[0]["email"] is None
            assert submissions[0]["rating"] is None

    @pytest.mark.asyncio
    async def test_validation_rejects_missing_or_short_message(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Too short (< 10 chars)
            payload = {
                "feedback_type": "general",
                "message": "Hi there",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 400
            assert "at least 10 characters" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_validation_rejects_invalid_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "malicious_type",
                "message": "Valid feedback message with more than ten characters.",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 400
            assert "Invalid feedback type" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_validation_rejects_invalid_rating(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "general",
                "message": "Valid feedback message with more than ten characters.",
                "rating": 6,  # Out of bounds (> 5)
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 400
            assert "between 1 and 5" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_validation_rejects_invalid_email_format(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "general",
                "message": "Valid feedback message with more than ten characters.",
                "email": "not-an-email",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 400
            assert "valid email" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_honeypot_discards_bot_submission(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "general",
                "message": "Spam message generated by automated spider.",
                "hp_website": "http://spamsite.example.com",
            }
            res = await client.post("/api/feedback", json=payload)
            # Must return success to deceive the bot
            assert res.status_code == 200
            # Must NOT be stored in database
            submissions = get_feedback_submissions(limit=10)
            assert len(submissions) == 0

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        transport = ASGITransport(app=app)
        headers = {"X-Forwarded-For": "198.51.100.42"}
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Submit 5 valid entries (limit is 5)
            for i in range(5):
                res = await client.post(
                    "/api/feedback",
                    json={
                        "feedback_type": "feature",
                        "message": f"Valid feature feedback note number {i + 1}.",
                    },
                    headers=headers,
                )
                assert res.status_code == 200

            # 6th submission within the hour window must be rejected with 429
            res_6 = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "feature",
                    "message": "Attempting 6th feature request in quick succession.",
                },
                headers=headers,
            )
            assert res_6.status_code == 429
            assert "submitted feedback recently" in res_6.json()["detail"]

    @pytest.mark.asyncio
    async def test_public_cannot_retrieve_feedback_records(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # GET /api/feedback does NOT exist
            res = await client.get("/api/feedback")
            assert res.status_code in [404, 405]

            # GET /api/admin/feedback without secret header is forbidden
            admin_res = await client.get("/api/admin/feedback")
            assert admin_res.status_code == 403

    @pytest.mark.asyncio
    async def test_authorized_admin_can_retrieve_feedback(self):
        transport = ASGITransport(app=app)
        test_admin_key = "test_super_secret_admin_key_987"
        os.environ["SAKINA_ADMIN_KEY"] = test_admin_key

        # Populate a record
        add_feedback(
            feedback_type="bug",
            message="Testing admin retrieval of persisted bug report.",
            rating=3,
        )

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Authorized request
            res = await client.get(
                "/api/admin/feedback",
                headers={"X-Admin-Key": test_admin_key},
            )
            assert res.status_code == 200
            data = res.json()
            assert "feedback" in data
            assert len(data["feedback"]) == 1
            assert data["feedback"][0]["feedback_type"] == "bug"

    @pytest.mark.asyncio
    async def test_cors_headers_support_render_static_site(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Test OPTIONS preflight from the Render static landing site
            headers = {
                "Origin": "https://sakina-landing.onrender.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            }
            res = await client.options("/api/feedback", headers=headers)
            assert res.status_code == 200
            assert "access-control-allow-origin" in res.headers
            assert res.headers["access-control-allow-origin"] == "https://sakina-landing.onrender.com"


class TestPublicReviews:
    """Comprehensive test suite for the public reviews system and moderation."""

    @pytest.mark.asyncio
    async def test_review_submission_stores_correctly_and_held_for_moderation(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "feedback_type": "review",
                "message": "Sakina has completely shifted my evening routine towards peaceful reflection.",
                "rating": 5,
                "name": "Mariam E.",
            }
            res = await client.post("/api/feedback", json=payload)
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert data["is_approved"] is False

            # Verify held for moderation (not in public reviews)
            pub_res = await client.get("/api/reviews")
            assert pub_res.status_code == 200
            pub_data = pub_res.json()
            assert pub_data["total_reviews"] == 0
            assert len(pub_data["reviews"]) == 0

    @pytest.mark.asyncio
    async def test_admin_approves_review_and_it_becomes_public(self):
        test_admin_key = "secret_admin_key_test"
        os.environ["SAKINA_ADMIN_KEY"] = test_admin_key
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Visitor submits review
            payload = {
                "message": "The dhikr mindfulness feature helps me stay grounded in gratitude.",
                "rating": 5,
                "name": "Zaid K.",
            }
            sub_res = await client.post("/api/feedback", json=payload)
            assert sub_res.status_code == 200

            # Inspect admin feedback to get review ID
            admin_list = await client.get(
                "/api/admin/feedback",
                headers={"X-Admin-Key": test_admin_key},
            )
            assert admin_list.status_code == 200
            records = admin_list.json()["feedback"]
            assert len(records) == 1
            review_id = records[0]["id"]
            assert records[0]["name"] == "Zaid K."
            assert records[0]["is_approved"] == 0

            # 2. Admin approves review
            appr_res = await client.post(
                f"/api/admin/feedback/{review_id}/approve",
                headers={"X-Admin-Key": test_admin_key},
                json={"is_approved": True},
            )
            assert appr_res.status_code == 200
            assert "approved" in appr_res.json()["message"]

            # 3. Public visitor retrieves reviews
            pub_res = await client.get("/api/reviews")
            assert pub_res.status_code == 200
            pub_data = pub_res.json()
            assert pub_data["total_reviews"] == 1
            assert pub_data["average_rating"] == 5.0
            assert len(pub_data["reviews"]) == 1

            review_item = pub_data["reviews"][0]
            assert review_item["name"] == "Zaid K."
            assert review_item["rating"] == 5
            assert "dhikr mindfulness" in review_item["message"]
            assert "created_at" in review_item

            # Strict privacy check: Private fields MUST NOT exist in public response
            assert "email" not in review_item
            assert "ip_hash" not in review_item
            assert "user_agent" not in review_item
            assert "is_approved" not in review_item

    @pytest.mark.asyncio
    async def test_average_rating_and_count_calculation_from_published_only(self):
        test_admin_key = "secret_admin_key_test"
        os.environ["SAKINA_ADMIN_KEY"] = test_admin_key
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Add 2 approved reviews (5 and 4 stars)
            res1 = add_feedback(feedback_type="review", message="Five star tranquil review.", rating=5, name="User A", is_approved=1)
            res2 = add_feedback(feedback_type="review", message="Four star good review.", rating=4, name="User B", is_approved=1)
            # Add 1 unapproved review (1 star)
            res3 = add_feedback(feedback_type="review", message="Pending review not yet moderated.", rating=1, name="User C", is_approved=0)

            pub_res = await client.get("/api/reviews")
            assert pub_res.status_code == 200
            pub_data = pub_res.json()

            # Only 2 approved reviews
            assert pub_data["total_reviews"] == 2
            # Average of 5 and 4 = 4.5
            assert pub_data["average_rating"] == 4.5
            assert len(pub_data["reviews"]) == 2
            names = [r["name"] for r in pub_data["reviews"]]
            assert "User A" in names
            assert "User B" in names
            assert "User C" not in names

    @pytest.mark.asyncio
    async def test_anonymous_review_defaults_to_anonymous(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Submit without name
            res = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "review",
                    "message": "Submitting a peaceful reflection completely anonymously.",
                    "rating": 5,
                },
            )
            assert res.status_code == 200

            # Approve it directly in DB
            submissions = get_feedback_submissions(limit=5)
            assert len(submissions) == 1
            assert submissions[0]["name"] == "Anonymous"
            from database import approve_feedback
            approve_feedback(submissions[0]["id"], is_approved=1)

            # Public check
            pub_res = await client.get("/api/reviews")
            assert pub_res.status_code == 200
            pub_data = pub_res.json()
            assert pub_data["reviews"][0]["name"] == "Anonymous"

    @pytest.mark.asyncio
    async def test_review_requires_rating_between_1_and_5(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Missing rating for review
            res = await client.post(
                "/api/feedback",
                json={
                    "feedback_type": "review",
                    "message": "Valid text with more than 10 characters but missing star rating.",
                },
            )
            assert res.status_code == 400
            assert "Rating is required" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_moderate_reviews(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # No X-Admin-Key header
            res = await client.post("/api/admin/feedback/1/approve", json={"is_approved": True})
            assert res.status_code == 403

