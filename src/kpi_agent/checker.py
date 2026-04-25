from __future__ import annotations

from .models import NormalizedKPI

RED_FLAGS = {"red", "critical"}
YELLOW_FLAGS = {"yellow", "medium"}

# 5 chỉ số cảnh báo chính
ALERT_METRICS = {"impressions", "imp_video", "ctr", "cvr", "cpm", "cpa", "revenue"}


def find_issues(records: list[NormalizedKPI]) -> list[NormalizedKPI]:
    issues: list[NormalizedKPI] = []
    for record in records:
        if record.status in {"red", "yellow"}:
            issues.append(record)
            continue
        if record.severity in RED_FLAGS | YELLOW_FLAGS:
            issues.append(record)
    return issues


def has_revenue_drop(records: list[NormalizedKPI], drop_threshold: float = 0.20) -> bool:
    """Trả về True nếu metric revenue giảm hơn `drop_threshold` so với ngày hôm trước."""
    for r in records:
        if r.metric.lower() == "revenue" and r.drop_pct is not None:
            if r.drop_pct >= drop_threshold:
                return True
    return False


def get_alert_metrics_snapshot(records: list[NormalizedKPI]) -> list[NormalizedKPI]:
    """Lấy snapshot 5 chỉ số chính (impressions, CTR, CVR, CPM, CPA) để báo cáo kèm."""
    result = []
    for r in records:
        if r.metric.lower() in ALERT_METRICS:
            result.append(r)
    return result
