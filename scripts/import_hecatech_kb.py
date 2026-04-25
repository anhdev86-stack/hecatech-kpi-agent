from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pandas as pd
import yaml


SOURCE_XLSX = Path('/Users/admin/Downloads/Hecatech_Funnel_Matrix_v12 30_3.xlsx')
TARGET_YAML = Path('data/knowledge_base.yaml')


@dataclass
class RowRule:
    section: str
    metric_raw: str
    factors: str
    actions: str
    owner: str
    thresholds_pct: str
    thresholds_abs: str


def norm_text(v: Any) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    if s.lower() == 'nan':
        return ''
    return s


def normalize_metric(metric_raw: str) -> str:
    m = metric_raw.lower()
    mapping = [
        ('roi set', 'roi_floor'),
        ('imp video', 'imp_video'),
        ('imp thẻ', 'imp_product_card'),
        ('product card', 'imp_product_card'),
        ('cpm', 'cpm'),
        ('chi phí qc/ngày', 'spend'),
        ('rate 6s', 'rate_6s'),
        ('rate 2s', 'rate_2s'),
        ('ctr', 'ctr'),
        ('cpc', 'cpc'),
        ('clicks tuyệt đối', 'clicks'),
        ('creative pool', 'creative_pool'),
        ('số đơn/ngày', 'orders'),
        ('doanh số/ngày', 'revenue'),
        ('aov', 'aov'),
        ('cpa đơn thực', 'cpa'),
    ]
    for needle, key in mapping:
        if needle in m:
            return key

    slug = re.sub(r'[^a-z0-9]+', '_', m).strip('_')
    return slug[:60] or 'unknown_metric'


def split_actions(text: str) -> list[str]:
    chunks: list[str] = []
    for raw in re.split(r'\n|;|•', text):
        item = raw.strip(' -•\t')
        if not item:
            continue
        if len(item) < 6:
            continue
        chunks.append(item)
    dedup: list[str] = []
    seen = set()
    for c in chunks:
        lc = c.lower()
        if lc in seen:
            continue
        seen.add(lc)
        dedup.append(c)
    return dedup[:5]


def parse_sheet_matrix(path: Path, sheet_name: str = 'Bản chỉnh sửa') -> list[RowRule]:
    df = pd.read_excel(path, sheet_name=sheet_name, header=None)

    current_section = 'general'
    rules: list[RowRule] = []

    for _, row in df.iterrows():
        c0 = norm_text(row.iloc[0])
        c1 = norm_text(row.iloc[1])
        c3 = norm_text(row.iloc[3])
        c4 = norm_text(row.iloc[4])
        c5 = norm_text(row.iloc[5])
        c6 = norm_text(row.iloc[6])
        c7 = norm_text(row.iloc[7])

        if 'TẦNG' in c0 or 'BLOCK' in c0:
            current_section = c0
            continue

        if c0.startswith('T') and '|' in c0:
            continue

        if c1.lower() in {'chỉ số', 'nguồn'}:
            continue

        if not c1 or not c4:
            continue

        if c1 in {'ROI set'}:
            c1 = 'ROI floor'

        if any(x in c1.lower() for x in ['owner', 'ngưỡng', 'tầng phễu']):
            continue

        rules.append(
            RowRule(
                section=current_section,
                metric_raw=c1,
                factors=c3,
                actions=c4,
                owner=c5 or 'project_lead',
                thresholds_pct=c6,
                thresholds_abs=c7,
            )
        )

    return rules


def build_kb_records(rules: list[RowRule]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, r in enumerate(rules, start=1):
        metric = normalize_metric(r.metric_raw)
        actions = split_actions(r.actions)
        if not actions:
            actions = ['Chưa có knowledge phù hợp để đề xuất action.']

        diagnosis = (
            f"{r.metric_raw}: kiểm tra theo Funnel Matrix v12. "
            f"Nhóm yếu tố ảnh hưởng ưu tiên: {r.factors or 'theo ma trận hiện có'}."
        )

        keywords = sorted(
            {
                metric,
                *[w for w in re.findall(r'[A-Za-z0-9_]+', r.metric_raw.lower()) if len(w) >= 3],
                *[w for w in re.findall(r'[A-Za-z0-9_]+', r.section.lower()) if len(w) >= 3],
            }
        )

        record = {
            'id': f'KB-HEC-{metric.upper()}-{i:03d}',
            'metric': metric,
            'severity': None,
            'status': None,
            'keywords': keywords[:12],
            'diagnosis_template': diagnosis,
            'action_templates': actions,
            'owner_default': r.owner,
            'sla_hours': 24,
            'priority': 'P2',
            'source': {
                'file': str(SOURCE_XLSX),
                'sheet': 'Bản chỉnh sửa',
                'section': r.section,
                'thresholds_pct': r.thresholds_pct,
                'thresholds_abs': r.thresholds_abs,
            },
        }
        out.append(record)

    # Add targeted rules from impression and consideration sheets as generic playbooks
    out.extend(
        [
            {
                'id': 'KB-HEC-IMP-001',
                'metric': 'imp_video',
                'severity': 'high',
                'status': 'red',
                'keywords': ['imp', 'impressions', 'roi_floor', 'creative_pool'],
                'diagnosis_template': 'Impressions giảm mạnh, ưu tiên chẩn đoán ROI floor, budget utilization và creative pool theo Funnel Matrix.',
                'action_templates': [
                    'Hạ ROI floor 0.2 mỗi 2 ngày và theo dõi điều kiện dừng.',
                    'Bổ sung creative pool với video mới, ưu tiên video creator.',
                    'Kiểm tra Spend/Budget utilization để xác nhận hệ thống bị throttle.',
                ],
                'owner_default': 'SaoBT + CEO',
                'sla_hours': 8,
                'priority': 'P1',
                'source': {
                    'file': str(SOURCE_XLSX),
                    'sheet': '4. Tăng Impressions',
                    'section': '7 Đòn bẩy tăng impressions',
                },
            },
            {
                'id': 'KB-HEC-CONSIDERATION-001',
                'metric': 'ctr',
                'severity': 'high',
                'status': 'red',
                'keywords': ['ctr', 'rate_6s', 'cpc', 'consideration'],
                'diagnosis_template': 'CTR tầng consideration thấp cần đọc cùng Rate 6s và CPC để tránh tối ưu sai lớp.',
                'action_templates': [
                    'Giữ body winner, refresh hook và CTA để tăng tỷ lệ nhấp.',
                    'Tắt video hạng D khi đã đủ sample size, dồn ngân sách cho hạng S/A.',
                    'Nếu CTR cao nhưng clicks thấp, ưu tiên xử lý ROI floor thay vì sửa video.',
                ],
                'owner_default': 'SaoBT + TuND',
                'sla_hours': 8,
                'priority': 'P1',
                'source': {
                    'file': str(SOURCE_XLSX),
                    'sheet': '5. Lọc video Consideration',
                    'section': 'Quick filtering + diagnosis',
                },
            },
        ]
    )

    return out


def main() -> None:
    if not SOURCE_XLSX.exists():
        raise FileNotFoundError(f'Missing source file: {SOURCE_XLSX}')

    rules = parse_sheet_matrix(SOURCE_XLSX)
    records = build_kb_records(rules)

    TARGET_YAML.parent.mkdir(parents=True, exist_ok=True)
    with TARGET_YAML.open('w', encoding='utf-8') as f:
        yaml.safe_dump(records, f, allow_unicode=True, sort_keys=False)

    print({'rules_extracted': len(rules), 'kb_records_written': len(records), 'output': str(TARGET_YAML)})


if __name__ == '__main__':
    main()
