"""
FastAPI backend for Sakina UI.
Bridges the React frontend to the ADK agent (agent.py logic)
and the Dhikr module (dhikr.py logic) via an MCP background server.

Run with:
    uvicorn FrontendAPI:app --reload --port 8000
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import sys
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from dotenv import load_dotenv

# Import MCP Client utilities
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Import your existing modules
from system_prompt import SYSTEM_PROMPT
from dhikr import (
    DHIKR_TABLE, SECULAR_TABLE,
    DHIKR_COMMENTARY_PROMPT, SECULAR_COMMENTARY_PROMPT,
    resolve_emotion_with_ai,
    get_practice_personalizations,
    get_ai_commentary,
)
from mood_tracker import log_and_synthesize, get_dashboard

load_dotenv()

APP_NAME  = "Sakina"
USER_ID   = "default_user"
CHAT_SESSION = "chat_session"
DHIKR_SESSION = "dhikr_session"
RESOLVER_SESSION = "resolver_session"
MOOD_SESSION = "mood_session"

# Global references for runners and background tasks
chat_runner = None
mood_runner = None
mcp_cleanup = None

# ─────────────────────────────────────────────
# LIFECYCLE: CONNECT TO MCP SERVER ON STARTUP
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global chat_runner, mood_runner, mcp_cleanup
    
    session_service = InMemorySessionService()
    
    # Configure parameters to spawn server.py as a background protocol worker
    server_params = StdioServerParameters(
    command=sys.executable,
    args=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")],
    env=os.environ.copy()
)
    
    # Setup context managers manually to stay open for the whole app duration
    ctx = stdio_client(server_params)
    read, write = await ctx.__aenter__()
    
    session_ctx = ClientSession(read, write)
    mcp_session = await session_ctx.__aenter__()
    await mcp_session.initialize()
    
    # Fetch available tools over the protocol channel
    mcp_tools_response = await mcp_session.list_tools()
    
    # Build sync-safe wrappers so Google ADK can execute them without thread deadlocks
 
    for tool in mcp_tools_response.tools:
        def make_mcp_call(tool_name=tool.name):
            async def async_wrapper(**kwargs):
                res = await mcp_session.call_tool(tool_name, arguments=kwargs)
                return "".join(
                    content.text for content in res.content if hasattr(content, "text")
                )
            return async_wrapper

        agent_tools = []
        for tool in mcp_tools_response.tools:
            tool_func = make_mcp_call(tool.name)
            tool_func.__name__ = tool.name
            tool_func.__doc__ = tool.description or f"MCP tool: {tool.name}"
            agent_tools.append(tool_func)

    # Instantiate the dynamic Agents
    chat_agent = Agent(name="Sakina", model="gemini-2.5-flash", instruction=SYSTEM_PROMPT, tools=agent_tools)
    
    mood_agent = Agent(
        name="Sakina",
        model="gemini-2.5-flash",
        instruction=SYSTEM_PROMPT,
        tools=agent_tools,  # Inject dynamic MCP tools here
    )
    
    chat_runner = Runner(agent=chat_agent, session_service=session_service, app_name=APP_NAME)
    mood_runner = Runner(agent=mood_agent, session_service=session_service, app_name=APP_NAME)
    
    # Pre-warm sessions
    await session_service.create_session(user_id=USER_ID, session_id=CHAT_SESSION, app_name=APP_NAME)
    await session_service.create_session(user_id=USER_ID, session_id=MOOD_SESSION, app_name=APP_NAME)
    await session_service.create_session(user_id=USER_ID, session_id=DHIKR_SESSION, app_name=APP_NAME)
    await session_service.create_session(user_id=USER_ID, session_id=RESOLVER_SESSION, app_name=APP_NAME)
    
    yield
    # Clean cleanup on application exit
    await session_ctx.__aexit__(None, None, None)
    await ctx.__aexit__(None, None, None)

# Initialize FastAPI with the lifespan orchestrator
app = FastAPI(lifespan=lifespan)

# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────
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
# GREETING ENDPOINT
# ─────────────────────────────────────────────
@app.post("/api/greeting")
async def post_greeting_endpoint():
    try:
        response = chat_runner.run_async(
            user_id=USER_ID,
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
        if not final_text:
            final_text = "Assalam-o-Alaikum \n\nI am Sakina a space for stillness. Whatever is weighing on your heart today, you are welcome to share it here.\n\nWhat's on your mind?"
        return {"response": final_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# CORE CHAT ENDPOINT
# ─────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def post_chat_endpoint(req: ChatRequest):
    try:
        response = chat_runner.run_async(
            user_id=USER_ID,
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
        raise HTTPException(status_code=500, detail=str(e))

# ─────────────────────────────────────────────
# DHIKR ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/dhikr", response_model=DhikrResponse)
async def post_dhikr_endpoint(req: DhikrRequest):
    # Step 1: Resolve emotion
    # If the user clicked a preset button, emotion is already known.
    # If they typed free text, resolve it via AI.
    input_for_resolution = req.free_text if req.free_text.strip() else req.emotion
    emotion = req.emotion if req.emotion.strip() else await resolve_emotion_with_ai(
        input_for_resolution, chat_runner, RESOLVER_SESSION
    )

    # Step 2: Fetch static practice entries from the correct table
    table = DHIKR_TABLE if req.mode == "islamic" else SECULAR_TABLE
    raw_practices = table.get(emotion, table["anxiety"])

    # Step 3: Get AI-generated personalization notes (one per practice)
    personalization_notes = await get_practice_personalizations(
        emotional_state=emotion,
        free_text=req.free_text,
        entries=raw_practices,
        mode=req.mode,
        runner=chat_runner,
        session_id=DHIKR_SESSION,
    )

    # Step 4: Merge static data + personalization note into full practice objects
    # The frontend renders different fields depending on mode:
    #   Islamic:  arabic, transliteration, translation, reference, repetitions, personalization
    #   Secular:  name, instruction, why, source, personalization
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

    # Step 5: Generate AI commentary (warm introduction paragraph)
    commentary = await get_ai_commentary(
        emotional_state=emotion,
        mode=req.mode,
        runner=chat_runner,
        session_id=DHIKR_SESSION,
    )
    if not commentary:
        commentary = "Here are some practices that may bring you stillness."

    return DhikrResponse(commentary=commentary, practices=practices, emotion=emotion)

# ─────────────────────────────────────────────
# MOOD ENDPOINTS
# ─────────────────────────────────────────────
@app.post("/api/mood")
async def post_mood_endpoint(req: MoodRequest):
    try:
        data = await log_and_synthesize(
            emotional_state=req.emotion,
            intensity=req.intensity,
            note=req.note,
            mode=req.mode,
            runner=mood_runner,
            session_id=MOOD_SESSION,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/mood")
async def get_mood_endpoint(mode: str = "islamic"):
    try:
        data = await get_dashboard(
            mode=mode,
            runner=mood_runner,
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
    # Fallback endpoint if static files are completely missing
    @app.get("/")
    def read_root():
        return {
            "status": "Backend Live",
            "message": "Welcome to 'Sakina' API! (Note: 'dist' folder was not detected, frontend is not mounted).",
            "docs": "/docs"
        }