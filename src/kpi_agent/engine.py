from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .alert_log import AlertLogger
from .checker import find_issues, get_alert_metrics_snapshot, has_revenue_drop
from .config import load_app_config, load_yaml
from .diagnoser import build_issue_from_knowledge
from .formatters import (
    build_ceo_payload,
    build_project_payload,
    format_ceo_message,
    format_project_3day_message,
    format_project_message,
)
from .knowledge import parse_knowledge, retrieve_knowledge
from .lark import send_text
from .llm import OpenAIKnowledgeExplainer
from .loaders import load_kpi_workbook_from_source, load_knowledge_base
from .normalizer import normalize_sheet
from .snapshot_store import SnapshotStore
from .wide_loader import parse_wide_sheet


# ─────────────────────────────────────────────────────────────────────────────
# Lịch thông báo
#   • Group dự án : 3 ngày báo 1 lần (ngày day % 3 == 0)
#                   Báo cáo tổng hợp kết quả cả 3 ngày (trending table)
#   • Alert khẩn  : doanh số giảm > REVENUE_DROP_THRESHOLD → báo ngay dù
#                   chưa đến lịch định kỳ
#   • CEO          : hàng ngày – tất cả dự án
# ─────────────────────────────────────────────────────────────────────────────
REVENUE_DROP_THRESHOLD = 0.20   # 20%
PROJECT_REPORT_CYCLE = 3        # 3 ngày / lần


