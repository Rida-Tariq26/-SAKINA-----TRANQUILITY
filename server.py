import os
import json
import datetime
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Sakina Wellness Tools")


MOOD_LOG_FILE = os.environ.get(
    "MOOD_LOG_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mood_log.json")
)

from database import add_mood_log, get_recent_mood_logs

@mcp.tool()
def mood_log_tool(emotional_state: str, intensity: int, user_id: str = "default_user") -> str:
    user_id = (user_id or "default_user").strip()
    add_mood_log(user_id=user_id, state=emotional_state, intensity=intensity, note="")
    return f"Noted. Logged: {emotional_state} (intensity {intensity}/10)."

@mcp.tool()
def mood_history_tool(user_id: str = "default_user") -> str:
    user_id = (user_id or "default_user").strip()
    recent = get_recent_mood_logs(user_id=user_id, limit=7)
    if not recent:
        return "No mood history found yet. We will build that together over time."

    summary = "Here is what I have noted from our recent sessions:\n"
    for entry in recent:
        date = entry["timestamp"][:10]
        note = f" — {entry['note']}" if entry.get("note") else ""
        summary += f"  • {date}: {entry['state']} (intensity {entry['intensity']}/10){note}\n"

    return summary

if __name__ == "__main__":
    # Runs the server using standard input/output (stdio) transport protocol
    mcp.run()
