from __future__ import annotations

from .models import Issue, KnowledgeItem, NormalizedKPI
from .typing import IssueExplainer


NO_KNOWLEDGE_MSG = "Chưa có knowledge phù hợp để đề xuất action."


def build_issue_from_knowledge(
    record: NormalizedKPI,
    knowledge_items: list[KnowledgeItem],
    leader: str,
    explainer: IssueExplainer | None = None,
) -> Issue:
    if not knowledge_items:
        return Issue(
            project=record.project,
            metric=record.metric,
            actual_value=record.actual_value,
            benchmark=record.benchmark,
            threshold=record.threshold,
            gap=record.gap,
            status=record.status,
            severity=record.severity,
            report_date=record.report_date,
            diagnosis=f"[{record.project}] {record.metric.upper()}={_fmt(record.actual_value)} | {NO_KNOWLEDGE_MSG}",
            recommended_actions=[NO_KNOWLEDGE_MSG],
            owner=leader,
            sla="N/A",
            priority="N/A",
            knowledge_refs=[],
            prev_value=record.prev_value,
            drop_pct=record.drop_pct,
        )

    primary = knowledge_items[0]

    # ── Context riêng của từng dự án ──
    context_prefix = _build_context_prefix(record)

    try:
        base_diagnosis = primary.diagnosis_template.format(
            project=record.project,
            metric=record.metric,
            actual_value=record.actual_value,
            benchmark=record.benchmark,
            threshold=record.threshold,
            gap=record.gap,
            status=record.status,
            severity=record.severity,
        )
    except (KeyError, ValueError):
        base_diagnosis = primary.diagnosis_template

    try:
        base_actions = [
            a.format(
                project=record.project,
                metric=record.metric,
                actual_value=record.actual_value,
                benchmark=record.benchmark,
                threshold=record.threshold,
                gap=record.gap,
                status=record.status,
                severity=record.severity,
            )
            for a in primary.action_templates
        ]
    except (KeyError, ValueError):
        base_actions = primary.action_templates[:]

    if not base_actions:
        base_actions = [NO_KNOWLEDGE_MSG]

    # Gắn context prefix vào đầu diagnosis → mỗi dự án khác nhau
    diagnosis = f"{context_prefix} → {base_diagnosis}"

    # Owner: luôn dùng leader của dự án (tránh hardcode từ KB)
    owner = leader
    sla_hours = primary.sla_hours if primary.sla_hours is not None else 24
    priority = primary.priority or _priority_from_severity(record.severity)
    actions = base_actions
    refs = [k.id for k in knowledge_items]

    if explainer is not None:
        llm_result = explainer.explain(record, knowledge_items)
        if llm_result is not None:
            diagnosis = llm_result.diagnosis or diagnosis
            actions = llm_result.recommended_actions or base_actions
            refs = llm_result.used_knowledge_refs or refs

    return Issue(
        project=record.project,
        metric=record.metric,
        actual_value=record.actual_value,
        benchmark=record.benchmark,
        threshold=record.threshold,
        gap=record.gap,
        status=record.status,
        severity=record.severity,
        report_date=record.report_date,
        diagnosis=diagnosis,
        recommended_actions=actions,
        owner=owner,
        sla=f"{sla_hours}h",
        priority=priority,
        knowledge_refs=refs,
        prev_value=record.prev_value,
        drop_pct=record.drop_pct,
    )


def _build_context_prefix(record: NormalizedKPI) -> str:
    """Tạo chuỗi context ngắn chứa số liệu thực tế của dự án."""
    parts = [f"[{record.project}] {record.metric.upper()}={_fmt(record.actual_value)}"]
    if record.benchmark is not None:
        parts.append(f"BM={_fmt(record.benchmark)}")
    if record.drop_pct is not None and record.drop_pct > 0:
        parts.append(f"▼{record.drop_pct*100:.1f}%")
    parts.append(f"({record.status})")
    return " | ".join(parts)


def _fmt(v) -> str:
    if v is None:
        return "N/A"
    try:
        f = float(v)
        if abs(f) >= 1_000_000:
            return f"{f/1_000_000:.2f}M"
        if abs(f) >= 1_000:
            return f"{f/1_000:.1f}K"
        return f"{f:.4f}" if abs(f) < 1 else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(v)


def _priority_from_severity(severity: str) -> str:
    s = severity.lower()
    if s in {"critical", "high"}:
        return "P1"
    if s == "medium":
        return "P2"
    return "P3"
