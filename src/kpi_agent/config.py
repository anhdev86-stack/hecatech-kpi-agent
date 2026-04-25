from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProjectConfig:
    sheet: str
    project: str
    leader: str
    project_webhook: str


@dataclass
class AppConfig:
    timezone: str
    ceo_webhook: str
    projects: dict[str, ProjectConfig]


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_app_config(path: str | Path) -> AppConfig:
    data = load_yaml(path)
    projects: dict[str, ProjectConfig] = {}
    for item in data.get("projects", []):
        cfg = ProjectConfig(
            sheet=item["sheet"],
            project=item["project"],
            leader=item["leader"],
            project_webhook=item["project_webhook"],
        )
        projects[cfg.sheet] = cfg

    return AppConfig(
        timezone=data.get("timezone", "Asia/Bangkok"),
        ceo_webhook=data["ceo_webhook"],
        projects=projects,
    )
