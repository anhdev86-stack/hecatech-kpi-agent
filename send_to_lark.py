#!/usr/bin/env python3
"""
Hecatech AI Agent — Gửi mock output lên Lark Webhook

Dùng data mẫu có sẵn (không cần Anthropic API key).
Gửi 2 tin nhắn:
  1. Per-Project Warning (XKMVN)
  2. CEO Briefing (11 dự án)

Usage:
    python3 send_to_lark.py <LARK_WEBHOOK_URL>

Ví dụ:
    python3 send_to_lark.py "https://open.larksuite.com/open-apis/bot/v2/hook/xxxxxxxx"

Lấy webhook URL:
    Lark Group → Settings → Bots → Add Custom Bot → copy Webhook URL
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# DATA MẪU (giống run_mock.py)
# ─────────────────────────────────────────────────────────────────────────────

MOCK_PROJECT_OUTPUT = {
    "project": "XKMVN",
    "date": "2026-04-12",
    "summary": {
        "gmv_yesterday": {
            "value": 205000000,
            "status": "green",
            "vs_benchmark_daily": "+23%"
        },
        "gmv_mtd": {
            "value": 2400000000,
            "target": 5000000000,
            "pct": 48,
            "pacing_status": "on_track"
        },
        "net_profit_margin_mtd": {
            "value": 0.109,
            "status": "yellow"
        }
    },
    "warnings": [
        {
            "priority": 1,
            "metric": "Take Rate",
            "value": "32.4%",
            "status": "red",
            "threshold": "benchmark ≤ 28%",
            "consecutive_days": 12,
            "root_cause": "TikTok tăng platform fee từ 28% → 32% kể từ 01/04. Đây là thay đổi chính sách hệ thống, không phải lỗi vận hành.",
            "action": "CEO xem xét renegotiate với TikTok account manager hoặc điều chỉnh giá bán để bù COGS. SaoBT cần mô hình lại P&L với take rate mới.",
            "owner": "SaoBT + CEO",
            "missing_data_note": None
        },
        {
            "priority": 2,
            "metric": "CPA",
            "value": "54.6K VND",
            "status": "yellow",
            "threshold": "benchmark ngày ≤ 52K",
            "consecutive_days": 3,
            "root_cause": "CTR giảm nhẹ từ 2.53% → 2.49% — creative hiện tại có dấu hiệu mệt mỏi sau 12 ngày chạy liên tục.",
            "action": "TuND refresh ít nhất 3 creative mới trước 15/04 (TikTok Sale). SaoBT test 2 angle mới: 'before/after' và 'social proof' format.",
            "owner": "SaoBT + TuND",
            "missing_data_note": None
        }
    ],
    "bright_spots": [
        {
            "metric": "AOV Live",
            "value": "243K VND",
            "note": "cao nhất trong 12 ngày qua — LinhDTH đang upsell hiệu quả"
        },
        {
            "metric": "GMV hôm qua",
            "value": "205M VND",
            "note": "+23% vs benchmark ngày — vượt kế hoạch ngày"
        },
        {
            "metric": "CVR Product Card",
            "value": "54.8%",
            "note": "ổn định cao, thumbnail đang hoạt động tốt"
        }
    ],
    "top_actions_today": [
        {
            "priority": 1,
            "action": "CEO + SaoBT họp 15 phút re: Take Rate — quyết định tăng giá bán hay negotiate TikTok",
            "owner": "CEO + SaoBT",
            "deadline": "trước 10:00 hôm nay"
        },
        {
            "priority": 2,
            "action": "TuND: Deploy 3 creative mới trước 15/04 TikTok Sale để tránh creative fatigue",
            "owner": "TuND",
            "deadline": "14/04 EOD"
        },
        {
            "priority": 3,
            "action": "MaiDN: Confirm booking budget 15/04 Sale — ưu tiên creator có Rate 6s > 35%",
            "owner": "MaiDN",
            "deadline": "hôm nay trưa"
        }
    ],
    "data_quality_flags": [
        "is_mega_day: false — không cần adjust benchmark hôm nay",
        "ACC Audience data: chưa có trong sheet — TuND check thủ công nếu muốn phân tích reach"
    ]
}

MOCK_CEO_OUTPUT = {
    "date": "2026-04-12",
    "headline": {
        "status": "at_risk",
        "one_liner": "Toàn hệ thống đang 40% target MTD vào ngày 12/30 — Take Rate tăng hệ thống là rủi ro chính cần CEO quyết định ngay hôm nay."
    },
    "rollup": {
        "gmv_yesterday": 1348000000,
        "gmv_daily_target": 1950000000,
        "pacing_pct": 69,
        "gmv_mtd": 13650000000,
        "gmv_mtd_target": 33500000000,
        "expected_mtd_pct": 40,
        "mtd_pacing_pct": 41,
        "total_ads_spend_yesterday": 145000000,
        "blended_take_rate": 0.319,
        "blended_net_margin_mtd": 0.098,
        "net_profit_yesterday": 82000000
    },
    "top_3_performers": [
        {
            "project": "KTLVN",
            "reason": "GMV +45% vs benchmark ngày, margin 14.5% xanh, ROAS 3.8x cao nhất VN",
            "learn_from": "Creative refresh rate 42% — nhân rộng framework creative rotation sang XKMVN và KTMVN"
        },
        {
            "project": "XKMPH",
            "reason": "Philippines launch tuần 1: ROAS 4.1x, pacing on_track dù mới ra mắt",
            "learn_from": "Lookalike audience từ VN chuyển tốt cho SEA expansion — tài liệu hóa playbook này"
        },
        {
            "project": "XKMVN",
            "reason": "GMV hôm qua vượt 23% benchmark ngày, AOV Live đạt đỉnh 12 ngày",
            "learn_from": "LinhDTH đang upsell hiệu quả trong live — chia sẻ script với team Thailand"
        }
    ],
    "bottom_3_need_rescue": [
        {
            "project": "TDCVN",
            "reason": "GMV -22% vs benchmark, margin 7.2% đỏ, MTD 39% — nguy cơ miss target tháng cao nhất",
            "who_handles": "CEO + SaoBT họp riêng sau briefing. Cân nhắc tăng budget paid hoặc push live thêm 2 session/tuần"
        },
        {
            "project": "MNĐS",
            "reason": "MTD chỉ 32% sau 12 ngày — cần 68% GMV trong 18 ngày còn lại (bất khả thi với tốc độ hiện tại)",
            "who_handles": "HoangNH + CEO: điều chỉnh target tháng hoặc bơm booking budget khẩn"
        },
        {
            "project": "SRMR",
            "reason": "Không có data — có thể project đã pause hoặc sheet delay nghiêm trọng",
            "who_handles": "NgocNT check ngay trạng thái dự án và update CEO trước 10:00"
        }
    ],
    "ceo_must_decide_today": [
        {
            "priority": 1,
            "decision": "Take Rate 32%+ toàn hệ thống: Tăng giá bán hay negotiate TikTok platform fee?",
            "context": "4/11 dự án đang đỏ về Take Rate 10+ ngày liên tiếp. Nếu không xử lý, margin toàn hệ thống sẽ giảm thêm 1.5-2% MTD.",
            "stakeholder": "SaoBT (số liệu), TikTok Account Manager (negotiate)",
            "deadline": "Quyết định trước 10:00 — SaoBT cần model P&L mới trước cuộc họp team"
        },
        {
            "priority": 2,
            "decision": "TDCVN: Có push thêm budget paid tháng này hay accept miss target?",
            "context": "Net margin 7.2% — nếu tăng budget sẽ xuống <6%. Nếu không làm gì, MTD sẽ đạt ~55% target.",
            "stakeholder": "SaoBT + team TDCVN",
            "deadline": "Trước 12:00 để SaoBT điều campaign"
        },
        {
            "priority": 3,
            "decision": "15/04 TikTok Sale: Confirm budget toàn hệ thống và phân bổ theo dự án",
            "context": "Ngày mai là TikTok Shop 4.15 Sale — cần confirm budget tăng vs ngày thường và creative sẵn sàng chưa.",
            "stakeholder": "SaoBT, TuND, toàn team",
            "deadline": "Hôm nay 14:00"
        }
    ],
    "cross_project_patterns": [
        {
            "pattern": "Take Rate tăng hệ thống 28% → 32%+ trên tất cả dự án TikTok VN trong 12 ngày",
            "hypothesis": "TikTok đã điều chỉnh chính sách platform fee từ 01/04. Không phải lỗi vận hành của từng dự án.",
            "recommendation": "Escalate lên TikTok regional account manager. Nếu không negotiate được, điều chỉnh giá bán +8-10% để bù."
        },
        {
            "pattern": "ROAS tốt nhất ở các dự án có Creative Fresh Rate cao (KTLVN 42%, XKMPH 38%)",
            "hypothesis": "TikTok algorithm ưu tiên creative mới. Dự án nào không rotate creative sau 7-10 ngày sẽ thấy CTR giảm và CPA tăng.",
            "recommendation": "Implement quy trình: mỗi dự án phải có ít nhất 2-3 creative mới/tuần. TuND cần thêm 1 editor hoặc dùng AI tool."
        }
    ],
    "quick_wins_available": [
        "Nhân rộng live upsell script của LinhDTH (XKMVN) sang team Thailand — có thể tăng AOV 10-15%",
        "Dùng lookalike audience từ VN cho Malaysia và Myanmar — XKMPH đã prove ROAS 4.1x tuần đầu",
        "Push booking cho 15/04 Sale ngay hôm nay — creator lead time cần 24-48h"
    ],
    "data_quality_flags": [
        "SRMR: Không có data — cần xác nhận ngay",
        "is_mega_day 15/04: Các dự án cần adjust benchmark ×1.5 cho ngày mai (TikTok Sale)"
    ]
}


# ─────────────────────────────────────────────────────────────────────────────
# RENDER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def format_vnd(value) -> str:
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


def render_project_card(result: dict) -> str:
    emoji = {"green": "✅", "yellow": "🟡", "red": "🔴"}
    lines = []

    lines.append(f"{'='*60}")
    lines.append(f"  {result['project']} — {result['date']}")
    lines.append(f"{'='*60}")
    lines.append("")

    s = result.get("summary", {})
    lines.append("📊 TỔNG QUAN")
    if "gmv_yesterday" in s:
        g = s["gmv_yesterday"]
        lines.append(f"  GMV hôm qua: {format_vnd(g['value'])} {emoji.get(g.get('status', ''), '')}")
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
        lines.append(f"  Net margin MTD: {n['value']:.1%} {emoji.get(n.get('status', ''), '')}")
    lines.append("")

    warnings = result.get("warnings", [])
    if warnings:
        lines.append(f"⚠️  WARNING ({len(warnings)} chỉ số cần chú ý)")
        lines.append("")
        for w in warnings:
            streak = f" — ngày thứ {w['consecutive_days']}" if w.get("consecutive_days", 0) > 1 else ""
            lines.append(
                f"  {w['priority']}. {emoji.get(w['status'], '')} {w['metric']}: "
                f"{w['value']} ({w.get('threshold', '')}){streak}"
            )
            lines.append(f"     ↳ Nguyên nhân: {w.get('root_cause', '—')}")
            lines.append(f"     ↳ Hành động: {w.get('action', '—')}")
            lines.append(f"     ↳ Owner: {w.get('owner', '—')}")
            if w.get("missing_data_note"):
                lines.append(f"     ℹ️  {w['missing_data_note']}")
            lines.append("")
    else:
        lines.append("⚠️  Không có warning — tất cả metric xanh")
        lines.append("")

    spots = result.get("bright_spots", [])
    if spots:
        lines.append("✅ ĐIỂM SÁNG")
        for b in spots:
            lines.append(f"  - {b['metric']}: {b['value']} ({b.get('note', '')})")
        lines.append("")

    actions = result.get("top_actions_today", [])
    if actions:
        lines.append("📋 TOP VIỆC HÔM NAY")
        for a in actions:
            lines.append(f"  {a['priority']}. {a['action']} — {a['owner']}")
        lines.append("")

    flags = result.get("data_quality_flags", [])
    if flags:
        lines.append("⚙️  DATA NOTES")
        for f in flags:
            lines.append(f"  - {f}")
        lines.append("")

    return "\n".join(lines)


def render_ceo_briefing(b: dict) -> str:
    status_emoji = {"on_track": "🟢", "at_risk": "🟡", "alert": "🔴"}
    lines = []
    r = b.get("rollup", {})

    lines.append(f"{'='*65}")
    lines.append(f"  📈 CEO BRIEFING — {b.get('date', '?')}")
    lines.append(f"{'='*65}")

    h = b.get("headline", {})
    lines.append(f"\n{status_emoji.get(h.get('status', ''), '')} {h.get('one_liner', '')}\n")

    lines.append("─" * 65)
    lines.append("TỔNG QUAN HÔM QUA")
    lines.append(f"  GMV hôm qua: {format_vnd(r.get('gmv_yesterday'))} / {format_vnd(r.get('gmv_daily_target'))} ({r.get('pacing_pct', 0)}%)")
    lines.append(
        f"  MTD: {format_vnd(r.get('gmv_mtd'))} / {format_vnd(r.get('gmv_mtd_target'))} "
        f"({r.get('mtd_pacing_pct', 0)}% vs expected {r.get('expected_mtd_pct', 0)}%)"
    )
    lines.append(f"  Ads spend hôm qua: {format_vnd(r.get('total_ads_spend_yesterday'))}")
    lines.append(
        f"  Blended take rate: {r.get('blended_take_rate', 0)*100:.1f}% | "
        f"Net margin MTD: {r.get('blended_net_margin_mtd', 0)*100:.1f}%"
    )
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


# ─────────────────────────────────────────────────────────────────────────────
# LARK SENDER
# ─────────────────────────────────────────────────────────────────────────────

def send_lark_text(webhook_url: str, text: str, label: str = "") -> bool:
    """Gửi plain text lên Lark webhook. Trả về True nếu thành công."""
    payload = {
        "msg_type": "text",
        "content": {"text": text}
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                print(f"  ✅ Gửi {label} thành công!")
                return True
            else:
                print(f"  ❌ Lark trả lỗi [{label}]: {body}")
                return False
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code} khi gửi {label}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"  ❌ Lỗi kết nối [{label}]: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("❌ Thiếu Lark Webhook URL.\n")
        print("Usage: python3 send_to_lark.py <WEBHOOK_URL>")
        print('Ví dụ: python3 send_to_lark.py "https://open.larksuite.com/open-apis/bot/v2/hook/xxxx"')
        sys.exit(1)

    webhook_url = sys.argv[1].strip()
    if not webhook_url.startswith("http"):
        print(f"❌ Webhook URL không hợp lệ: {webhook_url}")
        sys.exit(1)

    print("\n🚀 HECATECH AI AGENT — Gửi mock data lên Lark")
    print(f"   Webhook: {webhook_url[:60]}...")
    print()

    # ── Agent #1: Per-Project Warning ─────────────────────────────────────────
    print("📤 [1/2] Gửi Per-Project Warning (XKMVN)...")
    project_text = render_project_card(MOCK_PROJECT_OUTPUT)
    print(project_text)
    send_lark_text(webhook_url, project_text, label="Agent #1 Per-Project")

    print()

    # ── Agent #5: CEO Briefing ────────────────────────────────────────────────
    print("📤 [2/2] Gửi CEO Briefing (11 dự án)...")
    ceo_text = render_ceo_briefing(MOCK_CEO_OUTPUT)
    print(ceo_text)
    send_lark_text(webhook_url, ceo_text, label="Agent #5 CEO Briefing")

    print()
    print("✅ Xong! Kiểm tra Lark group để xem tin nhắn.")
    print()
    print("─" * 60)
    print("Bước tiếp theo — chạy thật với Claude AI:")
    print('  export ANTHROPIC_API_KEY="sk-ant-xxxxx"')
    print("  python3 test_local.py sample_data.json")


if __name__ == "__main__":
    main()
