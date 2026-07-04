import os
os.environ["OTEL_SDK_DISABLED"] = "true"

import asyncio
import requests
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

load_dotenv()

APP_NAME = "SakinaDhikr"
USER_ID = "default_user"

# ─────────────────────────────────────────────
# SECTION 1: STATIC DHIKR TABLE
# Each entry: (arabic, transliteration, translation, reference, repetitions)
# ─────────────────────────────────────────────

DHIKR_TABLE = {
    "anxiety": [
        (
            "حَسْبُنَا اللَّهُ وَنِعْمَ الْوَكِيلُ",
            "Hasbunallahu wa ni'mal wakeel",
            "Allah is sufficient for us, and He is the best disposer of affairs.",
            "Quran 3:173 — recited by Ibrahim (AS) and the Companions in moments of fear",
            "100x or as needed"
        ),
        (
            "لَا حَوْلَ وَلَا قُوَّةَ إِلَّا بِاللَّهِ",
            "La hawla wa la quwwata illa billah",
            "There is no power nor strength except with Allah.",
            "Sahih Bukhari 6384 — described as a treasure from the treasures of Jannah",
            "As often as possible"
        ),
    ],
    "grief": [
        (
            "إِنَّا لِلَّهِ وَإِنَّا إِلَيْهِ رَاجِعُونَ",
            "Inna lillahi wa inna ilayhi raji'un",
            "Indeed, to Allah we belong and to Him we shall return.",
            "Quran 2:156 — revealed for those who face loss and calamity",
            "Recite with reflection whenever grief arises"
        ),
        (
            "اللَّهُمَّ أْجُرْنِي فِي مُصِيبَتِي وَأَخْلِفْ لِي خَيْرًا مِنْهَا",
            "Allahumma ajurni fi museebati wa akhlif li khayran minha",
            "O Allah, reward me in my affliction and replace it with something better.",
            "Sahih Muslim 918 — the du'a taught for times of loss",
            "3x after reciting Inna lillahi"
        ),
    ],
    "panic": [
        (
            "اللَّهُمَّ إِنِّي أَعُوذُ بِكَ مِنَ الْهَمِّ وَالْحَزَنِ",
            "Allahumma inni a'udhu bika minal-hammi wal-hazan",
            "O Allah, I seek refuge in You from worry and grief.",
            "Sahih Bukhari 6369 — du'a of the Prophet ﷺ for distress",
            "Recite slowly, with deep breaths between each repetition"
        ),
        (
            "سُبْحَانَ اللَّهِ وَبِحَمْدِهِ",
            "Subhanallahi wa bihamdihi",
            "Glory be to Allah and praise be to Him.",
            "Sahih Bukhari 6405 — described as beloved to Allah and light on the tongue",
            "100x"
        ),
    ],
    "overwhelmed": [
        (
            "اللَّهُ أَكْبَرُ",
            "Allahu Akbar",
            "Allah is the Greatest.",
            "Established Sunnah — recited in every prayer and at moments of magnitude",
            "33x — grounds the heart by re-centering on Allah's greatness above all burdens"
        ),
        (
            "يَا حَيُّ يَا قَيُّومُ بِرَحْمَتِكَ أَسْتَغِيثُ",
            "Ya Hayyu Ya Qayyum, bi rahmatika astaghith",
            "O Ever-Living, O Self-Sustaining — I seek help through Your mercy.",
            "Tirmidhi 3524 — recommended by the Prophet ﷺ for times of distress",
            "Recite as needed, especially before Fajr"
        ),
    ],
    "loneliness": [
        (
            "اللَّهُمَّ آنِسْ وَحْشَتِي",
            "Allahumma anis wahshati",
            "O Allah, ease my loneliness.",
            "Reported du'a for times of isolation and solitude",
            "Recite at night or in quiet moments"
        ),
        (
            "سُبْحَانَ اللَّهِ وَالْحَمْدُ لِلَّهِ وَلَا إِلَهَ إِلَّا اللَّهُ وَاللَّهُ أَكْبَرُ",
            "Subhanallah, Alhamdulillah, La ilaha illallah, Allahu Akbar",
            "Glory be to Allah, Praise be to Allah, There is no god but Allah, Allah is the Greatest.",
            "Sahih Muslim 2695 — the four most beloved phrases to Allah",
            "33x each — fills the heart with companionship of dhikr"
        ),
    ],
    "guilt": [
        (
            "أَسْتَغْفِرُ اللَّهَ الْعَظِيمَ الَّذِي لَا إِلَهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ وَأَتُوبُ إِلَيْهِ",
            "Astaghfirullaha al-'Azeem alladhi la ilaha illa Huwa al-Hayyu al-Qayyum wa atubu ilayh",
            "I seek forgiveness from Allah the Mighty, besides Whom there is no god, the Ever-Living, the Self-Sustaining, and I turn to Him in repentance.",
            "Tirmidhi 3577 — the Sayyid al-Istighfar, master of seeking forgiveness",
            "Once in the morning and evening sincerely"
        ),
    ],
    "restlessness": [
        (
            "أَلَا بِذِكْرِ اللَّهِ تَطْمَئِنُّ الْقُلُوبُ",
            "Ala bidhikrillahi tatma'inn al-qulub",
            "Verily, in the remembrance of Allah do hearts find rest.",
            "Quran 13:28 — not a dhikr to recite but a truth to anchor the practice",
            "Reflect on this ayah, then recite: Subhanallah 33x, Alhamdulillah 33x, Allahu Akbar 34x"
        ),
    ],
    "hopelessness": [
        (
            "لَا تَقْنَطُوا مِن رَّحْمَةِ اللَّهِ",
            "La taqnatu min rahmatillah",
            "Do not despair of the mercy of Allah.",
            "Quran 39:53 — a direct address to those who feel lost",
            "Recite slowly and reflect on each word"
        ),
        (
            "اللَّهُمَّ رَحْمَتَكَ أَرْجُو",
            "Allahumma rahmataka arju",
            "O Allah, it is Your mercy that I hope for.",
            "Abu Dawud 5090 — du'a taught for moments of despair",
            "Recite before sleep and upon waking"
        ),
    ],
    "gratitude": [
        (
            "الْحَمْدُ لِلَّهِ الَّذِي بِنِعْمَتِهِ تَتِمُّ الصَّالِحَاتُ",
            "Alhamdulillahil-ladhi bini'matihi tatimmus-salihat",
            "All praise is due to Allah, by whose favor good deeds are completed.",
            "Ibn Majah 3803 — recommended upon witnessing or receiving something pleasing",
            "Recite whenever gratitude arises, especially after good news"
        ),
        (
            "اللَّهُمَّ أَعِنِّي عَلَى ذِكْرِكَ وَشُكْرِكَ وَحُسْنِ عِبَادَتِكَ",
            "Allahumma a'inni 'ala dhikrika wa shukrika wa husni 'ibadatik",
            "O Allah, help me to remember You, to thank You, and to worship You in the best manner.",
            "Sunan Abi Dawud 1522 — taught by the Prophet ﷺ to Mu'adh ibn Jabal",
            "After each of the five daily prayers"
        ),
    ],
    "calm": [
        (
            "يَا أَيَّتُهَا النَّفْسُ الْمُطْمَئِنَّةُ ارْجِعِي إِلَى رَبِّكِ رَاضِيَةً مَرْضِيَّةً",
            "Ya ayyatuha an-nafsu al-mutma'innah, irji'i ila Rabbiki radiyatan mardiyyah",
            "O reassured soul, return to your Lord, well-pleased and pleasing to Him.",
            "Quran 89:27-28 — describing the soul at rest through remembrance",
            "Recite slowly and reflect, especially in quiet moments"
        ),
        (
            "رَبِّ اشْرَحْ لِي صَدْرِي وَيَسِّرْ لِي أَمْرِي",
            "Rabbi ishrah li sadri wa yassir li amri",
            "My Lord, expand for me my chest and ease my task for me.",
            "Quran 20:25-26 — the du'a of Musa (AS) for calm and ease",
            "Recite before or during moments requiring steadiness"
        ),
    ],
    "contentment": [
        (
            "رَضِيتُ بِاللَّهِ رَبًّا وَبِالْإِسْلَامِ دِينًا وَبِمُحَمَّدٍ صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ نَبِيًّا",
            "Radhitu billahi Rabban, wa bil-Islami dinan, wa bi-Muhammadin sallallahu 'alayhi wa sallam nabiyya",
            "I am pleased with Allah as my Lord, Islam as my religion, and Muhammad ﷺ as my Prophet.",
            "Sunan Abi Dawud 5072",
            "3x, morning and evening"
        ),
        (
            "اللَّهُمَّ قَنِّعْنِي بِمَا رَزَقْتَنِي وَبَارِكْ لِي فِيهِ",
            "Allahumma qanni'ni bima razaqtani wa barik li fih",
            "O Allah, make me content with what You have provided me, and bless it for me.",
            "Reflects the Prophetic teaching on contentment (qana'ah) in Sahih Muslim 1054",
            "Recite when reflecting on your blessings"
        ),
    ],
    "hope": [
        (
            "حَسْبِيَ اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ عَلَيْهِ تَوَكَّلْتُ",
            "Hasbiyallahu la ilaha illa huwa, 'alayhi tawakkaltu",
            "Allah is sufficient for me; there is no deity except Him. Upon Him I have relied.",
            "Quran 9:129 — also recommended 7x morning and evening per Sunan Abi Dawud 5081",
            "7x morning and evening"
        ),
        (
            "وَلَا تَيْأَسُوا مِن رَّوْحِ اللَّهِ إِنَّهُ لَا يَيْأَسُ مِن رَّوْحِ اللَّهِ إِلَّا الْقَوْمُ الْكَافِرُونَ",
            "Wa la tay'asu min rawhillah, innahu la yay'asu min rawhillahi illal qawmul kafirun",
            "And despair not of relief from Allah, for none despairs of relief from Allah except the disbelieving people.",
            "Quran 12:87 — Ya'qub (AS) instructing his sons never to lose hope",
            "Reflect and recite when you need a reminder to hold on"
        ),
    ],

}

