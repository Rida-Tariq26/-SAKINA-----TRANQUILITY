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

@mcp.tool()
def mood_log_tool(emotional_state: str, intensity: int) -> str:
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "state": emotional_state,
        "intensity": intensity
    }

    if os.path.exists(MOOD_LOG_FILE):
        with open(MOOD_LOG_FILE, "r") as f:
            log = json.load(f)
    else:
        log = []

    log.append(entry)

    with open(MOOD_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    return f"Noted. Logged: {emotional_state} (intensity {intensity}/10)."

@mcp.tool()
def mood_history_tool() -> str:
    if not os.path.exists(MOOD_LOG_FILE):
        return "No mood history found yet. We will build that together over time."

    with open(MOOD_LOG_FILE, "r") as f:
        log = json.load(f)

    if not log:
        return "No entries logged yet."

    recent = log[-7:]
    summary = "Here is what I have noted from our recent sessions:\n"
    for entry in recent:
        date = entry["timestamp"][:10]
        summary += f"  • {date}: {entry['state']} (intensity {entry['intensity']}/10)\n"

    return summary

if __name__ == "__main__":
    # Runs the server using standard input/output (stdio) transport protocol
    mcp.run()
