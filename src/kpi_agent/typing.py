from __future__ import annotations

from typing import Protocol

from .models import KnowledgeItem, NormalizedKPI


class IssueExplainer(Protocol):
    def explain(self, issue: NormalizedKPI, knowledge_items: list[KnowledgeItem]): ...
