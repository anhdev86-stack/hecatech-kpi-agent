from __future__ import annotations

from collections import Counter
from typing import Any

from .models import Issue, NormalizedKPI


CEO_LINE_HEAVY = "=============================================================="
CEO_LINE_LIGHT = "──────────────────────────────────────────────────────────────"

# Icon trạng thái
STATUS_ICON = {"green": "🟢", "yellow": "🟡", "red": "🔴", "unknown": "⚪"}
SEV_ICON = {"critical": "🚨", "high": "⚠️", "medium": "📊", "low": "✅", "none": "➖"}

# 5 chỉ số cảnh báo
FIVE_METRICS_ORDER = ["impressions", "ctr", "cvr", "cpm", "cpa"]


# ─────────────────────────────────────────────
# Build payloads
# ─────────────────────────────────────────────

def build_project_payload(
    bot_name: str,
    project: str,
    report_date: str,
    issues: list[Issue],
    revenue_drop_pct: float | None = None,
    alert_snapshot: list[NormalizedKPI] | None = None,
) -> dict:
    sev_count = Counter(i.severity for i in issues)
    status = _project_status(issues)

    highlights = [
        f"{project}: {len(issues)} issues | critical={sev_count.get('critical', 0)} | high={sev_count.get('high', 0)}"
    ]

    top_tasks = [
        f"[{i.priority}] {i.metric} -> owner {i.owner}, SLA {i.sla}"
        for i in sorted(issues, key=lambda x: x.priority)[:5]
    ]

    return {
        "bot_name": bot_name,
        "project": project,
        "report_date": report_date,
        "title": f"KPI Report - {project} ({report_date})",
        "summary": f"Trang thai: {status}. Tong issue: {len(issues)}.",
        "issues": [issue_to_dict(i) for i in issues],
        "highlights": highlights,
        "top_tasks": top_tasks,
        "revenue_drop_pct": revenue_drop_pct,
        "alert_snapshot": [_snapshot_to_dict(r) for r in (alert_snapshot or [])],
        "brain_note": "Actions chi duoc de xuat khi co knowledge_refs hop le.",
    }


def issue_to_dict(i: Issue) -> dict:
    return {
        "project": i.project,
        "metric": i.metric,
        "actual_value": i.actual_value,
        "benchmark": i.benchmark,
        "threshold": i.threshold,
        "gap": i.gap,
        "status": i.status,
        "severity": i.severity,
        "diagnosis": i.diagnosis,
        "recommended_actions": i.recommended_actions,
        "owner": i.owner,
        "sla": i.sla,
        "priority": i.priority,
        "knowledge_refs": i.knowledge_refs,
        "prev_value": i.prev_value,
        "drop_pct": i.drop_pct,
    }


def _snapshot_to_dict(r: NormalizedKPI) -> dict:
    return {
        "metric": r.metric,
        "actual_value": r.actual_value,
        "benchmark": r.benchmark,
        "status": r.status,
        "drop_pct": r.drop_pct,
    }


# ─────────────────────────────────────────────
# Format project message (single-day, khi doanh số giảm khẩn)
# ─────────────────────────────────────────────

