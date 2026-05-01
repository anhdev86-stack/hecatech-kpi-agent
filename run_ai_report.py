#!/usr/bin/env python3
"""
Hecatech AI Agent — Full Pipeline với Brain (Knowledge Base)

Luồng:
  1. Đọc Google Sheet → data thực tế
  2. Load brain/ → knowledge base công ty
  3. Gọi Claude API → phân tích bám sát playbook
  4. Format → Gửi Lark

Usage:
    export ANTHROPIC_API_KEY="sk-ant-xxxxx"
    python3 run_ai_report.py morning      # 10:00 — báo cáo hôm qua
    python3 run_ai_report.py afternoon    # 16:00 — báo cáo ngày hiện tại
    python3 run_ai_report.py              # tự detect theo giờ hệ thống

Fallback: Nếu không có ANTHROPIC_API_KEY → chạy rule-based (không gọi Claude)
"""

import csv
import io
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Import brain loader
sys.path.insert(0, str(Path(__file__).parent))
from brain_loader import load_brain, brain_summary
from brain_advisor import build_warning_cards

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SHEET_ID      = "1VtwiBZb-wq3ZX4ss-lYvcJqfsgZIZhifotu7dszw_m4"
LARK_WEBHOOK  = "https://open.larksuite.com/open-apis/bot/v2/hook/ad36383c-06b9-48ee-ad3b-08dd771fa9fa"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
MODEL         = "claude-sonnet-4-5"
SCRIPT_DIR    = Path(__file__).parent
PROMPT_FILE   = SCRIPT_DIR / "prompt_system.md"

# ─────────────────────────────────────────────────────────────────────────────
# MODE
# ─────────────────────────────────────────────────────────────────────────────

def get_mode() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in ("morning", "afternoon"):
        return sys.argv[1]
    return "morning" if datetime.now().hour < 13 else "afternoon"

# ─────────────────────────────────────────────────────────────────────────────
# FETCH GOOGLE SHEET
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sheet(url: str) -> list[list]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print("❌ Sheet chưa share public: Share → Anyone with link → Viewer")
        else:
            print(f"❌ HTTP {e.code}: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi kết nối sheet: {e}")
        sys.exit(1)
    reader = csv.reader(io.StringIO(raw))
    return list(reader)

# ─────────────────────────────────────────────────────────────────────────────
# PARSE SHEET → STRUCTURED DATA
# ─────────────────────────────────────────────────────────────────────────────

