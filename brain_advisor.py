#!/usr/bin/env python3
"""
brain_advisor.py — Tra cứu brain IF-THEN docs và đưa ra hành động CÓ CƠ SỞ

NGUYÊN TẮC VÀNG:
  Mọi đề xuất PHẢI được trích dẫn từ tài liệu trong brain/.
  Nếu không tìm thấy tài liệu phù hợp → ghi rõ "chưa có playbook".
  KHÔNG BAO GIỜ tự bịa hành động mà không có nguồn.

Flow:
  1. Nhận project data (tên dự án + số liệu)
  2. Tìm file ifthen_*.md tương ứng với dự án
  3. Search section phù hợp (theo chỉ số bị cảnh báo)
  4. Extract: giá trị, nguyên nhân, hành động, owner, mức rủi ro
  5. Trả về advice có trích dẫn nguồn

Nếu không tìm được → fallback sang playbook_*.md / funnel_*.md
"""

import re
from pathlib import Path

BRAIN_DIR = Path(__file__).parent / "brain"


# ─────────────────────────────────────────────────────────────────────────────
# PROJECT → IF-THEN FILE MAPPING
# ─────────────────────────────────────────────────────────────────────────────

# Map tên dự án (từ Google Sheet) → file IF-THEN trong brain/
PROJECT_FILE_MAP = {
    # Việt Nam
    "TDCVN":  ["ifthen_TDCVN.md"],
    "KTLVN":  ["ifthen_KTLVN.md"],
    "KTMVN":  ["ifthen_IF_THEN_KTMVN.md"],
    "KTMR":   ["ifthen_IF_THEN_KTMR.md", "ifthen_IF_THEN_KTM_SRM.md"],
    "MNVN":   ["ifthen_MNVN.md"],
    "SRMR":   ["ifthen_SRMR.md", "ifthen_IF_THEN_KTM_SRM.md"],
    "XKMVN":  ["ifthen_XKMVN.md", "ifthen_IF_THEN_XKM_KTL.md"],
    # Quốc tế
    "XKMPH":  ["ifthen_XKMPH.md"],
    "XKMMY":  ["ifthen_XKMMY.md"],
    "KTLTL":  ["ifthen_KTLTL_TH.md"],
    "Thái":   ["ifthen_KTLTL_TH.md"],
    "TH":     ["ifthen_KTLTL_TH.md"],
    "Malay":  ["ifthen_XKMMY.md"],
    "Phil":   ["ifthen_XKMPH.md"],
}

# Aliases: biến thể tên dự án từ sheet → tên chuẩn
PROJECT_ALIASES = {
    "XKM VN": "XKMVN", "XKM PH": "XKMPH", "XKM MY": "XKMMY",
    "KTL VN": "KTLVN", "KTL TH": "KTLTL", "KTL TL": "KTLTL",
    "KTM VN": "KTMVN", "KTM R": "KTMR",
    "MN VN": "MNVN", "SRM R": "SRMR", "SRMVN": "SRMR",
    "TDC VN": "TDCVN", "TDC": "TDCVN",
    "Philippines": "XKMPH", "Malaysia": "XKMMY", "Thailand": "KTLTL",
}


# ─────────────────────────────────────────────────────────────────────────────
# ISSUE → KEYWORD MAPPING (để tìm section trong IF-THEN docs)
# ─────────────────────────────────────────────────────────────────────────────

