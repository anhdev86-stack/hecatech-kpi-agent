# Hecatech AI Agent System — Hướng Dẫn Setup Hoàn Chỉnh

## Tổng quan hệ thống

```
Google Sheets (Dashboard) 
    ↓ (đọc data realtime)
n8n (automation engine)
    ↓ (gửi data)
Claude AI (phân tích)
    ↓ (trả kết quả)
Lark Groups (nhận báo cáo + warning)
```

**3 workflow hoạt động:**
- `workflow_01`: CEO Briefing → 7:00 AM mỗi ngày → Lark CEO Group
- `workflow_02`: Project Warnings → 7:30 AM mỗi ngày → 11 Lark project groups
- `workflow_03`: Lark Interactive → khi nhân viên @mention bot → bot trả lời tức thì

---

## BƯỚC 1 — Tạo Google Service Account

> **Ai làm:** IT/HangTTT | **Thời gian:** 15-20 phút

1. Vào https://console.cloud.google.com
2. Tạo Project mới → đặt tên "Hecatech Agent"
3. Vào "APIs & Services" → Enable "Google Sheets API"
4. Vào "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
   - Application type: Web application
   - Authorized redirect URI: `https://[your-n8n-domain]/rest/oauth2-credential/callback`
5. Tải file JSON credentials → lưu lại

**Lấy Google Sheet ID:**
- Mở file Dashboard Tracking Masterplan trên Google Drive
- URL dạng: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
- Copy `[SHEET_ID]` — đây là giá trị `GOOGLE_SHEET_ID`

---

## BƯỚC 2 — Setup n8n Cloud

> **Ai làm:** IT/HangTTT | **Thời gian:** 10 phút

1. Đăng ký tại https://n8n.io → chọn plan "Starter" (~$20/tháng)
2. Đăng nhập vào n8n dashboard
3. Vào **Settings** → **n8n Settings** → đổi timezone thành `Asia/Ho_Chi_Minh`

---

## BƯỚC 3 — Lấy Anthropic API Key

> **Ai làm:** CEO/IT | **Thời gian:** 5 phút

1. Vào https://console.anthropic.com
2. Đăng ký/đăng nhập
3. Vào "API Keys" → "Create Key" → copy key (dạng `sk-ant-...`)
4. Nạp credit: $20 dùng được ~3-4 tháng (1 lần gọi/ngày cho CEO briefing)

---

## BƯỚC 4 — Kết nối Google Sheets vào n8n

> **Ai làm:** IT | **Thời gian:** 10 phút

1. Trong n8n, vào **Credentials** → **Add Credential** → chọn "Google Sheets OAuth2 API"
2. Upload file JSON credentials từ Bước 1
3. Authorize → đăng nhập Google account của công ty
4. Đặt tên credential: "Google Sheets Account"
5. **Lưu lại Credential ID** (sẽ cần điền vào workflow JSON)

---

## BƯỚC 5 — Tạo Lark Bots và lấy Webhook URLs

> **Ai làm:** IT hoặc bất kỳ ai có quyền admin Lark | **Thời gian:** 30 phút

### 5A. Webhook Bot (cho CEO Briefing và Project Warnings)

Làm cho **mỗi group** (CEO Group + 11 project groups):

1. Mở Lark group → nhấn vào tên group ở trên → "Settings"
2. Chọn "Bots" → "Add Bot" → "Custom Bot"
3. Đặt tên bot: "Hecatech AI Agent"
4. Copy **Webhook URL** (dạng `https://open.larksuite.com/open-apis/bot/v2/hook/xxx`)
5. Lưu vào bảng sau:

| Group | Webhook URL |
|-------|-------------|
| CEO Briefing | (điền vào) |
| XKMVN | (điền vào) |
| KTLVN | (điền vào) |
| TDCVN | (điền vào) |
| KTMVN | (điền vào) |
| MNVN | (điền vào) |
| KTMR | (điền vào) |
| SRMR | (điền vào) |
| KTLTL | (điền vào) |
| XKMTL | (điền vào) |
| XKMPH | (điền vào) |
| XKMMY | (điền vào) |

### 5B. Custom App Bot (cho Interactive Q&A — workflow 03)

1. Vào https://open.larksuite.com → "Create App"
2. Đặt tên: "Hecatech AI Assistant"
3. Vào "Permissions" → Enable:
   - `im:message:send_as_bot`
   - `im:message:readonly`
