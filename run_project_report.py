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
from brain_advisor import get_advice, detect_issues, load_brain_context
import os

try:
    from anthropic import Anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

SCRIPT_DIR = Path(__file__).parent
SHEET_ID   = "1FZj7u5y3TzRogBNkH_KxQflHOv2Dmfrq8p1Nski0Jb4"

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — Mapping project → Lark webhook
# Thêm webhook của từng dự án vào đây
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_WEBHOOKS = {
    "XKMVN": "https://open.larksuite.com/open-apis/bot/v2/hook/2e6c6bb2-ad5e-4dd0-a8bf-43effb4b0994",
    "KTLVN": "https://open.larksuite.com/open-apis/bot/v2/hook/12e67bd6-bb59-4ba1-97b1-5c692b66357c",
    "MNVN": "https://open.larksuite.com/open-apis/bot/v2/hook/0c5022ee-375c-413e-b400-4b3a02d2d31e",
    "TDCVN": "https://open.larksuite.com/open-apis/bot/v2/hook/c27c9609-35f9-406f-b441-351fc1eb6e7f",
    "KTMVN": "https://open.larksuite.com/open-apis/bot/v2/hook/c0d15040-a328-4500-9358-97f5a634ac72",
    "SRMR": "https://open.larksuite.com/open-apis/bot/v2/hook/877a9dff-f9fd-4b12-8354-d0f7f833250d",
    "KTMR": "https://open.larksuite.com/open-apis/bot/v2/hook/9e781e8d-9a91-45d7-8c81-09ff41841178",
    "KTLTL": "https://open.larksuite.com/open-apis/bot/v2/hook/02743e78-30b3-4ecf-9f94-f9576513676f",
    "XKMMY": "https://open.larksuite.com/open-apis/bot/v2/hook/da40deff-b9e3-44bb-89e3-f4c5bc9a7aad",
    "XKMTL": "https://open.larksuite.com/open-apis/bot/v2/hook/58f0258e-c09b-4137-9ef5-34e4e9d865d3",
    "XKMPH": "https://open.larksuite.com/open-apis/bot/v2/hook/2505e7e8-0eb8-4181-bb59-692344df1442",
    "XKMUS": "https://open.larksuite.com/open-apis/bot/v2/hook/42e47aa1-1a98-4ff2-b40a-596c3fcd01a9",
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


# ─────────────────────────────────────────────────────────────────────────────
# FORMAT VND / NUMBER
# ─────────────────────────────────────────────────────────────────────────────

def fmt(v_str: str) -> str:
    """Format string value (VND, %, x) -> human readable (tr, M, K)"""
    if not v_str or v_str in ("0", "—", ""):
        return v_str
    
    val = parse_value(v_str)
    if val is None:
        return v_str
    
    # Nếu là %, giữ nguyên
    if "%" in v_str:
        return v_str

    if val >= 1_000_000_000:
        return f"{val/1_000_000_000:.1f}B"
    if val >= 1_000_000:
        return f"{val/1_000_000:.1f}M"
    if val >= 1_000:
        # Nếu là tiền đồng (CPA/CPM thường > 1000)
        return f"{val/1_000:.1f}K"
    
    return v_str

# ─────────────────────────────────────────────────────────────────────────────
# DETERMINE STATUS FROM VALUE vs BENCHMARK
# ─────────────────────────────────────────────────────────────────────────────

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
    Tìm n_days cột ngày hoàn chỉnh GẦN NHẤT — luôn loại trừ hôm nay.
    VD: chạy ngày 06/05 → lấy 05/05, 04/05, 03/05.
    """
    today = datetime.now().date()
    valid_cols = []
    for col_idx, date_str in date_cols.items():
        try:
            year = datetime.now().year
            d = datetime.strptime(f"{date_str[:5]}/{year}", "%d/%m/%Y").date()
            if d > today and (d - today).days > 180:
                d = datetime.strptime(f"{date_str[:5]}/{year-1}", "%d/%m/%Y").date()
            if d < today:  # chỉ lấy ngày trước hôm nay (ngày đã hoàn chỉnh)
                valid_cols.append((col_idx, date_str, d))
        except Exception:
            continue
    valid_cols.sort(key=lambda x: x[2], reverse=True)
    return [(col_idx, date_str) for col_idx, date_str, _ in valid_cols[:n_days]]


def parse_project_metrics(rows: list[list], project: str, n_days: int = 3) -> dict:
    """
    Parse metrics từ sheet, lấy dữ liệu n_days ngày gần nhất.
    Group report mặc định n_days=3 (chạy 3 ngày 1 lần, báo chỉ số cả 3 ngày).
    """
    if not rows:
        return {}

    date_row = rows[1] if len(rows) > 1 else []

    # Tìm tất cả cột có date header (bỏ qua col 0 = tên metric, col 1 = benchmark)
    date_cols = {}
    for i, v in enumerate(date_row):
        if i >= 2 and re.match(r"\d{2}/\d{2}/\d{4}", v.strip()):
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

    # Tìm Phase và Target (thường ở hàng 0 hoặc 1)
    phase = ""
    target = ""
    for r in rows[:3]:
        for c in r:
            if "Phase" in c: phase = c.strip()
            if "Target" in c: target = c.strip()

    return {
        "project":      project,
        "latest_date":  latest_date,
        "report_dates": report_dates,   # list ngày trong kỳ báo cáo
        "metrics":      metrics,
        "phase":        phase,
        "target":       target,
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

def _get_short_name(name: str) -> str:
    name_map = {
        "Tổng GMV": "GMV",
        "Lần hiển thị": "Lượt HT",
        "Tổng Số lượt hiển thị": "Lượt HT",
        "CTR quảng cáo": "CTR",
        "CVR quảng cáo": "CVR",
        "CPM": "CPM",
        "CPA": "CPA",
    }
    for k, v in name_map.items():
        if k.lower() in name.lower():
            return v
    return name

def _get_vn_weekday(date_str: str) -> str:
    """VD: 28/04/2024 -> T3"""
    try:
        dt = datetime.strptime(date_str, "%d/%m/%Y")
        days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        return days[dt.weekday()]
    except:
        return ""

def ai_analyze_project(parsed: dict) -> dict | None:
    """
    Gọi Claude API phân tích metrics + brain → trả về:
      summary, issues (list), warning, actions (list), owner
    Fallback None nếu không có API key hoặc lỗi.
    """
    if not HAS_ANTHROPIC:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    project      = parsed["project"]
    metrics      = parsed["metrics"]
    report_dates = parsed.get("report_dates", [])
    phase        = parsed.get("phase", "")
    target       = parsed.get("target", "")

    # Format date labels
    date_labels = []
    for d in reversed(report_dates):
        wd = _get_vn_weekday(d)
        date_labels.append(f"{wd} {d[:5]}")
    header_dates = ", ".join(date_labels)

    # Build metrics text — chỉ các chỉ số có data
    metrics_lines = []
    for m in metrics:
        vals = []
        for d in reversed(report_dates):
            v = m["daily_values"].get(d, "—")
            vals.append(v if v else "—")
        val_str = " → ".join(vals) if len(vals) > 1 else (vals[0] if vals else "—")
        if val_str in ("—", "— → —", "— → — → —"):
            continue
        bench  = m.get("benchmark", "—")
        status = m.get("status", "unknown")
        metrics_lines.append(
            f"- {m['name']}: {val_str} | Benchmark: {bench} | Status: {status}"
        )
    metrics_text = "\n".join(metrics_lines[:50])

    # Load brain context
    brain_content = load_brain_context(project, max_chars=5000)

    # Strip emojis from metrics_text to avoid JSON corruption
    emoji_pattern = re.compile(
        "["
        u"\U0001F300-\U0001F9FF"
        u"\U00002702-\U000027B0"
        u"\U0000FE00-\U0000FE0F"
        u"\u2600-\u26FF"
        "]+", flags=re.UNICODE
    )
    metrics_text_clean = emoji_pattern.sub("", metrics_text)

    def _build_prompt(metrics_txt: str, brain_txt: str) -> str:
        brain_section = f"""TÀI LIỆU IF-THEN (BỘ NÃO):
{brain_txt}

QUAN TRỌNG: Mọi đề xuất hành động PHẢI lấy từ tài liệu IF-THEN ở trên. Không được tự sáng tạo hành động từ kiến thức chung. Nếu không tìm thấy hướng dẫn trong tài liệu trên, ghi rõ "Chưa có playbook cho tình huống này".""" if brain_txt.strip() else "TÀI LIỆU IF-THEN: Chưa có — không đề xuất hành động cụ thể."

        return f"""Bạn là AI analyst của Hecatech — TikTok Shop performance marketing.
Nhiệm vụ: phân tích số liệu và tra cứu TÀI LIỆU IF-THEN bên dưới để đưa ra hành động CỤ THỂ.

DỰ ÁN: {project} | {header_dates}

SỐ LIỆU THỰC TẾ:
{metrics_txt}

{brain_section}

---
Trả về JSON thuần (không markdown, không code block, không xuống dòng trong string):
{{"summary": "1-2 câu tóm tắt tình trạng — có số liệu cụ thể, nêu chỉ số đỏ/vàng nổi bật nhất",
"issues": ["Vấn đề 1: tên chỉ số + giá trị + xu hướng + nguyên nhân từ IF-THEN", "Vấn đề 2", "Vấn đề 3"],
"warning": "1 câu cảnh báo cụ thể — rủi ro nếu không xử lý. Để trống nếu xanh hết.",
"actions": ["Hành động cụ thể từ IF-THEN — deadline — owner", "Hành động 2 — owner", "Hành động 3 — owner"],
"owner": "tên owner chính từ IF-THEN"}}

NGUYÊN TẮC BẮT BUỘC:
- TOÀN BỘ output PHẢI tiếng Việt CÓ DẤU đầy đủ. TUYỆT ĐỐI không viết: "tat", "hang", "tren", "duoi", "tuan", "ngay", "bat"
- KHÔNG dùng emoji trong JSON string
- issues tối đa 3, actions tối đa 3. Nếu xanh hết: issues=[], warning="", actions=[]
- Hành động PHẢI lấy từ tài liệu IF-THEN, ghi rõ owner và deadline theo tài liệu
- Không trích dẫn tên file"""

    def _parse_ai_response(text: str) -> dict | None:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)

    client = Anthropic(api_key=api_key)

    # Attempt 1: full brain context
    try:
        prompt1 = _build_prompt(metrics_text_clean, brain_content)
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1800,
            messages=[{"role": "user", "content": prompt1}],
        )
        return _parse_ai_response(resp.content[0].text)
    except Exception as e1:
        print(f"   ⚠️ AI attempt 1 loi: {e1}")

    # Attempt 2: shorter brain context + fewer metrics
    try:
        short_brain = brain_content[:2000] if brain_content else ""
        short_metrics = "\n".join(metrics_text_clean.splitlines()[:20])
        prompt2 = _build_prompt(short_metrics, short_brain)
        resp2 = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt2}],
        )
        return _parse_ai_response(resp2.content[0].text)
    except Exception as e2:
        print(f"   ⚠️ AI attempt 2 loi: {e2}")
        return None


def render_project_report(parsed: dict, mode: str) -> str:
    project      = parsed["project"]
    metrics      = parsed["metrics"]
    report_dates = parsed.get("report_dates", [])
    phase        = parsed.get("phase", "")
    target       = parsed.get("target", "")

    # Dates: cũ → mới
    date_labels = [f"{_get_vn_weekday(d)} {d[:5]}" for d in reversed(report_dates)]
    header_dates = ", ".join(date_labels)

    # ── Gọi AI ──────────────────────────────────────────────────────────────
    print(f"   🤖 Đang phân tích AI...")
    ai = ai_analyze_project(parsed)

    # ── Header ──────────────────────────────────────────────────────────────
    lines = [f"📊 {project} — Báo cáo | {header_dates}"]

    if phase or target:
        pt = f"{phase} | {target}".strip(" |")
        lines.append(pt)

    lines.append("")

    # ── AI summary ──────────────────────────────────────────────────────────
    if ai and ai.get("summary"):
        lines.append(ai["summary"])
        lines.append("")

    # ── GMV ─────────────────────────────────────────────────────────────────
    gmv_m = next((m for m in metrics if "Tổng GMV" in m["name"]), None)
    if gmv_m:
        vals = [fmt(gmv_m["daily_values"].get(d, "—")) for d in reversed(report_dates)]
        lines.append(f"GMV: {' | '.join(vals)}")

    # ── 5 KPI metrics — mỗi ngày có icon ────────────────────────────────────
    seen_short = set()
    for m_name in ALERT_METRICS_5:
        m = next((m for m in metrics if m_name.lower() in m["name"].lower()), None)
        if not m:
            continue
        short = _get_short_name(m["name"])
        if short in seen_short:
            continue
        seen_short.add(short)

        day_parts = []
        for d in reversed(report_dates):
            v = m["daily_values"].get(d, "—")
            icon = ""
            if v and v not in ("0", "—", ""):
                s = status_from_benchmark(v, m["benchmark"], m["name"])
                icon = {"green": "✅", "yellow": "🟡", "red": "🔴"}.get(s, "")
            day_parts.append(f"{fmt(v)}{icon}")
        lines.append(f"• {short}: {' → '.join(day_parts)}")

    lines.append("")

    # ── Analysis ─────────────────────────────────────────────────────────────
    if ai:
        issues_list  = ai.get("issues", [])
        warning_text = ai.get("warning", "")
        actions_list = ai.get("actions", [])
        owner        = ai.get("owner", "Team")

        if issues_list:
            lines.append("🔍 Vấn đề:")
            for i, iss in enumerate(issues_list, 1):
                lines.append(f"{i}. {iss}")
            lines.append("")

        if warning_text:
            lines.append(f"🚨🚨 CẢNH BÁO: {warning_text}")
            lines.append("")

        if actions_list:
            lines.append(f"✅ Hành động (@{owner}):")
            for i, act in enumerate(actions_list, 1):
                lines.append(f"{i}. {act}")
        elif not issues_list:
            lines.append("✅ Tất cả chỉ số xanh — duy trì vận hành.")

    else:
        # Fallback rule-based
        flat_data = {
            "project": project,
            "cp_ds":   parse_value(next((m["latest"] for m in metrics if "Ads/DS" in m["name"] or "CP/DS" in m["name"]), "0")),
            "ln_day":  parse_value(next((m["latest"] for m in metrics if "LỢI NHUẬN RÒNG" in m["name"]), "0")),
            "ds_day":  parse_value(next((m["latest"] for m in metrics if "Tổng GMV" in m["name"]), "0")),
            "thr_red": parse_value(parsed.get("target", "0")),
            "ty_le":   parse_value(next((m["latest"] for m in metrics if "Net Profit Margin" in m["name"]), "0")),
            "status":  "red" if any(m["status"] == "red" for m in metrics) else "yellow" if any(m["status"] == "yellow" for m in metrics) else "green",
        }
        rule_issues = detect_issues(flat_data)
        all_advice  = [get_advice(iss, parsed) for iss in rule_issues if get_advice(iss, parsed)]

        if all_advice:
            critical = all_advice[0]
            lines.append("🔍 Vấn đề:")
            for i, adv in enumerate(all_advice[:3], 1):
                lines.append(f"{i}. {adv.get('root_cause', '—')}")
            lines.append("")
            lines.append(f"🚨🚨 CẢNH BÁO: Rủi ro {critical.get('risk_level', 'CAO')}. {critical.get('root_cause', '')}")
            lines.append("")
            lines.append(f"✅ Hành động (@{all_advice[0].get('owner', 'Team')}):")
            acts = []
            for adv in all_advice:
                for act in adv.get("actions", []):
                    if act not in acts:
                        acts.append(act)
            for i, act in enumerate(acts[:3], 1):
                lines.append(f"{i}. {act}")
        else:
            lines.append("✅ Tất cả chỉ số xanh — duy trì vận hành.")

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
