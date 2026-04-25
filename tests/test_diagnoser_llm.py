from dataclasses import dataclass

from kpi_agent.diagnoser import build_issue_from_knowledge
from kpi_agent.llm import LLMExplainResult
from kpi_agent.models import KnowledgeItem, NormalizedKPI


@dataclass
class FakeExplainer:
    def explain(self, issue, knowledge_items):
        return LLMExplainResult(
            diagnosis="Dien giai tu knowledge",
            recommended_actions=["Fix funnel"],
            used_knowledge_refs=["KB1"],
        )


def test_llm_explainer_overrides_with_knowledge_grounded_output():
    rec = NormalizedKPI(
        project="XKMVN",
        metric="cvr",
        actual_value=0.01,
        mtd_value=0.02,
        benchmark=0.03,
        threshold=0.02,
        gap=-0.02,
        status="red",
        severity="high",
        report_date="2026-04-24",
    )

    kb = [
        KnowledgeItem(
            id="KB1",
            metric="cvr",
            severity="high",
            status="red",
            keywords=["cvr"],
            diagnosis_template="CVR low",
            action_templates=["Fix funnel"],
            owner_default="growth",
            sla_hours=8,
            priority="P1",
        )
    ]

    issue = build_issue_from_knowledge(rec, kb, leader="lead_a", explainer=FakeExplainer())

    assert issue.diagnosis == "Dien giai tu knowledge"
    assert issue.recommended_actions == ["Fix funnel"]
    assert issue.knowledge_refs == ["KB1"]
