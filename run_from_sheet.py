#!/usr/bin/env python3
"""
Hecatech AI Agent — Single Project Dashboard
Sheet format: Hàng = Chỉ số, Cột = Ngày (gid=301205895)

Usage:
    python3 run_from_sheet.py morning      # 10:00 — Báo cáo hôm qua
    python3 run_from_sheet.py afternoon    # 16:00 — Real-time hôm nay
    python3 run_from_sheet.py              # Tự detect theo giờ
"""

import csv, io, json, sys, urllib.request, urllib.error
from datetime import datetime, timedelta

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SHEET_ID     = "1VtwiBZb-wq3ZX4ss-lYvcJqfsgZIZhifotu7dszw_m4"
SHEET_GID    = "301205895"
PROJECT_NAME = "XKMVN"   # ← đổi tên project nếu cần
LARK_WEBHOOK = "https://open.larksuite.com/open-apis/bot/v2/hook/ad36383c-06b9-48ee-ad3b-08dd771fa9fa"

SHEET_CSV_URL = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
    f"/export?format=csv&gid={SHEET_GID}"
)

MTD_COL        = 5   # index cột T04.2026 (lũy kế tháng)
DATE_START_COL = 6   # index cột 01/04/2026

# ─────────────────────────────────────────────────────────────────────────────
# MODE
# ─────────────────────────────────────────────────────────────────────────────

def get_mode() -> str:
    if len(sys.argv) > 1 and sys.argv[1] in ("morning", "afternoon"):
        return sys.argv[1]
    return "morning" if datetime.now().hour < 13 else "afternoon"

def get_target_date(mode: str) -> datetime:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return today - timedelta(days=1) if mode == "morning" else today

