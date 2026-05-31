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
import yaml
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
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

# Per-session state
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
            "plant_data": None,
            "scenario_id": None,
            "scenario_changes": {},
            "scenario_in_flight": [],
        }
    return _sessions[sid]


def _sse(event_type: str, **kwargs) -> str:
    return f"data: {json.dumps({'type': event_type, **kwargs})}\n\n"


async def _stream(user_message: str, session: dict) -> AsyncGenerator[str, None]:
    session["messages"].append({"role": "user", "content": user_message})
    current = list(session["messages"])

    while True:
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
                    if delta and delta.type == "text_delta":
                        yield _sse("text", delta=delta.text)

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

                    # Emit scenario_ready so frontend can build the configurator
                    if result.get("scenario_json"):
                        yield _sse("scenario_ready", scenario_json=result["scenario_json"])

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result.get("text", ""),
                    })

            current.append({"role": "user", "content": tool_results})

        else:
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


@app.post("/run-configured")
async def run_configured(request: Request):
    """Run RL with a user-confirmed YAML + pre-committed upgrades from the configurator."""
    body = await request.json()
    sid = body.get("session_id", "default")
    yaml_text = body.get("yaml_text", "").strip()
    selected = body.get("selected_upgrades", [])  # [{step_idx, upgrade_id, count}]
    agent = body.get("agent", "greedy")
    episodes = int(body.get("episodes", 200))

    session = _get_session(sid)

    # Parse YAML from editor (user may have modified it)
    try:
        from simulation.loader import load_scenario_from_yaml, _build_line_from_data
        if yaml_text:
            line = load_scenario_from_yaml(yaml_text)
        else:
            line = session.get("line")
            if not line:
                return JSONResponse({"error": "No scenario loaded"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"YAML error: {e}"}, status_code=400)

    # Apply pre-committed upgrades from the configurator
    working_line = line.reset()
    for sel in selected:
        step_idx = int(sel["step_idx"])
        upgrade_id = sel["upgrade_id"]
        count = int(sel.get("count", 1))
        for _ in range(count):
            try:
                working_line.apply_upgrade(step_idx, upgrade_id)
            except Exception:
                pass  # skip invalid (budget exceeded etc.)

    # Run RL optimization on the remaining budget
    def _do_run():
        from rl.trainer import run_greedy, run_dqn
        if agent == "dqn":
            return run_dqn(working_line, episodes=episodes)[0]
        return run_greedy(working_line)[0]

    best_line = await asyncio.to_thread(_do_run)

    # Update session with the scenario used (keeps chat in sync)
    session["line"] = line
    session["baseline_profit"] = line.reset().gross_profit_per_period

    from tools.executor import _render_comparison_html, _line_text_summary, _fmt_money

    baseline = line.reset()
    bp = baseline.gross_profit_per_period
    op = best_line.gross_profit_per_period

    pre_committed = [
        f"{s['upgrade_id']} on step {s['step_idx']}" for s in selected
    ]

    label = f"{'DQN' if agent == 'dqn' else 'Greedy'} Optimization"
    if pre_committed:
        label += f" (+ {len(pre_committed)} pre-committed)"

    html = _render_comparison_html(baseline, best_line, label)

    return {
        "html": html,
        "profit_delta": op - bp,
        "capex_total": best_line.total_capex_spent,
        "upgrade_log": best_line.capex_log,
        "summary": _line_text_summary(best_line, "optimized"),
    }


@app.post("/validate-yaml")
async def validate_yaml(request: Request):
    """Parse and validate a YAML scenario string; return structured data or errors."""
    body = await request.json()
    yaml_text = body.get("yaml_text", "")
    try:
        from simulation.loader import load_scenario_from_yaml
        line = load_scenario_from_yaml(yaml_text)
        return {
            "valid": True,
            "name": line.name,
            "steps": len(line.steps),
            "budget": line.budget,
            "bottleneck": line.bottleneck_step.name,
            "throughput": line.system_throughput,
            "yield_pct": round(line.effective_yield * 100, 2),
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.get("/scenarios")
async def scenarios_list():
    """Return all saved scenarios as JSON."""
    from tools.scenario_manager import list_scenarios
    return list_scenarios()


@app.get("/scenarios/{scenario_id}")
async def scenario_get(scenario_id: str):
    from tools.scenario_manager import load_scenario
    record = load_scenario(scenario_id)
    if record is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return record


@app.delete("/scenarios/{scenario_id}")
async def scenario_delete(scenario_id: str):
    from tools.scenario_manager import delete_scenario
    ok = delete_scenario(scenario_id)
    return {"ok": ok}


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
