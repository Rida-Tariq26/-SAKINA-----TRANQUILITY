import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import json
import asyncio
import datetime
import statistics
from collections import Counter
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

APP_NAME = "SakinaMood"
USER_ID = "default_user"
MOOD_LOG_FILE = os.environ.get(
    "MOOD_LOG_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "mood_log.json")
)

# ─────────────────────────────────────────────
# SECTION 1: EMOTION CONSTANTS
# Shared vocabulary with the Dhikr module, plus
# two positive states for balanced tracking.
# ─────────────────────────────────────────────

TRACKABLE_EMOTIONS = [
    "anxiety", "grief", "panic", "overwhelmed", "loneliness",
    "guilt", "restlessness", "hopelessness", "calm", "gratitude",
    "contentment", "hope",
]

NEGATIVE_EMOTIONS = {
    "anxiety", "grief", "panic", "overwhelmed",
    "loneliness", "guilt", "restlessness", "hopelessness",
}

# ─────────────────────────────────────────────
# SECTION 2: PERSISTENCE LAYER
# ─────────────────────────────────────────────

def _load_log() -> list:
    if not os.path.exists(MOOD_LOG_FILE):
        return []
    with open(MOOD_LOG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save_log(log: list) -> None:
    with open(MOOD_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


# ─────────────────────────────────────────────
# SECTION 3: CORE LOGGING TOOLS
# ─────────────────────────────────────────────

def log_mood_tool(emotional_state: str, intensity: int, note: str = "") -> str:
    """Logs a single mood entry with timestamp, state, intensity (1-10), and an optional note."""
    state = emotional_state.strip().lower()
    intensity = max(1, min(10, int(intensity)))

    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "state": state,
        "intensity": intensity,
        "note": note.strip(),
    }

    log = _load_log()
    log.append(entry)
    _save_log(log)

    return f"Logged: {state} (intensity {intensity}/10)."


def get_recent_entries_tool(limit: int = 7) -> str:
    """Returns a human-readable summary of the most recent mood entries."""
    log = _load_log()
    if not log:
        return "No mood history found yet. We will build that together over time."

    recent = log[-limit:]
    lines = ["Here is what I have noted from our recent check-ins:"]
    for entry in recent:
        date = entry["timestamp"][:10]
        note = f" — {entry['note']}" if entry.get("note") else ""
        lines.append(f"  • {date}: {entry['state']} (intensity {entry['intensity']}/10){note}")
    return "\n".join(lines)


def get_mood_history_tool() -> str:
    """Tool wrapper returning recent entries — kept for parity with agent.py's mood_history_tool."""
    return get_recent_entries_tool(limit=7)


# ─────────────────────────────────────────────
# SECTION 4: TREND ANALYSIS ENGINE
# ─────────────────────────────────────────────

def _parse_date(ts: str) -> datetime.date:
    return datetime.datetime.fromisoformat(ts).date()


def analyze_trends(days: int = 30) -> dict:
    """
    Computes comparative metrics across a tracking cycle:
    - baseline intensity shift (first half vs second half of the window)
    - dominant emotional states
    - escalation / resilience signal, overall and per-emotion
    - streak of logging (engagement)
    """
    log = _load_log()
    if not log:
        return {"has_data": False}

    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    window = [e for e in log if _parse_date(e["timestamp"]) >= cutoff]

    if len(window) < 2:
        return {"has_data": True, "insufficient_for_trend": True, "entry_count": len(window)}

    window.sort(key=lambda e: e["timestamp"])
    midpoint = len(window) // 2
    first_half = window[:midpoint] if midpoint > 0 else window[:1]
    second_half = window[midpoint:]

    first_avg = statistics.mean(e["intensity"] for e in first_half)
    second_avg = statistics.mean(e["intensity"] for e in second_half)
    delta = round(second_avg - first_avg, 2)

    neg_first = [e["intensity"] for e in first_half if e["state"] in NEGATIVE_EMOTIONS]
    neg_second = [e["intensity"] for e in second_half if e["state"] in NEGATIVE_EMOTIONS]
    neg_delta = round(statistics.mean(neg_second) - statistics.mean(neg_first), 2) if (neg_first and neg_second) else None

    state_counts = Counter(e["state"] for e in window)
    dominant_state, dominant_count = state_counts.most_common(1)[0]

    per_emotion = {}
    for emo in set(e["state"] for e in window):
        entries = [e for e in window if e["state"] == emo]
        if len(entries) >= 2:
            entries.sort(key=lambda e: e["timestamp"])
            half = max(1, len(entries) // 2)
            before = statistics.mean(e["intensity"] for e in entries[:half])
            after = statistics.mean(e["intensity"] for e in entries[half:])
            per_emotion[emo] = round(after - before, 2)

    logged_days = sorted({_parse_date(e["timestamp"]) for e in window}, reverse=True)
    streak = 0
    expected = datetime.date.today()
    for d in logged_days:
        if d == expected:
            streak += 1
            expected -= datetime.timedelta(days=1)
        elif d == expected + datetime.timedelta(days=1):
            continue
        else:
            break

    if delta <= -1.0:
        overall_signal = "improving"
    elif delta >= 1.0:
        overall_signal = "escalating"
    else:
        overall_signal = "stable"

    return {
        "has_data": True,
        "insufficient_for_trend": False,
        "window_days": days,
        "entry_count": len(window),
        "first_half_avg_intensity": round(first_avg, 2),
        "second_half_avg_intensity": round(second_avg, 2),
        "overall_intensity_delta": delta,
        "negative_emotion_delta": neg_delta,
        "overall_signal": overall_signal,
        "dominant_state": dominant_state,
        "dominant_state_count": dominant_count,
        "state_distribution": dict(state_counts),
        "per_emotion_delta": per_emotion,
        "logging_streak_days": streak,
    }


# ─────────────────────────────────────────────
# SECTION 5: ADK AGENT FOR SYNTHESIZED COMMENTARY
# ─────────────────────────────────────────────

TREND_COMMENTARY_PROMPT = """
You are Sakina, a compassionate wellness guide reflecting on a user's mood history.
You will be given structured trend metrics (intensity deltas, dominant emotional states,
a logging streak, and per-emotion shifts) gathered over their recent tracking cycle.

Your job is to write a warm, personal synthesis (5-8 sentences) that:
1. Reflects back the overall pattern (improving, escalating, or stable) in plain,
   non-clinical, encouraging language — never alarming.
2. Names one or two specific emotional patterns you notice (e.g. "your anxiety has
   eased while restlessness has grown") using the per-emotion data given.
3. Acknowledges their effort in showing up to track their feelings, if a logging
   streak is present.
4. Offers ONE concrete, gentle, specific wellness recommendation suited to what the
   data shows — CBT/ACT-based, or, if mode is Islamic, a relevant spiritual practice
   (dhikr, du'a, reflection) — without forcing religious framing in secular mode.
5. Ends with one sentence of grounded, realistic encouragement — not toxic positivity,
   and never dismissive of difficulty if the trend is escalating.

Do NOT use bullet points or restate the raw numbers verbatim. Write as if speaking
warmly, directly, and specifically to a friend who trusts you with this data.
If the trend signal is "escalating", be gentle but honest, and lightly note that
talking to a counselor or trusted person can help if things keep feeling heavier —
without being alarmist or clinical.
"""


def _build_trend_prompt(trends: dict, mode: str) -> str:
    if not trends.get("has_data"):
        return (
            "The user has no mood history yet. Write 2-3 warm sentences inviting "
            "them to begin logging how they feel, explaining gently why tracking "
            "patterns over time can help them understand themselves better."
        )

    if trends.get("insufficient_for_trend"):
        n = trends["entry_count"]
        return (
            f"The user has only {n} mood entr{'y' if n == 1 else 'ies'} logged so far — "
            "not yet enough to compute a meaningful trend. Write 2-3 warm sentences "
            "acknowledging what they've shared and gently encouraging them to keep "
            "checking in so patterns can emerge."
        )

    mode_note = (
        "The user has engaged with Sakina's Islamic mode, so a spiritual practice "
        "recommendation is welcome if it fits naturally."
        if mode == "islamic"
        else "The user has engaged with Sakina's secular mode, so keep recommendations "
        "strictly evidence-based and non-religious."
    )

    return (
        f"Here is the user's mood trend data over the last {trends['window_days']} days:\n"
        f"- Entries logged: {trends['entry_count']}\n"
        f"- Average intensity, first half of window: {trends['first_half_avg_intensity']}/10\n"
        f"- Average intensity, second half of window: {trends['second_half_avg_intensity']}/10\n"
        f"- Overall intensity shift: {trends['overall_intensity_delta']:+.2f}\n"
        f"- Overall signal: {trends['overall_signal']}\n"
        f"- Most frequently logged state: {trends['dominant_state']} ({trends['dominant_state_count']} times)\n"
        f"- Per-emotion intensity shifts (positive = worsening, negative = improving): {trends['per_emotion_delta']}\n"
        f"- Consecutive days logged (streak): {trends['logging_streak_days']}\n\n"
        f"{mode_note}\n\nWrite your warm, specific synthesis now."
    )


async def get_trend_commentary(trends: dict, mode: str, runner: Runner, session_id: str) -> str:
    """Gets AI-synthesized commentary on the user's mood trends."""
    prompt = _build_trend_prompt(trends, mode)
    try:
        response = runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
        )

        commentary = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                commentary = event.content.parts[0].text

        return commentary
    except Exception as e:
        return f"[Commentary unavailable: {e}]"


# ─────────────────────────────────────────────
# SECTION 6: PUBLIC API SURFACE
# (for FastAPI route: POST /api/mood and GET /api/mood/history)
# ─────────────────────────────────────────────

async def log_and_synthesize(
    emotional_state: str,
    intensity: int,
    note: str,
    mode: str,
    runner: Runner,
    session_id: str,
    window_days: int = 30,
) -> dict:
    """
    Full pipeline used by the FastAPI route: logs the new entry, recomputes
    trends, and returns both raw metrics and synthesized commentary for the
    frontend to render.
    """
    log_message = log_mood_tool(emotional_state, intensity, note)
    trends = analyze_trends(days=window_days)
    commentary = await get_trend_commentary(trends, mode, runner, session_id)

    return {
        "log_message": log_message,
        "trends": trends,
        "commentary": commentary,
        "recent_entries": _load_log()[-7:],
    }


async def get_dashboard(mode: str, runner: Runner, session_id: str, window_days: int = 30) -> dict:
    """Used by a GET endpoint to render the dashboard without requiring a new log entry."""
    trends = analyze_trends(days=window_days)
    commentary = await get_trend_commentary(trends, mode, runner, session_id)
    return {
        "trends": trends,
        "commentary": commentary,
        "recent_entries": _load_log()[-7:],
    }


# ─────────────────────────────────────────────
# SECTION 7: STANDALONE CLI FLOW
# (mirrors dhikr.py's standalone main loop for local testing)
# ─────────────────────────────────────────────

async def main():
    print("\n" + "=" * 50)
    print("     Sakina — Mood Tracker 📈")
    print("=" * 50)

    print("\nHow would you like your reflections framed?")
    print("  1. Islamic")
    print("  2. Secular")
    while True:
        mode_input = input("Enter 1 or 2: ").strip()
        if mode_input == "1":
            mode = "islamic"
            break
        elif mode_input == "2":
            mode = "secular"
            break
        print("Please enter 1 or 2.")

    session_id = "mood_session"
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

    commentary_agent = Agent(
        name="SakinaMoodGuide",
        model="gemini-2.5-flash",
        instruction=TREND_COMMENTARY_PROMPT,
    )
    runner = Runner(agent=commentary_agent, app_name=APP_NAME, session_service=session_service)

    while True:
        print("\n" + "-" * 50)
        print("  1. Log how I'm feeling")
        print("  2. View my trends & reflection")
        print("  3. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            print("\nHow are you feeling?")
            for i, emo in enumerate(TRACKABLE_EMOTIONS, 1):
                print(f"  {i}. {emo.capitalize()}")
            state_choice = input("Enter a number or type your feeling: ").strip()

            if state_choice.isdigit() and 1 <= int(state_choice) <= len(TRACKABLE_EMOTIONS):
                state = TRACKABLE_EMOTIONS[int(state_choice) - 1]
            else:
                state = state_choice.lower() or "anxiety"

            while True:
                intensity_input = input("Intensity (1-10): ").strip()
                if intensity_input.isdigit() and 1 <= int(intensity_input) <= 10:
                    intensity = int(intensity_input)
                    break
                print("Please enter a number from 1 to 10.")

            note = input("Anything you'd like to note? (optional): ").strip()
            print(f"\n  {log_mood_tool(state, intensity, note)}")

        elif choice == "2":
            print("\n  Reflecting on your patterns...\n")
            trends = analyze_trends(days=30)
            commentary = await get_trend_commentary(trends, mode, runner, session_id)
            print(f"  {commentary}\n")
            print(get_recent_entries_tool(limit=7))

        elif choice == "3":
            print("\n  May your heart find steadiness. 🌿\n")
            break
        else:
            print("Please choose 1, 2, or 3.")


if __name__ == "__main__":
    asyncio.run(main())