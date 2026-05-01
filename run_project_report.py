#!/usr/bin/env python3
"""
Hecatech AI Agent — Per-Project Report
Đọc sheet riêng của từng dự án, parse metrics vs benchmark,
tạo cảnh báo + action từ brain, gửi vào group Lark riêng.

Usage:
    python3 run_project_report.py           # chạy tất cả dự án đã config
    python3 run_project_report.py XKMVN     # chỉ chạy 1 dự án
"""

import csv, io, json, re, sys, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brain_advisor import get_advice

SCRIPT_DIR = Path(__file__).parent
SHEET_ID   = "1VtwiBZb-wq3ZX4ss-lYvcJqfsgZIZhifotu7dszw_m4"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — Mapping project → Lark webhook
# Thêm webhook của từng dự án vào đây
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_WEBHOOKS = {
    "XKMVN": "https://open.larksuite.com/open-apis/bot/v2/hook/2e6c6bb2-ad5e-4dd0-a8bf-43effb4b0994",
    # "KTLVN": "https://open.larksuite.com/open-apis/bot/v2/hook/XXXX",
    # "MNVN":  "https://open.larksuite.com/open-apis/bot/v2/hook/XXXX",
    # "TDCVN": "https://open.larksuite.com/open-apis/bot/v2/hook/XXXX",
    # Thêm các dự án khác ở đây...
}

# ─────────────────────────────────────────────────────────────────────────────
# KEY METRICS cần theo dõi (subset từ sheet)
# ─────────────────────────────────────────────────────────────────────────────

WATCH_METRICS = [
    "Tổng GMV",
    "GMV Livestream",
    "Ads/DS (Take Rate)",
    "ROAS",
    "CTR quảng cáo",
    "CVR quảng cáo",
    "CPA",
    "Net Profit Margin",
    "Tỷ lệ hủy đơn",
    "Tỷ lệ hoàn",
    "CP/DS Live",
    "AOV Live",
    "AOV Ads",
    "CPM",
    "Tổng Số lượt hiển thị",
    "Tỷ lệ GMV từ Ads",
    "Lần hiển thị",
    "★ LỢI NHUẬN RÒNG",
]

# 5 chỉ số cảnh báo chính (chỉ cảnh báo 5 chỉ số này trong group report)
# Theo yêu cầu: Lượt hiển thị, CTR, CVR, CPM, CPA
ALERT_METRICS_5 = [
    "Tổng Số lượt hiển thị",
    "Lần hiển thị",
    "CTR quảng cáo",
    "CVR quảng cáo",
    "CPM",
    "CPA",
]

# ─────────────────────────────────────────────────────────────────────────────
# FETCH SHEET
# ─────────────────────────────────────────────────────────────────────────────

def fetch_project_sheet(project: str) -> list[list]:
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={project}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
        return list(csv.reader(io.StringIO(raw)))
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP {e.code} — sheet '{project}' không tồn tại hoặc chưa share public")
        return []
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# PARSE BENCHMARK STRING
# ─────────────────────────────────────────────────────────────────────────────

def parse_benchmark(bench_str: str) -> dict:
    """
    Từ '🔴 <4.3 tỷ  🟡 4.3–5 tỷ  ✅ ≥5 tỷ'
    Trả về {'red_label': '...', 'yellow_label': '...', 'green_label': '...'}
    """
    if not bench_str:
        return {}

    result = {}
    # Extract từng phần
    red_m    = re.search(r"🔴\s*([^🟡✅]+)", bench_str)
    yellow_m = re.search(r"🟡\s*([^🔴✅]+)", bench_str)
    green_m  = re.search(r"✅\s*([^🔴🟡]+)", bench_str)

    if red_m:    result["red"]    = red_m.group(1).strip().rstrip(" ,")
    if yellow_m: result["yellow"] = yellow_m.group(1).strip().rstrip(" ,")
    if green_m:  result["green"]  = green_m.group(1).strip().rstrip(" ,")

    return result

# ─────────────────────────────────────────────────────────────────────────────
# DETERMINE STATUS FROM VALUE vs BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

def parse_value(s: str) -> float:
    """Convert string value → float (VND, %, x)"""
    if not s:
        return None
    s = s.strip().replace(",", "")
    # Handle % → keep as ratio
    if "%" in s:
        try: return float(s.replace("%", ""))
        except: return None
    # Remove text suffixes
    s = re.sub(r"[^\d.\-]", "", s)
    try: return float(s)
    except: return None


