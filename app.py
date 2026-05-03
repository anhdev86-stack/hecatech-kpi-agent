"""
Hecatech AI Agent — Local Web UI
FastAPI server wrapping 2 agents (per-project + CEO briefing) với UI preview.

Run:
    pip3 install -r requirements.txt
    export ANTHROPIC_API_KEY="sk-ant-xxxxx"
    uvicorn app:app --reload --port 3000
"""

import csv
import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from anthropic import Anthropic
except ImportError:
    raise RuntimeError("Chưa cài anthropic SDK. Chạy: pip3 install -r requirements.txt")


BASE = Path(__file__).parent
STATIC = BASE / "static"
MODEL = "claude-sonnet-4-5"

app = FastAPI(title="Hecatech AI Agent Preview")


class AnalyzeRequest(BaseModel):
    agent_type: str  # "project" | "ceo"
    data: dict


def extract_system_prompt(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"## 1\. SYSTEM PROMPT.*?```\s*(.*?)```", text, re.DOTALL)
    if not m:
        raise RuntimeError(f"Không tìm thấy SYSTEM PROMPT trong {md_path.name}")
    return m.group(1).strip()


def load_benchmark_rows() -> list[dict]:
    rows = []
    with open(BASE / "benchmark_config.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("project") == "XKMVN":
                rows.append(row)
    return rows


def call_claude(system: str, user_message: str) -> dict:
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        temperature=0.3,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"Claude không trả về JSON hợp lệ: {e}. Raw: {text[:500]}")
    return {
        "parsed": parsed,
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
            "cost_usd": resp.usage.input_tokens * 3 / 1e6
            + resp.usage.output_tokens * 15 / 1e6,
        },
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(
            500,
            "ANTHROPIC_API_KEY chưa được set. Chạy: export ANTHROPIC_API_KEY=\"sk-ant-xxx\" rồi restart server."
        )

    if req.agent_type == "project":
        system = extract_system_prompt(BASE / "prompt_system.md")
        benchmark = [r for r in load_benchmark_rows() if r.get("metric_group") != "_META"]
        user_msg = (
            f"BENCHMARK CONFIG (XKMVN):\n```json\n{json.dumps(benchmark, ensure_ascii=False, indent=2)}\n```\n\n"
            f"DATA NGÀY {req.data.get('date', '?')}:\n```json\n{json.dumps(req.data, ensure_ascii=False, indent=2)}\n```\n\n"
            "Phân tích theo ma trận phễu v12 và trả về CHỈ JSON theo schema."
        )
    elif req.agent_type == "ceo":
        system = extract_system_prompt(BASE / "prompt_ceo_briefing.md")
        user_msg = json.dumps(req.data, ensure_ascii=False, indent=2)
    else:
        raise HTTPException(400, f"agent_type phải là 'project' hoặc 'ceo', nhận: {req.agent_type}")

    return call_claude(system, user_msg)





@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "api_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "model": MODEL,
    }


# Serve static UI (HTML/CSS/JS) — must be mounted AFTER /api routes
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def root():
    return FileResponse(STATIC / "index.html")