4. Vào "Event Subscriptions" → thêm event: `im.message.receive_v1`
5. Request URL: `https://[your-n8n-domain]/webhook/lark-chat`
6. Publish app → lấy **Bot Token** (dạng `t-xxx...`)

---

## BƯỚC 6 — Điền biến vào n8n

> **Ai làm:** IT | **Thời gian:** 10 phút

Trong n8n, vào **Settings** → **Variables** → thêm các biến:

| Tên biến | Giá trị |
|----------|---------|
| `GOOGLE_SHEET_ID` | ID của file Google Sheets Dashboard |
| `ANTHROPIC_API_KEY` | Key từ console.anthropic.com |
| `LARK_CEO_WEBHOOK_URL` | Webhook URL của CEO group |
| `LARK_XKMVN_WEBHOOK` | Webhook URL của group XKMVN |
| `LARK_KTLVN_WEBHOOK` | Webhook URL của group KTLVN |
| `LARK_TDCVN_WEBHOOK` | Webhook URL của group TDCVN |
| `LARK_KTMVN_WEBHOOK` | Webhook URL của group KTMVN |
| `LARK_MNVN_WEBHOOK` | Webhook URL của group MNVN |
| `LARK_KTMR_WEBHOOK` | Webhook URL của group KTMR |
| `LARK_SRMR_WEBHOOK` | Webhook URL của group SRMR |
| `LARK_KTLTL_WEBHOOK` | Webhook URL của group KTLTL |
| `LARK_XKMTL_WEBHOOK` | Webhook URL của group XKMTL |
| `LARK_XKMPH_WEBHOOK` | Webhook URL của group XKMPH |
| `LARK_XKMMY_WEBHOOK` | Webhook URL của group XKMMY |
| `LARK_BOT_TOKEN` | Bot Token từ Lark App (dành cho Webhook Interactive) |
| `LARK_ADS_WEBHOOK_URL` | Webhook URL của group Ads Team |
| `LARK_CS_WEBHOOK_URL` | Webhook URL của group Customer Service |
| `REVIEW_SHEET_ID` | ID của Google Sheet chứa review (có thể khác Dashboard Sheet) |
| `SUB_CEO_BRIEFING_ID` | (điền sau khi import) ID của SUB CEO Briefing workflow |
| `SUB_PROJECT_WARNINGS_ID` | (điền sau khi import) ID của SUB Project Warnings workflow |
| `SUB_ADS_OPTIMIZER_ID` | (điền sau khi import) ID của SUB Ads Optimizer workflow |
| `SUB_REVIEW_MGMT_ID` | (điền sau khi import) ID của SUB Review Management workflow |
| `SUB_COMPETITIVE_INTEL_ID` | (điền sau khi import) ID của SUB Competitive Intelligence workflow |
| `SUB_CONTENT_PRODUCTION_ID` | (điền sau khi import) ID của SUB Content Production workflow |
| `COMPETITOR_SHEET_ID` | ID của Google Sheet theo dõi đối thủ cạnh tranh |
| `KALODATA_API_URL` | URL API Kalodata (nếu có) — bỏ qua nếu không dùng |
| `KALODATA_API_KEY` | API Key của Kalodata (nếu có) |
| `LARK_LEADERS_WEBHOOK_URL` | Webhook URL của group Leaders (nhận Competitive Intel briefing) |

---

## BƯỚC 7 — Import Workflows vào n8n

> **Ai làm:** IT | **Thời gian:** 15 phút

1. Trong n8n, vào **Workflows** → **Import from File**
2. Import theo đúng thứ tự này (quan trọng — sub-workflows phải import trước):
   - `SUB_ceo_briefing.json`
   - `SUB_project_warnings.json`
   - `SUB_ads_optimizer.json`
   - `SUB_review_management.json`
   - `SUB_competitive_intel.json`
   - `SUB_content_production.json`
   - `WEBHOOK_lark_interactive.json`
   - `MAIN_orchestrator.json` ← import cuối cùng
3. Sau khi import, vào từng workflow, mở từng Google Sheets node và:
   - Thay `REPLACE_WITH_CREDENTIAL_ID` bằng Credential ID thực (từ Bước 4)
