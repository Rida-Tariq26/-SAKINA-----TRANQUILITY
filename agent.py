from fastapi.middleware import asyncexitstack
import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import sys
import json
import datetime
import asyncio
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from system_prompt import SYSTEM_PROMPT
from guardrails import evaluate_guardrails, get_user_country, CrisisTier

# Import MCP Client utilities
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from fastapi import FastAPI

app = FastAPI()


load_dotenv()

APP_NAME = "Sakina"
USER_ID = "default_user"
SESSION_ID = "default"

# ─────────────────────────────────────────────
# SECTION 1: FAREWELL DETECTION
# ─────────────────────────────────────────────

FAREWELL_KEYWORDS = [
    "quit", "exit", "bye", "goodbye", "allah hafiz", "khuda hafiz",
    "allah haafiz", "fi amanillah", "take care",
    "i have to go", "i need to go", "i wish to leave", "i want to leave",
    "i'm going now", "got to go", "gotta go",
    "that's all for now", "i'll talk to you later",
    "talk later", "see you", "see ya",
    "it's been good", "i should go", "have to leave",
    "need to leave", "signing off", "log off", "i'm done",
    "that will be all", "i think i'm good"
]


async def is_farewell(text: str, runner: Runner, session_service: InMemorySessionService) -> bool:
    text_lower = text.lower().strip()

    if any(keyword in text_lower for keyword in FAREWELL_KEYWORDS):
        return True

    detection_prompt = (
        f'The user said: "{text}". '
        "Are they trying to end or leave the conversation? "
        "Reply with only one word: YES or NO."
    )

    temp_session_id = SESSION_ID + "_farewell_check"
    try:
        await session_service.create_session(
            user_id=USER_ID,
            session_id=temp_session_id,
            app_name=APP_NAME
        )
    except Exception:
        pass

    try:
        response = runner.run_async(
            user_id=USER_ID,
            session_id=temp_session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=detection_prompt)]
            )
        )

        result = False
        async for event in response:
            if event.is_final_response() and event.content and event.content.parts:
                answer = event.content.parts[0].text.strip().upper()
                result = answer.startswith("YES")

        return result
    except Exception as e:
        print(f"\n[System Warning: Farewell check skipped due to API limitations: {e}]")

    return False


# ─────────────────────────────────────────────
# SECTION 2: ADK AGENT SETUP
# ─────────────────────────────────────────────

runner = None
_country_code: str = "DEFAULT"

# ─────────────────────────────────────────────
# SECTION 3: CORE CHAT FUNCTION
# ─────────────────────────────────────────────

async def chat(user_message: str) -> str:
    response = runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=user_message)]
        )
    )

    final_text = "I'm here. Take your time."
    async for event in response:
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text

    return final_text


# ─────────────────────────────────────────────
# SECTION 4: WEB SERVICE LIFECYCLE & ROUTES
# ─────────────────────────────────────────────
from contextlib import asynccontextmanager
from pydantic import BaseModel

# Create a clean Pydantic schema for your API requests
class ChatRequest(BaseModel):
    message: str

_country_code: str = "DEFAULT"
session_service = InMemorySessionService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This replaces your old main() loop setup. It automatically runs 
    when Uvicorn boots up, establishing the MCP server connection securely.
    """
    global runner, _country_code
    print("\n[System] Starting Sakina backend service...")
    
    _country_code = get_user_country()   
    
    await session_service.create_session(
        user_id=USER_ID,
        session_id=SESSION_ID,
        app_name=APP_NAME
    )


    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")],
        env=os.environ.copy()
    )

    from contextlib import AsyncExitStack
    async with AsyncExitStack() as stack:
        read, write = await stack.enter_async_context(stdio_client(server_params))
        mcp_session = await stack.enter_async_context(ClientSession(read, write))
        
        await mcp_session.initialize()
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

        sakina_agent = Agent(
            name="Sakina",
            model="gemini-2.5-flash",
            instruction=SYSTEM_PROMPT,
            tools=agent_tools,
        )

        runner = Runner(
            agent=sakina_agent,
            session_service=session_service,
            app_name=APP_NAME
        )
        print("[System] MCP Client & Gemini Runner connected successfully.\n")
        
        yield  
        
        print("\n[System] Shutting down Sakina backend service...")


app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": "Welcome to 'Sakina' — A Guided Space for Psychological & Spiritual Tranquility!"}

@app.post("/api/chat")
async def api_chat(payload: ChatRequest):
    """
    Exposes your chat workflow via HTTP POST requests
    """
    user_input = payload.message.strip()
    if not user_input:
        return {"response": "I'm here. Take your time."}

    # 1. Guardrail evaluation
    guardrail = await evaluate_guardrails(
        text=user_input,
        country_code=_country_code,
        runner=runner,
        session_service=session_service,
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    if guardrail.tier == CrisisTier.SEVERE:
        return {"response": guardrail.response_text}

    if guardrail.tier in (CrisisTier.MILD, CrisisTier.MODERATE):
        if guardrail.tier == CrisisTier.MODERATE:
            return {"response": guardrail.response_text}

    # 2. Farewell detection
    if await is_farewell(user_input, runner, session_service):
        closing_prompt = (
            "The user is ending the session now. Send them off warmly and "
            "personally, referencing something meaningful from our conversation today. "
            "If you were in Mode 1 or Mode 2, end with a single relevant Quranic verse "
            "OR hadith. You MUST include the full reference in this exact format — "
            "for a verse: 'Verse text' (Surah Name, Ayah X:X). "
            "For a hadith: 'Hadith text' (Source, e.g. Sahih Bukhari 1234). "
            "NEVER omit the reference under any circumstance. If unsure of the exact "
            "reference, choose a different verse or hadith you are certain about. "
            "If you were in Mode 3, close with an uplifting quote and its author. "
            "Keep the entire closing brief and sincere."
        )
        closing = await chat(closing_prompt)
        return {"response": closing, "session_ended": True}

    # 3. Normal agent response
    response = await chat(user_input)
    return {"response": response, "session_ended": False}



    