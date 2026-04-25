# KPI AI Agent

AI Agent KPI chạy theo 2 lịch cố định timezone `Asia/Bangkok`:
- `10:00`: báo cáo dữ liệu **ngày hôm qua**
- `16:00`: báo cáo dữ liệu **ngày hiện tại**

## Luồng xử lý
1. Load KPI file (mỗi sheet = 1 project)
2. Load Knowledge Base (JSON/YAML/Markdown)
3. Load project config
4. Normalize KPI về schema chung
5. KPI checker phát hiện issue
6. Retrieve knowledge theo metric/status/keyword
7. Chỉ tạo diagnosis/action khi có knowledge; nếu không có knowledge thì block recommendation
8. Build payload project + CEO
9. Format message project + CEO
10. Route đúng webhook Lark project và CEO
11. Ghi alert log để audit/chống spam/debug

## Cài đặt
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Chạy thủ công
```bash
python -m src.main run --scope morning
python -m src.main run --scope afternoon
```

## Chạy scheduler
```bash
python -m src.main scheduler
```

## Cấu trúc config chính
- `config/projects.yaml`: mapping sheet -> project + leader + webhook project + webhook CEO
- `config/kpi_schema.yaml`: metric map + benchmark + threshold
- `data/knowledge_base.yaml`: rule/playbook/case history có `id` để trace

## Alert log
File `data/alert_log.jsonl` ghi:
- `report_scope`
- `report_date`
- `project`
- `metric`
- `severity`
- `used_knowledge_refs`
- `message_sent_status`
- `timestamp`


## LLM Layer (OpenAI)
LLM chỉ dùng để diễn giải nội dung đã retrieve từ knowledge base. Guardrail:
- Không có knowledge => không đề xuất action.
- `knowledge_refs` luôn phải có khi có action.
- Action LLM sẽ bị lọc để chỉ nằm trong tập action templates của knowledge đã retrieve.

Bật LLM khi chạy:
```bash
export OPENAI_API_KEY="<your_key>"
python -m src.main run --scope morning --use-llm --llm-model gpt-4.1-mini
python -m src.main scheduler --use-llm --llm-model gpt-4.1-mini
```


## Chạy với Google Sheet URL
```bash
python -m src.main run --scope morning --kpi-source "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit#gid=..."
```
Agent tự convert URL sang `export?format=xlsx` để đọc toàn bộ workbook.
