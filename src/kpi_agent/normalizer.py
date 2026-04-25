from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from .models import NormalizedKPI

# Các metric mà giá trị CAO hơn là TỆ hơn (cost-type)
COST_METRICS = {"cpa", "cpm", "cost/revenue", "chi_phi_doanh_so"}

# Các metric mà giá trị THẤP hơn là TỆ hơn (rate-type)
RATE_METRICS = {"ctr", "cvr", "impressions", "imp_video", "revenue"}


def normalize_sheet(
    df: pd.DataFrame,
    project: str,
    report_date: date,
    schema_map: dict[str, Any],
) -> list[NormalizedKPI]:
    records: list[NormalizedKPI] = []
    metric_col = schema_map.get("metric_col", "metric")
    actual_col = schema_map.get("actual_col", "actual_value")
    mtd_col = schema_map.get("mtd_col", "mtd_value")
    prev_col = schema_map.get("prev_col", "prev_value")

    benchmark_map = schema_map.get("benchmarks", {})
    threshold_map = schema_map.get("thresholds", {})

    for _, row in df.iterrows():
        metric = str(row.get(metric_col, "")).strip()
        if not metric:
            continue

        actual = _to_float(row.get(actual_col))
        mtd = _to_float(row.get(mtd_col))
        prev = _to_float(row.get(prev_col))
        benchmark = _to_float(benchmark_map.get(metric))
        threshold = _to_float(threshold_map.get(metric))

        gap = None if benchmark is None or actual is None else actual - benchmark

        # Tính % giảm so với ngày hôm trước
        drop_pct: float | None = None
        if actual is not None and prev is not None and prev > 0:
            drop_pct = (prev - actual) / prev  # dương = giảm

        status, severity = _derive_status(actual, benchmark, threshold, metric)

        if actual is None:
            continue

        records.append(
            NormalizedKPI(
                project=project,
                metric=metric,
                actual_value=actual,
                mtd_value=mtd,
                benchmark=benchmark,
                threshold=threshold,
                gap=gap,
                status=status,
                severity=severity,
                report_date=report_date.isoformat(),
                prev_value=prev,
                drop_pct=drop_pct,
                raw={k: (v.item() if hasattr(v, "item") else v) for k, v in row.to_dict().items()},
            )
        )

    return records


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _derive_status(
    actual: float | None,
    benchmark: float | None,
    threshold: float | None,
    metric: str,
) -> tuple[str, str]:
    if actual is None:
        return "unknown", "none"

    m = metric.lower()

    # Profit âm -> critical
    if "profit" in m and actual < 0:
        return "red", "critical"

    # Revenue < 0 -> critical
    if m == "revenue" and actual < 0:
        return "red", "critical"

    # Cost-type metrics: cao hơn là tệ hơn
    if any(x in m for x in COST_METRICS):
        if threshold is not None and actual > threshold:
            return "red", "high"
        if benchmark is not None and actual > benchmark:
            return "yellow", "medium"
        return "green", "low"

    # Rate/volume metrics: thấp hơn là tệ hơn
    # (ctr, cvr, impressions, revenue, và các metric mặc định)
    if benchmark is not None and actual < benchmark:
        if threshold is not None and actual < threshold:
            return "red", "high"
        return "yellow", "medium"

    return "green", "low"