def format_project_message(payload: dict) -> str:
    """Dùng cho alert khẩn (revenue drop >20%). Báo ngay, không theo lịch."""
    project = payload["project"]
    report_date = payload["report_date"]
    drop_pct = payload.get("revenue_drop_pct")
    snapshot = payload.get("alert_snapshot", [])

    lines = [f"🚨 [{project}] CẢNH BÁO KHẨN – {report_date}"]

    # ── Cảnh báo doanh số giảm ──
    if drop_pct is not None and drop_pct > 0:
        pct_str = f"{drop_pct * 100:.1f}%"
        lines += [
            "",
            f"📉 DOANH SỐ GIẢM {pct_str} so với hôm qua",
            "Trạng thái 5 chỉ số:",
        ]
        metric_map = {s["metric"].lower(): s for s in snapshot}
        for m in FIVE_METRICS_ORDER:
            info = metric_map.get(m)
            if info:
                icon = STATUS_ICON.get(info["status"], "⚪")
                actual = _fmt_val(info["actual_value"])
                bm = f" (BM: {_fmt_val(info['benchmark'])})" if info["benchmark"] is not None else ""
                d = f" ▼{info['drop_pct']*100:.1f}%" if info.get("drop_pct") and info["drop_pct"] > 0 else ""
                lines.append(f"  {icon} {m.upper()}: {actual}{bm}{d}")
            else:
                lines.append(f"  ⚪ {m.upper()}: N/A")

    # ── Chi tiết issue ──
    if payload["issues"]:
        lines += ["", "⚠️ Chi tiết:"]
        for idx, issue in enumerate(payload["issues"], 1):
            sev_ico = SEV_ICON.get(issue["severity"], "")
            actual = _fmt_val(issue["actual_value"])
            bm = _fmt_val(issue["benchmark"]) if issue["benchmark"] is not None else "—"
            drop_str = f" ▼{issue['drop_pct']*100:.1f}%" if issue.get("drop_pct") and issue["drop_pct"] > 0 else ""
            lines.append(
                f"{idx}. {sev_ico} {issue['metric'].upper()} | {actual}{drop_str} | BM: {bm}"
            )
            lines.append(f"   → {issue['diagnosis']}")
            for act in issue["recommended_actions"][:3]:
                lines.append(f"   • {act}")
            lines.append(f"   Owner: @{issue['owner']} | {issue['priority']} | SLA {issue['sla']}")

    if not payload["issues"] and drop_pct is None:
        lines += ["", "✅ Không có issue mới."]

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Format project 3-day summary (lịch định kỳ)
# ─────────────────────────────────────────────

def format_project_3day_message(
    project: str,
    leader: str,
    end_date: str,
    day_snapshots: list[dict],
    issues: list[Issue],
) -> str:
    """
    Báo cáo định kỳ 3 ngày gửi vào group dự án.
    day_snapshots: [{"date": "2026-04-23", "metrics": {metric: {...}}}, ...]  cũ → mới
    """
    n = len(day_snapshots)
    date_range = (
        f"{day_snapshots[0]['date']} → {day_snapshots[-1]['date']}"
        if n > 1
        else end_date
    )

    lines = [
        f"📋 [{project}] Báo cáo {n} ngày",
        f"📅 {date_range}",
        f"👤 Lead: @{leader}",
        CEO_LINE_LIGHT,
    ]

    # ── Bảng xu hướng 5 chỉ số qua từng ngày ──
    lines.append("📊 Xu hướng chỉ số:")

    # Header: Chỉ số | 04-23 | 04-24 | 04-25
    header_dates = " | ".join(f"{s['date'][5:]:^8}" for s in day_snapshots)
    lines.append(f"  {'Chỉ số':<14}| {header_dates}")
    sep = "──────────────┼" + "┼".join("──────────" for _ in day_snapshots)
    lines.append(f"  {sep}")

    for m in FIVE_METRICS_ORDER:
        cells = []
        for snap in day_snapshots:
            info = snap["metrics"].get(m)
            if info:
                icon = STATUS_ICON.get(info.get("status", "unknown"), "⚪")
                val = _fmt_val(info.get("actual_value"))
                cells.append(f"{icon}{val:>7}")
            else:
                cells.append(f"{'—':^8}")
        row_data = "  | ".join(f"{c}" for c in cells)
        lines.append(f"  {m.upper():<14}| {row_data}")

    lines.append(f"  {sep}")

    # ── Issues cần xử lý (tính theo ngày cuối) ──
    if issues:
        lines += [CEO_LINE_LIGHT, f"⚠️ Issue cần xử lý ({end_date}):"]
        for idx, issue in enumerate(issues, 1):
            sev_ico = SEV_ICON.get(issue.severity, "")
            actual = _fmt_val(issue.actual_value)
            bm = _fmt_val(issue.benchmark) if issue.benchmark is not None else "—"
            lines.append(
                f"{idx}. {sev_ico} {issue.metric.upper()} | Thực tế: {actual} | BM: {bm}"
            )
            lines.append(f"   → {issue.diagnosis}")
            for act in issue.recommended_actions[:3]:
                lines.append(f"   • {act}")
            lines.append(f"   Owner: @{issue.owner} | {issue.priority} | SLA {issue.sla}")
    else:
        lines += [CEO_LINE_LIGHT, "✅ Không có issue trong kỳ này."]

    lines.append(CEO_LINE_LIGHT)
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Build & format CEO message (hàng ngày)
# ─────────────────────────────────────────────