# ─────────────────────────────────────────────
# SECTION 2: STATIC SECULAR PRACTICES TABLE (MODE 3)
# ─────────────────────────────────────────────

SECULAR_TABLE = {
    "anxiety": [
        (
            "4-7-8 Breathing",
            "Inhale for 4 counts, hold for 7, exhale slowly for 8.",
            "Activates the parasympathetic nervous system, reducing the physiological stress response.",
            "Developed by Dr. Andrew Weil; supported by research on slow-paced breathing and HRV"
        ),
        (
            "Cognitive Defusion (ACT)",
            "Notice the anxious thought and label it: 'I'm having the thought that...'",
            "Creates distance between you and the thought, reducing its emotional grip without suppressing it.",
            "Acceptance and Commitment Therapy — Hayes et al., 2006"
        ),
    ],
    "grief": [
        (
            "Expressive Writing",
            "Write freely about your loss for 15-20 minutes without editing or judging.",
            "Shown to reduce grief intensity and improve long-term emotional processing.",
            "Pennebaker & Beall (1986); replicated across multiple clinical studies"
        ),
        (
            "Behavioural Activation",
            "Schedule one small, meaningful activity today — even a 10-minute walk.",
            "Counters the withdrawal that deepens grief by gently re-engaging with life.",
            "Evidence-based component of CBT for depression and bereavement"
        ),
    ],
    "panic": [
        (
            "5-4-3-2-1 Grounding",
            "Name 5 things you see, 4 you can touch, 3 you hear, 2 you smell, 1 you taste.",
            "Interrupts the panic feedback loop by anchoring attention to present sensory reality.",
            "Widely used in trauma-focused CBT and DBT protocols"
        ),
        (
            "Diaphragmatic Breathing",
            "Place one hand on your chest, one on your belly. Breathe so only the lower hand rises.",
            "Directly counteracts hyperventilation, the physiological driver of panic escalation.",
            "Barlow et al. — Panic Control Treatment protocol"
        ),
    ],
    "overwhelmed": [
        (
            "Task Chunking",
            "Write down everything overwhelming you. Pick the single smallest next action and do only that.",
            "Reduces cognitive load by converting an abstract burden into one concrete, manageable step.",
            "GTD methodology (David Allen); supported by research on decision fatigue"
        ),
        (
            "Progressive Muscle Relaxation",
            "Tense each muscle group for 5 seconds, then release. Start from your feet upward.",
            "Releases physical tension that accumulates with overwhelm, signalling safety to the nervous system.",
            "Jacobson (1938); standard protocol in clinical anxiety treatment"
        ),
    ],
    "loneliness": [
        (
            "Behavioural Scheduling",
            "Send one message to someone you care about today — it doesn't need to be deep.",
            "Loneliness is reinforced by withdrawal; one small social act interrupts the cycle.",
            "CBT for social anxiety and depression; Cacioppo & Patrick (2008) — Loneliness research"
        ),
        (
            "Self-Compassion Practice",
            "Place your hand on your heart and say: 'This is hard. I am not alone in feeling this.'",
            "Activates the self-soothing system, reducing the shame that often amplifies loneliness.",
            "Kristin Neff — Self-Compassion Scale research, 2003+"
        ),
    ],
    "guilt": [
        (
            "Cognitive Restructuring",
            "Ask: Is this guilt proportionate? What would I say to a friend in this situation?",
            "Separates healthy remorse (which motivates repair) from toxic guilt (which only punishes).",
            "Standard CBT technique — Beck et al.; Burns, Feeling Good (1980)"
        ),
        (
            "Making Amends (Behavioural)",
            "If repair is possible, take one concrete step. If not, write a letter you don't send.",
            "Transforms passive guilt into active resolution, breaking the rumination cycle.",
            "Emotion-focused therapy (EFT) — Greenberg; 12-step amends process research"
        ),
    ],
    "restlessness": [
        (
            "Mindful Body Scan",
            "Lie down. Slowly move attention from your toes to your head, noticing without judging.",
            "Channels restless mental energy into structured bodily awareness, inducing calm.",
            "MBSR — Kabat-Zinn (1990); extensively validated for restlessness and insomnia"
        ),
        (
            "Physical Discharge",
            "Do 20 jumping jacks, a brisk 5-minute walk, or shake your limbs vigorously.",
            "Restlessness often has unspent physical energy at its root; movement metabolises stress hormones.",
            "Somatic experiencing (Levine); exercise and cortisol reduction research"
        ),
    ],
    "hopelessness": [
        (
            "Values Clarification (ACT)",
            "Ask: If I felt 10% better, what is one thing I would do? What does that say about what I value?",
            "Reconnects to personal meaning when motivation has collapsed, without requiring mood to improve first.",
            "Acceptance and Commitment Therapy — Hayes, Wilson & Gifford"
        ),
        (
            "Behavioural Experiment",
            "Test the hopeless belief: 'Nothing will help.' Try one small thing and record the actual result.",
            "Hopelessness is a cognitive distortion — behavioural experiments provide evidence against it.",
            "CBT for depression — Beck's cognitive model of hopelessness"
        ),
    ],
    "gratitude": [
        (
            "Gratitude Journaling",
            "Write down three specific things that went well today and why.",
            "Repeatedly shown to increase sustained positive affect by shifting attentional bias toward the positive.",
            "Emmons & McCullough (2003) — 'Counting Blessings' study"
        ),
        (
            "Savoring Practice",
            "Pause on a positive moment and deliberately extend it — notice details, replay it mentally.",
            "Amplifies and prolongs positive emotion by countering hedonic adaptation.",
            "Bryant & Veroff — Savoring: A New Model of Positive Experience (2007)"
        ),
    ],
    "calm": [
        (
            "Box Breathing",
            "Inhale for 4 counts, hold for 4, exhale for 4, hold for 4. Repeat.",
            "Regulates the autonomic nervous system and lowers physiological arousal.",
            "Standard clinical stress-reduction protocol; supported by HRV biofeedback research"
        ),
        (
            "Single-Point Focus Meditation",
            "Sit quietly and rest your attention on one neutral point — your breath, a sound, a flame.",
            "Trains sustained attention and reduces the mind-wandering associated with low-grade stress.",
            "Core technique in Mindfulness-Based Stress Reduction — Kabat-Zinn (1990)"
        ),
    ],
    "contentment": [
        (
            "Values-Based Reflection",
            "Ask: what do I already have that aligns with what truly matters to me?",
            "Shifts focus from acquisition to appreciation, reducing hedonic-treadmill effects.",
            "Acceptance and Commitment Therapy — Hayes et al."
        ),
        (
            "Comparison Detox",
            "Notice one moment today you compared yourself to someone else, and redirect attention to your own circumstances.",
            "Social comparison is a primary driver of dissatisfaction; redirecting attention restores baseline contentment.",
            "Festinger's Social Comparison Theory; positive psychology applications"
        ),
    ],
    "hope": [
        (
            "Hope Mapping",
            "Write down one goal, one pathway to reach it, and one reason you believe you can.",
            "Builds agency and pathways thinking, the two components shown to predict resilience and wellbeing.",
            "C.R. Snyder — Hope Theory (1991+)"
        ),
        (
            "Best Possible Self Exercise",
            "Spend 10 minutes writing about your life going as well as it possibly could in the future.",
            "One of the most replicated positive-psychology interventions for boosting optimism and positive affect.",
            "King (2001); Sheldon & Lyubomirsky (2006)"
        ),
    ],
}

