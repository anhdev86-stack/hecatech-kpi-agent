from datetime import datetime
from zoneinfo import ZoneInfo

from kpi_agent.engine import KPIAgentEngine


class DummyEngine(KPIAgentEngine):
    pass


def test_scope_contract():
    e = KPIAgentEngine(
        project_config_path="config/projects.yaml",
        schema_config_path="config/kpi_schema.yaml",
        kpi_source="data/kpi_main.xlsx",
        knowledge_file_path="data/knowledge_base.yaml",
        alert_log_path="data/alert_log_test.jsonl",
        bot_name="test",
    )

    tz = ZoneInfo("Asia/Bangkok")
    now = datetime.now(tz).date()

    assert e._resolve_report_date("afternoon") == now
    assert e._resolve_report_date("morning") <= now
