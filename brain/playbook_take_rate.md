# Playbook: Xử Lý Take Rate Cao (>28%)

## Triệu chứng
- Take Rate > 28% → 🟡 Yellow
- Take Rate > 30% → 🔴 Red
- Thường xảy ra khi: ads spend tăng nhanh hơn organic GMV, TikTok điều chỉnh platform fee

## Bước 1 — Chẩn đoán (SaoBT, trong 30 phút)

1. Vào TikTok Ads Manager → Report → pull breakdown by campaign
2. Tìm campaign nào có ROAS < 2.0x → đó là "gánh nặng" chính
3. Check % Ads GMV vs Total GMV:
   - Nếu Ads GMV > 60% tổng → vấn đề cơ cấu, không chỉ bid
   - Nếu Ads GMV < 40% → có thể do Live/AFF giảm, không phải ads tăng

## Bước 2 — Hành động tức thì (SaoBT, trong ngày)

| Tình huống | Hành động |
|-----------|-----------|
| ROAS < 2x | Giảm bid 10-15%, không tắt campaign (tránh reset learning) |
| Budget burn nhanh | Đặt daily budget cap = 80% mức hiện tại |
| Ads GMV > 60% | Tăng Live thêm 1 session, push Affiliate booking |

## Bước 3 — Tăng Organic để hạ Take Rate

- **Live**: LinhDTH + MaiDN thêm 1 session/ngày, ưu tiên khung 20:00-22:00
- **Affiliate**: MaiDN push creator active, tăng commission 1-2% nếu cần
- **Video Organic**: TuND đăng 2-3 video/ngày không boost

## Bước 4 — Escalation (nếu > 3 ngày không cải thiện)

- SaoBT báo CEO + số liệu cụ thể
- CEO contact TikTok Account Manager để negotiate platform fee
- Cân nhắc tăng giá bán 5-8% để bù margin

## Bước 5 — Phòng ngừa

- Theo dõi Take Rate hàng ngày (cột trong Dashboard)
- Không để Ads GMV vượt 55% tổng GMV quá 5 ngày liên tiếp
- Rotate creative mỗi 7-10 ngày để duy trì CTR (giảm CPA → giảm Take Rate)

## SLA
- Yellow (>28%): xử lý trong 2 ngày
- Red (>30%): xử lý trong ngày, báo cáo CEO EOD

---
*Playbook v1 — cập nhật tháng 04/2026*
