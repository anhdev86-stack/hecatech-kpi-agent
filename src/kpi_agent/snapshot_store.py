"""
snapshot_store.py
─────────────────
Lưu và đọc KPI snapshot hàng ngày theo từng dự án.

Cấu trúc JSON:
{
  "XKMVN": {
    "2026-04-23": { "revenue": 12500.0, "impressions": 45000.0, ... },
    "2026-04-24": { ... },
    "2026-04-25": { ... }
  },
  ...
}
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .models import NormalizedKPI


class SnapshotStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, dict[str, Any]]] = self._load()

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def save_day(self, project: str, report_date: date, records: list[NormalizedKPI]) -> None:
        """Lưu snapshot metrics cho một dự án vào ngày report_date."""
        day_str = report_date.isoformat()
        if project not in self._data:
            self._data[project] = {}
        self._data[project][day_str] = {
            r.metric: {
                "actual_value": r.actual_value,
                "benchmark": r.benchmark,
                "status": r.status,
                "severity": r.severity,
                "drop_pct": r.drop_pct,
            }
            for r in records
        }
        self._persist()

    def get_last_n_days(
        self, project: str, end_date: date, n: int = 3
    ) -> list[dict[str, Any]]:
        """
        Trả về list n ngày (cũ → mới), mỗi phần tử là:
          { "date": "2026-04-23", "metrics": { metric_name: {...} } }
        Ngày nào chưa có snapshot thì bỏ qua.
        """
        result = []
        project_data = self._data.get(project, {})
        for delta in range(n - 1, -1, -1):  # n-1 → 0 (cũ → mới)
            d = (end_date - timedelta(days=delta)).isoformat()
            if d in project_data:
                result.append({"date": d, "metrics": project_data[d]})
        return result

    def has_enough_days(self, project: str, end_date: date, n: int = 3) -> bool:
        """Kiểm tra đã có đủ n ngày snapshot chưa."""
        return len(self.get_last_n_days(project, end_date, n)) >= 1  # gửi dù ít hơn n ngày

    # ─────────────────────────────────────────
    # Internal
    # ─────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _persist(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