class KPIAgentEngine:
    def __init__(
        self,
        project_config_path: str | Path,
        schema_config_path: str | Path,
        kpi_source: str | Path,
        knowledge_file_path: str | Path,
        alert_log_path: str | Path,
        snapshot_store_path: str | Path = "data/daily_snapshots.json",
        bot_name: str = "KPI AI Agent",
        use_llm: bool = False,
        llm_model: str = "gpt-5.5",
    ):
        self.app_cfg = load_app_config(project_config_path)
        self.schema_cfg = load_yaml(schema_config_path)
        self.kpi_source = kpi_source
        self.knowledge_file_path = Path(knowledge_file_path)
        self.bot_name = bot_name
        self.alert_logger = AlertLogger(alert_log_path)
        self.snapshot_store = SnapshotStore(snapshot_store_path)
        self.explainer = OpenAIKnowledgeExplainer(model=llm_model) if use_llm else None

    def run(self, report_scope: str, force_project_send: bool = False) -> dict:
        report_date = self._resolve_report_date(report_scope)
        revenue_drop_threshold = float(
            self.schema_cfg.get("default", {}).get(
                "revenue_drop_alert_pct", REVENUE_DROP_THRESHOLD
            )
        )

        workbook = load_kpi_workbook_from_source(self.kpi_source)
        raw_kb = load_knowledge_base(self.knowledge_file_path)
        kb = parse_knowledge(raw_kb)

        # Dùng để build CEO payload (tất cả dự án, hàng ngày)
        ceo_project_payloads: list[dict] = []

        for sheet_name, df in workbook.items():
            project_cfg = self.app_cfg.projects.get(sheet_name)
            if not project_cfg:
                continue

            schema_map = self.schema_cfg.get("default", {})
            per_project = self.schema_cfg.get("projects", {}).get(project_cfg.project, {})
            merged_schema = {**schema_map, **per_project}

            normalized = _load_normalized(
                df, project_cfg.project, report_date, merged_schema
            )

            # ── 1. Lưu snapshot hàng ngày + backfill 3 ngày trước ──
            _backfill_snapshots(
                df, project_cfg.project, report_date, merged_schema,
                self.snapshot_store, n_days=PROJECT_REPORT_CYCLE,
            )

            # ── 2. Kiểm tra doanh số giảm (chỉ scope morning – dữ liệu hôm qua đã đầy đủ) ──
            # Scope afternoon dữ liệu chưa có của toàn ngày nên dễ false alarm
            revenue_drop = (
                report_scope == "morning"
                and has_revenue_drop(normalized, revenue_drop_threshold)
            )
            revenue_drop_pct = _get_revenue_drop_pct(normalized)
            alert_snapshot = get_alert_metrics_snapshot(normalized)

            # ── 3. Build issues (ngày hiện tại) ──
            issue_records = find_issues(normalized)
            issues = self._build_issues(
                issue_records, kb, project_cfg.leader,
                report_scope, report_date, skip_logged=not revenue_drop,
            )

            # ── 4. Xây dựng payload cho CEO (hàng ngày) ──
            ceo_payload_item = build_project_payload(
                bot_name=self.bot_name,
                project=project_cfg.project,
                report_date=report_date.isoformat(),
                issues=issues,
                revenue_drop_pct=revenue_drop_pct,
                alert_snapshot=alert_snapshot,
            )
            ceo_project_payloads.append(ceo_payload_item)

            # ── 5a. Alert khẩn khi doanh số giảm > ngưỡng (bỏ qua lịch) ──
            if revenue_drop:
                emergency_payload = build_project_payload(
                    bot_name=self.bot_name,
                    project=project_cfg.project,
                    report_date=report_date.isoformat(),
                    issues=issues,
                    revenue_drop_pct=revenue_drop_pct,
                    alert_snapshot=alert_snapshot,
                )
                msg = format_project_message(emergency_payload)
                ok, status = send_text(project_cfg.project_webhook, msg)
                self.alert_logger.append(
                    report_scope=report_scope,
                    report_date=report_date.isoformat(),
                    project=project_cfg.project,
                    metric="revenue",
                    severity="revenue_drop_alert",
                    used_knowledge_refs=[],
                    message_sent_status=f"project_emergency:{'ok' if ok else 'fail'}:{status}",
                )

            # ── 5b. Báo cáo định kỳ 3 ngày (hoặc force) ──
            elif self._is_scheduled_day(report_date) or force_project_send:
                day_snapshots = self.snapshot_store.get_last_n_days(
                    project_cfg.project, report_date, PROJECT_REPORT_CYCLE
                )
                msg = format_project_3day_message(
                    project=project_cfg.project,
                    leader=project_cfg.leader,
                    end_date=report_date.isoformat(),
                    day_snapshots=day_snapshots,
                    issues=issues,
                )
                ok, status = send_text(project_cfg.project_webhook, msg)
                # Log summary (kể cả khi không có issue)
                log_metric = issues[0].metric if issues else "__3day_summary__"
                self.alert_logger.append(
                    report_scope=report_scope,
                    report_date=report_date.isoformat(),
                    project=project_cfg.project,
                    metric=log_metric,
                    severity="3day_report",
                    used_knowledge_refs=[],
                    message_sent_status=f"project_3day:{'ok' if ok else 'fail'}:{status}",
                )
                for issue in issues:
                    if issue.metric == log_metric:
                        continue  # đã log ở trên
                    self.alert_logger.append(
                        report_scope=report_scope,
                        report_date=report_date.isoformat(),
                        project=issue.project,
                        metric=issue.metric,
                        severity=issue.severity,
                        used_knowledge_refs=issue.knowledge_refs,
                        message_sent_status=f"project_3day:{'ok' if ok else 'fail'}:{status}",
                    )

        # ── 6. CEO: hàng ngày – gửi tất cả dự án ──
        ceo_payload = build_ceo_payload(report_date.isoformat(), ceo_project_payloads)
        ceo_msg = format_ceo_message(ceo_payload)
        ceo_ok, ceo_status = send_text(self.app_cfg.ceo_webhook, ceo_msg)

        for p in ceo_project_payloads:
            self.alert_logger.append(
                report_scope=report_scope,
                report_date=report_date.isoformat(),
                project=p["project"],
                metric="__ceo_summary__",
                severity="summary",
                used_knowledge_refs=[],
                message_sent_status=f"ceo:{'ok' if ceo_ok else 'fail'}:{ceo_status}",
            )

        return {
            "report_scope": report_scope,
            "report_date": report_date.isoformat(),
            "project_count": len(ceo_project_payloads),
            "ceo_sent": ceo_ok,
        }

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _build_issues(
        self,
        issue_records,
        kb,
        leader: str,
        report_scope: str,
        report_date,
        skip_logged: bool,
    ):
        issues = []
        for ir in issue_records:
            knowledge_hits = retrieve_knowledge(ir, kb)
            issue = build_issue_from_knowledge(
                ir, knowledge_hits, leader, explainer=self.explainer
            )
            if skip_logged and self.alert_logger.exists(
                report_scope=report_scope,
                report_date=report_date.isoformat(),
                project=issue.project,
                metric=issue.metric,
                severity=issue.severity,
            ):
                continue
            issues.append(issue)
        return issues

    def _resolve_report_date(self, report_scope: str):
        tz = ZoneInfo(self.app_cfg.timezone)
        now = datetime.now(tz)

        if report_scope == "morning":
            return (now - timedelta(days=1)).date()
        if report_scope == "afternoon":
            return now.date()

        raise ValueError("report_scope must be one of: morning, afternoon")

    @staticmethod
    def _is_scheduled_day(report_date) -> bool:
        """Báo cáo định kỳ 3 ngày: ngày mà day % 3 == 0 (ngày 3, 6, 9, ...)."""
        return report_date.day % PROJECT_REPORT_CYCLE == 0


