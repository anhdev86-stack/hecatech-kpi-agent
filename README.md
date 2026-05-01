# Hecatech CEO Agent — Build Package v2

Đây là package hoàn chỉnh để build AI Agent cho Hecatech (pilot: dự án XKMVN).

## Bạn cần làm gì — theo đúng thứ tự

### Bước 1 — Test cả 2 agent ngay trên máy bạn (20 phút, không cần IT)
Mục đích: thấy agent chạy thật, kiểm tra output có đúng ý không, TRƯỚC KHI đầu tư vào n8n.

```bash
cd "/Users/admin/Desktop/Hecatech Agent"

# 1. Cài thư viện (1 lần duy nhất)
pip3 install anthropic

# 2. Lấy Claude API key tại https://console.anthropic.com → Settings → API Keys
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# 3a. Test PER-PROJECT agent (Agent #1 - warning cho group XKMVN)
python3 test_local.py sample_data.json

# 3b. Test CEO BRIEFING agent (Agent #5 - tổng hợp 11 dự án cho CEO)
python3 test_ceo_briefing.py sample_all_projects_outputs.json
```

**Per-project agent** sẽ:
- Đọc data XKMVN mẫu (ngày 12/04/2026)
- In ra warning: Take Rate đỏ, CPA vàng, margin cảnh báo + owner + hành động

**CEO Briefing agent** sẽ:
- Tổng hợp output của 11 dự án (VN + Thailand + Malaysia + Philippines)
- In ra 1 bản tin: GMV tổng, Top 3 / Bottom 3, 3 quyết định CEO phải làm hôm nay, cross-project patterns

**Nếu output OK** → chuyển sang Bước 2.
**Nếu cần điều chỉnh giọng văn/format/logic** → sửa prompt file tương ứng và chạy lại (miễn phí vì chưa lên production).

### Bước 2 — Review & Approve (30 phút với SaoBT)
- Gửi `benchmark_config.csv` cho SaoBT xác nhận benchmark thực tế tháng 4/2026
- Import vào Google Sheets mới tên "Agent Benchmark Config"
- Share quyền Viewer cho IT team

### Bước 3 — IT Team setup production (2-3 ngày)
Gửi cho IT team các file:
- `n8n_workflow.json` — import trực tiếp vào n8n
- `prompt_system.md` — paste vào node Claude API
- Hướng dẫn kết nối Google Sheets + Lark bot (xem section "Setup Guide" bên dưới)

### Bước 4 — Pilot 1 tuần với XKMVN
- Chạy chỉ group XKMVN + group CEO Briefing
- Mỗi sáng xem output, feedback cho tôi
- Sau 5-7 ngày nếu ổn → scale sang KTMR

### Bước 5 — Scale full (Tuần 3-4)
- Mở 11 dự án + group Vận hành + group Booking
- Upgrade lên Custom App Bot (2 chiều, nhân viên @mention bot để hỏi)

---

## Setup Guide cho IT Team

### 3.1 n8n
- Đăng ký n8n Cloud Starter ($20/tháng) tại https://n8n.io
- Import file `n8n_workflow.json` (menu: Workflows → Import from File)
- 3 credentials cần điền:
  - **Google Sheets**: Service Account JSON key
  - **Anthropic API**: key từ https://console.anthropic.com
  - **Lark Webhook**: URL từ mỗi group Lark (Settings → Bots → Custom Bot)

### 3.2 Google Sheets
Cần 3 sheet trên Google Drive (share Service Account quyền Viewer):
1. **Dashboard Tracking Masterplan** (đã có sẵn, realtime từ TikTok/Shopee)
2. **Agent Benchmark Config** (tạo mới, import từ `benchmark_config.csv`)
3. **Agent Daily Log** (tạo mới, n8n tự ghi)

### 3.3 Lark
Giai đoạn 1 (Notification Bot — 1 chiều):
- Mỗi group dự án → Settings → Bots → Add Custom Bot → copy Webhook URL
- Lưu URL vào n8n credentials, KHÔNG lưu vào file config (bảo mật)

Giai đoạn 2 (Custom App Bot — 2 chiều): xem section trong prompt_system.md.

---

## Chi phí vận hành

| Hạng mục | Chi phí/tháng |
|----------|---------------|
| n8n Cloud Starter | $20 |
| Claude API — morning briefing (30 lần × ~$0.05) | $1.5 |
| Claude API — interactive bot (~50 câu hỏi/ngày) | $30-60 |
| Lark Bot + Google Sheets API | $0 |
| **TỔNG giai đoạn 1 (chưa interactive)** | **~$22** |
| **TỔNG giai đoạn 2 (full interactive)** | **~$80** |

---

## File trong package

### Per-project Agent (Agent #1 — Morning Warning)
| File | Mục đích | Ai dùng |
|------|----------|---------|
| `prompt_system.md` | "Bộ não" per-project agent | IT paste vào n8n |
| `benchmark_config.csv` | Config benchmark per-project | SaoBT review → Google Sheets |
| `sample_data.json` | Data mẫu XKMVN để test | CEO (test local) |
| `test_local.py` | Prototype per-project chạy local | CEO chạy Bước 1 |

### CEO Briefing Agent (Agent #5 — tổng hợp 11 dự án)
| File | Mục đích | Ai dùng |
|------|----------|---------|
| `prompt_ceo_briefing.md` | "Bộ não" CEO aggregator | IT paste vào n8n |
| `sample_all_projects_outputs.json` | Mock output 11 dự án để test | CEO (test local) |
| `test_ceo_briefing.py` | Prototype CEO briefing | CEO chạy thử |

### Production
| File | Mục đích | Ai dùng |
|------|----------|---------|
| `n8n_workflow.json` | Workflow per-project production | IT team |

### Top level
| File | Mục đích |
|------|----------|
| `README.md` | File này — action plan |

---

## Thay đổi so với v1

Fix 5 lỗ hổng nghiêm trọng:
1. Model Claude: `claude-sonnet-4-20250514` → `claude-sonnet-4-6` (model hiện tại)
2. Embedded ma trận phễu v12 vào system prompt (trước đây chỉ reference)
3. Xử lý rõ khi thiếu data (Rate 6s, is_mega_day, ACC Audience): agent nói "cần check thủ công" thay vì đoán
4. Output format: JSON structured thay vì text tự do → parse 100% reliable
5. Thêm `benchmark_daily` formula vào config → agent biết so ngày với ngày

Fix 6 vấn đề medium: đồng bộ owner, bỏ stale context "12 ngày", định nghĩa rõ GMV Ads vs GMV Video, thêm `is_mega_day` flag, kill switch, rate limit interactive.