# ─────────────────────────────────────────────────────────────────────────────
# FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_sheet() -> list[list]:
    print(f"📥 Đang tải Google Sheet (gid={SHEET_GID})...")
    req = urllib.request.Request(SHEET_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        msg = "Sheet chưa share public → Share → Anyone with link → Viewer" if e.code in (401, 403) else f"HTTP {e.code}: {e.reason}"
        print(f"❌ {msg}"); sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi kết nối: {e}"); sys.exit(1)
    rows = list(csv.reader(io.StringIO(raw)))
    if not rows:
        print("❌ Sheet trống"); sys.exit(1)
    return rows

# ─────────────────────────────────────────────────────────────────────────────
# PARSE
# ─────────────────────────────────────────────────────────────────────────────

def parse_num(s: str) -> float:
    try:
        return float(s.replace(",", "").replace("%", "").replace("x", "").strip())
    except (ValueError, AttributeError):
        return 0.0

def find_date_col(rows: list[list], target: datetime) -> int | None:
    """Tìm index cột cho ngày target trong row[1] (row chứa dates)."""
    date_row = rows[1] if len(rows) > 1 else []
    target_str = target.strftime("%d/%m/%Y")
    for i, cell in enumerate(date_row):
        if cell.strip() == target_str:
            return i
    return None

def find_last_data_col(rows: list[list]) -> int:
    """Fallback: tìm cột cuối cùng có GMV > 0."""
    for row in rows[2:]:
        if row and row[0].strip() == "Tổng GMV":
            for i in range(len(row) - 1, DATE_START_COL - 1, -1):
                v = row[i].strip().replace(",", "")
                if v and v != "0":
                    return i
            break
    return DATE_START_COL

def parse_sheet(rows: list[list], target_date: datetime) -> dict:
    """
    Parse sheet format mới:
      rows[0] = header   (Chỉ số, Benchmark, T01, T02, T03, T04, TRUE...)
      rows[1] = dates    (empty×6, 01/04/2026, 02/04/2026, ...)
      rows[2+]= data     (section + metric rows + status section)

    Returns dict với metrics{} và statuses{} cho ngày target.
    """
    day_col = find_date_col(rows, target_date)
    if day_col is None:
        print(f"⚠️  Không tìm thấy cột {target_date.strftime('%d/%m/%Y')} → dùng cột cuối")
        day_col = find_last_data_col(rows)
    mtd_col = MTD_COL

    print(f"   📅 Ngày: {target_date.strftime('%d/%m/%Y')} | col={day_col} | MTD col={mtd_col}")

    metrics   = {}   # metric_key → {day, mtd, benchmark}
    statuses  = {}   # metric_key → "Đỏ"/"Vàng"/"Xanh"
    in_status = False
    dup_count = {}   # đếm duplicate metric names

    STATUS_VALS = {"Đỏ", "Vàng", "Xanh", "#DIV/0!"}

    def gc(row, idx):
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    for row in rows[2:]:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()

        # Bỏ qua section headers (A., B., C.,...)
        if len(name) >= 2 and name[1] == "." and name[0].isalpha():
            continue

        day_val = gc(row, day_col)

        # Phát hiện khu vực status (giá trị là Đỏ/Vàng/Xanh)
        if not in_status and day_val in STATUS_VALS:
            in_status = True

        if in_status:
            statuses[name] = day_val
            continue

        # Handle duplicate names với suffix
        key = name
        dup_count[name] = dup_count.get(name, 0) + 1
        if dup_count[name] > 1:
            key = f"{name} ({dup_count[name]})"

        metrics[key] = {
            "day": day_val,
            "mtd": gc(row, mtd_col),
            "benchmark": gc(row, 1),
        }

    return {
        "date":     target_date.strftime("%d/%m/%Y"),
        "project":  PROJECT_NAME,
        "metrics":  metrics,
        "statuses": statuses,
    }

# ─────────────────────────────────────────────────────────────────────────────
# FORMAT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def fmt(v: float) -> str:
    if v >= 1_000_000_000: return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:     return f"{v/1_000_000:.1f}M"
    if v >= 1_000:         return f"{v/1_000:.0f}K"
    return f"{v:.0f}"

def sem(status_str: str) -> str:
    """Status string → emoji."""
    if "Đỏ"   in status_str: return "🔴"
    if "Vàng" in status_str: return "🟡"
    if "Xanh" in status_str: return "✅"
    return "⚪"

def mday(data: dict, key: str) -> str:
    return data["metrics"].get(key, {}).get("day", "—")

def mmtd(data: dict, key: str) -> str:
    return data["metrics"].get(key, {}).get("mtd", "—")

def nday(data: dict, key: str) -> float:
    return parse_num(mday(data, key))

def nmtd(data: dict, key: str) -> float:
    return parse_num(mmtd(data, key))

def se(data: dict, key: str) -> str:
    return sem(data["statuses"].get(key, ""))

# ─────────────────────────────────────────────────────────────────────────────
# RENDER — DAILY REPORT
# ─────────────────────────────────────────────────────────────────────────────

def render_daily(data: dict, mode: str) -> str:
    prj  = data["project"]
    date = data["date"]

    if mode == "morning":
        label = "📅 BÁO CÁO NGÀY HÔM QUA (hoàn chỉnh)"
        note  = f"Dữ liệu chốt cuối ngày {date} — 10:00 AM"
    else:
        label = "⏱️  BÁO CÁO NGÀY HIỆN TẠI (real-time)"
        note  = f"Dữ liệu cập nhật real-time — 16:00 PM"

    lines = [label, note, "", "=" * 62, f"  {prj} — {date}", "=" * 62, ""]

    # ── A. Tổng quan ────────────────────────────────────────────
    gmv    = nday(data, "Tổng GMV")
    ln     = nday(data, "★ LỢI NHUẬN RÒNG")
    margin = mday(data, "Net Profit Margin")
    ads    = nday(data, "Tổng chi phí QC")
    roas   = mday(data, "ROAS")
    tr     = mday(data, "Ads/DS (Take Rate)")

    lines.append("📊 TỔNG QUAN NGÀY")
    lines.append(f"  GMV:            {fmt(gmv):<12s} {se(data, 'Tổng GMV')}")
    lines.append(f"  Lợi nhuận:     {fmt(ln):<12s} {se(data, '★ LỢI NHUẬN RÒNG')}")
    lines.append(f"  Net Margin:    {margin:<12s} {se(data, 'Net Profit Margin')}")
    lines.append(f"  Chi phí QC:    {fmt(ads):<12s}")
    lines.append(f"  ROAS:          {roas:<12s} {se(data, 'ROAS')}")
    lines.append(f"  Take Rate:     {tr:<12s} {se(data, 'Ads/DS (Take Rate)')}")
    lines.append("")

    # ── B. Ads Performance ──────────────────────────────────────
    impressions = mday(data, "Tổng Số lượt hiển thị")
    clicks = mday(data, "Tông số lượt nhấp")
    cpa  = mday(data, "CPA")
    ctr  = mday(data, "CTR quảng cáo")
    cvr  = mday(data, "CVR quảng cáo")
    orders = mday(data, "Tổng đơn hàng Ads")
    aov  = mday(data, "AOV Ads")

    lines.append("─" * 62)
    lines.append("🎯 ADS PERFORMANCE")
    lines.append(f"  Impressions:   {impressions:<12s}")
    lines.append(f"  Clicks:        {clicks:<12s}")
    lines.append(f"  CTR:            {ctr:<12s} {se(data, 'CTR quảng cáo')}")
    lines.append(f"  CVR:            {cvr:<12s} {se(data, 'CVR quảng cáo')}")
    lines.append(f"  CPA:            {cpa:<12s} {se(data, 'CPA')}")
    lines.append(f"  Tổng đơn Ads:  {orders:<12s} {se(data, 'Tổng đơn hàng Ads')}")
    lines.append(f"  AOV Ads:       {aov:<12s} {se(data, 'AOV Ads')}")
    lines.append("")

    # ── C. Livestream ───────────────────────────────────────────
    gmv_live   = mday(data, "GMV Livestream (2)")
    live_ratio = mday(data, "Tỷ trọng Live/Tổng GMV")
    live_hours = mday(data, "Số giờ live")
    live_orders= mday(data, "Số đơn hàng trong phiên live")

    lines.append("─" * 62)
    lines.append("📡 LIVESTREAM")
    lines.append(f"  GMV Live:      {gmv_live:<12s} {se(data, 'GMV Livestream')}")
    lines.append(f"  Tỷ trọng:      {live_ratio:<12s} {se(data, 'Tỷ trọng Live/Tổng GMV')}")
    lines.append(f"  Số giờ live:   {live_hours}")
    lines.append(f"  Đơn live:      {live_orders:<12s}")
    lines.append("")

    # ── D. Vận hành ─────────────────────────────────────────────
    cancel = mday(data, "Tỷ lệ hủy đơn")
    ret    = mday(data, "Tỷ lệ hoàn")

    lines.append("─" * 62)
    lines.append("🚚 VẬN HÀNH")
    lines.append(f"  Tỷ lệ hủy:     {cancel:<12s} {se(data, 'Tỷ lệ hủy đơn')}")
    lines.append(f"  Tỷ lệ hoàn:    {ret:<12s}  {se(data, 'Tỷ lệ hoàn')}")
    lines.append("")

    # ── Cảnh báo đỏ/vàng ────────────────────────────────────────
    reds    = [k for k, v in data["statuses"].items() if v == "Đỏ"]
    yellows = [k for k, v in data["statuses"].items() if v == "Vàng"]

    if reds or yellows:
        lines.append("─" * 62)
        lines.append(f"⚠️  CẢNH BÁO")
        if reds:
            lines.append(f"  🔴 Đỏ ({len(reds)}): {', '.join(reds[:5])}" + (" ..." if len(reds) > 5 else ""))
        if yellows:
            lines.append(f"  🟡 Vàng ({len(yellows)}): {', '.join(yellows[:5])}" + (" ..." if len(yellows) > 5 else ""))
        lines.append("")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# RENDER — MTD REPORT
# ─────────────────────────────────────────────────────────────────────────────

def render_mtd(data: dict, mode: str) -> str:
    prj  = data["project"]
    date = data["date"]

    note = "📅 Lũy kế tháng — 10:00 AM" if mode == "morning" else "⏱️  Lũy kế tháng — 16:00 PM"

    lines = [note, "", "=" * 62, f"  {prj} — MTD đến {date}", "=" * 62, ""]

    gmv_mtd  = nmtd(data, "Tổng GMV")
    ln_mtd   = nmtd(data, "★ LỢI NHUẬN RÒNG")
    ads_mtd  = nmtd(data, "Tổng chi phí QC")
    ds_mtd   = nmtd(data, "Tổng doanh số")
    margin   = mmtd(data, "Net Profit Margin")

    lines.append("📈 MTD TOÀN HỆ THỐNG")
    lines.append(f"  GMV:           {fmt(gmv_mtd)}")
    lines.append(f"  Doanh số:      {fmt(ds_mtd)}")
    lines.append(f"  Lợi nhuận:    {fmt(ln_mtd)}")
    lines.append(f"  Net Margin:   {margin}")
    lines.append(f"  Chi phí QC:   {fmt(ads_mtd)}")
    lines.append("")

    # GMV breakdown
    gmv_live_mtd  = nmtd(data, "GMV Livestream (2)")
    gmv_video_mtd = nmtd(data, "GMV Video")
    gmv_card_mtd  = nmtd(data, "DS thẻ SP")

    if gmv_mtd > 0:
        lines.append("─" * 62)
        lines.append("📊 CƠ CẤU GMV MTD")
        def pct(v): return f"{v/gmv_mtd*100:.1f}%" if gmv_mtd else "—"
        lines.append(f"  GMV Ads:      {fmt(nmtd(data, 'GMV Ads'))} ({pct(nmtd(data, 'GMV Ads'))})")
        lines.append(f"  GMV Video:   {fmt(gmv_video_mtd)} ({pct(gmv_video_mtd)})")
        lines.append(f"  GMV Live:    {fmt(gmv_live_mtd)} ({pct(gmv_live_mtd)})")
        lines.append(f"  GMV Thẻ SP:  {fmt(gmv_card_mtd)} ({pct(gmv_card_mtd)})")
        lines.append("")

    lines.append("─" * 62)
    lines.append("🎯 ADS MTD")
    lines.append(f"  Impressions:  {mmtd(data, 'Tổng Số lượt hiển thị')}")
    lines.append(f"  CTR:          {mmtd(data, 'CTR quảng cáo')}")
    lines.append(f"  CVR:          {mmtd(data, 'CVR quảng cáo')}")
    lines.append(f"  ROAS:         {mmtd(data, 'ROAS')}")
    lines.append(f"  Take Rate:    {mmtd(data, 'Ads/DS (Take Rate)')}")
    lines.append(f"  CPA:          {mmtd(data, 'CPA')}")
    lines.append(f"  Hủy đơn:      {mmtd(data, 'Tỷ lệ hủy đơn')}")
    lines.append(f"  Tỷ lệ hoàn:   {mmtd(data, 'Tỷ lệ hoàn')}")
    lines.append("")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# LARK SENDER
# ─────────────────────────────────────────────────────────────────────────────

def send_lark(text: str, label: str = "") -> bool:
    payload = {"msg_type": "text", "content": {"text": text}}
    data    = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req     = urllib.request.Request(
        LARK_WEBHOOK, data=data,
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
# RENDER — FUNNEL KPI CARD (5 chỉ số chính)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_green_benchmark(bench_raw: str) -> str:
    """Trích ngưỡng ✅ từ benchmark text (có thể chứa newlines)."""
    import re
    if not bench_raw or not bench_raw.strip():
        return "—"
    # Thay newline thành space
    flat = bench_raw.replace("\n", " ").replace("\r", " ").strip()
    # Tìm phần sau ✅
    m = re.search(r"✅\s*(.+?)(?:\s*🔴|🟡|⛔|$)", flat)
    if m:
        return m.group(1).strip()
    # Nếu không tìm ✅, lấy dòng cuối (thường là ngưỡng tốt)
    parts = [p.strip() for p in flat.split("  ") if p.strip()]
    return parts[-1] if parts else flat[:20]


def render_funnel_kpi(data: dict, mode: str) -> str:
    """Render bảng 5 chỉ số phễu chính: Impressions, CTR, CVR, CPM, CPA."""
    prj  = data["project"]
    date = data["date"]

    if mode == "morning":
        label = "📊 PHỄU ADS — HÔM QUA"
    else:
        label = "📊 PHỄU ADS — HÔM NAY (real-time)"

    # 5 chỉ số chính với key mapping
    kpi_map = [
        ("IMPRESSIONS", "Tổng Số lượt hiển thị", None),
        ("CTR",         "CTR quảng cáo",          "CTR quảng cáo"),
        ("CVR",         "CVR quảng cáo",          "CVR quảng cáo"),
        ("CPM",         "CPM",                    "CPM"),
        ("CPA",         "CPA",                    "CPA"),
    ]

    lines = []
    lines.append(f"{label}")
    lines.append(f"{prj} — {date}")
    lines.append("")
    lines.append(f"  {'Chỉ số':<12s} | {'Ngày':>12s} | {'MTD':>12s} | {'Ngưỡng ✅':>12s}")
    lines.append(f"  {'-'*12}-+-{'-'*12}-+-{'-'*12}-+-{'-'*12}")

    for display_name, metric_key, status_key in kpi_map:
        day_val = mday(data, metric_key)
        mtd_val = mmtd(data, metric_key)
        bench   = data["metrics"].get(metric_key, {}).get("benchmark", "—")

        # Format: nếu trống thì hiện —
        day_str = day_val if day_val and day_val != "0" else "—"
        mtd_str = mtd_val if mtd_val and mtd_val != "0" else "—"
        bench_str = _extract_green_benchmark(bench)

        # Status emoji
        status_emoji = se(data, status_key) if status_key else ""

        lines.append(
            f"  {status_emoji} {display_name:<10s} | {day_str:>12s} | {mtd_str:>12s} | {bench_str:>12s}"
        )

    lines.append("")
    lines.append(f"🧠 Nguồn: TTS Ads Manager → Google Sheet")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    mode        = get_mode()
    target_date = get_target_date(mode)
    icon        = "🌅" if mode == "morning" else "🌆"
    label_vn    = "Buổi sáng — hôm qua" if mode == "morning" else "Buổi chiều — hôm nay"

    print(f"\n🚀 HECATECH AI AGENT [{PROJECT_NAME}] — {icon} {label_vn}")
    print(f"   Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={SHEET_GID}")
    print()

    rows = fetch_sheet()
    data = parse_sheet(rows, target_date)

    print(f"   ✅ Parse xong: {len(data['metrics'])} chỉ số | {len(data['statuses'])} trạng thái")
    print()

    daily_msg = render_daily(data, mode)
    mtd_msg   = render_mtd(data, mode)
    kpi_msg   = render_funnel_kpi(data, mode)

    # Preview terminal
    print(daily_msg)
    print(mtd_msg)
    print(kpi_msg)

    # Gửi Lark
    print("─" * 62)
    print("📤 Đang gửi lên Lark...")
    send_lark(daily_msg, label=f"Daily [{mode}]")
    send_lark(mtd_msg,   label=f"MTD [{mode}]")
    send_lark(kpi_msg,   label=f"Funnel KPI [{mode}]")

    print()
    print("✅ Hoàn tất! Kiểm tra Lark group.")


if __name__ == "__main__":
    main()