def build_ceo_payload(report_date: str, project_payloads: list[dict]) -> dict:
    statuses = []
    all_issues = []
    for p in project_payloads:
        issues = p.get("issues", [])
        all_issues.extend(issues)
        statuses.append(
            {
                "project": p["project"],
                "status": _project_status_dicts(issues),
                "issue_count": len(issues),
                "revenue_drop_pct": p.get("revenue_drop_pct"),
            }
        )

    status_counter = Counter(s["status"] for s in statuses)

    important = sorted(
        all_issues,
        key=lambda x: (0 if x["severity"] == "critical" else 1 if x["severity"] == "high" else 2),
    )[:10]

    return {
        "report_date": report_date,
        "project_statuses": statuses,
        "total_green": status_counter.get("green", 0),
        "total_yellow": status_counter.get("yellow", 0),
        "total_red": status_counter.get("red", 0),
        "important_alerts": important,
        "ceo_tasks": [
            f"Follow up {a['project']} - {a['metric']} ({a['severity']}) → @{a['owner']}"
            for a in important[:5]
        ],
        "highlights": [p["summary"] for p in project_payloads],
        "data_notes": "10:00 = du lieu hom qua, 16:00 = du lieu hien tai.",
        "brain_note": "Tong hop toan bo du an; route message theo projects.yaml.",
    }


def format_ceo_message(payload: dict) -> str:
    """CEO nhận báo cáo hàng ngày – tất cả dự án."""
    lines = [
        f"📊 CEO KPI REPORT – {payload['report_date']}",
        CEO_LINE_HEAVY,
        f"Tổng: 🟢{payload['total_green']} | 🟡{payload['total_yellow']} | 🔴{payload['total_red']}",
        CEO_LINE_LIGHT,
        "Trạng thái dự án:",
    ]

    for s in payload["project_statuses"]:
        icon = STATUS_ICON.get(s["status"], "⚪")
        drop_note = ""
        if s.get("revenue_drop_pct") and s["revenue_drop_pct"] > 0:
            drop_note = f" 🚨 ▼{s['revenue_drop_pct']*100:.1f}%"
        issues_note = f" ({s['issue_count']} issue)" if s["issue_count"] else ""
        lines.append(f"  {icon} {s['project']}{issues_note}{drop_note}")

    if payload["important_alerts"]:
        lines += [CEO_LINE_LIGHT, "⚠️ Cảnh báo quan trọng:"]
        for a in payload["important_alerts"]:
            sev_ico = SEV_ICON.get(a["severity"], "")
            lines.append(
                f"  {sev_ico} {a['project']} | {a['metric'].upper()} | @{a['owner']} | {a['priority']}"
            )
            lines.append(f"     → {a['diagnosis']}")

    lines += [CEO_LINE_LIGHT, "📌 Việc CEO cần giao:"]
    lines += [f"  • {x}" for x in payload["ceo_tasks"]] or ["  • (Không có)"]

    lines += [
        CEO_LINE_LIGHT,
        f"📝 {payload['data_notes']}",
        CEO_LINE_HEAVY,
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _project_status(issues: list[Issue]) -> str:
    if not issues:
        return "green"
    severities = {i.severity for i in issues}
    if "critical" in severities or "high" in severities:
        return "red"
    return "yellow"


def _project_status_dicts(issues: list[dict]) -> str:
    if not issues:
        return "green"
    severities = {i["severity"] for i in issues}
    if "critical" in severities or "high" in severities:
        return "red"
    return "yellow"


def _fmt_val(v: float | None) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v/1_000:.1f}K"
    return f"{v:.2f}"


def _short(text: str, max_len: int = 120) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[:max_len].rstrip() + "…"