ISSUE_KEYWORDS = {
    "take_rate_high": [
        "take rate", "ads/ds", "tỷ lệ gmv từ ads", "chi phí", "cp/ds",
    ],
    "high_cost_ratio": [
        "take rate", "ads/ds", "chi phí", "cpa", "roas",
    ],
    "negative_margin": [
        "lợi nhuận", "net profit", "margin", "biên",
    ],
    "low_ds_vs_target": [
        "tổng gmv", "doanh số", "impressions", "hiển thị", "imp",
    ],
    "creative_fatigue": [
        "ctr", "video", "creative", "rate 6s", "self-produced", "format",
    ],
    "low_impressions": [
        "impressions", "hiển thị", "imp", "lượt hiển thị",
    ],
    "high_cpa": [
        "cpa", "chi phí mỗi đơn", "cost per",
    ],
    "low_roas": [
        "roas", "return on",
    ],
    "high_cpm": [
        "cpm", "cost per mille",
    ],
    "high_cancel_rate": [
        "hủy đơn", "hoàn đơn", "tỷ lệ hủy", "tỷ lệ hoàn",
    ],
    "low_orders": [
        "đơn hàng", "tổng đơn",
    ],
    "low_aov": [
        "aov", "giá trị đơn",
    ],
    "booking_zero": [
        "booking", "kol", "koc", "creator", "affiliate",
    ],
    "low_cvr": [
        "cvr", "conversion", "tỷ lệ chuyển đổi",
    ],
    "low_ctr": [
        "ctr", "click-through", "tỷ lệ nhấp",
    ],
}

# Fallback playbook files khi không tìm thấy IF-THEN
FALLBACK_PLAYBOOKS = {
    "take_rate_high": ["playbook_take_rate.md"],
    "high_cost_ratio": ["playbook_take_rate.md"],
    "negative_margin": ["playbook_take_rate.md", "funnel_04_quick_action.md"],
    "low_ds_vs_target": ["funnel_05_impressions.md", "funnel_04_quick_action.md"],
    "creative_fatigue": ["playbook_creative_rotation.md", "funnel_06_video_consideration.md"],
    "low_impressions": ["funnel_05_impressions.md"],
    "high_cpa": ["playbook_take_rate.md"],
    "low_roas": ["playbook_take_rate.md"],
    "high_cpm": ["funnel_05_impressions.md"],
    "high_cancel_rate": ["funnel_04_quick_action.md"],
}


# ─────────────────────────────────────────────────────────────────────────────
# LOAD & SEARCH BRAIN DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

def _load_doc(filename: str) -> str:
    """Đọc 1 file từ brain/."""
    f = BRAIN_DIR / filename
    if not f.exists():
        return ""
    return f.read_text(encoding="utf-8")


def _resolve_project(project_name: str) -> str:
    """Normalize tên dự án → mã chuẩn."""
    name = project_name.strip().upper()
    # Thử match trực tiếp
    if name in PROJECT_FILE_MAP:
        return name
    # Thử alias
    for alias, code in PROJECT_ALIASES.items():
        if alias.upper() in name or name in alias.upper():
            return code
    # Thử substring match
    for code in PROJECT_FILE_MAP:
        if code in name or name in code:
            return code
    return project_name  # giữ nguyên nếu không match


def _find_ifthen_files(project_name: str) -> list[str]:
    """Tìm danh sách file IF-THEN cho dự án."""
    code = _resolve_project(project_name)
    files = PROJECT_FILE_MAP.get(code, [])
    # Nếu không tìm thấy, thử tìm theo tên file
    if not files:
        for f in BRAIN_DIR.glob("ifthen_*.md"):
            if code.lower() in f.name.lower():
                files.append(f.name)
    return files


def _search_section(doc_text: str, keywords: list[str]) -> dict | None:
    """
    Tìm section trong IF-THEN doc dựa trên keywords.
    Trả về dict với: title, content, actions, owner, risk_level, ref_section
    """
    if not doc_text:
        return None

    # Split doc thành sections (theo ### headers)
    sections = re.split(r'(?=^###\s)', doc_text, flags=re.MULTILINE)

    best_match = None
    best_score = 0

    for section in sections:
        if not section.strip():
            continue

        section_lower = section.lower()
        score = 0
        for kw in keywords:
            if kw.lower() in section_lower:
                score += 1
                # Bonus nếu keyword nằm trong tiêu đề (dòng đầu)
                first_line = section.split('\n')[0].lower()
                if kw.lower() in first_line:
                    score += 2

        if score > best_score:
            best_score = score
            best_match = section

    if not best_match or best_score < 1:
        return None

    return _parse_section(best_match)


