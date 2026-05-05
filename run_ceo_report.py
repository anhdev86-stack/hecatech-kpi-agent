#!/usr/bin/env python3
"""
Hecatech AI Agent — CEO Daily Briefing
Tổng quan ngắn gọn tất cả dự án, gửi group CEO Lark.

Usage:
    python3 run_ceo_report.py             # tự detect giờ
    python3 run_ceo_report.py morning     # 10:00 — dữ liệu hôm qua
    python3 run_ceo_report.py afternoon   # 16:00 — dữ liệu hôm nay
"""

import json, os, sys, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from run_project_report import (
    fetch_project_sheet, parse_project_metrics,
    status_from_benchmark, fmt, _get_short_name, _get_vn_weekday,
    ALERT_METRICS_5, PROJECT_WEBHOOKS,
)

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).parent
CEO_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/ad36383c-06b9-48ee-ad3b-08dd771fa9fa"
MODEL       = "claude-sonnet-4-6"
SEP         = "=" * 42


# ─────────────────────────────────────────────────────────────────────────────
# MODE
# ─────────────────────────────────────────────────────────────────────────────

def get_mode() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in ("morning", "afternoon"):
        return sys.argv[1]
    return "morning" if datetime.now().hour < 13 else "afternoon"


# ─────────────────────────────────────────────────────────────────────────────
# BUILD SNAPSHOT — tóm tắt 1 dự án
# ─────────────────────────────────────────────────────────────────────────────

