from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class AlertLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self, report_scope: str, report_date: str, project: str, metric: str, severity: str) -> bool:
        if not self.path.exists():
            return False
        key = (report_scope, report_date, project, metric, severity)
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                old = (
                    obj.get("report_scope"),
                    obj.get("report_date"),
                    obj.get("project"),
                    obj.get("metric"),
                    obj.get("severity"),
                )
                if old == key:
                    return True
        return False

    def append(
        self,
        report_scope: str,
        report_date: str,
        project: str,
        metric: str,
        severity: str,
        used_knowledge_refs: list[str],
        message_sent_status: str,
    ) -> None:
        row = {
            "report_scope": report_scope,
            "report_date": report_date,
            "project": project,
            "metric": metric,
            "severity": severity,
            "used_knowledge_refs": used_knowledge_refs,
            "message_sent_status": message_sent_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
