import json
import datetime
import os

MOOD_LOG_FILE = "mood_log.json"

from database import add_mood_log, get_recent_mood_logs

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
    add_mood_log(user_id="default_user", state=emotional_state, intensity=intensity, note="")
    return f"Noted. I've logged: {emotional_state} (intensity {intensity}/10)."


def mood_history_tool() -> str:
    """
    Retrieves the user's recent emotional history from persistent storage.
    Call this when the user asks how they've been feeling, asks about patterns,
    or wants to reflect on their emotional journey over time.

    Returns:
        A formatted summary of recent mood entries
    """
    recent = get_recent_mood_logs(user_id="default_user", limit=7)
    if not recent:
        return "No entries logged yet."

    summary = "Here's what I've noted from our recent sessions:\n"
    for entry in recent:
        date = entry["timestamp"][:10]
        note = f" — {entry['note']}" if entry.get("note") else ""
        summary += f"  • {date}: {entry['state']} (intensity {entry['intensity']}/10){note}\n"

    return summary