def _get_revenue_drop_pct(records) -> float | None:
    for r in records:
        if r.metric.lower() == "revenue" and r.drop_pct is not None:
            return r.drop_pct
    return None


def _load_normalized(df, project: str, report_date, schema_map: dict):
    """
    Tự động phát hiện wide-format (sheet Hecatech thực tế) vs
    tall-format (schema cũ metric/actual_value) và parse phù hợp.
    """
    import pandas as pd

    first_row = df.iloc[0] if len(df) > 0 else pd.Series(dtype=object)
    has_dates = any(
        hasattr(v, "date") or isinstance(v, pd.Timestamp)
        for v in first_row.values
        if v is not None and str(v) != "nan"
    )

    if has_dates:
        std_df = parse_wide_sheet(df, report_date)
        from .normalizer import normalize_sheet
        return normalize_sheet(std_df, project, report_date, schema_map)
    else:
        from .normalizer import normalize_sheet
        return normalize_sheet(df, project, report_date, schema_map)


def _backfill_snapshots(df, project: str, report_date, schema_map: dict,
                        snapshot_store, n_days: int = 3):
    """
    Backfill snapshot store với N ngày gần nhất từ Excel wide-format.
    Chỉ lưu ngày nào chưa có trong store (tránh ghi đè).
    """
    import pandas as pd
    from datetime import date as _date, timedelta

    first_row = df.iloc[0] if len(df) > 0 else pd.Series(dtype=object)
    has_dates = any(
        hasattr(v, "date") or isinstance(v, pd.Timestamp)
        for v in first_row.values
        if v is not None and str(v) != "nan"
    )

    if has_dates:
        # Wide format → extract nhiều ngày
        from .wide_loader import extract_multi_day_snapshots
        from .normalizer import normalize_sheet

        multi = extract_multi_day_snapshots(df, report_date, n_days)
        for day_str, day_df in multi.items():
            day_date = _date.fromisoformat(day_str)
            # Luôn cập nhật (dữ liệu mới nhất từ sheet)
            normalized = normalize_sheet(day_df, project, day_date, schema_map)
            snapshot_store.save_day(project, day_date, normalized)
    else:
        # Tall format: chỉ lưu report_date
        from .normalizer import normalize_sheet
        normalized = normalize_sheet(df, project, report_date, schema_map)
        snapshot_store.save_day(project, report_date, normalized)
