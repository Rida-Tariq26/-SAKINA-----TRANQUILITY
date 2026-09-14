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
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Request, status
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
    add_mood_log, get_recent_mood_logs,
    export_user_data, delete_user_data,
)

# Import MCP Client utilities
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import existing modules
from system_prompt import SYSTEM_PROMPT
from dhikr import (
    DHIKR_TABLE, SECULAR_TABLE,
    DHIKR_COMMENTARY_PROMPT, SECULAR_COMMENTARY_PROMPT,
    resolve_emotion_with_ai,
    get_practice_personalizations,
    get_ai_commentary,
)
from mood_tracker import log_and_synthesize, get_dashboard, TREND_COMMENTARY_PROMPT

load_dotenv()

logger = logging.getLogger("sakina.api")

APP_NAME = "Sakina"
DEFAULT_USER_ID = "default_user"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

CHAT_SESSION = "chat_session"
DHIKR_SESSION = "dhikr_session"
RESOLVER_SESSION = "resolver_session"
MOOD_SESSION = "mood_session"

# Global references for shared services and MCP tools
session_service = InMemorySessionService()
mcp_agent_tools: List[Any] = []


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


def create_chat_runner(api_key: Optional[str] = None, model_name: Optional[str] = None) -> Runner:
    """Creates a scoped Chat Runner configured with the target API key & MCP tools."""
    llm = create_llm_instance(model_name or DEFAULT_MODEL, api_key)
    agent = Agent(
        name="Sakina",
        model=llm,
        instruction=SYSTEM_PROMPT,
        tools=mcp_agent_tools,
    )
    return Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
        auto_create_session=True,
    )


def create_mood_runner(api_key: Optional[str] = None, model_name: Optional[str] = None) -> Runner:
    """Creates a scoped Mood Runner configured with the target API key & MCP tools."""
    llm = create_llm_instance(model_name or DEFAULT_MODEL, api_key)
    agent = Agent(
        name="SakinaMood",
        model=llm,
        instruction=TREND_COMMENTARY_PROMPT,
        tools=mcp_agent_tools,
    )
    return Runner(
        agent=agent,
        session_service=session_service,
        app_name=APP_NAME,
        auto_create_session=True,
    )


# ─────────────────────────────────────────────
# LIFECYCLE: CONNECT TO MCP SERVER ON STARTUP
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp_agent_tools

    # Initialise SQLite database
    init_db()

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

    yield

    # Clean cleanup on application exit
    await session_ctx.__aexit__(None, None, None)
    await ctx.__aexit__(None, None, None)


# Initialize FastAPI with the lifespan orchestrator
app = FastAPI(lifespan=lifespan)


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────
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
    model_to_test = req.model or x_gemini_model or DEFAULT_MODEL

    if not key_to_test:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No API key provided to verify.",
        )

    try:
        client = Client(api_key=key_to_test)
        # Lightweight ping to test key and model connectivity
        test_response = client.models.generate_content(
            model=model_to_test,
            contents="Respond with only: OK",
        )
        if test_response and test_response.text:
            return KeyVerifyResponse(
                valid=True,
                model=model_to_test,
                message=f"Gemini API key is active and connected to {model_to_test}.",
            )
        else:
            return KeyVerifyResponse(
                valid=True,
                model=model_to_test,
                message="Key connected successfully.",
            )
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            detail = "API key is valid, but current quota limit (429) was reached. Please wait a few minutes."
        elif "API_KEY_INVALID" in err_msg or "400" in err_msg or "403" in err_msg or "not valid" in err_msg:
            detail = "Invalid Google Gemini API key. Please verify your key on Google AI Studio."
        elif "404" in err_msg or "NOT_FOUND" in err_msg:
            detail = f"Model {model_to_test} not found. Please use {DEFAULT_MODEL}."
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
    return {"status": "ok"}