def status_from_benchmark(value_str: str, bench_str: str, metric_name: str) -> str:
    """Trả về 'red' / 'yellow' / 'green' / 'unknown'"""
    if not bench_str or not value_str:
        return "unknown"

    val = parse_value(value_str)
    if val is None:
        return "unknown"

    bench_lower = bench_str.lower()

    # Heuristic: tìm các thresholds dạng số trong benchmark
    # Đọc màu từ pattern như "<X", ">X", "≥X", "≤X", "X–Y"
    red_nums    = [parse_value(x) for x in re.findall(r"🔴[^🟡✅]*?(\d[\d,\.]+)", bench_str)]
    yellow_nums = [parse_value(x) for x in re.findall(r"🟡[^🔴✅]*?(\d[\d,\.]+)", bench_str)]
    green_nums  = [parse_value(x) for x in re.findall(r"✅[^🔴🟡]*?(\d[\d,\.]+)", bench_str)]

    red_nums    = [x for x in red_nums if x is not None]
    yellow_nums = [x for x in yellow_nums if x is not None]
    green_nums  = [x for x in green_nums if x is not None]

    # Detect direction: "higher is better" vs "lower is better"
    lower_better = any(kw in metric_name.lower() for kw in [
        "hủy", "hoàn", "take rate", "ads/ds", "cp/ds", "cpa", "cpm", "phí", "cost",
        "voucher", "tỷ lệ voucher", "tỷ lệ giá vốn"
    ])

    # Nếu không parse được threshold → dùng màu trong chuỗi benchmark
    if not red_nums and not green_nums:
        return "unknown"

    if lower_better:
        # Red: value > threshold_red_num
        if red_nums and val > max(red_nums):
            return "red"
        elif yellow_nums:
            mid = (max(red_nums) + min(yellow_nums)) / 2 if red_nums else min(yellow_nums)
            if val > mid:
                return "yellow"
        return "green"
    else:
        # Higher is better: Red: value < threshold
        if red_nums and val < min(red_nums):
            return "red"
        elif yellow_nums:
            mid = (min(red_nums) + max(yellow_nums)) / 2 if red_nums else max(yellow_nums)
            if val < mid:
                return "yellow"
        elif green_nums and val < min(green_nums):
            return "yellow"
        return "green"

# ─────────────────────────────────────────────────────────────────────────────
# PARSE PROJECT SHEET → METRICS
# ─────────────────────────────────────────────────────────────────────────────

def _find_recent_data_cols(date_cols: dict, gmv_row: list, n_days: int = 3) -> list[tuple]:
    """
    Tìm n_days cột NGÀY GẦN NHẤT (theo thứ tự calendar).
    Luôn lấy ngày hiện tại + 2 ngày trước đó, kể cả khi chưa có data.
    Trả về list[(col_idx, date_str)] — mới nhất trước.
    """
    # Sắp xếp theo col index giảm dần (cột bên phải = ngày mới nhất)
    sorted_cols = sorted(date_cols.keys(), reverse=True)
    result = [(col_idx, date_cols[col_idx]) for col_idx in sorted_cols[:n_days]]
    return result


