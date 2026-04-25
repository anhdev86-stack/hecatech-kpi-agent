from __future__ import annotations

import argparse
import os
import time

# Load .env nếu có (OPENAI_API_KEY, KPI_SOURCE, ...)
try:
    from pathlib import Path as _Path
    from dotenv import load_dotenv
    _env_path = _Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv chưa cài – dùng env vars từ shell

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from kpi_agent.engine import KPIAgentEngine



def build_engine(
    use_llm: bool = False,
    llm_model: str = "gpt-5.5",
    kpi_source: str | None = None,
) -> KPIAgentEngine:
    return KPIAgentEngine(
        project_config_path="config/projects.yaml",
        schema_config_path="config/kpi_schema.yaml",
        kpi_source=kpi_source or os.getenv("KPI_SOURCE", "data/kpi_main.xlsx"),
        knowledge_file_path="data/knowledge_base.yaml",
        alert_log_path="data/alert_log.jsonl",
        snapshot_store_path="data/daily_snapshots.json",
        bot_name="AI Agent KPI",
        use_llm=use_llm,
        llm_model=llm_model,
    )


def run_once(scope: str, use_llm: bool, llm_model: str, kpi_source: str | None, force: bool = False) -> None:
    engine = build_engine(use_llm=use_llm, llm_model=llm_model, kpi_source=kpi_source)
    result = engine.run(scope, force_project_send=force)
    print(result)


def run_scheduler(use_llm: bool, llm_model: str, kpi_source: str | None) -> None:
    engine = build_engine(use_llm=use_llm, llm_model=llm_model, kpi_source=kpi_source)
    scheduler = BlockingScheduler(timezone="Asia/Bangkok")

    scheduler.add_job(
        lambda: print(engine.run("morning")),
        CronTrigger(hour=10, minute=0, timezone="Asia/Bangkok"),
        id="kpi_morning_1000",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: print(engine.run("afternoon")),
        CronTrigger(hour=16, minute=0, timezone="Asia/Bangkok"),
        id="kpi_afternoon_1600",
        replace_existing=True,
    )

    print("Scheduler started: 10:00 morning-report(yesterday), 16:00 afternoon-report(today) [Asia/Bangkok]")
    scheduler.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KPI AI Agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_cmd = sub.add_parser("run", help="Run one cycle")
    run_cmd.add_argument("--scope", choices=["morning", "afternoon"], required=True)
    run_cmd.add_argument("--use-llm", action="store_true", help="Enable OpenAI-based explanation")
    run_cmd.add_argument("--llm-model", default=os.getenv("OPENAI_MODEL", "gpt-5.5"))
    run_cmd.add_argument("--force", action="store_true", help="Force gửi báo cáo group dự án ngay (bỏ qua lịch 3 ngày)")
    run_cmd.add_argument("--kpi-source", default=os.getenv("KPI_SOURCE"), help="Local KPI xlsx path or Google Sheet URL")

    sched_cmd = sub.add_parser("scheduler", help="Run recurring scheduler")
    sched_cmd.add_argument("--use-llm", action="store_true", help="Enable OpenAI-based explanation")
    sched_cmd.add_argument("--llm-model", default=os.getenv("OPENAI_MODEL", "gpt-5.5"))
    sched_cmd.add_argument("--kpi-source", default=os.getenv("KPI_SOURCE"), help="Local KPI xlsx path or Google Sheet URL")

    args = parser.parse_args()

    if args.cmd == "run":
        run_once(args.scope, use_llm=args.use_llm, llm_model=args.llm_model, kpi_source=args.kpi_source, force=args.force)
    elif args.cmd == "scheduler":
        run_scheduler(use_llm=args.use_llm, llm_model=args.llm_model, kpi_source=args.kpi_source)
    else:
        time.sleep(0.1)
