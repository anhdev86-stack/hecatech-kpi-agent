"""
wide_loader.py
──────────────
Đọc Google Sheet dạng wide-format của Hecatech:
  - Hàng 0: ngày (datetime) ở các cột daily
  - Cột 0 ('Unnamed: 0'): tên metric
  - Cột 1 ('Benchmark'): ngưỡng benchmark (text có emoji)
  - Cột 'T04.2026' (tháng): giá trị MTD tháng hiện tại
  - Các cột daily: giá trị từng ngày

Output: DataFrame chuẩn với các cột:
  metric | actual_value | prev_value | mtd_value | benchmark_text
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

import pandas as pd


# Các metric muốn track (normalize tên về key chuẩn)
METRIC_MAP: dict[str, str] = {
    "tổng doanh số": "revenue",
    "doanh số đơn giao hàng": "revenue",
    "tổng gmv": "revenue",
    "ctr(%)": "ctr",
    "ctr quảng cáo": "ctr",
    "cvr quảng cáo": "cvr",
    "cvr": "cvr",
    "cpa": "cpa",
    "cpm(vnđ)": "cpm",
    "cpm": "cpm",
    "net profit margin": "margin",
    "★ lợi nhuận ròng": "profit",
    "lợi nhuận ròng": "profit",
}

# Độ ưu tiên khi có nhiều dòng match cùng key (thấp hơn = ưu tiên hơn)
METRIC_PRIORITY: dict[str, list[str]] = {
    "revenue": ["tổng doanh số", "doanh số đơn giao hàng", "tổng gmv"],
    "ctr": ["ctr(%)", "ctr quảng cáo"],
    "cvr": ["cvr quảng cáo", "cvr"],
    "cpa": ["cpa"],
    "cpm": ["cpm(vnđ)", "cpm"],
    "margin": ["net profit margin"],
    "profit": ["★ lợi nhuận ròng", "lợi nhuận ròng"],
}


def parse_wide_sheet(df: pd.DataFrame, report_date: date) -> pd.DataFrame:
    """
    Chuyển sheet wide-format thành DataFrame chuẩn:
      metric | actual_value | prev_value | mtd_value
    """
    # ── Bước 1: Tìm cột ứng với report_date và ngày hôm trước ──
    date_row = df.iloc[0]  # hàng 0 chứa datetime của các cột daily
    target_col = _find_date_col(date_row, report_date)
    prev_col = _find_date_col(date_row, report_date - timedelta(days=1))

    # ── Bước 2: Tìm cột MTD (Tháng hiện tại: T04.2026, T05.2026...) ──
    mtd_col = _find_mtd_col(df.columns, report_date)

    metric_col = df.columns[0]

    # ── Bước 3: Collect tất cả rows rồi deduplicate theo priority ──
    candidates: dict[str, list[dict]] = {}  # key → list of {priority, data}

    for idx, row in df.iloc[1:].iterrows():
        raw_name = str(row.get(metric_col, "")).strip()
        if not raw_name or raw_name.lower() == "nan":
            continue

        std_key = _normalize_metric_name(raw_name)
        if std_key is None:
            continue

        actual = _to_float(row.get(target_col) if target_col else None)
        prev = _to_float(row.get(prev_col) if prev_col else None)
        mtd = _to_float(row.get(mtd_col) if mtd_col else None)

        if actual is None and mtd is None:
            continue

        effective_actual = actual if actual is not None else mtd
        priority = _metric_priority(std_key, raw_name)

        if std_key not in candidates:
            candidates[std_key] = []
        candidates[std_key].append({
            "priority": priority,
            "data": {
                "metric": std_key,
                "actual_value": effective_actual,
                "prev_value": prev,
                "mtd_value": mtd,
            }
        })

    # Chỉ giữ dòng có priority thấp nhất (tốt nhất) cho mỗi key
    rows_out = []
    for std_key, items in candidates.items():
        best = min(items, key=lambda x: x["priority"])
        rows_out.append(best["data"])

    return pd.DataFrame(rows_out, columns=["metric", "actual_value", "prev_value", "mtd_value"])


def extract_multi_day_snapshots(
    df: pd.DataFrame, end_date: date, n_days: int = 3
) -> dict[str, pd.DataFrame]:
    """
    Extract N ngày dữ liệu từ wide-format sheet.
    Returns: { "2026-04-23": DataFrame, "2026-04-24": DataFrame, "2026-04-25": DataFrame }
    Mỗi DataFrame có cấu trúc giống parse_wide_sheet output.
    """
    date_row = df.iloc[0]
    mtd_col = _find_mtd_col(df.columns, end_date)
    metric_col = df.columns[0]

    result = {}
    for delta in range(n_days - 1, -1, -1):
        target_date = end_date - timedelta(days=delta)
        prev_date = target_date - timedelta(days=1)

        target_col = _find_date_col(date_row, target_date)
        prev_col = _find_date_col(date_row, prev_date)

        if target_col is None:
            continue  # Ngày này không có trong sheet

        candidates: dict[str, list[dict]] = {}

        for idx, row in df.iloc[1:].iterrows():
            raw_name = str(row.get(metric_col, "")).strip()
            if not raw_name or raw_name.lower() == "nan":
                continue

            std_key = _normalize_metric_name(raw_name)
            if std_key is None:
                continue

            actual = _to_float(row.get(target_col))
            prev = _to_float(row.get(prev_col) if prev_col else None)
            mtd = _to_float(row.get(mtd_col) if mtd_col else None)

            if actual is None:
                continue

            priority = _metric_priority(std_key, raw_name)
            if std_key not in candidates:
                candidates[std_key] = []
            candidates[std_key].append({
                "priority": priority,
                "data": {
                    "metric": std_key,
                    "actual_value": actual,
                    "prev_value": prev,
                    "mtd_value": mtd,
                }
            })

        rows_out = []
        for std_key, items in candidates.items():
            best = min(items, key=lambda x: x["priority"])
            rows_out.append(best["data"])

        if rows_out:
            result[target_date.isoformat()] = pd.DataFrame(
                rows_out, columns=["metric", "actual_value", "prev_value", "mtd_value"]
            )

    return result


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _find_date_col(date_row: pd.Series, target: date):
    """Tìm tên cột ứng với target date trong hàng header phụ."""
    for col, val in date_row.items():
        if isinstance(val, (pd.Timestamp,)) or hasattr(val, "date"):
            try:
                if val.date() == target:
                    return col
            except Exception:
                pass
        elif hasattr(val, "year"):
            try:
                d = date(val.year, val.month, val.day)
                if d == target:
                    return col
            except Exception:
                pass
    return None


def _find_mtd_col(columns, report_date: date):
    """Tìm cột MTD dạng 'T04.2026' cho tháng của report_date."""
    month_str = f"T{report_date.month:02d}.{report_date.year}"
    for col in columns:
        if str(col).strip() == month_str:
            return col
    return None


def _normalize_metric_name(name: str) -> str | None:
    """Map tên metric tiếng Việt → key chuẩn (en)."""
    key = name.lower().strip()
    # Bỏ emoji và ký tự đặc biệt đầu dòng
    key = re.sub(r"^[★✅🔴🟡\s]+", "", key).strip()
    return METRIC_MAP.get(key)


def _metric_priority(std_key: str, raw_name: str) -> int:
    """Trả về index ưu tiên (thấp hơn = quan trọng hơn)."""
    prio_list = METRIC_PRIORITY.get(std_key, [])
    raw_lower = raw_name.lower().strip()
    raw_lower = re.sub(r"^[★✅🔴🟡\s]+", "", raw_lower).strip()
    try:
        return prio_list.index(raw_lower)
    except ValueError:
        return 999


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and str(value) == "nan":
        return None
    if isinstance(value, str):
        v = value.strip()
        if not v or v in ("nan", "NaN", "—", "Đỏ", "Xanh", "Vàng", "#DIV/0!"):
            return None
        v = v.replace(",", "").replace("%", "")
        try:
            return float(v)
        except ValueError:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