def build_snapshot(parsed: dict) -> dict:
    project      = parsed["project"]
    metrics      = parsed["metrics"]
    report_dates = parsed.get("report_dates", [])
    latest_date  = report_dates[0] if report_dates else ""

    # GMV
    gmv_m   = next((m for m in metrics if "Tổng GMV" in m["name"]), None)
    gmv_val = gmv_m["daily_values"].get(latest_date, "—") if gmv_m else "—"

    # Net profit margin
    margin_m = next((m for m in metrics if "Net Profit Margin" in m["name"]), None)
    margin_val = margin_m["daily_values"].get(latest_date, "—") if margin_m else "—"
    margin_status = "unknown"
    if margin_m and margin_val and margin_val not in ("", "0", "—"):
        margin_status = status_from_benchmark(margin_val, margin_m["benchmark"], margin_m["name"])

    # 5 key metrics
    key_metrics = {}
    for m_name in ALERT_METRICS_5:
        m = next((x for x in metrics if m_name.lower() in x["name"].lower()), None)
        if not m:
            continue
        short = _get_short_name(m["name"])
        if short in key_metrics:
            continue
        v = m["daily_values"].get(latest_date, "—")
        s = status_from_benchmark(v, m["benchmark"], m["name"]) if v and v not in ("", "0", "—") else "unknown"
        key_metrics[short] = {"value": v, "status": s}

    red_list    = [k for k, v in key_metrics.items() if v["status"] == "red"]
    yellow_list = [k for k, v in key_metrics.items() if v["status"] == "yellow"]
    overall     = "red" if red_list else "yellow" if yellow_list else "green"

    return {
        "project":       project,
        "date":          latest_date,
        "gmv":           gmv_val,
        "margin":        margin_val,
        "margin_status": margin_status,
        "key_metrics":   key_metrics,
        "red":           red_list,
        "yellow":        yellow_list,
        "overall":       overall,
        "phase":         parsed.get("phase", ""),
        "target":        parsed.get("target", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# RENDER 1 PROJECT BLOCK — ngắn gọn
# ─────────────────────────────────────────────────────────────────────────────

EMOJI = {"green": "✅", "yellow": "🟡", "red": "🔴", "unknown": ""}

def render_block(snap: dict) -> str:
    e        = EMOJI.get(snap["overall"], "")
    wd       = _get_vn_weekday(snap["date"])
    date_s   = f"{wd} {snap['date'][:5]}" if snap["date"] else "—"
    gmv_disp = fmt(snap["gmv"]) if snap["gmv"] not in ("—", "", "0") else "—"

    lines = [f"{e} {snap['project']}  |  {date_s}"]

    # Phase/Target nếu có (ngắn gọn)
    if snap.get("phase") or snap.get("target"):
        pt = f"{snap.get('phase','')} {snap.get('target','')}".strip()
        lines.append(f"   {pt}")

    # GMV + margin
    margin_e = EMOJI.get(snap["margin_status"], "")
    margin_disp = snap["margin"] if snap["margin"] not in ("—", "", "0") else "—"
    lines.append(f"   GMV: {gmv_disp}   |   Margin: {margin_disp}{margin_e}")

    # Key metrics chỉ show cái có data và khác xanh
    alert_parts = []
    for short, info in snap["key_metrics"].items():
        v = info["value"]
        if not v or v in ("", "0", "—"):
            continue
        icon = EMOJI.get(info["status"], "")
        if info["status"] in ("red", "yellow"):
            alert_parts.append(f"{short}: {fmt(v)}{icon}")
    if alert_parts:
        lines.append(f"   {'  '.join(alert_parts)}")

    # Summary
    if snap["red"]:
        lines.append(f"   🚨 Cần xử lý: {', '.join(snap['red'])}")
    elif snap["yellow"]:
        lines.append(f"   ⚠️  Theo dõi: {', '.join(snap['yellow'])}")
    else:
        lines.append("   ✅ Tất cả xanh")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# AI HEADLINE — 2-3 câu tổng thể cho CEO
# ─────────────────────────────────────────────────────────────────────────────

def ai_headline(snapshots: list[dict], mode: str) -> str:
    if not HAS_ANTHROPIC:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    mode_label = "hôm qua (chốt cuối ngày)" if mode == "morning" else "hôm nay (real-time đến giờ này)"
    lines = []
    for s in snapshots:
        alerts = []
        if s["red"]:
            alerts.append(f"ĐỎ: {', '.join(s['red'])}")
        if s["yellow"]:
            alerts.append(f"VÀNG: {', '.join(s['yellow'])}")
        alert_str = " | ".join(alerts) if alerts else "xanh"
        gmv = fmt(s["gmv"]) if s["gmv"] not in ("—", "", "0") else "—"
        lines.append(f"- {s['project']}: GMV={gmv}, Margin={s['margin']}, {alert_str}")

    prompt = f"""Bạn là AI assistant tổng hợp cho CEO Hecatech (TikTok Shop multi-market).
Dữ liệu {mode_label}:
{chr(10).join(lines)}

Viết đúng 3 câu ngắn cho CEO:
1. Tình trạng chung (x xanh / y vàng / z đỏ — healthy hay cần chú ý)
2. Dự án/điểm nổi bật nhất (tốt hoặc xấu nhất)
3. 1 action ưu tiên nhất nếu cần (hoặc "Không có action khẩn" nếu tất cả xanh)

Tiếng Việt, không markdown, không bullet, không xuống dòng thừa."""

    try:
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"   ⚠️ AI headline lỗi: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# SEND LARK
# ─────────────────────────────────────────────────────────────────────────────

def send_lark(webhook: str, text: str, label: str = "") -> bool:
    payload = {"msg_type": "text", "content": {"text": text}}
    data    = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req     = urllib.request.Request(
        webhook, data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            ok   = body.get("code") == 0 or body.get("StatusCode") == 0
            print(f"  {'✅' if ok else '❌'} Gửi [{label}]: {'OK' if ok else body}")
            return ok
    except Exception as e:
        print(f"  ❌ Lỗi gửi Lark: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    mode  = get_mode()
    icon  = "🌅" if mode == "morning" else "🌆"
    label = "10:00 — Dữ liệu hôm qua" if mode == "morning" else "16:00 — Dữ liệu hôm nay"
    now   = datetime.now().strftime("%d/%m/%Y %H:%M")

    print(f"\n🚀 CEO BRIEFING | {icon} {label}  ({now})\n")

    # 1. Đọc tất cả dự án (n_days=1 — chỉ lấy ngày gần nhất)
    snapshots = []
    failed    = []
    for project in PROJECT_WEBHOOKS:
        print(f"  📊 [{project}]...", end=" ", flush=True)
        rows = fetch_project_sheet(project)
        if not rows:
            print("❌ skip")
            failed.append(project)
            continue
        parsed = parse_project_metrics(rows, project, n_days=1)
        if not parsed:
            print("❌ parse")
            failed.append(project)
            continue
        snap = build_snapshot(parsed)
        snapshots.append(snap)
        e = EMOJI.get(snap["overall"], "")
        gmv = fmt(snap["gmv"]) if snap["gmv"] not in ("—", "", "0") else "—"
        print(f"{e}  GMV={gmv}")

    if not snapshots:
        print("❌ Không có dữ liệu")
        return

    n_red    = sum(1 for s in snapshots if s["overall"] == "red")
    n_yellow = sum(1 for s in snapshots if s["overall"] == "yellow")
    n_green  = sum(1 for s in snapshots if s["overall"] == "green")
    header_e = "🔴" if n_red >= 3 else "🟡" if n_red >= 1 or n_yellow >= 3 else "🟢"

    # 2. AI headline
    print("\n  🤖 AI headline...", end=" ", flush=True)
    headline = ai_headline(snapshots, mode)
    print("✅" if headline else "skip")

    # 3. Build message
    lines = []
    lines.append(f"📈 CEO BRIEFING  {icon}  {now}")
    lines.append(f"{label}")
    lines.append(SEP)
    lines.append(f"{header_e} Tổng {len(snapshots)} dự án: ✅{n_green} xanh  🟡{n_yellow} vàng  🔴{n_red} đỏ")

    if headline:
        lines.append("")
        lines.append(headline)

    if failed:
        lines.append(f"⚠️  Không lấy được data: {', '.join(failed)}")

    # Sắp xếp: đỏ trước, vàng, xanh sau
    order = {"red": 0, "yellow": 1, "green": 2}
    snapshots_sorted = sorted(snapshots, key=lambda s: order.get(s["overall"], 3))

    for snap in snapshots_sorted:
        lines.append("")
        lines.append(SEP)
        lines.append(render_block(snap))

    lines.append("")
    lines.append(SEP)

    msg = "\n".join(lines)

    # 4. Preview + gửi
    print()
    print(msg)
    print()
    print("📤 Gửi CEO Lark...")
    send_lark(CEO_WEBHOOK, msg, label=f"CEO [{mode}]")

    print("✅ Hoàn tất!")


if __name__ == "__main__":
    main()