MENU_EMOTIONS = [
    "anxiety",
    "grief",
    "panic",
    "overwhelmed",
    "loneliness",
    "guilt",
    "restlessness",
    "hopelessness",
    "gratitude",
    "calm",
    "contentment",
    "hope",
]

# ─────────────────────────────────────────────
# SECTION 3: ADK AGENT FOR COMMENTARY
# ─────────────────────────────────────────────

DHIKR_COMMENTARY_PROMPT = """
You are Sakina, a compassionate Islamic wellness guide.
You will be given a user's emotional state and a set of dhikr practices.
Your job is to write a brief, warm, deeply personal introduction (4-6 sentences) that:
1. Validates the user's emotional state with empathy
2. Explains WHY these specific practices are suited to what they are feeling
3. Connects the Islamic wisdom to a modern psychological insight naturally
4. Ends with one sentence of gentle encouragement to begin

Do NOT list the practices again. Do NOT use bullet points. Write as if speaking warmly to a friend.
Keep it concise and human — this is a guide, not a lecture.
"""

SECULAR_COMMENTARY_PROMPT = """
You are Sakina, a compassionate evidence-based wellness guide.
You will be given a user's emotional state and a set of scientifically-supported practices.
Your job is to write a brief, warm, personal introduction (4-6 sentences) that:
1. Validates the user's emotional state with empathy and without judgment
2. Explains the psychological reasoning behind why these practices help
3. Normalises what they are feeling using psychological language (not religious)
4. Ends with one sentence of gentle encouragement to begin

Do NOT list the practices again. Do NOT use bullet points. Write as if speaking warmly to a friend.
Keep it concise and human — this is a guide, not a lecture.
"""