def parse_num(s: str) -> float:
    try:
        return float(s.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0

def parse_pct(s: str) -> float:
    try:
        return float(s.replace("%", "").replace(",", ".").strip())
    except (ValueError, AttributeError):
        return 0.0

def parse_sheet(rows: list[list]) -> dict:
    header   = rows[0]
    date_str = header[0].strip()
    try:
        year     = datetime.now().year
        date_obj = datetime.strptime(f"{date_str}/{year}", "%d/%m/%Y")
        date_display = date_obj.strftime("%d/%m/%Y")
    except ValueError:
        date_display = date_str

    projects = []
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        g = lambda i, d="": row[i].strip() if i < len(row) else d
        status_raw = g(8)
        status = "red" if "🔴" in status_raw else "yellow" if "🟡" in status_raw else "green"

        projects.append({
            "project": g(0),
            "status": status,
            "status_emoji": status_raw,
            "market": g(9),
            # Daily
            "ds_day":   parse_num(g(1)),
            "dt_day":   parse_num(g(2)),
            "voucher":  parse_num(g(3)),
            "cp_day":   parse_num(g(4)),
            "ln_day":   parse_num(g(5)),
            "thr_red":  parse_num(g(6)),
            "thr_green":parse_num(g(7)),
            # MTD
            "ds_mtd":  parse_num(g(10)),
            "cp_mtd":  parse_num(g(11)),
            "ln_mtd":  parse_num(g(12)),
            "dt_mtd":  parse_num(g(13)),
            "ty_le":   parse_pct(g(14)),
            "cp_ds":   parse_pct(g(15)),
        })

    return {"date": date_display, "projects": projects}

# ─────────────────────────────────────────────────────────────────────────────
# LOAD SYSTEM PROMPT (từ prompt_system.md)
# ─────────────────────────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    text = PROMPT_FILE.read_text(encoding="utf-8")
    m = re.search(r"## 1\. SYSTEM PROMPT.*?```\s*(.*?)```", text, re.DOTALL)
    if not m:
        raise RuntimeError("Không tìm thấy SYSTEM PROMPT trong prompt_system.md")
    return m.group(1).strip()

# ─────────────────────────────────────────────────────────────────────────────
# FORMAT VND
# ─────────────────────────────────────────────────────────────────────────────

def fmt(v: float) -> str:
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:     return f"{v/1_000_000:.1f}M"
    if v >= 1_000:         return f"{v/1_000:.0f}K"
    return f"{v:.0f}"

# ─────────────────────────────────────────────────────────────────────────────
# BUILD CLAUDE PROMPT (sheet data + brain)
# ─────────────────────────────────────────────────────────────────────────────

def build_analysis_prompt(data: dict, mode: str) -> str:
    date     = data["date"]
    projects = data["projects"]

    # Summary table
    rows_txt = []
    for p in projects:
        e = "🔴" if p["status"] == "red" else "🟡" if p["status"] == "yellow" else "✅"
        rows_txt.append(
            f"| {e} {p['project']} | {fmt(p['ds_day'])} | {fmt(p['cp_day'])} | "
            f"{fmt(p['ln_day'])} | {p['ty_le']:+.1f}% | {fmt(p['thr_red'])} | {fmt(p['thr_green'])} |"
        )

    table = (
        "| Status | Project | DS Ngày | Chi phí | LN | Biên MTD | Ngưỡng🔴 | Ngưỡng✅ |\n"
        "|--------|---------|---------|---------|----|-----------|-----------|-----------|\n"
        + "\n".join(rows_txt)
    )

    total_ds  = sum(p["ds_day"] for p in projects)
    total_cp  = sum(p["cp_day"] for p in projects)
    total_ln  = sum(p["ln_day"] for p in projects)
    n_red     = sum(1 for p in projects if p["status"] == "red")
    n_yellow  = sum(1 for p in projects if p["status"] == "yellow")
    n_green   = sum(1 for p in projects if p["status"] == "green")
    margin    = (total_ln / total_ds * 100) if total_ds else 0

    mode_label = "hôm qua (dữ liệu chốt cuối ngày)" if mode == "morning" else "ngày hiện tại (real-time đến giờ này)"

    day_of_month = datetime.now().day
    days_in_month = 30  # default

    return f"""Ngày báo cáo: {date} ({mode_label})
Ngày trong tháng: {day_of_month}/30

TỔNG QUAN HỆ THỐNG:
- Tổng doanh số: {fmt(total_ds)} | Chi phí: {fmt(total_cp)} | Lợi nhuận: {fmt(total_ln)}
- Biên LN toàn hệ thống: {margin:+.1f}%
- Trạng thái: ✅ {n_green} xanh | 🟡 {n_yellow} vàng | 🔴 {n_red} đỏ

DỮ LIỆU TỪNG DỰ ÁN:
{table}

PHÂN TÍCH CHI TIẾT MỖI DỰ ÁN LỖ / ĐỎ:
{json.dumps([p for p in projects if p['status'] in ('red', 'yellow') or p['ln_day'] < 0],
            ensure_ascii=False, indent=2)}

YÊU CẦU (BẮT BUỘC):
1. Phân tích theo ma trận phễu v12
2. ⚠️ QUAN TRỌNG NHẤT: Với MỖI dự án bị cảnh báo, TÌM file ifthen_<MÃ>.md trong KNOWLEDGE BASE
   VD: TDCVN → tìm trong [ifthen_TDCVN.md], XKMPH → tìm trong [ifthen_XKMPH.md]
3. Trong file IF-THEN, tìm SECTION chỉ số tương ứng (VD: CPM, CPA, Take Rate...)
4. TRÍCH DẪN ĐÚNG: hành động, owner, mức rủi ro từ IF-THEN → KHÔNG tự nghĩ ra
5. Mỗi warning PHẢI có field playbook_ref = 'brain/ifthen_XXX.md → [section name]'
6. Nếu KHÔNG tìm thấy IF-THEN → ghi playbook_ref = '⚠️ Chưa có IF-THEN — cần bổ sung'
7. Owner phải ĐÚNG theo file IF-THEN (VD: Vinh, Ngọc, Hằng, Mai, GiangNT...)
8. Trả về JSON theo đúng schema trong system prompt"""

# ─────────────────────────────────────────────────────────────────────────────
# CALL CLAUDE
# ─────────────────────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_message: str) -> dict | None:
    if not HAS_ANTHROPIC:
        print("⚠️  anthropic SDK chưa cài: pip install anthropic")
        return None
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️  Chưa set ANTHROPIC_API_KEY — chạy fallback rule-based")
        return None

    client = Anthropic()
    print(f"🤖 Đang gọi Claude ({MODEL}) với brain...")
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        print(f"❌ Claude API lỗi: {e}")
        return None

    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    try:
        parsed = json.loads(text)
        cost = (resp.usage.input_tokens * 3 + resp.usage.output_tokens * 15) / 1_000_000
        print(f"   ✅ Claude OK — {resp.usage.input_tokens} in + {resp.usage.output_tokens} out (~${cost:.4f})")
        return parsed
    except json.JSONDecodeError as e:
        print(f"❌ Claude không trả JSON hợp lệ: {e}")
        print("RAW:", text[:300])
        return None

# ─────────────────────────────────────────────────────────────────────────────
# RENDER LARK MESSAGES
# ─────────────────────────────────────────────────────────────────────────────

EMOJI = {"green": "✅", "yellow": "🟡", "red": "🔴"}

def render_ai_report(result: dict, mode: str) -> str:
    """Render JSON từ Claude thành text Lark."""
    label = "📅 BÁO CÁO NGÀY HÔM QUA (AI + Brain)" if mode == "morning" else "⏱️  BÁO CÁO NGÀY HIỆN TẠI (AI + Brain)"

    lines = [label, ""]
    lines.append(f"{'='*62}")
    lines.append(f"  {result.get('project','Hecatech')} — {result.get('date','')}")
    lines.append(f"{'='*62}")
    lines.append("")

    # Summary
    s = result.get("summary", {})
    lines.append("📊 TỔNG QUAN")
    if "gmv_yesterday" in s:
        g = s["gmv_yesterday"]
        lines.append(f"  GMV: {fmt(g.get('value',0))} {EMOJI.get(g.get('status',''), '')}")
        if g.get("vs_benchmark_daily"):
            lines.append(f"    vs benchmark: {g['vs_benchmark_daily']}")
    if "gmv_mtd" in s:
        m = s["gmv_mtd"]
        lines.append(f"  MTD: {fmt(m.get('value',0))} / {fmt(m.get('target',0))} ({m.get('pct',0)}% — {m.get('pacing_status','')})")
    if "net_profit_margin_mtd" in s:
        n = s["net_profit_margin_mtd"]
        v = n.get("value", 0)
        lines.append(f"  Net margin MTD: {v:.1%} {EMOJI.get(n.get('status',''), '')}")
    lines.append("")

    # Warnings (với playbook reference)
    warnings = result.get("warnings", [])
    if warnings:
        lines.append(f"⚠️  WARNING ({len(warnings)} chỉ số)")
        lines.append("")
        for w in warnings:
            streak = f" — ngày thứ {w['consecutive_days']}" if w.get("consecutive_days", 0) > 1 else ""
            lines.append(
                f"  {w.get('priority','')}. {EMOJI.get(w.get('status',''), '')} {w.get('metric','')}: "
                f"{w.get('value','')} ({w.get('threshold','')}){streak}"
            )
            if w.get("root_cause"):
                lines.append(f"     ↳ Nguyên nhân: {w['root_cause']}")
            if w.get("action"):
                lines.append(f"     ↳ Hành động: {w['action']}")
            if w.get("owner"):
                lines.append(f"     ↳ Owner: {w['owner']}")
            if w.get("playbook_ref"):
                lines.append(f"     📖 Playbook: {w['playbook_ref']}")
            if w.get("missing_data_note"):
                lines.append(f"     ℹ️  {w['missing_data_note']}")
            lines.append("")
    else:
        lines.append("✅ Không có warning — tất cả metric xanh")
        lines.append("")

    # Bright spots
    for b in result.get("bright_spots", []):
        lines.append(f"  ✅ {b.get('metric','')}: {b.get('value','')} ({b.get('note','')})")

    # Top actions
    actions = result.get("top_actions_today", [])
    if actions:
        lines.append("")
        lines.append("📋 TOP VIỆC HÔM NAY")
        for a in actions:
            lines.append(f"  {a.get('priority','')}. {a.get('action','')} — {a.get('owner','')}")

    # Data flags
    flags = result.get("data_quality_flags", [])
    if flags:
        lines.append("")
        lines.append("⚙️  DATA NOTES")
        for f in flags:
            lines.append(f"  - {f}")

    return "\n".join(lines)


def render_brain_report(data: dict, mode: str) -> str:
    """
    Render báo cáo CEO format — cảnh báo + hành động bám playbook brain.
    Format bám sát screenshot: header, tổng quan, warning có action từ playbook, top việc.
    """
    label = "🔥 BÁO CÁO NGÀY HÔM QUA" if mode == "morning" else "⏱️  BÁO CÁO NGÀY HIỆN TẠI"
    projects = data["projects"]
    date     = data["date"]

    # ── Tổng rollup ─────────────────────────────────────────────────────────
    total_ds    = sum(p["ds_day"] for p in projects)
    total_ln    = sum(p["ln_day"] for p in projects)
    total_thr_g = sum(p["thr_green"] for p in projects)
    total_thr_r = sum(p["thr_red"] for p in projects)
    margin      = (total_ln / total_ds * 100) if total_ds else 0
    pct_g       = (total_ds / total_thr_g * 100) if total_thr_g else 0
    n_g = sum(1 for p in projects if p["status"] == "green")
    n_y = sum(1 for p in projects if p["status"] == "yellow")
    n_r = sum(1 for p in projects if p["status"] == "red")

    rollup_status = "🟢" if n_r == 0 and n_y <= 2 else "🟡" if n_r <= 2 else "🔴"

    lines = []
    lines.append(f"Bot CEO: {label}")
    lines.append(f"{'='*62}")
    lines.append(f"  Hecatech — {date}")
    lines.append(f"{'='*62}")
    lines.append("")

    # ── Tổng quan ────────────────────────────────────────────────────────────
    lines.append("📊 TỔNG QUAN")
    lines.append(f"  GMV hôm nay: {fmt(total_ds)} / ngưỡng xanh {fmt(total_thr_g)} ({pct_g:.0f}%)")
    lines.append(f"  Lợi nhuận:   {fmt(total_ln)} | Biên: {margin:+.1f}%")
    lines.append(f"  Trạng thái:  {rollup_status}  ✅ {n_g} xanh  🟡 {n_y} vàng  🔴 {n_r} đỏ")
    lines.append("")

    # ── Per-project nhanh ────────────────────────────────────────────────────
    lines.append("─" * 62)
    for p in projects:
        e   = "🔴" if p["status"] == "red" else "🟡" if p["status"] == "yellow" else "✅"
        pct = (p["ds_day"] / p["thr_green"] * 100) if p["thr_green"] else 0
        ln_e = "✅" if p["ln_day"] >= 0 else "🔴"
        lines.append(
            f"  {e} {p['project']:10s}  DS: {fmt(p['ds_day']):>8s}  "
            f"LN: {fmt(p['ln_day']):>8s} {ln_e}  ({pct:.0f}%)"
        )
    lines.append("")

    # ── Warnings + actions từ brain ──────────────────────────────────────────
    alert_projects = [p for p in projects if p["status"] in ("red", "yellow") or p["ln_day"] < 0]
    all_warnings = []
    for p in alert_projects:
        cards = build_warning_cards(p)
        for card in cards:
            card["_project"] = p["project"]
            all_warnings.append(card)

    if all_warnings:
        lines.append("─" * 62)
        lines.append(f"⚠️  CẢNH BÁO & HÀNH ĐỘNG ({len(all_warnings)} vấn đề cần xử lý)")
        lines.append("")
        for i, w in enumerate(all_warnings, 1):
            e = "🔴" if w["status"] == "red" else "🟡"
            lines.append(f"  {i}. {e} [{w['_project']}] {w['metric']}: {w['value']} ({w['threshold']})")
            if w.get("risk_level"):
                lines.append(f"     ⚡ Mức rủi ro: {w['risk_level']}")
            lines.append(f"     ↳ Nguyên nhân: {w['root_cause']}")

            # Actions từ brain IF-THEN — format thành numbered list
            raw_actions = w.get("action", "")
            if " → " in raw_actions:
                steps = raw_actions.split(" → ")
                for j, step in enumerate(steps[:3], 1):
                    lines.append(f"     {j}. {step.strip()}")
            else:
                lines.append(f"     ↳ Hành động: {raw_actions}")

            lines.append(f"     ↳ Owner: {w['owner']}  |  SLA: {w['sla']}")
            if w.get("playbook_ref") and w["playbook_ref"] != "—":
                lines.append(f"     {w['playbook_ref']}")
            lines.append("")
    else:
        lines.append("✅ Không có cảnh báo — tất cả dự án đang xanh")
        lines.append("")

    # ── Top 3 việc hôm nay (aggregate từ tất cả warning) ────────────────────
    if all_warnings:
        lines.append("─" * 62)
        lines.append("📋 TOP VIỆC HÔM NAY")
        priorities = []
        for w in all_warnings[:3]:
            raw = w.get("action", "")
            first_step = raw.split(" → ")[0].strip() if " → " in raw else raw[:80]
            priorities.append(f"  {len(priorities)+1}. {first_step} — {w['owner']}")
        lines.extend(priorities)
        lines.append("")

    # ── Điểm sáng (top performers) ───────────────────────────────────────────
    bright = sorted(
        [p for p in projects if p["ln_day"] > 0 and p["status"] == "green"],
        key=lambda x: x["ds_day"], reverse=True
    )[:3]
    if bright:
        lines.append("─" * 62)
        lines.append("✅ ĐIỂM SÁNG")
        for b in bright:
            pct = (b["ds_day"] / b["thr_green"] * 100) if b["thr_green"] else 0
            lines.append(f"  - {b['project']}: DS {fmt(b['ds_day'])} ({pct:.0f}% target) | LN {fmt(b['ln_day'])} | Biên {b['ty_le']:+.1f}%")
        lines.append("")

    # ── Data notes ───────────────────────────────────────────────────────────
    no_mtd = [p["project"] for p in projects if p["ds_mtd"] == 0]
    if no_mtd:
        lines.append("⚙️  DATA NOTES")
        lines.append(f"  - Chưa có dữ liệu MTD: {', '.join(no_mtd)}")
        lines.append("")

    # Count brain sources
    n_ifthen = sum(1 for w in all_warnings if w.get("source") == "brain_ifthen")
    n_playbook = sum(1 for w in all_warnings if w.get("source") == "brain_playbook")
    n_missing = sum(1 for w in all_warnings if w.get("source") == "no_brain_match")
    brain_files = len(list((Path(__file__).parent / "brain").glob("ifthen_*.md")))
    lines.append(f"🧠 [Brain: {brain_files} IF-THEN files | Nguồn: 📖{n_ifthen} IF-THEN, 📘{n_playbook} playbook, ⚠️{n_missing} chưa có | Sheet: {date}]")
    return "\n".join(lines)


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
        print(f"  ❌ Lỗi gửi Lark [{label}]: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    mode  = get_mode()
    icon  = "🌅" if mode == "morning" else "🌆"
    label = "Buổi sáng 10:00 — hôm qua" if mode == "morning" else "Buổi chiều 16:00 — hôm nay"

    print(f"\n🚀 HECATECH AI AGENT — {icon} {label}")
    print(f"   Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    # 1. Load brain
    print("📚 Đang load brain (knowledge base)...")
    brain_kb = load_brain()
    print(f"   {brain_summary()}")
    print()

    # 2. Fetch sheet
    print("📥 Đang tải Google Sheet...")
    rows = fetch_sheet(SHEET_CSV_URL)
    data = parse_sheet(rows)
    print(f"   ✅ {len(data['projects'])} dự án — ngày {data['date']}")
    print()

    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY")) and HAS_ANTHROPIC

    if has_api_key and brain_kb:
        # 3a. AI mode — gọi Claude với brain
        print("🧠 Chế độ: AI + Brain (Claude)")
        base_system = load_system_prompt()
        full_system = base_system + "\n\n" + brain_kb
        user_msg    = build_analysis_prompt(data, mode)
        ai_result   = call_claude(full_system, user_msg)

        if ai_result:
            msg = render_ai_report(ai_result, mode)
        else:
            print("⚠️  Claude thất bại, chuyển sang brain rule-based")
            msg = render_brain_report(data, mode)
    else:
        # 3b. Brain rule-based — cảnh báo + hành động từ playbook, không cần API key
        reason = "chưa có ANTHROPIC_API_KEY" if not has_api_key else "brain/ trống"
        print(f"🧠 Chế độ: Brain Rule-based ({reason})")
        msg = render_brain_report(data, mode)

    # 4. Preview
    print()
    print(msg)

    # 5. Gửi Lark
    print("─" * 62)
    print("📤 Đang gửi lên Lark...")
    send_lark(LARK_WEBHOOK, msg, label=f"AI Report [{mode}]")

    # 6. Lưu log
    log_path = SCRIPT_DIR / f"ai_report_{mode}_{datetime.now().strftime('%Y%m%d')}.json"
    log_path.write_text(
        json.dumps({
            "timestamp": datetime.now().isoformat(),
            "mode": mode,
            "date": data["date"],
            "n_projects": len(data["projects"]),
            "used_brain": bool(brain_kb),
            "used_ai": has_api_key,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"💾 Log: {log_path.name}")
    print()
    print("✅ Hoàn tất!")


if __name__ == "__main__":
    main()