def _parse_section(section_text: str) -> dict:
    """Parse 1 section IF-THEN thành structured data."""
    lines = section_text.strip().split('\n')

    # Title
    title = lines[0].replace('###', '').strip().lstrip('0123456789. ')

    # Extract các field đã format
    content = section_text

    # Tìm các field bằng bold pattern
    def _extract_field(name_pattern: str) -> str:
        pattern = rf'\*\*{name_pattern}[:\*]*\*\*\s*(.*?)(?=\*\*[^*]+\*\*|---|\Z)'
        m = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip('*').strip()
        return ""

    current_value = _extract_field(r'Giá trị hiện tại.*?')
    distance_red = _extract_field(r'Khoảng cách.*?')
    risk_level = _extract_field(r'Mức.*?rủi ro.*?') or _extract_field(r'Mức độ.*?')
    actions_raw = _extract_field(r'Hành động.*?')
    owner = _extract_field(r'Owner.*?')

    # Clean up risk level
    risk_level = risk_level.replace('\n', ' ').strip()
    if not risk_level:
        if 'CỰC CAO' in content:
            risk_level = 'CỰC CAO'
        elif 'CAO' in content.upper():
            risk_level = 'CAO'
        elif 'TRUNG BÌNH' in content:
            risk_level = 'TRUNG BÌNH'
        elif 'THẤP' in content:
            risk_level = 'THẤP'

    # Parse action lines
    action_lines = []
    for line in actions_raw.split('\n'):
        line = line.strip()
        if line and len(line) > 5:
            # Remove markdown formatting
            line = re.sub(r'^[\s①②③④⑤⑥⑦⑧⑨⑩\d.)\-•]+\s*', '', line).strip()
            if line and len(line) > 5:
                action_lines.append(line)

    # Clean owner
    owner = owner.split('\n')[0].strip() if owner else ""
    owner = re.sub(r'\*+', '', owner).strip()

    # Clean root cause from distance_red
    root_cause = distance_red.split('\n')[0].strip() if distance_red else ""

    return {
        "title": title,
        "current_value": current_value.split('\n')[0].strip() if current_value else "",
        "root_cause": root_cause,
        "risk_level": risk_level,
        "actions": action_lines[:5],  # Max 5 actions
        "owner": owner,
        "full_text": section_text[:500],  # Preserve for reference
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API — get_advice (tra cứu brain → trả về advice)
# ─────────────────────────────────────────────────────────────────────────────

def get_advice(issue_type: str, context: dict = None) -> dict:
    """
    Tra cứu brain IF-THEN docs cho dự án cụ thể.

    Returns dict:
      root_cause, actions (list[str]), owner, playbook_ref, sla, source
    """
    p = context or {}
    project_name = p.get("project", "")
    cp_ds = p.get("cp_ds", 0)

    # 1. Tìm file IF-THEN cho dự án
    ifthen_files = _find_ifthen_files(project_name)
    keywords = ISSUE_KEYWORDS.get(issue_type, [])

    # 2. Search trong IF-THEN docs
    for filename in ifthen_files:
        doc = _load_doc(filename)
        if not doc:
            continue

        result = _search_section(doc, keywords)
        if result and result["actions"]:
            # Format SLA dựa trên mức rủi ro
            sla_map = {
                "CỰC CAO": "Xử lý NGAY trong ngày",
                "CAO": "Xử lý trong ngày, báo cáo CEO",
                "TRUNG BÌNH": "Xử lý trong 2 ngày",
                "THẤP": "Giám sát hàng tuần",
            }
            sla = sla_map.get(result["risk_level"], "Review hàng ngày")

            return {
                "root_cause": result["root_cause"] or f"Xem phân tích chi tiết trong {filename}",
                "actions": result["actions"],
                "owner": result["owner"] or "Xem owner trong brain/",
                "playbook_ref": f"brain/{filename} → {result['title']}",
                "sla": sla,
                "source": "brain_ifthen",
                "risk_level": result["risk_level"],
            }

    # 3. Fallback: search trong playbook/funnel docs
    fallback_files = FALLBACK_PLAYBOOKS.get(issue_type, [])
    for filename in fallback_files:
        doc = _load_doc(filename)
        if not doc:
            continue

        result = _search_section(doc, keywords)
        if result and result["actions"]:
            return {
                "root_cause": result["root_cause"] or f"Theo {filename}",
                "actions": result["actions"],
                "owner": result["owner"] or "Xem phân công trong 00_company_context.md",
                "playbook_ref": f"brain/{filename}",
                "sla": "Review hàng ngày",
                "source": "brain_playbook",
                "risk_level": result.get("risk_level", ""),
            }

    # 4. Nếu KHÔNG tìm thấy gì trong brain → ghi rõ
    return {
        "root_cause": (
            f"⚠️ CHƯA CÓ PLAYBOOK cho [{project_name}] - [{issue_type}] trong brain/. "
            f"Cần bổ sung tài liệu IF-THEN cho dự án này."
        ),
        "actions": [
            f"Kiểm tra dữ liệu chi tiết trên TTMS Ads Manager",
            f"Tạo bảng IF-THEN cho dự án {project_name} → thêm vào brain/",
        ],
        "owner": "CEO / Leader dự án",
        "playbook_ref": "— (chưa có tài liệu)",
        "sla": "Cần bổ sung playbook",
        "source": "no_brain_match",
        "risk_level": "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# DETECT ISSUES FROM PROJECT DATA
# ─────────────────────────────────────────────────────────────────────────────

def detect_issues(project: dict) -> list[str]:
    """Phát hiện các vấn đề của 1 dự án dựa trên số liệu."""
    issues = []

    cp_ds  = project.get("cp_ds", 0)       # Chi phí / Doanh số %
    ln     = project.get("ln_day", 0)       # Lợi nhuận ngày
    ds     = project.get("ds_day", 0)       # Doanh số ngày
    thr_r  = project.get("thr_red", 0)      # Ngưỡng đỏ
    thr_g  = project.get("thr_green", 0)    # Ngưỡng xanh
    ty_le  = project.get("ty_le", 0)        # % lợi nhuận MTD
    status = project.get("status", "")

    # Take rate / chi phí cao
    if cp_ds > 40:
        issues.append("take_rate_high")
    elif cp_ds > 30:
        issues.append("high_cost_ratio")

    # Lợi nhuận âm
    if ln < 0:
        issues.append("negative_margin")

    # Doanh số quá thấp so với ngưỡng đỏ
    if thr_r > 0 and ds < thr_r * 0.6:
        issues.append("low_ds_vs_target")

    # Margin MTD thấp (possible creative fatigue / cpa issue)
    if 0 < ty_le < 5 and status in ("yellow", "red"):
        issues.append("creative_fatigue")

    # Doanh số dưới ngưỡng đỏ nhưng không quá thấp
    if thr_r > 0 and ds < thr_r and "low_ds_vs_target" not in issues:
        issues.append("low_impressions")

    # Deduplicate
    return list(dict.fromkeys(issues))


# ─────────────────────────────────────────────────────────────────────────────
# BUILD WARNING CARDS (format giống mock output — dựa 100% vào brain)
# ─────────────────────────────────────────────────────────────────────────────

def build_warning_cards(project: dict) -> list[dict]:
    """Trả về list warning cards với advice trích từ brain IF-THEN."""
    issues = detect_issues(project)
    cards  = []

    pname  = project.get("project", "?")
    status = project.get("status", "unknown")
    ln     = project.get("ln_day", 0)
    cp_ds  = project.get("cp_ds", 0)
    ds     = project.get("ds_day", 0)
    thr_r  = project.get("thr_red", 0)
    ty_le  = project.get("ty_le", 0)

    for i, issue in enumerate(issues, 1):
        advice = get_advice(issue, project)

        # Format value string
        if issue in ("take_rate_high", "high_cost_ratio"):
            metric = "Chi phí / Doanh số (CP/DS)"
            value  = f"{cp_ds:.1f}%"
            threshold = "ngưỡng tốt ≤ 35%"
        elif issue == "negative_margin":
            metric = "Lợi nhuận ngày"
            value  = f"{ln:,.0f} VND"
            threshold = "cần > 0"
        elif issue in ("low_ds_vs_target", "low_impressions"):
            pct = (ds / thr_r * 100) if thr_r else 0
            metric = "Doanh số vs Ngưỡng"
            value  = f"{pct:.0f}% ngưỡng đỏ"
            threshold = f"ngưỡng đỏ {thr_r:,.0f}"
        elif issue == "creative_fatigue":
            metric = "Biên lợi nhuận MTD"
            value  = f"{ty_le:+.1f}%"
            threshold = "target ≥ 8%"
        else:
            metric = issue
            value  = "—"
            threshold = "—"

        # Format action text từ brain — dùng numbered list thay vì nối →
        actions = advice.get("actions", [])
        action_text = " → ".join(actions[:3]) if actions else "⚠️ Chưa có playbook — cần bổ sung vào brain/"

        # Source tag
        source = advice.get("source", "unknown")
        source_tag = "📖" if source == "brain_ifthen" else "📘" if source == "brain_playbook" else "⚠️"

        cards.append({
            "priority": i,
            "metric": metric,
            "value": value,
            "status": status,
            "threshold": threshold,
            "root_cause": advice["root_cause"],
            "action": action_text,
            "owner": advice["owner"],
            "playbook_ref": f"{source_tag} {advice['playbook_ref']}",
            "sla": advice["sla"],
            "risk_level": advice.get("risk_level", ""),
            "source": source,
        })

    return cards


# ─────────────────────────────────────────────────────────────────────────────
# BRAIN COVERAGE REPORT (kiểm tra dự án nào đã có IF-THEN)
# ─────────────────────────────────────────────────────────────────────────────

def brain_coverage_report() -> str:
    """In ra báo cáo coverage: dự án nào có/chưa có IF-THEN trong brain."""
    lines = ["📊 BRAIN COVERAGE — IF-THEN Files:"]
    lines.append("")

    all_ifthen = list(BRAIN_DIR.glob("ifthen_*.md"))
    lines.append(f"  Tổng file IF-THEN: {len(all_ifthen)}")
    for f in sorted(all_ifthen):
        size_kb = f.stat().st_size / 1024
        lines.append(f"    ✅ {f.name} ({size_kb:.1f} KB)")

    lines.append("")
    lines.append("  Coverage theo dự án:")
    for code, files in sorted(PROJECT_FILE_MAP.items()):
        existing = [f for f in files if (BRAIN_DIR / f).exists()]
        status = "✅" if existing else "❌"
        lines.append(f"    {status} {code}: {', '.join(existing) if existing else 'CHƯA CÓ'}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(brain_coverage_report())
    print("=" * 60)

    # Test với từng dự án
    test_projects = [
        {"project": "TDCVN", "status": "red", "ds_day": 15_000_000,
         "thr_red": 25_000_000, "thr_green": 35_000_000,
         "ln_day": -2_000_000, "cp_ds": 42, "ty_le": -5.7},
        {"project": "XKMPH", "status": "red", "ds_day": 8_000_000,
         "thr_red": 10_000_000, "thr_green": 15_000_000,
         "ln_day": 2_000_000, "cp_ds": 35, "ty_le": 25.3},
        {"project": "KTMR", "status": "yellow", "ds_day": 61_300_000,
         "thr_red": 100_000_000, "thr_green": 130_000_000,
         "ln_day": -3_160_533, "cp_ds": 29.7, "ty_le": 8.2},
    ]

    for sample in test_projects:
        print(f"\n{'='*60}")
        print(f"🔍 Test: {sample['project']}")
        print(f"{'='*60}")
        cards = build_warning_cards(sample)
        if not cards:
            print("  ✅ Không có warning")
        for c in cards:
            print(f"\n  ⚠️  {c['metric']}: {c['value']}")
            print(f"     Root cause: {c['root_cause'][:100]}...")
            print(f"     Action: {c['action'][:120]}...")
            print(f"     Owner: {c['owner']}")
            print(f"     Ref: {c['playbook_ref']}")
            print(f"     Source: {c['source']}")