PRACTICE_PERSONALIZATION_PROMPT = """
You are Sakina, a compassionate {framework} wellness guide.

The user is feeling: {emotional_state}.{free_text_clause}

Below is a numbered list of practices that have already been selected for them.
Each practice's wording is fixed and must NOT be rewritten, translated, or quoted back at length.

{listed_practices}

For EACH practice above, in the same order, write one short personalized note (2-4 sentences) that:
1. Explains specifically why THIS practice suits what the user is feeling right now (not a generic reason)
2. Where it would genuinely help, suggests one small tailored variation they could try — for example an
   adjusted repetition count, a slower pace, pairing it with a breath count, or a moment of day that fits
   their situation. Only suggest a variation if it adds real value; otherwise skip that part.

Rules:
- Do not restate or quote the practice's own translation/instruction text verbatim.
- Do not add your own numbering, headers, or bullet points inside a note.
- Separate the notes with the exact delimiter "###" on its own line, and output NOTHING else
  (no preamble, no closing remarks) — just the {count} notes separated by {count_minus_one} delimiters.
"""


async def get_practice_personalizations(
    emotional_state: str,
    free_text: str,
    entries: list,
    mode: str,
    runner: Runner,
    session_id: str,
) -> list:
    """
    Asks the agent to produce one personalized note per practice, explaining why
    that specific practice fits the user's situation and optionally suggesting a
    tailored variation. The static practice content itself (Arabic/translation/
    citation, or instruction/why/source) is never altered by this step.

    Returns a list of strings, same length and order as `entries`. Falls back to
    a generic, locally-generated note per entry if the agent call fails or the
    response can't be cleanly split.
    """
    framework = "Islamic" if mode != "secular" else "evidence-based, secular"

    if mode != "secular":
        listed_practices = "\n".join(
            f'{i}. "{e[2]}" — {e[3]}'
            for i, e in enumerate(entries, 1)
        )
    else:
        listed_practices = "\n".join(
            f"{i}. {e[0]}: {e[1]}"
            for i, e in enumerate(entries, 1)
        )

    free_text_clause = f' They described it in their own words as: "{free_text}".' if free_text else ""

    prompt = PRACTICE_PERSONALIZATION_PROMPT.format(
        framework=framework,
        emotional_state=emotional_state,
        free_text_clause=free_text_clause,
        listed_practices=listed_practices,
        count=len(entries),
        count_minus_one=max(len(entries) - 1, 0),
    )

    fallback = [
        "This was chosen because it directly matches what you're feeling right now — let it meet you where you are."
        for _ in entries
    ]

    try:
        response = runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
            )
        )

        raw = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                raw = event.content.parts[0].text

        notes = [n.strip() for n in raw.split("###") if n.strip()]

        if len(notes) == len(entries):
            return notes

        return fallback

    except Exception:
        return fallback


