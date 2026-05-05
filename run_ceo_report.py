#!/usr/bin/env python3
"""
Hecatech AI Agent — CEO Daily Briefing
Đọc sheet "Báo cáo" (gid=228758703), cột J–P → bảng tổng hợp theo thị trường.

Usage:
    python3 run_ceo_report.py             # tự detect giờ
    python3 run_ceo_report.py morning     # 10:00
    python3 run_ceo_report.py afternoon   # 16:00
"""

import csv, io, json, os, sys, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SHEET_ID    = "1FZj7u5y3TzRogBNkH_KxQflHOv2Dmfrq8p1Nski0Jb4"
BAOCAO_GID  = "228758703"
CEO_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/ad36383c-06b9-48ee-ad3b-08dd771fa9fa"
MODEL       = "claude-sonnet-4-6"
SEP         = "─" * 44

MARKET_ORDER = ["Tổng", "Beucare", "Retolab", "Thái", "Malay", "Phil"]


# ─────────────────────────────────────────────────────────────────────────────
# MODE
# ─────────────────────────────────────────────────────────────────────────────

def get_mode() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in ("morning", "afternoon"):
        return sys.argv[1]
    return "morning" if datetime.now().hour < 13 else "afternoon"


# ─────────────────────────────────────────────────────────────────────────────
# FETCH SHEET
# ─────────────────────────────────────────────────────────────────────────────

