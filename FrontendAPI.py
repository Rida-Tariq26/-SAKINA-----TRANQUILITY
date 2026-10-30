"""
FastAPI backend for Sakina UI with Bring Your Own Key (BYOK) Architecture.
Bridges the React frontend to the ADK agent and MCP background server
while supporting user-provided Google Gemini API keys.

Run with:
    uvicorn FrontendAPI:app --reload --port 8000
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import sys
import json
import asyncio
import logging
import hashlib
import html
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Request, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models.registry import LLMRegistry
from google.genai import types, Client
from dotenv import load_dotenv

# Google OAuth token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# SQLite database layer
from database import (
    init_db, upsert_user, get_user,
    add_mood_log, get_recent_mood_logs, get_all_mood_logs,
    add_journal_entry, get_journal_entries, get_journal_entry,
    update_journal_entry, delete_journal_entry,
    export_user_data, delete_user_data,
    add_feedback, count_recent_feedback_by_ip, get_feedback_submissions,
    approve_feedback, get_public_reviews, seed_sample_reviews_if_empty,
)

# Import MCP Client utilities
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import existing modules
from system_prompt import SYSTEM_PROMPT
from dhikr import (
    DHIKR_TABLE, SECULAR_TABLE,
    DHIKR_COMMENTARY_PROMPT, CLINICAL_SCIENTIFIC_COMMENTARY_PROMPT,
    resolve_emotion_with_ai,
    get_practice_personalizations,
    get_ai_commentary,
)
from mood_tracker import log_and_synthesize, get_dashboard, analyze_trends, TREND_COMMENTARY_PROMPT

load_dotenv()

logger = logging.getLogger("sakina.api")

APP_NAME = "Sakina"
DEFAULT_USER_ID = "default_user"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# Global references for shared services and MCP tools
session_service = InMemorySessionService()
mcp_session_instance: Optional[ClientSession] = None
mcp_discovered_tools: List[Any] = []
mcp_agent_tools: List[Any] = []

# In-memory mood commentary cache: (user_id, normalized_mode, latest_ts, log_count) -> commentary
mood_commentary_cache: Dict[str, str] = {}


def get_scoped_mcp_tools(target_user_id: str) -> List[Any]:
    """
    Returns user-scoped MCP tool callables.
    Enforces that all tool invocations (such as mood_log_tool and mood_history_tool)
    are bound strictly and immutably to target_user_id, preventing cross-user data leakage.
    """
    safe_uid = (target_user_id or DEFAULT_USER_ID).strip()
    if not mcp_session_instance or not mcp_discovered_tools:
        return mcp_agent_tools

    scoped_tools = []
    for tool_def in mcp_discovered_tools:
        tool_name = tool_def.name

        def make_scoped_call(name=tool_name, uid=safe_uid):
            async def async_wrapper(**kwargs):
                args = dict(kwargs)
                args["user_id"] = uid
                res = await mcp_session_instance.call_tool(name, arguments=args)
                return "".join(
                    content.text for content in res.content if hasattr(content, "text")
                )
            return async_wrapper

        tool_func = make_scoped_call(tool_name, safe_uid)
        tool_func.__name__ = tool_def.name
        tool_func.__doc__ = tool_def.description or f"MCP tool: {tool_def.name}"
        scoped_tools.append(tool_func)

    return scoped_tools


# ─────────────────────────────────────────────
# RUNNER & AGENT FACTORY (BYOK SUPPORT)
# ─────────────────────────────────────────────
def get_effective_api_key(header_key: Optional[str] = None) -> Optional[str]:
    """Resolves user-supplied header key or server environment fallback."""
    if header_key and header_key.strip():
        return header_key.strip()
    env_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip() and not env_key.startswith("your_"):
        return env_key.strip()
    return None


def create_llm_instance(model_name: str, api_key: Optional[str] = None):
    """Creates a model instance targeting the specific API key and active model."""
    target_model = model_name if model_name and model_name.strip() else DEFAULT_MODEL
    # Sanitize any legacy unsupported model identifiers
    if "gemini-2.5" in target_model:
        target_model = DEFAULT_MODEL
    try:
        cls = LLMRegistry.resolve(target_model)
    except Exception:
        cls = LLMRegistry.resolve(DEFAULT_MODEL)
        target_model = DEFAULT_MODEL

    effective_key = get_effective_api_key(api_key)
    if effective_key:
        client = Client(api_key=effective_key)
        return cls(model=target_model, client=client)
    return cls(model=target_model)


def create_chat_runner(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    user_id: str = DEFAULT_USER_ID,
) -> Runner:
    """Creates a scoped Chat Runner configured with the target API key & user-isolated MCP tools."""
    llm = create_llm_instance(model_name or DEFAULT_MODEL, api_key)
    tools = get_scoped_mcp_tools(user_id)
    agent = Agent(
        name="Sakina",
        model=llm,
        instruction=SYSTEM_PROMPT,
        tools=tools,
    )
    return Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
        auto_create_session=True,
    )


def create_mood_runner(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    user_id: str = DEFAULT_USER_ID,
) -> Runner:
    """Creates a scoped Mood Runner configured with the target API key & user-isolated MCP tools."""
    llm = create_llm_instance(model_name or DEFAULT_MODEL, api_key)
    tools = get_scoped_mcp_tools(user_id)
    agent = Agent(
        name="SakinaMood",
        model=llm,
        instruction=TREND_COMMENTARY_PROMPT,
        tools=tools,
    )
    return Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
        auto_create_session=True,
    )


async def prune_session_history(user_id: str, session_id: str, max_messages: int = 14) -> None:
    """Prune session history to keep memory bounded and response fast."""
    try:
        session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        if session and hasattr(session, "history") and session.history:
            if len(session.history) > max_messages:
                session.history = session.history[-max_messages:]
    except Exception as e:
        logger.debug(f"Session history prune notice: {e}")


# ─────────────────────────────────────────────
# LIFECYCLE: CONNECT TO MCP SERVER ON STARTUP
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp_agent_tools, mcp_session_instance, mcp_discovered_tools

    # Initialise SQLite database
    init_db()
    seed_sample_reviews_if_empty()

    ctx = None
    session_ctx = None

    try:
        # Configure parameters to spawn server.py as a background protocol worker
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")],
            env=os.environ.copy(),
        )

        ctx = stdio_client(server_params)
        read, write = await ctx.__aenter__()

        session_ctx = ClientSession(read, write)
        mcp_session = await session_ctx.__aenter__()
        await mcp_session.initialize()

        # Fetch available tools over the protocol channel
        mcp_tools_response = await mcp_session.list_tools()
        mcp_session_instance = mcp_session
        mcp_discovered_tools = list(mcp_tools_response.tools)

        agent_tools = []
        for tool in mcp_tools_response.tools:
            def make_mcp_call(tool_name=tool.name):
                async def async_wrapper(**kwargs):
                    res = await mcp_session.call_tool(tool_name, arguments=kwargs)
                    return "".join(
                        content.text for content in res.content if hasattr(content, "text")
                    )
                return async_wrapper

            tool_func = make_mcp_call(tool.name)
            tool_func.__name__ = tool.name
            tool_func.__doc__ = tool.description or f"MCP tool: {tool.name}"
            agent_tools.append(tool_func)

        mcp_agent_tools = agent_tools
        logger.info("MCP server connected successfully with %d tools.", len(agent_tools))
    except Exception as e:
        logger.warning(f"MCP server initialization encountered notice (proceeding in standalone mode): {e}")
        mcp_agent_tools = []
        mcp_session_instance = None
        mcp_discovered_tools = []

    yield

    # Clean cleanup on application exit
    mcp_session_instance = None
    mcp_discovered_tools = []
    if session_ctx:
        try:
            await session_ctx.__aexit__(None, None, None)
        except Exception:
            pass
    if ctx:
        try:
            await ctx.__aexit__(None, None, None)
        except Exception:
            pass


# Initialize FastAPI with the lifespan orchestrator
app = FastAPI(lifespan=lifespan)

# ─────────────────────────────────────────────
# CORS CONFIGURATION (Enables Render Static Landing Site access)
# ─────────────────────────────────────────────
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
allowed_origins = [
    "https://sakina-landing.onrender.com",
    "https://sakina-islamic-wellness-ai.onrender.com",
    "https://sakina-tranquility.onrender.com",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5500",
]
if cors_origins_env:
    for origin in cors_origins_env.split(","):
        origin = origin.strip()
        if origin and origin not in allowed_origins:
            allowed_origins.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https:\/\/.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────
class FeedbackCreateRequest(BaseModel):
    feedback_type: Optional[str] = "review"
    message: str
    rating: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    hp_website: Optional[str] = None  # Honeypot field for spam prevention

class ModerateFeedbackRequest(BaseModel):
    is_approved: bool = True

class TokenVerifyRequest(BaseModel):
    token: str

class UserProfileResponse(BaseModel):
    sub: str
    email: str
    name: str
    picture: str

class KeyVerifyRequest(BaseModel):
    key: str
    model: Optional[str] = DEFAULT_MODEL

class KeyVerifyResponse(BaseModel):
    valid: bool
    model: str
    message: str

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class DhikrRequest(BaseModel):
    emotion: str = ""
    free_text: str = ""
    mode: str = "islamic"

class DhikrResponse(BaseModel):
    commentary: str
    practices: list
    emotion: str

class MoodRequest(BaseModel):
    emotion: str
    intensity: int
    note: str = ""
    mode: str = "islamic"

class JournalEntryCreate(BaseModel):
    title: str
    content: str
    mood: Optional[str] = ""
    prompt: Optional[str] = ""

class JournalEntryUpdate(BaseModel):
    title: str
    content: str
    mood: Optional[str] = ""
    prompt: Optional[str] = ""


# ─────────────────────────────────────────────
# API KEY VALIDATION ENDPOINT
# ─────────────────────────────────────────────
@app.post("/api/key/verify", response_model=KeyVerifyResponse)
async def verify_api_key_endpoint(
    req: KeyVerifyRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
):
    key_to_test = req.key.strip() if req.key else (x_gemini_api_key.strip() if x_gemini_api_key else "")
    primary_model = req.model or x_gemini_model or DEFAULT_MODEL

    if not key_to_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No API key provided to verify.",
        )

    # Candidate models to try in case the key is tied to a specific API namespace/endpoint
    candidate_models = [primary_model]
    for fallback in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"]:
        if fallback not in candidate_models:
            candidate_models.append(fallback)

    last_err = None
    try:
        client = Client(api_key=key_to_test)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to initialize Gemini client: {str(e)}",
        )

    for candidate in candidate_models:
        try:
            test_response = client.models.generate_content(
                model=candidate,
                contents="Respond with only: OK",
            )
            if test_response:
                return KeyVerifyResponse(
                    valid=True,
                    model=candidate,
                    message=f"Gemini API key is active and connected to {candidate}.",
                )
        except Exception as e:
            last_err = e
            err_msg = str(e)
            if "API_KEY_INVALID" in err_msg or "400" in err_msg or "403" in err_msg or "not valid" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid Google Gemini API key. Please verify your key on Google AI Studio.",
                )
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="API key is valid, but current quota limit (429) was reached. Please wait a few minutes.",
                )
            # If 404 / NOT_FOUND, continue trying candidate models
            continue

    err_msg = str(last_err) if last_err else "Unknown error"
    if "404" in err_msg or "NOT_FOUND" in err_msg:
        detail = f"Could not find a supported Gemini model for this API key. Tested: {', '.join(candidate_models)}."
    else:
        detail = f"Verification failed: {err_msg}"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


# ─────────────────────────────────────────────
# AUTH & USER DATA ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/auth/verify", response_model=UserProfileResponse)
async def verify_google_token(req: TokenVerifyRequest):
    try:
        client_id = os.environ.get("VITE_GOOGLE_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
        idinfo = id_token.verify_oauth2_token(
            req.token,
            google_requests.Request(),
            audience=client_id if client_id else None
        )
        
        user_id = idinfo.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid token payload: missing sub")
            
        email = idinfo.get("email", "")
        name = idinfo.get("name", "")
        picture = idinfo.get("picture", "")
        
        upsert_user(user_id=user_id, email=email, name=name, picture=picture)
        return UserProfileResponse(sub=user_id, email=email, name=name, picture=picture)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


@app.post("/api/auth/logout")
async def logout_endpoint(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if x_user_id:
        user_id = x_user_id.strip()
        keys_to_remove = [k for k in mood_commentary_cache if k.startswith(f"{user_id}:")]
        for k in keys_to_remove:
            mood_commentary_cache.pop(k, None)
    return {"status": "ok"}


@app.get("/api/user/data/export")
async def export_user_data_endpoint(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    data = export_user_data(x_user_id.strip())
    return JSONResponse(content=data)


@app.delete("/api/user/data")
async def delete_user_data_endpoint(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    user_id = x_user_id.strip()
    delete_user_data(user_id)

    # 1. Purge user-scoped in-memory sessions from InMemorySessionService
    if APP_NAME in session_service.sessions and user_id in session_service.sessions[APP_NAME]:
        session_service.sessions[APP_NAME].pop(user_id, None)
    if APP_NAME in session_service.user_state and user_id in session_service.user_state[APP_NAME]:
        session_service.user_state[APP_NAME].pop(user_id, None)

    # 2. Purge user-scoped in-memory commentary cache
    keys_to_remove = [k for k in mood_commentary_cache if k.startswith(f"{user_id}:")]
    for k in keys_to_remove:
        mood_commentary_cache.pop(k, None)

    return {"status": "deleted"}


# ─────────────────────────────────────────────
# GREETING ENDPOINT
# ─────────────────────────────────────────────
@app.post("/api/greeting")
async def post_greeting_endpoint(
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    fallback_greeting = (
        "Assalam-o-Alaikum \n\n"
        "I am Sakina a space for stillness. Whatever is weighing on your heart today, "
        "you are welcome to share it here.\n\nWhat's on your mind?"
    )

    effective_key = get_effective_api_key(x_gemini_api_key)
    if not effective_key:
        return {"response": fallback_greeting}

    user_id = (x_user_id or DEFAULT_USER_ID).strip()
    session_id = f"chat_{user_id}"
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model, user_id=user_id)

    try:
        async def _call_greeting():
            response = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text="Greet the user warmly with your opening message.")]
                )
            )
            final_text = ""
            async for event in response:
                if event.is_final_response() and event.content and event.content.parts:
                    final_text = event.content.parts[0].text
            return final_text

        final_text = await asyncio.wait_for(_call_greeting(), timeout=20.0)
        return {"response": final_text if final_text else fallback_greeting}
    except Exception as e:
        logger.warning(f"Greeting generation fallback: {e}")
        return {"response": fallback_greeting}


# ─────────────────────────────────────────────
# CORE CHAT ENDPOINT
# ─────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def post_chat_endpoint(
    req: ChatRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    effective_key = get_effective_api_key(x_gemini_api_key)
    if not effective_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gemini API key is required. Please add your free personal Gemini API key in Settings.",
        )

    user_id = (x_user_id or DEFAULT_USER_ID).strip()
    session_id = f"chat_{user_id}"
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model, user_id=user_id)

    try:
        await prune_session_history(user_id=user_id, session_id=session_id, max_messages=14)

        async def _call_chat():
            response = runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=req.message)]
                )
            )
            final_text = ""
            async for event in response:
                if event.is_final_response() and event.content and event.content.parts:
                    final_text = event.content.parts[0].text
            return final_text

        final_text = await asyncio.wait_for(_call_chat(), timeout=25.0)
        if not final_text:
            final_text = "I am listening. Please continue."
            
        return ChatResponse(response=final_text)
    except asyncio.TimeoutError:
        logger.warning("Chat generation timed out after 25s.")
        return ChatResponse(
            response="I am taking a moment to reflect with you. Please feel free to rephrase or continue sharing whenever you are ready."
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Your Gemini API key has exceeded its rate or daily quota limit. Please check your key in Settings or wait a moment.",
            )
        elif "API_KEY_INVALID" in err_str or "400" in err_str or "401" in err_str or "403" in err_str or "not valid" in err_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Gemini API key. Please update your API key in Settings.",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=err_str)


# ─────────────────────────────────────────────
# DHIKR ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/dhikr", response_model=DhikrResponse)
async def post_dhikr_endpoint(
    req: DhikrRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    user_id = (x_user_id or DEFAULT_USER_ID).strip()
    dhikr_session = f"dhikr_{user_id}"
    resolver_session = f"resolver_{user_id}"

    effective_key = get_effective_api_key(x_gemini_api_key)
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model, user_id=user_id) if effective_key else None

    is_islamic = req.mode not in ("secular", "clinical_scientific")

    # Step 1: Resolve emotion
    input_for_resolution = req.free_text if req.free_text.strip() else req.emotion
    if req.emotion.strip():
        emotion = req.emotion.strip()
    elif runner:
        try:
            emotion = await asyncio.wait_for(
                resolve_emotion_with_ai(input_for_resolution, runner, resolver_session, user_id=user_id),
                timeout=15.0,
            )
        except Exception:
            emotion = "anxiety"
    else:
        emotion = "anxiety"

    # Step 2: Fetch static practice entries from the table
    table = DHIKR_TABLE if is_islamic else SECULAR_TABLE
    raw_practices = table.get(emotion, table.get("anxiety", []))

    # Step 3: Get AI-generated personalization notes (or fallback)
    personalization_notes = []
    if runner:
        try:
            personalization_notes = await asyncio.wait_for(
                get_practice_personalizations(
                    emotional_state=emotion,
                    free_text=req.free_text,
                    entries=raw_practices,
                    mode="islamic" if is_islamic else "clinical_scientific",
                    runner=runner,
                    session_id=dhikr_session,
                    user_id=user_id,
                ),
                timeout=20.0,
            )
        except Exception:
            personalization_notes = []

    # Step 4: Merge static data + personalization notes
    practices = []
    if is_islamic:
        for i, entry in enumerate(raw_practices):
            arabic, transliteration, translation, reference, repetitions = entry
            note = personalization_notes[i] if i < len(personalization_notes) else ""
            practices.append({
                "arabic": arabic,
                "transliteration": transliteration,
                "translation": translation,
                "reference": reference,
                "repetitions": repetitions,
                "personalization": note,
            })
    else:
        for i, entry in enumerate(raw_practices):
            name, instruction, why, source = entry
            note = personalization_notes[i] if i < len(personalization_notes) else ""
            practices.append({
                "name": name,
                "instruction": instruction,
                "why": why,
                "source": source,
                "personalization": note,
            })

    # Step 5: Generate AI commentary (or fallback)
    commentary = ""
    if runner:
        try:
            commentary = await asyncio.wait_for(
                get_ai_commentary(
                    emotional_state=emotion,
                    mode="islamic" if is_islamic else "clinical_scientific",
                    runner=runner,
                    session_id=dhikr_session,
                    user_id=user_id,
                ),
                timeout=20.0,
            )
        except Exception:
            commentary = ""

    if not commentary:
        commentary = (
            "Here are practices tailored to bring tranquility and presence to your heart."
            if is_islamic
            else "Here are clinical & scientific practices designed to help center your nervous system."
        )

    return DhikrResponse(commentary=commentary, practices=practices, emotion=emotion)


# ─────────────────────────────────────────────
# MOOD ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/mood")
async def post_mood_endpoint(
    req: MoodRequest,
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = (x_user_id or DEFAULT_USER_ID).strip()
        mood_session = f"mood_{user_id}"
        effective_key = get_effective_api_key(x_gemini_api_key)
        runner = create_mood_runner(api_key=effective_key, model_name=x_gemini_model, user_id=user_id)

        normalized_mode = "islamic" if req.mode not in ("secular", "clinical_scientific") else "clinical_scientific"

        data = await asyncio.wait_for(
            log_and_synthesize(
                emotional_state=req.emotion,
                intensity=req.intensity,
                note=req.note,
                mode=normalized_mode,
                runner=runner,
                session_id=mood_session,
                user_id=user_id,
            ),
            timeout=25.0,
        )

        # Update cache for instant subsequent dashboard retrieval
        recent = data.get("recent_entries", [])
        latest_ts = recent[-1]["timestamp"] if recent else "new"
        all_logs = get_all_mood_logs(user_id=user_id)
        cache_key = f"{user_id}:{normalized_mode}:{latest_ts}:{len(all_logs)}"
        if data.get("commentary"):
            mood_commentary_cache[cache_key] = data["commentary"]

        return data
    except Exception as e:
        logger.error(f"Error in post_mood_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mood")
async def get_mood_endpoint(
    mode: str = "islamic",
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = (x_user_id or DEFAULT_USER_ID).strip()
        mood_session = f"mood_{user_id}"
        normalized_mode = "islamic" if mode not in ("secular", "clinical_scientific") else "clinical_scientific"

        # Check cached commentary
        recent_logs = get_recent_mood_logs(user_id=user_id, limit=7)
        latest_ts = recent_logs[-1]["timestamp"] if recent_logs else "empty"
        all_logs = get_all_mood_logs(user_id=user_id)
        log_count = len(all_logs)
        cache_key = f"{user_id}:{normalized_mode}:{latest_ts}:{log_count}"

        if cache_key in mood_commentary_cache:
            trends = analyze_trends(user_id=user_id, days=30)
            return {
                "trends": trends,
                "commentary": mood_commentary_cache[cache_key],
                "recent_entries": recent_logs,
            }

        effective_key = get_effective_api_key(x_gemini_api_key)
        runner = create_mood_runner(api_key=effective_key, model_name=x_gemini_model, user_id=user_id)

        data = await asyncio.wait_for(
            get_dashboard(
                mode=normalized_mode,
                runner=runner,
                session_id=mood_session,
                user_id=user_id,
            ),
            timeout=25.0,
        )

        if data.get("commentary"):
            mood_commentary_cache[cache_key] = data["commentary"]

        return data
    except Exception as e:
        logger.warning(f"Dashboard load fallback: {e}")
        # Return fallback dashboard instead of 500
        trends = analyze_trends(user_id=user_id, days=30)
        return {
            "trends": trends,
            "commentary": "Taking time to notice your patterns is a meaningful step toward balance and clarity. Keep checking in with yourself as you navigate each day.",
            "recent_entries": get_recent_mood_logs(user_id=user_id, limit=7),
        }


# ─────────────────────────────────────────────
# JOURNAL ENDPOINTS
# ─────────────────────────────────────────────
@app.get("/api/journal")
async def get_journal_endpoint(
    search: Optional[str] = "",
    mood: Optional[str] = "",
    limit: int = 100,
    offset: int = 0,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = x_user_id.strip() if (x_user_id and x_user_id.strip()) else DEFAULT_USER_ID
        entries = get_journal_entries(
            user_id=user_id,
            search=search or "",
            mood=mood or "",
            limit=limit,
            offset=offset
        )
        return {"entries": entries}
    except Exception as e:
        logger.error(f"Error fetching journal entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/journal")
async def create_journal_endpoint(
    req: JournalEntryCreate,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = x_user_id.strip() if (x_user_id and x_user_id.strip()) else DEFAULT_USER_ID
        if not req.title.strip() and not req.content.strip():
            raise HTTPException(status_code=400, detail="Journal entry cannot be empty")
        entry = add_journal_entry(
            user_id=user_id,
            title=req.title.strip() or "Untitled Reflection",
            content=req.content,
            mood=req.mood or "",
            prompt=req.prompt or ""
        )
        return entry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating journal entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/journal/{entry_id}")
async def update_journal_endpoint(
    entry_id: int,
    req: JournalEntryUpdate,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = x_user_id.strip() if (x_user_id and x_user_id.strip()) else DEFAULT_USER_ID
        updated = update_journal_entry(
            entry_id=entry_id,
            user_id=user_id,
            title=req.title.strip() or "Untitled Reflection",
            content=req.content,
            mood=req.mood or "",
            prompt=req.prompt or ""
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating journal entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/journal/{entry_id}")
async def delete_journal_endpoint(
    entry_id: int,
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    try:
        user_id = x_user_id.strip() if (x_user_id and x_user_id.strip()) else DEFAULT_USER_ID
        deleted = delete_journal_entry(entry_id=entry_id, user_id=user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Journal entry not found")
        return {"status": "deleted", "id": entry_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting journal entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# VISITOR FEEDBACK & PUBLIC REVIEWS ENDPOINTS
# ─────────────────────────────────────────────
ALLOWED_FEEDBACK_TYPES = {"general", "feature", "bug", "experience", "review"}

@app.post("/api/feedback")
async def submit_feedback_endpoint(req: FeedbackCreateRequest, request: Request):
    """
    Public feedback and review submission endpoint for the landing page.
    Validates, sanitizes, rate-limits, and securely persists visitor feedback.
    Never exposes internal error traces, API keys, or private records.
    """
    try:
        # 1. Honeypot check (spam bot trap)
        if req.hp_website and req.hp_website.strip():
            logger.info("Feedback honeypot triggered; discarding bot submission.")
            return {"status": "success", "message": "Thank you for sharing your feedback with Sakina."}

        # 2. Rate limiting via salted client IP hash
        client_ip = request.headers.get("x-forwarded-for", "")
        if client_ip:
            client_ip = client_ip.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        ip_salt = os.environ.get("FEEDBACK_IP_SALT", "sakina_privacy_salt_2026")
        ip_hash = hashlib.sha256(f"{client_ip}:{ip_salt}".encode("utf-8")).hexdigest()[:32]

        recent_count = count_recent_feedback_by_ip(ip_hash, window_seconds=3600)
        if recent_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You have submitted feedback recently. Please wait a while before submitting again.",
            )

        # 3. Validate feedback type (defaults to 'review' if not provided)
        raw_type = (req.feedback_type or "review").strip().lower()
        cleaned_type = raw_type if raw_type else "review"
        if cleaned_type not in ALLOWED_FEEDBACK_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid feedback type '{cleaned_type}'. Allowed types: {', '.join(sorted(ALLOWED_FEEDBACK_TYPES))}.",
            )

        # 4. Validate rating (required for reviews, optional for other feedback types)
        cleaned_rating = req.rating
        if cleaned_type == "review" and cleaned_rating is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rating is required for reviews (1 to 5 stars).",
            )
        if cleaned_rating is not None:
            if not isinstance(cleaned_rating, int) or cleaned_rating < 1 or cleaned_rating > 5:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Rating must be an integer between 1 and 5.",
                )

        # 5. Validate & sanitize message (required, 10-2000 chars)
        raw_message = (req.message or "").strip()
        if len(raw_message) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback message must be at least 10 characters long.",
            )
        if len(raw_message) > 2000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback message cannot exceed 2000 characters.",
            )

        # Sanitize HTML tags
        cleaned_message = html.escape(raw_message)

        # 6. Validate & sanitize name (optional display name, max 50 chars)
        raw_name = (req.name or "").strip()
        if not raw_name or raw_name.lower() in ("anonymous", "anon"):
            cleaned_name = "Anonymous"
        else:
            cleaned_name = html.escape(raw_name[:50])

        # 7. Validate & sanitize email (optional, max 100 chars, valid regex)
        cleaned_email = None
        if req.email and req.email.strip():
            raw_email = req.email.strip().lower()
            if len(raw_email) > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email address cannot exceed 100 characters.",
                )
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", raw_email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please enter a valid email address.",
                )
            cleaned_email = raw_email

        # 8. Extract sanitized User-Agent
        raw_ua = request.headers.get("user-agent", "")
        cleaned_ua = raw_ua[:250] if raw_ua else None

        # 9. Immediate publication status (reviews display publicly immediately without moderation)
        is_approved = 1

        # 10. Persist to SQLite
        add_feedback(
            feedback_type=cleaned_type,
            message=cleaned_message,
            rating=cleaned_rating,
            name=cleaned_name,
            email=cleaned_email,
            ip_hash=ip_hash,
            user_agent=cleaned_ua,
            is_approved=is_approved,
        )

        # Redacted logging (Never log message text, IP, or user email)
        logger.info("Feedback successfully submitted: type=%s, rating=%s, approved=%s", cleaned_type, cleaned_rating, is_approved)

        return {
            "status": "success",
            "message": "Thank you for sharing your experience!",
            "is_approved": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing feedback submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while saving your feedback. Please try again later.",
        )


@app.get("/api/reviews")
@app.get("/api/feedback/public")
async def get_public_reviews_endpoint(limit: int = 10, offset: int = 0):
    """
    Public endpoint to retrieve reviews for the landing page.
    Excludes all sensitive/private information (emails, IP hashes, user agents).
    Returns average rating, total count of published reviews, and recent reviews.
    """
    try:
        data = get_public_reviews(limit=limit, offset=offset)
        return data
    except Exception as e:
        logger.error(f"Error fetching public reviews: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve reviews.",
        )


@app.post("/api/admin/feedback/{feedback_id}/approve")
@app.patch("/api/admin/feedback/{feedback_id}/approve")
async def moderate_feedback_endpoint(
    feedback_id: int,
    req: Optional[ModerateFeedbackRequest] = None,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """
    Secure administrative endpoint to approve or reject a review for public display.
    Strictly protected by X-Admin-Key header and never accessible publicly.
    """
    expected_key = os.environ.get("SAKINA_ADMIN_KEY")
    if not expected_key or not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized. Admin authorization required.",
        )
    should_approve = req.is_approved if req else True
    success = approve_feedback(feedback_id, is_approved=1 if should_approve else 0)
    if not success:
        raise HTTPException(status_code=404, detail="Review not found.")
    action = "approved" if should_approve else "rejected"
    return {"status": "success", "message": f"Review #{feedback_id} has been {action}."}


@app.get("/api/admin/feedback")
async def get_admin_feedback_endpoint(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    moderation_status: Optional[str] = Query(None, alias="status"),
    limit: int = 50,
    offset: int = 0,
):
    """
    Secure administrative endpoint to inspect submitted feedback.
    Strictly protected by X-Admin-Key header and never accessible publicly.
    """
    expected_key = os.environ.get("SAKINA_ADMIN_KEY")
    if not expected_key or not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized. Admin authorization required.",
        )
    return {"feedback": get_feedback_submissions(limit=limit, offset=offset, status=moderation_status)}


# ─────────────────────────────────────────────
# SERVE REACT FRONTEND (Production Build) & SEO ROUTES
# ─────────────────────────────────────────────
root_path = os.path.dirname(os.path.abspath(__file__))
build_path = os.path.join(root_path, "dist")
public_path = os.path.join(root_path, "public")

ALLOWED_ROOT_FILES = {"robots.txt", "sitemap.xml"}


def _get_static_file(filename: str) -> Optional[str]:
    """Helper to locate a static asset across project root, dist/ (production), or public/ (development)."""
    safe_name = os.path.basename(filename)

    # 1. Project root directory check for designated SEO and site verification files
    if filename == safe_name and (
        safe_name in ALLOWED_ROOT_FILES
        or (safe_name.startswith("google") and safe_name.endswith(".html"))
    ):
        root_file = os.path.join(root_path, safe_name)
        if os.path.isfile(root_file):
            return root_file

    # 2. Production build directory
    dist_file = os.path.join(build_path, filename)
    if os.path.isfile(dist_file):
        return dist_file

    # 3. Development / source public directory
    pub_file = os.path.join(public_path, filename)
    if os.path.isfile(pub_file):
        return pub_file

    return None


# Explicit SEO and crawler routes (registered BEFORE SPA catch-all)
@app.get("/robots.txt", include_in_schema=False)
async def serve_robots():
    file_path = _get_static_file("robots.txt")
    if file_path:
        return FileResponse(file_path, media_type="text/plain")
    raise HTTPException(status_code=404, detail="robots.txt not found")


@app.get("/sitemap.xml", include_in_schema=False)
async def serve_sitemap():
    file_path = _get_static_file("sitemap.xml")
    if file_path:
        return FileResponse(file_path, media_type="application/xml")
    raise HTTPException(status_code=404, detail="sitemap.xml not found")


@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon_ico():
    file_path = _get_static_file("favicon.ico")
    if file_path:
        return FileResponse(file_path, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.ico not found")


@app.get("/favicon.svg", include_in_schema=False)
async def serve_favicon_svg():
    file_path = _get_static_file("favicon.svg")
    if file_path:
        return FileResponse(file_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="favicon.svg not found")


@app.get("/og-image.png", include_in_schema=False)
async def serve_og_image():
    file_path = _get_static_file("og-image.png")
    if file_path:
        return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="og-image.png not found")


@app.get("/apple-touch-icon.png", include_in_schema=False)
async def serve_apple_touch_icon():
    file_path = _get_static_file("apple-touch-icon.png")
    if file_path:
        return FileResponse(file_path, media_type="image/png")
    raise HTTPException(status_code=404, detail="apple-touch-icon.png not found")


@app.get("/site.webmanifest", include_in_schema=False)
async def serve_site_manifest():
    file_path = _get_static_file("site.webmanifest")
    if file_path:
        return FileResponse(file_path, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="site.webmanifest not found")


# Mount /assets directory if production dist exists
assets_path = os.path.join(build_path, "assets")
if os.path.exists(assets_path):
    app.mount("/assets", StaticFiles(directory=assets_path), name="assets")


if os.path.exists(build_path):
    @app.get("/", include_in_schema=False)
    async def serve_root():
        index_file = os.path.join(build_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file, media_type="text/html")
        raise HTTPException(status_code=404, detail="index.html not found")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        # Do not catch unhandled /api/ routes with HTML
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API endpoint not found")
        # Check if direct file exists in dist/ or public/
        direct_file = _get_static_file(full_path)
        if direct_file:
            return FileResponse(direct_file)
        # SPA fallback for client-side routes
        index_file = os.path.join(build_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file, media_type="text/html")
        raise HTTPException(status_code=404, detail="Frontend build not found.")
else:
    @app.get("/")
    def read_root():
        return {
            "status": "Backend Live",
            "message": "Welcome to 'Sakina' API! (Note: 'dist' folder was not detected, frontend is not mounted).",
            "docs": "/docs"
        }