async def get_ai_commentary(emotional_state: str, mode: str, runner: Runner, session_id: str) -> str:
    """Gets personalised AI commentary for the given emotional state and mode."""

    system_prompt = DHIKR_COMMENTARY_PROMPT if mode != "secular" else SECULAR_COMMENTARY_PROMPT
    practice_type = "dhikr and du'a practices" if mode != "secular" else "evidence-based practices"

    user_prompt = (
        f"The user is feeling: {emotional_state}.\n"
        f"You are about to present them with {practice_type} tailored to this state.\n"
        f"Write your warm, personal introduction now."
    )

    try:
        response = runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=user_prompt)]
            )
        )

        commentary = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                commentary = event.content.parts[0].text

        return commentary

    except Exception as e:
        return f"[Commentary unavailable: {e}]"


# ─────────────────────────────────────────────
# SECTION 4: DISPLAY FUNCTIONS
# ─────────────────────────────────────────────

def display_dhikr(entries: list) -> None:
    """Prints dhikr entries in a clean, readable terminal format."""
    for i, (arabic, transliteration, translation, reference, repetitions) in enumerate(entries, 1):
        print(f"\n  {'─' * 44}")
        print(f"  Practice {i}")
        print(f"  {'─' * 44}")
        print(f"\n  ❝ {arabic} ❞")
        print(f"\n  {transliteration}")
        print(f"  \"{translation}\"")
        print(f"\n  📖 {reference}")
        print(f"  🔁 {repetitions}")