4. **Lấy Workflow ID của tất cả sub-workflows:**
   - Mở từng SUB workflow → URL dạng `/workflow/[ID]` → copy ID
5. Thêm các biến vào n8n Variables (Bước 6):
   - `SUB_CEO_BRIEFING_ID` = ID của SUB CEO Briefing
   - `SUB_PROJECT_WARNINGS_ID` = ID của SUB Project Warnings
   - `SUB_ADS_OPTIMIZER_ID` = ID của SUB Ads Optimizer
   - `SUB_REVIEW_MGMT_ID` = ID của SUB Review Management
   - `SUB_COMPETITIVE_INTEL_ID` = ID của SUB Competitive Intelligence
   - `SUB_CONTENT_PRODUCTION_ID` = ID của SUB Content Production
6. Lưu tất cả workflows

---

## BƯỚC 8 — Test trước khi bật

> **Ai làm:** IT + CEO | **Thời gian:** 20 phút

### Test Sub-workflows riêng lẻ trước:
1. Mở `SUB CEO Briefing` → "Test workflow" → kiểm tra từng node ✅
2. Mở `SUB Project Warnings` → Test → kiểm tra từng node ✅

### Test MAIN Orchestrator:
1. Mở `MAIN Orchestrator` → nhấn "Test workflow" (chạy ngay không đợi 7AM)
2. Quan sát từng node chạy theo thứ tự:
   - Read Báo Cáo ✅ → Read Tổng Hợp ✅ → Transform ✅
   - EXEC SUB CEO Briefing ✅ → kiểm tra Lark CEO Group nhận được message
   - EXEC SUB All Project Warnings ✅ → kiểm tra từng group project
3. Nếu lỗi ở "EXEC SUB" node → kiểm tra biến `SUB_CEO_BRIEFING_ID` và `SUB_PROJECT_WARNINGS_ID` đã đúng chưa

### Test WEBHOOK Interactive:
1. Bật toggle **Active** cho `WEBHOOK Lark Interactive`
2. Vào Lark group, @mention bot: "@Hecatech AI XKMVN hôm qua doanh số bao nhiêu?"
3. Bot nên trả lời trong 10-15 giây

---

## BƯỚC 9 — Bật chính thức

Sau khi test OK:
1. Bật toggle **Active** cho workflow 01 và 02
2. Workflow 03 đã active từ bước test
3. Ngày hôm sau lúc 7:00 AM và 7:30 AM, agent sẽ tự chạy

---

## Bảng chi phí hàng tháng

| Dịch vụ | Chi phí |
|---------|---------|
| n8n Cloud (Starter) | ~$20/tháng |
| Claude API — CEO Briefing (1 lần/ngày, Mon-Sat) | ~$3-5/tháng |
| Claude API — Project Warnings (11 projects/ngày) | ~$10-15/tháng |
| Claude API — Ads Optimizer (1 lần/ngày) | ~$2-3/tháng |
| Claude API — Review Management (1 lần/ngày) | ~$3-5/tháng |
| Claude API — Competitive Intel (1 lần/tuần, thứ Hai) | ~$1-2/tháng |
| Claude API — Content Production (1 lần/tuần, thứ Hai) | ~$1-2/tháng |
| Claude API — Interactive Q&A (~20 câu hỏi/ngày) | ~$5-8/tháng |
| Google Cloud (miễn phí với lượng nhỏ) | $0 |
| **Tổng** | **~$45-60/tháng** |

---

## Xử lý sự cố thường gặp

| Lỗi | Nguyên nhân | Cách fix |
|-----|------------|---------|
| Google Sheets không đọc được | Sai Sheet ID hoặc credential hết hạn | Kiểm tra lại biến GOOGLE_SHEET_ID, re-authorize credential |
| Lark không nhận được message | Sai Webhook URL | Copy lại webhook URL từ Lark group settings |
| Claude trả về lỗi 401 | API key sai hoặc hết credit | Kiểm tra key, nạp thêm credit |
| Workflow không tự chạy lúc 7AM | Sai timezone n8n | Vào Settings → đổi timezone sang Asia/Ho_Chi_Minh |
| Bot không trả lời @mention | Lark App chưa được approve | Publish app trong Lark Developer Console |

---

## Liên hệ hỗ trợ
- n8n docs: https://docs.n8n.io
- Lark API: https://open.larksuite.com/document
- Anthropic API: https://docs.anthropic.com
