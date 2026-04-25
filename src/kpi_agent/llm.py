from __future__ import annotations

import json
import os
from dataclasses import dataclass

from .models import KnowledgeItem, NormalizedKPI


@dataclass
class LLMExplainResult:
    diagnosis: str
    recommended_actions: list[str]
    used_knowledge_refs: list[str]


class OpenAIKnowledgeExplainer:
    def __init__(self, model: str = "gpt-5.5"):
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None

        try:
            from openai import OpenAI
        except Exception:  # noqa: BLE001
            return None

        self._client = OpenAI(api_key=api_key)
        return self._client

    def explain(self, issue: NormalizedKPI, knowledge_items: list[KnowledgeItem]) -> LLMExplainResult | None:
        client = self._get_client()
        if client is None:
            return None

        if not knowledge_items:
            return None

        allowed_refs = [k.id for k in knowledge_items]
        allowed_actions: list[str] = []
        for item in knowledge_items:
            allowed_actions.extend(item.action_templates)

        kb_text = []
        for item in knowledge_items:
            kb_text.append(
                {
                    "id": item.id,
                    "metric": item.metric,
                    "severity": item.severity,
                    "status": item.status,
                    "diagnosis_template": item.diagnosis_template,
                    "action_templates": item.action_templates,
                }
            )

        system_prompt = (
            "You are a KPI operations explainer. Use ONLY the provided knowledge. "
            "Do not invent causes or actions. Output strict JSON with keys: diagnosis, recommended_actions, used_knowledge_refs."
        )

        user_prompt = {
            "issue": {
                "project": issue.project,
                "metric": issue.metric,
                "actual_value": issue.actual_value,
                "benchmark": issue.benchmark,
                "threshold": issue.threshold,
                "gap": issue.gap,
                "status": issue.status,
                "severity": issue.severity,
                "report_date": issue.report_date,
            },
            "knowledge": kb_text,
            "rules": {
                "language": "Vietnamese",
                "must_only_use_knowledge": True,
                "must_include_used_knowledge_refs": True,
                "recommended_actions_must_be_subset_of_knowledge_action_templates": True,
                "max_actions": 5,
            },
        }

        try:
            resp = client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": json.dumps(user_prompt, ensure_ascii=False)}]},
                ],
                text={"format": {"type": "json_object"}},
            )
        except Exception:  # noqa: BLE001
            return None

        raw = getattr(resp, "output_text", "") or ""
        if not raw:
            return None

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        diagnosis = str(data.get("diagnosis", "")).strip()
        actions = [str(x).strip() for x in data.get("recommended_actions", []) if str(x).strip()]
        used_refs = [str(x).strip() for x in data.get("used_knowledge_refs", []) if str(x).strip()]

        if not diagnosis:
            return None

        valid_refs = [r for r in used_refs if r in allowed_refs]
        if not valid_refs:
            valid_refs = allowed_refs[:1]

        allowed_set = {a.strip() for a in allowed_actions if a.strip()}
        filtered_actions = [a for a in actions if a in allowed_set]
        if not filtered_actions:
            filtered_actions = list(allowed_set)[:3]

        return LLMExplainResult(
            diagnosis=diagnosis,
            recommended_actions=filtered_actions,
            used_knowledge_refs=valid_refs,
        )
