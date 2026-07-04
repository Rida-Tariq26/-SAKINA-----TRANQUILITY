import json
import datetime
import os

MOOD_LOG_FILE = "mood_log.json"

def mood_log_tool(emotional_state: str, intensity: int) -> str:
    """
    Logs the user's current emotional state and intensity to persistent storage.
    Call this whenever the user expresses or describes how they are feeling.
    Use your best judgment to identify the emotional state from context.

    Args:
        emotional_state: A single word or short phrase, e.g. 'anxiety', 
                        'grief', 'panic', 'loneliness', 'calm', 'overwhelmed'
        intensity: A number from 1 to 10 representing how strongly 
                  the user seems to feel this emotion

    Returns:
        A confirmation string
    """
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "state": emotional_state,
        "intensity": intensity
    }

    # Load existing log or start fresh
    if os.path.exists(MOOD_LOG_FILE):
        with open(MOOD_LOG_FILE, "r") as f:
            log = json.load(f)
    else:
        log = []

    log.append(entry)

    with open(MOOD_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)

    return f"Noted. I've logged: {emotional_state} (intensity {intensity}/10)."


def mood_history_tool() -> str:
    """
    Retrieves the user's recent emotional history from persistent storage.
    Call this when the user asks how they've been feeling, asks about patterns,
    or wants to reflect on their emotional journey over time.

    Returns:
        A formatted summary of recent mood entries
    """
    if not os.path.exists(MOOD_LOG_FILE):
        return "No mood history found yet. We'll build that together over time."

    with open(MOOD_LOG_FILE, "r") as f:
        log = json.load(f)

    if not log:
        return "No entries logged yet."

    # Return last 7 entries
    recent = log[-7:]
    summary = "Here's what I've noted from our recent sessions:\n"
    for entry in recent:
        date = entry["timestamp"][:10]
        summary += f"  • {date}: {entry['state']} (intensity {entry['intensity']}/10)\n"

    return summary