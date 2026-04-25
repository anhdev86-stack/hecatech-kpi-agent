from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NormalizedKPI:
    project: str
    metric: str
    actual_value: float
    mtd_value: float | None
    benchmark: float | None
    threshold: float | None
    gap: float | None
    status: str
    severity: str
    report_date: str
    prev_value: float | None = None   # giá trị ngày hôm trước
    drop_pct: float | None = None     # % giảm so với hôm trước (dương = giảm)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeItem:
    id: str
    metric: str | None
    severity: str | None
    status: str | None
    keywords: list[str]
    diagnosis_template: str
    action_templates: list[str]
    owner_default: str | None = None
    sla_hours: int | None = None
    priority: str | None = None


@dataclass
class Issue:
    project: str
    metric: str
    actual_value: float
    benchmark: float | None
    threshold: float | None
    gap: float | None
    status: str
    severity: str
    report_date: str
    diagnosis: str
    recommended_actions: list[str]
    owner: str
    sla: str
    priority: str
    knowledge_refs: list[str]
    prev_value: float | None = None
    drop_pct: float | None = None