def display_secular(entries: list) -> None:
    """Prints secular practice entries in a clean, readable terminal format."""
    for i, (name, instruction, why, source) in enumerate(entries, 1):
        print(f"\n  {'─' * 44}")
        print(f"  Practice {i}: {name}")
        print(f"  {'─' * 44}")
        print(f"\n  How: {instruction}")
        print(f"\n  Why it works: {why}")
        print(f"\n  📚 Source: {source}")


# ─────────────────────────────────────────────
# SECTION 5: EMOTION RESOLUTION
# ─────────────────────────────────────────────

async def resolve_emotion_with_ai(free_text: str, runner: Runner, session_id: str) -> str:
    """
    Uses Gemini to map a free-text emotional description to one of the
    canonical emotion keys in our table.
    """
    valid_keys = ", ".join(MENU_EMOTIONS)
    prompt = (
        f'A user described their emotional state as: "{free_text}".\n'
        f"Map this to exactly one of these emotion labels: {valid_keys}.\n"
        f"Reply with only the single matching word, nothing else."
    )

    try:
        response = runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=prompt)]
            )
        )

        result = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                result = event.content.parts[0].text.strip().lower()

        # Validate the returned key is one we know
        if result in MENU_EMOTIONS:
            return result

    except Exception:
        pass

    # Fallback: simple keyword match
    for emotion in MENU_EMOTIONS:
        if emotion in free_text.lower():
            return emotion

    return "anxiety"  # safe default


