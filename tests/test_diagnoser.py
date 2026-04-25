from kpi_agent.diagnoser import NO_KNOWLEDGE_MSG, build_issue_from_knowledge
from kpi_agent.models import KnowledgeItem, NormalizedKPI


def test_no_knowledge_blocks_recommendation():
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

    issue = build_issue_from_knowledge(rec, [], leader="lead_a")

    assert NO_KNOWLEDGE_MSG in issue.diagnosis   # context prefix + NO_KNOWLEDGE_MSG
    assert issue.recommended_actions == [NO_KNOWLEDGE_MSG]
    assert issue.knowledge_refs == []


def test_knowledge_attached_and_refs_present():
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

    issue = build_issue_from_knowledge(rec, kb, leader="lead_a")

    assert issue.knowledge_refs == ["KB1"]
    assert issue.recommended_actions == ["Fix funnel"]
