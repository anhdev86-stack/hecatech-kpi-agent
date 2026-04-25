from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml


def load_kpi_workbook(path: str | Path) -> dict[str, pd.DataFrame]:
    xls = pd.ExcelFile(path)
    sheets: dict[str, pd.DataFrame] = {}
    for sheet in xls.sheet_names:
        sheets[sheet] = xls.parse(sheet)
    return sheets


def load_kpi_workbook_from_source(source: str | Path, cache_path: str | Path = "data/kpi_main_downloaded.xlsx") -> dict[str, pd.DataFrame]:
    src = str(source)
    if src.startswith("http://") or src.startswith("https://"):
        export_url = to_google_sheet_export_url(src)
        local = download_file(export_url, cache_path)
        return load_kpi_workbook(local)
    return load_kpi_workbook(src)


def to_google_sheet_export_url(url: str) -> str:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        return url
    sheet_id = match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"


def download_file(url: str, target_path: str | Path) -> Path:
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=60) as res:
        res.raise_for_status()
        target.write_bytes(res.content)
    return target


def load_knowledge_base(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf-8"))
    if p.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if p.suffix.lower() == ".md":
        return _parse_markdown_knowledge(p.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported knowledge file type: {p.suffix}")


def _parse_markdown_knowledge(content: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    blocks = [b.strip() for b in content.split("\n---\n") if b.strip()]
    for block in blocks:
        data: dict[str, Any] = {"keywords": [], "action_templates": []}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key, value = key.strip(), value.strip()
            if key == "keywords":
                data[key] = [s.strip() for s in value.split(",") if s.strip()]
            elif key == "action_templates":
                data[key] = [s.strip() for s in value.split(";") if s.strip()]
            else:
                data[key] = value
        if data.get("id"):
            items.append(data)
    return items