# ─────────────────────────────────────────────
# SECTION 6: MAIN DHIKR FLOW
# ─────────────────────────────────────────────

async def main():
    print("\n" + "=" * 50)
    print("     Sakina — Dhikr & Practice Guide 🌿")
    print("=" * 50)

    # ── Mode selection ──
    print("\nHow would you like your suggestions today?")
    print("  1. Islamic (Dhikr & Du'a)")
    print("  2. Secular (Evidence-based practices only)")
    print()

    while True:
        mode_input = input("Enter 1 or 2: ").strip()
        if mode_input == "1":
            mode = "islamic"
            table = DHIKR_TABLE
            break
        elif mode_input == "2":
            mode = "secular"
            table = SECULAR_TABLE
            break
        else:
            print("Please enter 1 or 2.")

    # ── ADK setup ──
    session_id = "dhikr_session"
    system_prompt = DHIKR_COMMENTARY_PROMPT if mode == "islamic" else SECULAR_COMMENTARY_PROMPT

    commentary_agent = Agent(
        name="SakinaDhikrGuide",
        model="gemini-2.5-flash",
        instruction=system_prompt,
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )

    # Separate session for emotion resolution
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id="emotion_resolver"
    )

    runner = Runner(
        agent=commentary_agent,
        app_name=APP_NAME,
        session_service=session_service
    )

    # ── Emotion selection ──
    print("\nHow are you feeling right now?")
    print()
    for i, emotion in enumerate(MENU_EMOTIONS, 1):
        print(f"  {i}. {emotion.capitalize()}")
    print(f"  {len(MENU_EMOTIONS) + 1}. Describe in your own words")
    print()

    while True:
        choice = input("Enter a number or type your feeling: ").strip()

        # Numeric menu choice
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(MENU_EMOTIONS):
                emotional_state = MENU_EMOTIONS[num - 1]
                break
            elif num == len(MENU_EMOTIONS) + 1:
                free_text = input("\nDescribe how you're feeling: ").strip()
                if free_text:
                    print("\n  Reflecting on what you've shared...")
                    emotional_state = await resolve_emotion_with_ai(
                        free_text, runner, "emotion_resolver"
                    )
                    print(f"  I hear you — this sounds closest to: {emotional_state}\n")
                    break
            else:
                print(f"  Please enter a number between 1 and {len(MENU_EMOTIONS) + 1}.")

        # Free text fallback (non-numeric input)
        elif len(choice) > 2:
            print("\n  Reflecting on what you've shared...")
            emotional_state = await resolve_emotion_with_ai(choice, runner, "emotion_resolver")
            print(f"  I hear you — this sounds closest to: {emotional_state}\n")
            break
        else:
            print(f"  Please enter a number or describe your feeling.")

    # ── Fetch practices ──
    entries = table.get(emotional_state, table.get("anxiety"))

    # ── AI commentary ──
    print("\n" + "=" * 50)
    print(f"  For what you're feeling: {emotional_state.capitalize()}")
    print("=" * 50)
    print("\n  One moment...\n")

    commentary = await get_ai_commentary(emotional_state, mode, runner, session_id)
    print(f"  {commentary}\n")

    # ── Display practices ──
    if mode == "islamic":
        display_dhikr(entries)
    else:
        display_secular(entries)

    print(f"\n  {'─' * 44}")
    print("  May this bring you stillness. 🌿")
    print(f"  {'─' * 44}\n")


if __name__ == "__main__":
    asyncio.run(main())