def fetch_baocao_sheet() -> list[list[str]]:
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&gid={BAOCAO_GID}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(raw)))
        return rows
    except Exception as e:
        print(f"  ❌ Lỗi fetch sheet: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PARSE
# ─────────────────────────────────────────────────────────────────────────────

def parse_baocao(rows: list[list[str]]) -> dict:
    """
    Header row (index 0): A=date, ..., J=Thị trường, K=Doanh số, L=Chi phí,
                          M=Lợi nhuận, N=Doanh thu, O=Tỷ lệ, P=CP/DS
    Data rows (index 1+): cols J–P populated for each market.
    """
    if not rows:
        return {}

    header = rows[0]
    date_str = header[0].strip() if header else ""

    # Find column indices dynamically from header row
    col = {
        "thi_truong": 9,   # J
        "doanh_so":   10,  # K
        "chi_phi":    11,  # L
        "loi_nhuan":  12,  # M
        "doanh_thu":  13,  # N
        "ty_le":      14,  # O
        "cp_ds":      15,  # P
    }

    markets = {}
    for row in rows[1:]:
        if len(row) <= col["cp_ds"]:
            continue
        name = row[col["thi_truong"]].strip()
        if not name or name not in MARKET_ORDER:
            continue
        markets[name] = {
            "doanh_so": row[col["doanh_so"]].strip(),
            "chi_phi":  row[col["chi_phi"]].strip(),
            "loi_nhuan": row[col["loi_nhuan"]].strip(),
            "doanh_thu": row[col["doanh_thu"]].strip(),
            "ty_le":    row[col["ty_le"]].strip(),
            "cp_ds":    row[col["cp_ds"]].strip(),
        }

    return {"date": date_str, "markets": markets}


# ─────────────────────────────────────────────────────────────────────────────
# FORMAT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _clean_num(s: str) -> str:
    """Remove quotes and normalize number string."""
    return s.strip('"').strip("'").strip()

def _fmt_vnd(s: str) -> str:
    """Format VND number for display."""
    s = _clean_num(s)
    if not s or s in ("0", ""):
        return "—"
    try:
        n = int(s.replace(",", "").replace(".", ""))
        if n >= 1_000_000_000:
            return f"{n/1_000_000_000:.1f}B"
        if n >= 1_000_000:
            return f"{n/1_000_000:.0f}M"
        return f"{n:,}"
    except ValueError:
        return s

def _fmt_pct(s: str) -> str:
    """Normalize percentage string."""
    s = _clean_num(s)
    if not s or s in ("0", "0%", ""):
        return "—"
    if "%" not in s:
        try:
            return f"{float(s)*100:.2f}%"
        except ValueError:
            return s
    return s.replace(".", ",")

def _get_vn_weekday(date_str: str) -> str:
    """'04/05' → 'CN 04/05' etc."""
    days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    try:
        year = datetime.now().year
        d = datetime.strptime(f"{date_str[:5]}/{year}", "%d/%m/%Y")
        return f"{days[d.weekday()]} {date_str[:5]}"
    except Exception:
        return date_str[:5]


# ─────────────────────────────────────────────────────────────────────────────
# AI HEADLINE
# ─────────────────────────────────────────────────────────────────────────────

def ai_headline(data: dict) -> str:
    if not HAS_ANTHROPIC:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    markets = data.get("markets", {})
    tong = markets.get("Tổng", {})
    lines = []
    for name in MARKET_ORDER:
        m = markets.get(name)
        if not m:
            continue
        lines.append(
            f"- {name}: DS={_clean_num(m['doanh_so'])}, CP={_clean_num(m['chi_phi'])}, "
            f"LN={_clean_num(m['loi_nhuan'])}, CP/DS={_clean_num(m['cp_ds'])}, Tỷ lệ={_clean_num(m['ty_le'])}"
        )

    prompt = f"""Bạn là AI assistant tổng hợp cho CEO Hecatech (TikTok Shop multi-market).
Dữ liệu ngày {data.get('date','')}, các thị trường:
{chr(10).join(lines)}

Viết đúng 3 câu ngắn cho CEO (tiếng Việt có đầy đủ dấu):
1. Tổng quan doanh số và lợi nhuận toàn công ty
2. Thị trường nổi bật nhất (tốt hoặc cần chú ý nhất)
3. 1 khuyến nghị ưu tiên hoặc "Không có vấn đề khẩn cấp" nếu ổn

Tiếng Việt có dấu đầy đủ, không markdown, không bullet, không xuống dòng thừa."""

    try:
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  ⚠️ AI headline lỗi: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# BUILD MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def build_message(data: dict, headline: str, mode: str) -> str:
    now     = datetime.now().strftime("%d/%m/%Y %H:%M")
    icon    = "🌅" if mode == "morning" else "🌆"
    date_wd = _get_vn_weekday(data["date"])
    markets = data.get("markets", {})

    # Pre-render all values
    COL_HEADERS = ("Thi truong", "DS", "CP", "CP/DS", "Ty le")
    rows_data = []
    for name in MARKET_ORDER:
        m = markets.get(name)
        if not m:
            continue
        rows_data.append((
            name,
            _fmt_vnd(m["doanh_so"]),
            _fmt_vnd(m["chi_phi"]),
            _fmt_pct(m["cp_ds"]),
            _fmt_pct(m["ty_le"]),
        ))

    # Compute column widths from actual data
    w = [max(len(COL_HEADERS[i]), max(len(r[i]) for r in rows_data)) for i in range(5)]

    def row_str(r, sep=" | "):
        return f"{r[0]:<{w[0]}}{sep}{r[1]:>{w[1]}}{sep}{r[2]:>{w[2]}}{sep}{r[3]:>{w[3]}}{sep}{r[4]:>{w[4]}}"

    divider = "-+-".join("-" * c for c in w)

    # Build message
    lines = [
        f"📈 CEO BRIEFING  {icon}  {now}",
        f"Ngay: {date_wd}",
        SEP,
    ]

    if headline:
        lines.append(headline)
        lines.append(SEP)

    lines.append(row_str(COL_HEADERS))
    lines.append(divider)

    for r in rows_data:
        lines.append(row_str(r))
        if r[0] == "Tong" or r[0] == "Tổng":
            lines.append(divider)

    lines.append(SEP)
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
        print(f"  ❌ Lỗi gửi Lark: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    mode  = get_mode()
    icon  = "🌅" if mode == "morning" else "🌆"
    now   = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n🚀 CEO BRIEFING | {icon} {now}\n")

    # 1. Fetch
    print("  📊 Đang lấy dữ liệu sheet Báo cáo...", end=" ", flush=True)
    rows = fetch_baocao_sheet()
    if not rows:
        print("❌ Không có dữ liệu")
        return
    print("✅")

    # 2. Parse
    data = parse_baocao(rows)
    if not data.get("markets"):
        print("❌ Không parse được dữ liệu thị trường")
        return

    print(f"  📅 Ngày dữ liệu: {data['date']}")
    for name in MARKET_ORDER:
        m = data["markets"].get(name)
        if m:
            print(f"     {name}: DS={_fmt_vnd(m['doanh_so'])}  CP={_fmt_vnd(m['chi_phi'])}  CP/DS={_fmt_pct(m['cp_ds'])}")

    # 3. AI headline
    print("\n  🤖 AI headline...", end=" ", flush=True)
    headline = ai_headline(data)
    print("✅" if headline else "skip")

    # 4. Build + preview
    msg = build_message(data, headline, mode)
    print()
    print(msg)
    print()

    # 5. Send
    print("📤 Gửi CEO Lark...")
    send_lark(CEO_WEBHOOK, msg, label=f"CEO [{mode}]")
    print("✅ Hoàn tất!")


if __name__ == "__main__":
    main()
