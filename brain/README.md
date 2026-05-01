# BRAIN — Kho Kiến Thức AI Agent Hecatech

## Đây là gì?

Thư mục này là **bộ não** của AI Agent. Mỗi lần agent chạy và phân tích dữ liệu,
nó sẽ đọc **tất cả tài liệu trong thư mục này** trước khi đưa ra khuyến nghị.

Agent **bắt buộc** tham chiếu tài liệu ở đây khi đề xuất giải pháp.
Nếu có playbook phù hợp → follow đúng playbook.
Nếu chưa có → agent sẽ ghi rõ "chưa có playbook cho case này".

---

## Cách thêm tài liệu

1. Tạo file `.md` hoặc `.txt` trong thư mục này
2. Đặt tên rõ ràng, dùng tiền tố để phân loại:
   - `playbook_*.md` — SOP / quy trình xử lý sự cố
   - `strategy_*.md` — Chiến lược, định hướng
   - `product_*.md` — Thông tin sản phẩm
   - `team_*.md` — Thông tin team, phân công
   - `market_*.md` — Phân tích thị trường
   - `funnel_*.md` — Funnel Matrix, benchmark KPI
   - `ifthen_*.md` — Bảng giám sát rủi ro IF-THEN từng dự án
3. Không cần format đặc biệt — agent đọc được text thuần

---

## Loại tài liệu nên đặt vào đây

| Loại | Ví dụ |
|------|-------|
| Playbook xử lý sự cố | SOP khi Take Rate >30%, khi ROAS <2x |
| Chiến lược TikTok | Bid strategy, creative rotation, mega day plan |
| Thông tin sản phẩm | USP từng SKU, giá bán, margin target |
| Phân công team | Ai chịu trách nhiệm gì, escalation path |
| Benchmark & target | Target tháng/quý, KPI từng dự án |
| Lesson learned | Các case đã xảy ra và cách giải quyết |

---

## Giới hạn

- File hỗ trợ: `.md`, `.txt`
- PDF/Word: copy text → paste vào file `.md` mới
- Số lượng file: không giới hạn (Claude đọc được ~150,000 từ)
- File bắt đầu bằng `_` sẽ bị bỏ qua (dùng để draft)