@app.get("/api/user/data/export")
async def export_user_data_endpoint(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    data = export_user_data(x_user_id)
    return JSONResponse(content=data)


@app.delete("/api/user/data")
async def delete_user_data_endpoint(x_user_id: Optional[str] = Header(None, alias="X-User-Id")):
    if not x_user_id:
        raise HTTPException(status_code=400, detail="Missing X-User-Id header")
    delete_user_data(x_user_id)
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

    user_id = x_user_id or DEFAULT_USER_ID
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model)

    try:
        response = runner.run_async(
            user_id=user_id,
            session_id=CHAT_SESSION,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text="Greet the user warmly with your opening message.")]
            )
        )
        final_text = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
        
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

    user_id = x_user_id or DEFAULT_USER_ID
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model)

    try:
        response = runner.run_async(
            user_id=user_id,
            session_id=CHAT_SESSION,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=req.message)]
            )
        )
        final_text = ""
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text
        
        if not final_text:
            final_text = "I am listening. Please continue."
            
        return ChatResponse(response=final_text)
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
    effective_key = get_effective_api_key(x_gemini_api_key)
    runner = create_chat_runner(api_key=effective_key, model_name=x_gemini_model) if effective_key else None

    # Step 1: Resolve emotion
    input_for_resolution = req.free_text if req.free_text.strip() else req.emotion
    if req.emotion.strip():
        emotion = req.emotion.strip()
    elif runner:
        try:
            emotion = await resolve_emotion_with_ai(input_for_resolution, runner, RESOLVER_SESSION)
        except Exception:
            emotion = "anxiety"
    else:
        emotion = "anxiety"

    # Step 2: Fetch static practice entries from the table
    table = DHIKR_TABLE if req.mode == "islamic" else SECULAR_TABLE
    raw_practices = table.get(emotion, table.get("anxiety", []))

    # Step 3: Get AI-generated personalization notes (or fallback)
    personalization_notes = []
    if runner:
        try:
            personalization_notes = await get_practice_personalizations(
                emotional_state=emotion,
                free_text=req.free_text,
                entries=raw_practices,
                mode=req.mode,
                runner=runner,
                session_id=DHIKR_SESSION,
            )
        except Exception:
            personalization_notes = []

    # Step 4: Merge static data + personalization notes
    practices = []
    if req.mode == "islamic":
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
            commentary = await get_ai_commentary(
                emotional_state=emotion,
                mode=req.mode,
                runner=runner,
                session_id=DHIKR_SESSION,
            )
        except Exception:
            commentary = ""

    if not commentary:
        commentary = (
            "Here are practices tailored to bring tranquility and presence to your heart."
            if req.mode == "islamic"
            else "Here are evidence-based practices designed to help center your nervous system."
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
        if x_user_id:
            try:
                add_mood_log(user_id=x_user_id, state=req.emotion, intensity=req.intensity, note=req.note)
            except Exception as db_err:
                logger.warning(f"Failed to log mood to SQLite: {db_err}")

        effective_key = get_effective_api_key(x_gemini_api_key)
        runner = create_mood_runner(api_key=effective_key, model_name=x_gemini_model)

        data = await log_and_synthesize(
            emotional_state=req.emotion,
            intensity=req.intensity,
            note=req.note,
            mode=req.mode,
            runner=runner,
            session_id=MOOD_SESSION,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/mood")
async def get_mood_endpoint(
    mode: str = "islamic",
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_gemini_model: Optional[str] = Header(None, alias="X-Gemini-Model"),
):
    try:
        effective_key = get_effective_api_key(x_gemini_api_key)
        runner = create_mood_runner(api_key=effective_key, model_name=x_gemini_model)

        data = await get_dashboard(
            mode=mode,
            runner=runner,
            session_id=MOOD_SESSION,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# SERVE REACT FRONTEND (Production Build)
# ─────────────────────────────────────────────
build_path = os.path.join(os.path.dirname(__file__), "dist")

if os.path.exists(build_path):
    app.mount("/", StaticFiles(directory=build_path, html=True), name="static")
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(build_path, "index.html"))
else:
    @app.get("/")
    def read_root():
        return {
            "status": "Backend Live",
            "message": "Welcome to 'Sakina' API! (Note: 'dist' folder was not detected, frontend is not mounted).",
            "docs": "/docs"
        }