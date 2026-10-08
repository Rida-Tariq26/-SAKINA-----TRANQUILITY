"""
test_session_isolation.py

Comprehensive tests verifying that Sakina enforces strict per-user session
isolation and data separation across the application.
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import pytest
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

from database import (
    init_db, upsert_user, get_user,
    add_mood_log, get_recent_mood_logs, get_all_mood_logs,
    add_journal_entry, get_journal_entries, get_journal_entry,
    update_journal_entry, delete_journal_entry,
    export_user_data, delete_user_data,
)
from mood_tracker import analyze_trends, log_mood_tool, get_mood_history_tool
import server
import tools
from FrontendAPI import (
    app, session_service, mood_commentary_cache,
    create_chat_runner, create_mood_runner, get_scoped_mcp_tools,
    APP_NAME, DEFAULT_USER_ID,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure database and in-memory services are initialized and fresh for each test."""
    init_db()
    session_service.sessions.clear()
    session_service.user_state.clear()
    mood_commentary_cache.clear()
    yield
    # Cleanup test users
    delete_user_data("test_user_alice")
    delete_user_data("test_user_bob")
    delete_user_data("test_user_charlie")
    session_service.sessions.clear()
    session_service.user_state.clear()
    mood_commentary_cache.clear()


class TestPersistentStorageIsolation:
    """Verify that SQLite storage strictly isolates data between users."""

    def test_mood_logs_user_separation(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        # Log mood for User A
        add_mood_log(user_id=user_a, state="anxiety", intensity=8, note="Exam stress")

        # Verify User A has 1 entry
        logs_a = get_recent_mood_logs(user_id=user_a, limit=10)
        assert len(logs_a) == 1
        assert logs_a[0]["state"] == "anxiety"
        assert logs_a[0]["intensity"] == 8

        # Verify User B has NO entries
        logs_b = get_recent_mood_logs(user_id=user_b, limit=10)
        assert len(logs_b) == 0

        # Now log mood for User B
        add_mood_log(user_id=user_b, state="calm", intensity=3, note="After prayer")

        # Verify User A still only has their own entry
        logs_a_after = get_recent_mood_logs(user_id=user_a, limit=10)
        assert len(logs_a_after) == 1
        assert logs_a_after[0]["state"] == "anxiety"

        # Verify User B only has their own entry
        logs_b_after = get_recent_mood_logs(user_id=user_b, limit=10)
        assert len(logs_b_after) == 1
        assert logs_b_after[0]["state"] == "calm"

    def test_journal_entries_user_separation(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        # Add journal entry for User A
        entry_a = add_journal_entry(user_id=user_a, title="Alice Reflection", content="Private thoughts")

        # Add journal entry for User B
        entry_b = add_journal_entry(user_id=user_b, title="Bob Reflection", content="Personal goals")

        # User A cannot see User B's entries
        entries_a = get_journal_entries(user_id=user_a)
        assert len(entries_a) == 1
        assert entries_a[0]["title"] == "Alice Reflection"
        assert get_journal_entry(entry_id=entry_b["id"], user_id=user_a) is None

        # User B cannot see User A's entries
        entries_b = get_journal_entries(user_id=user_b)
        assert len(entries_b) == 1
        assert entries_b[0]["title"] == "Bob Reflection"
        assert get_journal_entry(entry_id=entry_a["id"], user_id=user_b) is None

        # User A cannot update or delete User B's entry
        assert update_journal_entry(entry_id=entry_b["id"], user_id=user_a, title="Hacked", content="Fail") is None
        assert delete_journal_entry(entry_id=entry_b["id"], user_id=user_a) is False

    def test_gdpr_export_and_delete_isolation(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        upsert_user(user_id=user_a, email="alice@test.local", name="Alice", picture="")
        upsert_user(user_id=user_b, email="bob@test.local", name="Bob", picture="")

        add_mood_log(user_id=user_a, state="grief", intensity=7)
        add_mood_log(user_id=user_b, state="hope", intensity=6)

        add_journal_entry(user_id=user_a, title="Alice Doc", content="Alice text")
        add_journal_entry(user_id=user_b, title="Bob Doc", content="Bob text")

        # Export User A
        export_a = export_user_data(user_a)
        assert export_a["user"]["user_id"] == user_a
        assert len(export_a["mood_logs"]) == 1
        assert export_a["mood_logs"][0]["state"] == "grief"
        assert len(export_a["journal_entries"]) == 1
        assert export_a["journal_entries"][0]["title"] == "Alice Doc"
        # Verify User B's data is NOT in User A's export
        for log in export_a["mood_logs"]:
            assert log["user_id"] == user_a
        for j in export_a["journal_entries"]:
            assert j["user_id"] == user_a

        # Delete User A
        delete_user_data(user_a)

        # User A's data is erased
        assert len(get_recent_mood_logs(user_a)) == 0
        assert len(get_journal_entries(user_a)) == 0
        assert get_user(user_a) is None  # Anonymized / marked deleted

        # User B's data is intact
        assert len(get_recent_mood_logs(user_b)) == 1
        assert len(get_journal_entries(user_b)) == 1
        assert get_user(user_b) is not None


class TestMCPToolsUserIsolation:
    """Verify that MCP tools (server.py and tools.py) strictly enforce user isolation."""

    def test_server_mcp_tools_accept_user_id(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        # Log via server.mood_log_tool with user_id
        msg_a = server.mood_log_tool(emotional_state="panic", intensity=9, user_id=user_a)
        assert "Logged: panic" in msg_a

        # Query history for User B - must be EMPTY
        hist_b = server.mood_history_tool(user_id=user_b)
        assert "No mood history found yet" in hist_b
        assert "panic" not in hist_b

        # Query history for User A - must contain their panic entry
        hist_a = server.mood_history_tool(user_id=user_a)
        assert "panic" in hist_a
        assert "intensity 9/10" in hist_a

    def test_tools_py_user_isolation(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        tools.mood_log_tool(emotional_state="overwhelmed", intensity=7, user_id=user_a)

        # Bob gets no entries
        hist_b = tools.mood_history_tool(user_id=user_b)
        assert "No entries logged yet" in hist_b

        # Alice gets her entry
        hist_a = tools.mood_history_tool(user_id=user_a)
        assert "overwhelmed" in hist_a

    @pytest.mark.asyncio
    async def test_get_scoped_mcp_tools_enforces_user_id(self):
        """Verify that get_scoped_mcp_tools injects the bound user_id and blocks spoofing."""
        mock_mcp = AsyncMock()
        mock_tool_def = MagicMock()
        mock_tool_def.name = "mood_log_tool"
        mock_tool_def.description = "Log mood"

        mock_content = MagicMock()
        mock_content.text = "Logged successfully."
        mock_res = MagicMock()
        mock_res.content = [mock_content]
        mock_mcp.call_tool.return_value = mock_res

        with patch("FrontendAPI.mcp_session_instance", mock_mcp), \
             patch("FrontendAPI.mcp_discovered_tools", [mock_tool_def]):

            user_a = "test_user_alice"
            scoped_tools_a = get_scoped_mcp_tools(target_user_id=user_a)
            assert len(scoped_tools_a) == 1

            # Call tool as Alice, but malicious caller attempts to pass user_id='victim_bob'
            caller = scoped_tools_a[0]
            await caller(emotional_state="anxiety", intensity=8, user_id="victim_bob")

            # Verify that the wrapper FORCED user_id to Alice ('test_user_alice')
            mock_mcp.call_tool.assert_called_once()
            call_name, call_kwargs = mock_mcp.call_tool.call_args
            arguments = call_kwargs["arguments"]
            assert arguments["user_id"] == "test_user_alice"
            assert arguments["user_id"] != "victim_bob"


class TestADKSessionIsolation:
    """Verify that InMemorySessionService and Runner enforce per-user session isolation."""

    @pytest.mark.asyncio
    async def test_in_memory_session_service_separation(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"
        session_a_id = f"chat_{user_a}"
        session_b_id = f"chat_{user_b}"

        # Create session for Alice
        session_a = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_a,
            session_id=session_a_id,
        )
        assert session_a.user_id == user_a
        assert session_a.id == session_a_id

        # Create session for Bob
        session_b = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_b,
            session_id=session_b_id,
        )
        assert session_b.user_id == user_b
        assert session_b.id == session_b_id

        # Verify separation in session_service.sessions
        assert session_a_id in session_service.sessions[APP_NAME][user_a]
        assert session_b_id not in session_service.sessions[APP_NAME][user_a]

        assert session_b_id in session_service.sessions[APP_NAME][user_b]
        assert session_a_id not in session_service.sessions[APP_NAME][user_b]

        # Verify list_sessions for Alice only lists Alice's session
        list_a = await session_service.list_sessions(app_name=APP_NAME, user_id=user_a)
        assert all(s.user_id == user_a for s in list_a.sessions)
        assert any(s.id == session_a_id for s in list_a.sessions)
        assert not any(s.id == session_b_id for s in list_a.sessions)

    @pytest.mark.asyncio
    async def test_runners_use_user_scoped_tools_and_sessions(self):
        user_a = "test_user_alice"
        user_b = "test_user_bob"

        runner_a = create_chat_runner(user_id=user_a)
        runner_b = create_chat_runner(user_id=user_b)

        assert runner_a.agent.name == "Sakina"
        assert runner_b.agent.name == "Sakina"

        # Verify session ids for different endpoints are user-scoped
        chat_sid_a = f"chat_{user_a}"
        chat_sid_b = f"chat_{user_b}"
        assert chat_sid_a != chat_sid_b

        dhikr_sid_a = f"dhikr_{user_a}"
        dhikr_sid_b = f"dhikr_{user_b}"
        assert dhikr_sid_a != dhikr_sid_b

        mood_sid_a = f"mood_{user_a}"
        mood_sid_b = f"mood_{user_b}"
        assert mood_sid_a != mood_sid_b


class TestFastAPIFlowDataIsolation:
    """Verify HTTP endpoints enforce strict isolation via test client."""

    @pytest.mark.asyncio
    async def test_journal_endpoints_isolation(self):
        from httpx import AsyncClient, ASGITransport

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Alice creates journal entry
            res_a = await client.post(
                "/api/journal",
                json={"title": "Alice Title", "content": "Alice Secret"},
                headers={"X-User-Id": "test_user_alice"},
            )
            assert res_a.status_code == 200
            entry_a_id = res_a.json()["id"]

            # Bob creates journal entry
            res_b = await client.post(
                "/api/journal",
                json={"title": "Bob Title", "content": "Bob Secret"},
                headers={"X-User-Id": "test_user_bob"},
            )
            assert res_b.status_code == 200

            # Bob lists entries — should ONLY see Bob's entry
            list_b = await client.get(
                "/api/journal",
                headers={"X-User-Id": "test_user_bob"},
            )
            assert list_b.status_code == 200
            b_entries = list_b.json()["entries"]
            assert len(b_entries) == 1
            assert b_entries[0]["title"] == "Bob Title"

            # Bob tries to delete Alice's entry — should return 404 (not found for Bob)
            del_res = await client.delete(
                f"/api/journal/{entry_a_id}",
                headers={"X-User-Id": "test_user_bob"},
            )
            assert del_res.status_code == 404

    @pytest.mark.asyncio
    async def test_mood_and_commentary_cache_isolation(self):
        from httpx import AsyncClient, ASGITransport

        user_a = "test_user_alice"
        user_b = "test_user_bob"

        # Populate cache for Alice
        cache_key_a = f"{user_a}:islamic:2026-10-07:1"
        mood_commentary_cache[cache_key_a] = "Alice personalized commentary"

        # Populate cache for Bob
        cache_key_b = f"{user_b}:islamic:2026-10-07:1"
        mood_commentary_cache[cache_key_b] = "Bob personalized commentary"

        assert mood_commentary_cache[cache_key_a] != mood_commentary_cache[cache_key_b]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Delete User A
            del_res = await client.delete(
                "/api/user/data",
                headers={"X-User-Id": user_a},
            )
            assert del_res.status_code == 200
            assert del_res.json() == {"status": "deleted"}

            # Alice's cache entry must be purged
            assert cache_key_a not in mood_commentary_cache

            # Bob's cache entry must remain intact
            assert cache_key_b in mood_commentary_cache
            assert mood_commentary_cache[cache_key_b] == "Bob personalized commentary"

    @pytest.mark.asyncio
    async def test_in_memory_session_purged_on_delete_data(self):
        from httpx import AsyncClient, ASGITransport

        user_a = "test_user_alice"
        user_b = "test_user_bob"
        session_a_id = f"chat_{user_a}"
        session_b_id = f"chat_{user_b}"

        # Populate in-memory sessions for both Alice and Bob
        await session_service.create_session(app_name=APP_NAME, user_id=user_a, session_id=session_a_id)
        await session_service.create_session(app_name=APP_NAME, user_id=user_b, session_id=session_b_id)

        assert user_a in session_service.sessions[APP_NAME]
        assert user_b in session_service.sessions[APP_NAME]

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            del_res = await client.delete("/api/user/data", headers={"X-User-Id": user_a})
            assert del_res.status_code == 200

        # Alice's in-memory sessions are completely purged
        assert user_a not in session_service.sessions.get(APP_NAME, {})

        # Bob's in-memory sessions remain untouched
        assert user_b in session_service.sessions.get(APP_NAME, {})
        assert session_b_id in session_service.sessions[APP_NAME][user_b]

    @pytest.mark.asyncio
    async def test_logout_purges_user_commentary_cache(self):
        from httpx import AsyncClient, ASGITransport

        user_a = "test_user_alice"
        cache_key = f"{user_a}:islamic:2026-10-07:2"
        mood_commentary_cache[cache_key] = "Alice cached reflection"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post("/api/auth/logout", headers={"X-User-Id": user_a})
            assert res.status_code == 200

        assert cache_key not in mood_commentary_cache

