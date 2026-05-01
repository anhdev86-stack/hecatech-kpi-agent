#!/usr/bin/env python3
"""
Hecatech CEO Briefing Agent — Local Test Runner
Tổng hợp output từ 11 agent dự án thành 1 bản tin CEO.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-xxxxx"
    python3 test_ceo_briefing.py sample_all_projects_outputs.json

Yêu cầu:
    pip3 install anthropic
"""

import json
import os
import re
import sys
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("❌ Chưa cài anthropic SDK. Chạy: pip3 install anthropic")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent
MODEL = "claude-sonnet-4-5"  # fallback
PROMPT_FILE = SCRIPT_DIR / "prompt_ceo_briefing.md"


def load_system_prompt() -> str:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    match = re.search(r"## 1\. SYSTEM PROMPT.*?```\s*(.*?)```", text, re.DOTALL)
    if not match:
        raise RuntimeError("Không tìm thấy SYSTEM PROMPT trong prompt_ceo_briefing.md")
    return match.group(1).strip()


def call_claude(system_prompt: str, user_message: str) -> dict:
    client = Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return {
        "parsed": json.loads(text),
        "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens},
    }


def format_vnd(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.0f}M"
    return f"{v:.0f}"


def render_ceo_briefing(b: dict) -> str:
    status_emoji = {"on_track": "🟢", "at_risk": "🟡", "alert": "🔴"}
    lines = []
    r = b.get("rollup", {})

    lines.append(f"\n{'='*65}")
    lines.append(f"  📈 CEO BRIEFING — {b.get('date', '?')}")
    lines.append(f"{'='*65}")

    h = b.get("headline", {})
    lines.append(f"\n{status_emoji.get(h.get('status', ''), '')} {h.get('one_liner', '')}\n")

    lines.append("─" * 65)
    lines.append("TỔNG QUAN HÔM QUA")
    lines.append(f"  GMV hôm qua: {format_vnd(r.get('gmv_yesterday'))} / {format_vnd(r.get('gmv_daily_target'))} ({r.get('pacing_pct', 0)}%)")
    lines.append(f"  MTD: {format_vnd(r.get('gmv_mtd'))} / {format_vnd(r.get('gmv_mtd_target'))} "
                 f"({r.get('mtd_pacing_pct', 0)}% vs expected {r.get('expected_mtd_pct', 0)}%)")
    lines.append(f"  Ads spend hôm qua: {format_vnd(r.get('total_ads_spend_yesterday'))}")
    lines.append(f"  Blended take rate: {r.get('blended_take_rate', 0)*100:.1f}% | "
                 f"Net margin MTD: {r.get('blended_net_margin_mtd', 0)*100:.1f}%")
    lines.append(f"  Lợi nhuận ròng hôm qua: {format_vnd(r.get('net_profit_yesterday'))}")

    lines.append("\n" + "─" * 65)
    lines.append("🏆 TOP 3 DẪN ĐẦU")
    for i, p in enumerate(b.get("top_3_performers", []), 1):
        lines.append(f"  {i}. {p['project']}: {p['reason']}")
        lines.append(f"     → Bài học: {p['learn_from']}")

    lines.append("\n🆘 3 DỰ ÁN CẦN CỨU")
    for i, p in enumerate(b.get("bottom_3_need_rescue", []), 1):
        lines.append(f"  {i}. {p['project']}: {p['reason']}")
        lines.append(f"     → {p['who_handles']}")

    lines.append("\n" + "─" * 65)
    lines.append("⚡ CEO QUYẾT ĐỊNH HÔM NAY")
    for d in b.get("ceo_must_decide_today", []):
        lines.append(f"\n  {d['priority']}. {d['decision']}")
        lines.append(f"     Context: {d['context']}")
        lines.append(f"     Người đợi: {d['stakeholder']}")
        lines.append(f"     Deadline: {d['deadline']}")

    patterns = b.get("cross_project_patterns", [])
    if patterns:
        lines.append("\n" + "─" * 65)
        lines.append("🔍 PATTERN ĐÁNG CHÚ Ý")
        for p in patterns:
            lines.append(f"\n  • {p['pattern']}")
            lines.append(f"    Giả thuyết: {p['hypothesis']}")
            lines.append(f"    Khuyến nghị: {p['recommendation']}")

    wins = b.get("quick_wins_available", [])
    if wins:
        lines.append("\n💡 QUICK WINS")
        for w in wins:
            lines.append(f"  • {w}")

    flags = b.get("data_quality_flags", [])
    if flags:
        lines.append("\n⚙️  DATA NOTES")
        for f in flags:
            lines.append(f"  - {f}")

    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_ceo_briefing.py <all_projects_outputs.json>")
        sys.exit(1)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Thiếu ANTHROPIC_API_KEY. Chạy:")
        print('   export ANTHROPIC_API_KEY="sk-ant-xxxxx"')
        sys.exit(1)

    data_path = Path(sys.argv[1])
    if not data_path.exists():
        print(f"❌ Không tìm thấy file: {data_path}")
        sys.exit(1)

    print("🔄 Đang load prompt CEO Briefing...")
    system_prompt = load_system_prompt()
    data = json.loads(data_path.read_text(encoding="utf-8"))

    print(f"🔄 Đang gọi Claude API tổng hợp {len(data.get('project_outputs', []))} dự án...")
    user_msg = json.dumps(data, ensure_ascii=False, indent=2)
    result = call_claude(system_prompt, user_msg)

    print(render_ceo_briefing(result["parsed"]))

    print(f"\n{'─'*65}")
    print(f"💰 Tokens: {result['usage']['in']} in + {result['usage']['out']} out")
    cost = (result['usage']['in'] * 3 / 1e6 + result['usage']['out'] * 15 / 1e6)
    print(f"💰 Chi phí call này: ~${cost:.4f} USD (≈{cost*24000:.0f} VND)")
    print(f"💰 Ước tính 30 ngày: ~${cost*30:.2f} USD/tháng")

    out_path = SCRIPT_DIR / f"ceo_briefing_{data['date']}.json"
    out_path.write_text(json.dumps(result["parsed"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 JSON output: {out_path.name}")


if __name__ == "__main__":
    main()