def parse_project_metrics(rows: list[list], project: str, n_days: int = 3) -> dict:
    """
    Parse metrics từ sheet, lấy dữ liệu n_days ngày gần nhất.
    Group report mặc định n_days=3 (chạy 3 ngày 1 lần, báo chỉ số cả 3 ngày).
    """
    if not rows:
        return {}

    date_row = rows[1] if len(rows) > 1 else []

    # Tìm tất cả cột có date header (col >= 6)
    date_cols = {}
    for i, v in enumerate(date_row):
        if i >= 6 and re.match(r"\d{2}/\d{2}/\d{4}", v.strip()):
            date_cols[i] = v.strip()

    # Tìm n_days cột mới nhất CÓ DATA THỰC TẾ (>0)
    gmv_row = rows[3] if len(rows) > 3 else []
    recent_cols = _find_recent_data_cols(date_cols, gmv_row, n_days)

    if not recent_cols:
        return {}

    latest_col = recent_cols[0][0]
    latest_date = recent_cols[0][1]

    # Build date info list: [(col_idx, date_str), ...] — mới nhất trước
    # Cũng lấy ngày trước ngày cũ nhất làm prev (để so sánh trend)
    oldest_col = recent_cols[-1][0] if recent_cols else latest_col
    prev_col_idx = oldest_col - 1
    while prev_col_idx >= 6 and prev_col_idx not in date_cols:
        prev_col_idx -= 1

    # Parse metrics — lấy values cho tất cả n_days ngày
    metrics = []
    for row in rows[2:]:
        if not row or not row[0].strip():
            continue
        name = row[0].strip()
        if re.match(r"^[A-Z]\.[\s]", name):
            continue

        is_watched = any(w.lower() in name.lower() for w in WATCH_METRICS) or name in WATCH_METRICS

        bench  = row[1].strip() if len(row) > 1 else ""
        mtd    = row[5].strip() if len(row) > 5 else ""
        latest = row[latest_col].strip() if latest_col < len(row) else ""
        prev   = row[prev_col_idx].strip() if prev_col_idx < len(row) else ""

        # Lấy values cho tất cả ngày trong khoảng báo cáo
        daily_values = {}
        for col_idx, date_str in recent_cols:
            val = row[col_idx].strip() if col_idx < len(row) else ""
            daily_values[date_str] = val

        if not bench and not mtd and not latest:
            continue

        status = "unknown"
        compare_val = latest if latest and latest not in ("0", "") else mtd
        if bench and compare_val and compare_val not in ("0", ""):
            status = status_from_benchmark(compare_val, bench, name)

        metrics.append({
            "name":         name,
            "benchmark":    bench,
            "mtd":          mtd,
            "latest":       latest,
            "prev":         prev,
            "status":       status,
            "is_watched":   is_watched,
            "daily_values": daily_values,  # {date_str: value} cho n_days ngày
        })

    # Dates list ordered mới → cũ
    report_dates = [d for _, d in recent_cols]

    return {
        "project":      project,
        "latest_date":  latest_date,
        "report_dates": report_dates,   # list ngày trong kỳ báo cáo
        "metrics":      metrics,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLASSIFY METRIC → ISSUE TYPE (for brain_advisor)
# ─────────────────────────────────────────────────────────────────────────────

METRIC_TO_ISSUE = {
    "take rate":         "take_rate_high",
    "ads/ds":            "take_rate_high",
    "cp/ds":             "take_rate_high",
    "cpa":               "high_cost_ratio",
    "cpm":               "low_ds_vs_target",
    "ctr quảng":         "creative_fatigue",
    "cvr quảng":         "creative_fatigue",
    "lần hiển thị":      "low_ds_vs_target",
    "tổng số lượt hiển": "low_ds_vs_target",
    "roas":              "high_cost_ratio",
    "net profit":        "negative_margin",
    "lợi nhuận ròng":    "negative_margin",
    "tỷ lệ hủy":         "high_cost_ratio",
    "tỷ lệ hoàn":        "high_cost_ratio",
    "gmv":               "low_ds_vs_target",
}

def classify_issue(metric_name: str) -> str:
    name_lower = metric_name.lower()
    for key, issue in METRIC_TO_ISSUE.items():
        if key in name_lower:
            return issue
    return "low_ds_vs_target"

# ─────────────────────────────────────────────────────────────────────────────
# RENDER PER-PROJECT LARK MESSAGE
# ─────────────────────────────────────────────────────────────────────────────

def _trend_arrow(values: list) -> str:
    """Trả về trend arrow dựa trên list giá trị (mới→cũ)."""
    nums = []
    for v in values:
        try:
            nums.append(float(v.replace(",", "").replace("%", "").strip()))
        except (ValueError, AttributeError):
            pass
    if len(nums) < 2:
        return ""
    if nums[0] > nums[1] * 1.05:
        return "📈"
    elif nums[0] < nums[1] * 0.95:
        return "📉"
    return "➡️"


def render_project_report(parsed: dict, mode: str) -> str:
    """
    Render báo cáo Group — hiển thị chỉ số CẢ 3 NGÀY gần nhất.
    Group report chạy 3 ngày 1 lần, mỗi lần báo đầy đủ data 3 ngày.
    """
    project  = parsed["project"]
    date     = parsed["latest_date"]
    metrics  = parsed["metrics"]
    report_dates = parsed.get("report_dates", [date])
    n_report_days = len(report_dates)

    label = "📊 BÁO CÁO 3 NGÀY (Group Report)"

    lines = []
    lines.append(f"Bot {project}: {label}")
    lines.append(f"{'='*58}")
    if n_report_days > 1:
        lines.append(f"  {project} — {report_dates[-1]} → {report_dates[0]}")
        lines.append(f"  Kỳ báo cáo: {n_report_days} ngày")
    else:
        lines.append(f"  {project} — {date}")
    lines.append(f"{'='*58}")
    lines.append("")

    # ── Tổng quan nhanh ─────────────────────────────────────────────────────
    watched = [m for m in metrics if m["is_watched"] and m["latest"]]
    n_red   = sum(1 for m in watched if m["status"] == "red")
    n_yel   = sum(1 for m in watched if m["status"] == "yellow")
    n_grn   = sum(1 for m in watched if m["status"] == "green")
    overall = "🔴" if n_red >= 2 else "🟡" if n_red >= 1 or n_yel >= 3 else "🟢"

    # Find key metrics
    gmv_m    = next((m for m in metrics if m["name"] == "Tổng GMV"), None)
    margin_m = next((m for m in metrics if "Net Profit" in m["name"]), None)
    ln_m     = next((m for m in metrics if "LỢI NHUẬN RÒNG" in m["name"]), None)

    lines.append("📊 TỔNG QUAN")
    if gmv_m:
        e = "✅" if gmv_m["status"] == "green" else "🟡" if gmv_m["status"] == "yellow" else "🔴"
        lines.append(f"  Tổng GMV ngày: {gmv_m['latest']} {e}")
        lines.append(f"  GMV MTD:       {gmv_m['mtd']}")
    if margin_m:
        e = "✅" if margin_m["status"] == "green" else "🟡" if margin_m["status"] == "yellow" else "🔴"
        lines.append(f"  Net Margin:    {margin_m['latest']} {e}  (MTD: {margin_m['mtd']})")
    if ln_m:
        lines.append(f"  LN ròng ngày:  {ln_m['latest']}  (MTD: {ln_m['mtd']})")
    lines.append(f"  Tổng trạng thái: {overall}  🔴 {n_red}  🟡 {n_yel}  ✅ {n_grn}")
    lines.append("")

    # ── Cảnh báo CHỈ 5 chỉ số chính: Impressions, CTR, CVR, CPM, CPA ────────
    def _is_alert_metric(name: str) -> bool:
        name_lower = name.lower()
        return any(k.lower() in name_lower for k in ALERT_METRICS_5)

    alerts = [m for m in watched if m["status"] in ("red", "yellow") and _is_alert_metric(m["name"])]

    # Dedup: chỉ giữ 1 cảnh báo cho mỗi tên metric (lấy cái đỏ ưu tiên)
    seen_names = {}
    for m in alerts:
        key = m["name"]
        if key not in seen_names or m["status"] == "red":
            seen_names[key] = m
    alerts = list(seen_names.values())
    # Sắp xếp: đỏ trước, vàng sau
    alerts.sort(key=lambda x: (0 if x["status"] == "red" else 1))

    if alerts:
        lines.append("─" * 58)
        lines.append(f"⚠️  CẢNH BÁO ({len(alerts)} chỉ số cần xử lý)")
        lines.append("")
        for i, m in enumerate(alerts, 1):
            e = "🔴" if m["status"] == "red" else "🟡"
            bench_str = m["benchmark"][:60] if m["benchmark"] else "—"

            lines.append(f"  {i}. {e} {m['name']}")

            # Hiển thị giá trị 3 ngày trong cảnh báo
            dv = m.get("daily_values", {})
            if n_report_days > 1 and dv:
                day_vals = []
                for d in report_dates:
                    v = dv.get(d, "—")
                    short_d = "/".join(d.split("/")[:2])
                    if v and v not in ("0", ""):
                        day_vals.append(f"{short_d}: {v}")
                if day_vals:
                    lines.append(f"     📅 {' → '.join(day_vals)}")
            else:
                lines.append(f"     Ngày {parsed['latest_date']}: {m['latest']}")

            lines.append(f"     MTD: {m['mtd']}  |  Benchmark: {bench_str}")

            # Advice từ brain — truyền đầy đủ context số thực
            issue  = classify_issue(m["name"])
            advice = get_advice(issue, {
                "metric_name": m["name"],
                "latest":      m["latest"],
                "mtd":         m["mtd"],
                "status":      m["status"],
                "cp_ds":       0,
            })
            lines.append(f"     ↳ Nguyên nhân: {advice['root_cause']}")
            lines.append(f"     ↳ Gợi ý hành động:")
            for j, action in enumerate(advice["actions"][:3], 1):
                lines.append(f"        {j}. {action}")
            lines.append(f"     ↳ Owner: {advice['owner']}  |  SLA: {advice['sla']}")
            if advice.get("playbook_ref") and advice["playbook_ref"] != "—":
                lines.append(f"     📖 Theo: {advice['playbook_ref']}")
            lines.append("")
    else:
        lines.append("✅ Tất cả chỉ số đang xanh — không có cảnh báo")
        lines.append("")

    # ── Điểm sáng (metrics xanh nổi bật) ────────────────────────────────────
    bright = [m for m in watched if m["status"] == "green" and m["latest"]][:4]
    if bright:
        lines.append(f"─" * 58)
        lines.append("✅ ĐIỂM SÁNG")
        for m in bright:
            lines.append(f"  - {m['name']}: {m['latest']} (MTD: {m['mtd']})")
        lines.append("")

    # ── Top việc ─────────────────────────────────────────────────────────────
    if alerts:
        lines.append("─" * 58)
        lines.append("📋 TOP VIỆC CẦN XỬ LÝ")
        top3 = alerts[:3]
        for i, m in enumerate(top3, 1):
            issue  = classify_issue(m["name"])
            advice = get_advice(issue, {"cp_ds": 0})
            action = advice["actions"][0] if advice["actions"] else "Xem playbook tương ứng"
            lines.append(f"  {i}. {action} — {advice['owner']}")
        lines.append("")

    date_range = f"{report_dates[-1]} → {report_dates[0]}" if n_report_days > 1 else date
    lines.append(f"🧠 [Brain: 9 playbooks | {project} | {date_range} | Chu kỳ: 3 ngày/lần]")
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

def get_mode() -> str:
    for arg in sys.argv[1:]:
        if arg in ("morning", "afternoon"):
            return arg
    return "morning" if datetime.now().hour < 13 else "afternoon"


def main():
    mode = get_mode()

    # Lọc dự án từ args (bỏ qua "morning"/"afternoon")
    target_projects = [a for a in sys.argv[1:] if a not in ("morning", "afternoon")]
    if not target_projects:
        target_projects = list(PROJECT_WEBHOOKS.keys())

    icon  = "🌅" if mode == "morning" else "🌆"
    label = "Buổi sáng (hôm qua)" if mode == "morning" else "Buổi chiều (hôm nay)"

    print(f"\n🚀 HECATECH AI AGENT — Per-Project Report | {icon} {label}")
    print(f"   Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"   Dự án: {', '.join(target_projects)}")
    print()

    for project in target_projects:
        webhook = PROJECT_WEBHOOKS.get(project)
        if not webhook:
            print(f"⚠️  {project}: chưa có webhook — bỏ qua")
            continue

        print(f"{'─'*58}")
        print(f"📊 [{project}] Đang đọc sheet...")

        rows = fetch_project_sheet(project)
        if not rows:
            print(f"   ❌ Không đọc được sheet {project}")
            continue

        print(f"   ✅ {len(rows)} rows, {len(rows[0])} cols")

        parsed = parse_project_metrics(rows, project)
        if not parsed:
            print(f"   ❌ Parse thất bại")
            continue

        n_metrics = len(parsed["metrics"])
        n_alerts  = sum(1 for m in parsed["metrics"] if m["status"] in ("red", "yellow"))
        print(f"   📅 Ngày mới nhất: {parsed['latest_date']}")
        print(f"   📈 {n_metrics} metrics, {n_alerts} cảnh báo")

        msg = render_project_report(parsed, mode)
        print()
        print(msg)
        print()

        print(f"📤 Gửi lên Lark group [{project}]...")
        send_lark(webhook, msg, label=f"{project} [{mode}]")
        print()

    print("✅ Hoàn tất tất cả dự án!")


if __name__ == "__main__":
    main()
