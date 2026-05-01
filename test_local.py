#!/usr/bin/env python3
"""
Hecatech CEO Agent — Local Test Runner
Chạy prototype agent trên máy local với data mẫu, gọi Claude API thật.

Usage:
    export ANTHROPIC_API_KEY="sk-ant-xxxxx"
    python3 test_local.py sample_data.json

Yêu cầu:
    pip3 install anthropic
"""

import json
import os
import sys
import re
from pathlib import Path

try:
    from anthropic import Anthropic
except ImportError:
    print("❌ Chưa cài anthropic SDK. Chạy: pip3 install anthropic")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).parent
MODEL = "claude-sonnet-4-5"  # fallback nếu 4-6 chưa available ở account
PROMPT_FILE = SCRIPT_DIR / "prompt_system.md"
BENCHMARK_FILE = SCRIPT_DIR / "benchmark_config.csv"


def load_system_prompt() -> str:
    """Trích block system prompt từ prompt_system.md (giữa dòng 'SYSTEM PROMPT' và phần kế tiếp)."""
    text = PROMPT_FILE.read_text(encoding="utf-8")
    # Lấy block code đầu tiên sau header "1. SYSTEM PROMPT"
    match = re.search(
        r"## 1\. SYSTEM PROMPT.*?```\s*(.*?)```",
        text,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("Không tìm thấy SYSTEM PROMPT trong prompt_system.md")
    return match.group(1).strip()


def load_benchmark_csv() -> list[dict]:
    """Đọc benchmark config CSV, trả về list các dict (chỉ rows XKMVN, bỏ _META vì không phải benchmark)."""
    import csv
    rows = []
    with open(BENCHMARK_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["project"] == "XKMVN":
                rows.append(row)
    return rows


def build_user_message(data: dict, benchmark_rows: list[dict]) -> str:
    """Build user message gồm benchmark + data thực."""
    benchmark_summary = {
        "project": "XKMVN",
        "benchmarks": [
            {
                "metric_group": r["metric_group"],
                "metric": r["metric"],
                "unit": r["unit"],
                "monthly": {
                    "red": r["benchmark_monthly_red"],
                    "yellow": r["benchmark_monthly_yellow"],
                    "green": r["benchmark_monthly_green"],
                },
                "daily": {
                    "red": r["benchmark_daily_red"],
                    "yellow": r["benchmark_daily_yellow"],
                    "green": r["benchmark_daily_green"],
                },
                "direction": r["direction"],
                "owner": r["owner"],
                "note": r["formula_note"],
            }
            for r in benchmark_rows
            if r["metric_group"] != "_META"
        ],
        "meta": {
            r["metric"]: r["benchmark_daily_green"]
            for r in benchmark_rows
            if r["metric_group"] == "_META"
        },
    }

    return f"""BENCHMARK CONFIG (XKMVN):
```json
{json.dumps(benchmark_summary, ensure_ascii=False, indent=2)}
```

DATA NGÀY {data['date']}:
```json
{json.dumps(data, ensure_ascii=False, indent=2)}
```

Phân tích theo ma trận phễu v12 và trả về JSON CHÍNH XÁC theo schema đã định trong system prompt. CHỈ trả về JSON, không thêm text giải thích."""


def call_claude(system_prompt: str, user_message: str) -> dict:
    """Gọi Claude API và parse JSON response."""
    client = Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()

    # Force parse JSON — strip markdown code fences nếu có
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        return {
            "parsed": json.loads(text),
            "raw": text,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        }
    except json.JSONDecodeError as e:
        print(f"⚠️  Claude không trả về JSON hợp lệ: {e}")
        print("\n--- RAW OUTPUT ---")
        print(text)
        sys.exit(1)


def render_lark_card(result: dict) -> str:
    """Render JSON output thành text format giống như sẽ gửi vào Lark."""
    emoji = {"green": "✅", "yellow": "🟡", "red": "🔴"}
    lines = []

    lines.append(f"\n{'='*60}")
    lines.append(f"  {result['project']} — {result['date']}")
    lines.append(f"{'='*60}\n")

    # Summary
    s = result.get("summary", {})
    lines.append("📊 TỔNG QUAN")
    if "gmv_yesterday" in s:
        g = s["gmv_yesterday"]
        lines.append(
            f"  GMV hôm qua: {format_vnd(g['value'])} {emoji.get(g.get('status', ''), '')}"
        )
        if g.get("vs_benchmark_daily"):
            lines.append(f"    vs benchmark ngày: {g['vs_benchmark_daily']}")
    if "gmv_mtd" in s:
        m = s["gmv_mtd"]
        lines.append(
            f"  MTD: {format_vnd(m['value'])} / {format_vnd(m['target'])} "
            f"({m['pct']}% — {m.get('pacing_status', '')})"
        )
    if "net_profit_margin_mtd" in s:
        n = s["net_profit_margin_mtd"]
        lines.append(
            f"  Net margin MTD: {n['value']:.1%} {emoji.get(n.get('status', ''), '')}"
        )
    lines.append("")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        lines.append(f"⚠️  WARNING ({len(warnings)} chỉ số cần chú ý)\n")
        for w in warnings:
            streak = f" — ngày thứ {w['consecutive_days']}" if w.get("consecutive_days", 0) > 1 else ""
            lines.append(
                f"  {w['priority']}. {emoji.get(w['status'], '')} {w['metric']}: "
                f"{w['value']} ({w['threshold']}){streak}"
            )
            lines.append(f"     ↳ Nguyên nhân: {w.get('root_cause', '—')}")
            lines.append(f"     ↳ Hành động: {w.get('action', '—')}")
            lines.append(f"     ↳ Owner: {w.get('owner', '—')}")
            if w.get("missing_data_note"):
                lines.append(f"     ℹ️  {w['missing_data_note']}")
            lines.append("")
    else:
        lines.append("⚠️  Không có warning — tất cả metric xanh\n")

    # Bright spots
    spots = result.get("bright_spots", [])
    if spots:
        lines.append("✅ ĐIỂM SÁNG")
        for b in spots:
            lines.append(f"  - {b['metric']}: {b['value']} ({b.get('note', '')})")
        lines.append("")

    # Top actions
    actions = result.get("top_actions_today", [])
    if actions:
        lines.append("📋 TOP VIỆC HÔM NAY")
        for a in actions:
            lines.append(f"  {a['priority']}. {a['action']} — {a['owner']}")
        lines.append("")

    # Data quality
    flags = result.get("data_quality_flags", [])
    if flags:
        lines.append("⚙️  DATA NOTES")
        for f in flags:
            lines.append(f"  - {f}")
        lines.append("")

    return "\n".join(lines)


def format_vnd(value) -> str:
    """Format số thành 1.23B/205M/500K VND."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.0f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}K"
    return f"{v:.0f}"


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_local.py <data_file.json>")
        print("Example: python3 test_local.py sample_data.json")
        sys.exit(1)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ Thiếu ANTHROPIC_API_KEY. Chạy:")
        print('   export ANTHROPIC_API_KEY="sk-ant-xxxxx"')
        sys.exit(1)

    data_path = Path(sys.argv[1])
    if not data_path.exists():
        print(f"❌ Không tìm thấy file: {data_path}")
        sys.exit(1)

    print("🔄 Đang load prompt system + benchmark config...")
    system_prompt = load_system_prompt()
    benchmark = load_benchmark_csv()
    data = json.loads(data_path.read_text(encoding="utf-8"))

    print(f"🔄 Đang gọi Claude API ({MODEL})...")
    user_msg = build_user_message(data, benchmark)
    result = call_claude(system_prompt, user_msg)

    # In Lark-style output
    print(render_lark_card(result["parsed"]))

    # In raw JSON + token cost
    print(f"\n{'─'*60}")
    print(f"💰 Tokens: {result['usage']['input_tokens']} in + "
          f"{result['usage']['output_tokens']} out")
    cost = (result['usage']['input_tokens'] * 3 / 1_000_000
            + result['usage']['output_tokens'] * 15 / 1_000_000)
    print(f"💰 Chi phí call này: ~${cost:.4f} USD")
    print(f"💰 Ước tính 30 ngày: ~${cost*30:.2f} USD/tháng")

    # Lưu output
    out_path = SCRIPT_DIR / f"output_{data['date']}.json"
    out_path.write_text(json.dumps(result["parsed"], ensure_ascii=False, indent=2),
                        encoding="utf-8")
    print(f"\n💾 Đã lưu JSON output vào: {out_path.name}")


if __name__ == "__main__":
    main()
