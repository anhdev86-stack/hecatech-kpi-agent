from __future__ import annotations

from typing import Any

from .models import KnowledgeItem, NormalizedKPI


def parse_knowledge(raw: list[dict[str, Any]]) -> list[KnowledgeItem]:
    items: list[KnowledgeItem] = []
    for obj in raw:
        if not obj.get("id"):
            continue
        items.append(
            KnowledgeItem(
                id=str(obj["id"]),
                metric=_norm(obj.get("metric")),
                severity=_norm(obj.get("severity")),
                status=_norm(obj.get("status")),
                keywords=[k.strip().lower() for k in obj.get("keywords", []) if str(k).strip()],
                diagnosis_template=str(obj.get("diagnosis_template", "")),
                action_templates=[str(s) for s in obj.get("action_templates", [])],
                owner_default=obj.get("owner_default"),
                sla_hours=_to_int(obj.get("sla_hours")),
                priority=obj.get("priority"),
            )
        )
    return items


def retrieve_knowledge(issue: NormalizedKPI, kb: list[KnowledgeItem]) -> list[KnowledgeItem]:
    metric_key = _normalize_metric(issue.metric)
    result: list[KnowledgeItem] = []

    for item in kb:
        item_metric = _normalize_metric(item.metric) if item.metric is not None else None
        metric_ok = item_metric in (None, metric_key)
        if not metric_ok and item_metric is not None:
            metric_ok = item_metric in metric_key or metric_key in item_metric
        status_ok = item.status in (None, issue.status.lower())
        severity_ok = item.severity in (None, issue.severity.lower())

        keyword_ok = True
        if item.keywords:
            text = f"{issue.metric} {issue.status} {issue.severity}".lower()
            keyword_ok = any(k in text for k in item.keywords)

        if metric_ok and status_ok and severity_ok and keyword_ok:
            result.append(item)

    return result


def _norm(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    return s or None


def _to_int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _normalize_metric(metric: str | None) -> str:
    if metric is None:
        return ""
    m = str(metric).strip().lower()
    alias = {
        "cpa đơn thực": "cpa",
        "rate 6s": "rate_6s",
        "rate 2s": "rate_2s",
        "chi phí qc/ngày": "spend",
        "imp thẻ sản phẩm": "imp_product_card",
    }
    if m in alias:
        return alias[m]
    m = m.replace(" ", "_")
    return m
