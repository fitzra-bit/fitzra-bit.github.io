"""OptiFlow — Manufacturing Process Optimization Chat.

Run:
    python app.py
    # opens http://localhost:8000 automatically
"""

import asyncio
import json
import os
import sys
import threading
import webbrowser
from pathlib import Path
from typing import AsyncGenerator

import anthropic
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Resolve paths
ROOT = Path(__file__).parent
FACTORY_SIM = ROOT.parent / "factory_sim"
sys.path.insert(0, str(FACTORY_SIM))

from tools.definitions import TOOL_DEFINITIONS
from tools.executor import execute_tool
from prompts.system import SYSTEM_PROMPT

app = FastAPI(title="OptiFlow")
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")

# Per-session state: {session_id: {messages, line, baseline_profit, last_agent}}
_sessions: dict = {}

client = anthropic.AsyncAnthropic()
MODEL = os.getenv("OPTIFLOW_MODEL", "claude-sonnet-4-6")


def _get_session(sid: str) -> dict:
    if sid not in _sessions:
        _sessions[sid] = {
            "messages": [],
            "line": None,
            "baseline_profit": 0.0,
            "last_agent": None,
        }
    return _sessions[sid]


def _sse(event_type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"


async def _stream(user_message: str, session: dict) -> AsyncGenerator[str, None]:
    session["messages"].append({"role": "user", "content": user_message})
    current = list(session["messages"])

    while True:
        assistant_content = []
        current_text = ""

        async with await client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=current,
        ) as stream:
            async for event in stream:
                t = event.type

                if t == "content_block_start":
                    cb = getattr(event, "content_block", None)
                    if cb and cb.type == "tool_use":
                        yield _sse("tool_start", name=cb.name, tool_id=cb.id)

                elif t == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        if delta.type == "text_delta":
                            yield _sse("text", delta=delta.text)
                            current_text += delta.text

            final = await stream.get_final_message()

        assistant_content = final.content
        current.append({"role": "assistant", "content": assistant_content})

        if final.stop_reason == "end_turn":
            session["messages"] = current
            break

        if final.stop_reason == "tool_use":
            tool_results = []
            for block in assistant_content:
                if getattr(block, "type", None) == "tool_use":
                    try:
                        result = await asyncio.to_thread(
                            execute_tool, block.name, block.input, session
                        )
                    except Exception as exc:
                        result = {"text": f"Tool error ({block.name}): {exc}", "html": None}

                    if result.get("html"):
                        yield _sse(
                            "tool_result_html",
                            html=result["html"],
                            tool_name=block.name,
                        )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result.get("text", ""),
                        }
                    )

            current.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            session["messages"] = current
            break

    yield _sse("done")


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/")
async def index():
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    sid = body.get("session_id", "default")
    msg = body.get("message", "").strip()
    if not msg:
        return {"error": "empty message"}

    session = _get_session(sid)

    return StreamingResponse(
        _stream(msg, session),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/reset")
async def reset(request: Request):
    body = await request.json()
    sid = body.get("session_id", "default")
    _sessions.pop(sid, None)
    return {"ok": True}


# ------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------

if __name__ == "__main__":
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    port = int(os.getenv("PORT", 8000))

    def _open():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=_open, daemon=True).start()
    print(f"OptiFlow starting on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
