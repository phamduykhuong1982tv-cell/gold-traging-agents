# 🤖 Hệ thống 5 AI Trade Vàng Tự Động (XAU/USD)

5 AI chuyên gia hợp tác phân tích, ra quyết định và trade mô phỏng vàng 24/5,
báo cáo kết quả về Telegram của bạn. **Mặc định chạy ở chế độ MÔ PHỎNG (không mất tiền thật).**

---

## 🧠 5 AI trong đội ngũ

| AI | Vai trò | Nhiệm vụ |
|---|---|---|
| **TECH_ANALYST** | Chuyên gia phân tích kỹ thuật | Đọc RSI, MACD, EMA, Bollinger, Stochastic, ADX → đưa tín hiệu BUY/SELL/NEUTRAL |
| **SENTIMENT_ANALYST** | Chuyên gia đa khung thời gian & tâm lý | Xem bức tranh lớn, cảnh báo bẫy thị trường, xác nhận/đối lập với phân tích kỹ thuật |
| **RISK_MANAGER** | Giám đốc rủi ro (người luôn nói KHÔNG) | Chỉ phê duyệt lệnh khi tỷ lệ R:R ≥ 1.5, độ tin cậy đủ cao, chưa vượt ngưỡng lỗ ngày |
| **EXECUTION_TRADER** | Nhà giao dịch thực thi | Quyết định cuối: vào lệnh, chờ, di chuyển stop, chốt lời, đóng vị thế |
| **REPORTER** | Giám sát & báo cáo | Tổng hợp, gửi báo cáo Telegram ngắn gọn, rút bài học |

**Luồng làm việc mỗi 30 phút:** Lấy dữ liệu giá → Kiểm tra vị thế mở có chạm SL/TP không →
5 AI lần lượt phân tích & tranh luận → Thực thi (mô phỏng) → Gửi báo cáo Telegram.

---

## 🚀 Cài đặt & Chạy (5 phút)

### Bước 1: Cài Python 3.10+ và thư viện
```bash
pip install -r requirements.txt
```

### Bước 2: Cấu hình
Sao chép file `.env.example` thành `.env`, rồi điền:
```ini
OPENAI_API_KEY=sk-...của-bạn...
OPENAI_MODEL=gpt-4o          # hoặc gpt-4o-mini để rẻ hơn ~10 lần
TRADE_MODE=PAPER              # GIỮ NGUYÊN PAPER, đừng đổi sang LIVE
INITIAL_BALANCE=10000         # vốn mô phỏng (USD)
CHECK_INTERVAL_MINUTES=30     # kiểm tra thị trường mỗi 30 phút
```

**Tùy chọn nhưng khuyến nghị — Telegram bot:**
1. Mở Telegram, chat với `@BotFather` → gửi `/newbot` → lấy `TELEGRAM_BOT_TOKEN`
2. Chat với `@userinfobot` → gửi `/start` → lấy `TELEGRAM_CHAT_ID`
3. Điền 2 giá trị này vào `.env`

### Bước 3: Chạy
```bash
python main.py
```
Xem log trên màn hình và nhận báo cáo trên Telegram. File `trading_state.json`
lưu trạng thái (số dư, vị thế mở, lịch sử lệnh) — đừng xóa.

---

## ☁️ Chạy 24/7 trên cloud (miễn phí) khi bạn tắt máy

### Cách dễ nhất: Render.com (miễn phí)
1. Đăng ký [render.com](https://render.com) bằng GitHub
2. Upload toàn bộ project này lên một repo GitHub riêng (để `.env` ra ngoài, dùng Secret Environment Variables trên Render)
3. Trên Render → **New +** → **Background Worker** → chọn repo của bạn
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. Trong **Environment** điền các biến từ file `.env` (đặc biệt `OPENAI_API_KEY`)
7. Deploy → hệ thống chạy 24/7, tự khởi động lại nếu bị lỗi.

> Lưu ý: gói free Render có thể ngủ sau 15 phút không có request, nhưng **Background Worker**
> thì chạy liên tục. Nếu thấy ngắt quãng, dùng gói Starter (~7$/tháng) hoặc dịch vụ khác
> như Railway, Fly.io, hay một VPS (Vultr/DigitalOcean ~5$/tháng).

### Cách khác: VPS + systemd / tmux
```bash
tmux new -s gold
python main.py
# Nhấn Ctrl+B rồi D để rời session (vẫn chạy nền). Vào lại: tmux attach -t gold
```

---

## ⚠️ Cảnh báo an toàn & Rủi ro (đọc kỹ trước khi dùng tiền thật)

1. **Hệ thống này là công cụ học tập & nghiên cứu, KHÔNG phải lời khuyên đầu tư.**
2. **Mặc định PAPER TRADING** — không có code nào thực hiện lệnh thật. Hàm `execute_live_order()`
   trong `tools.py` cố ý để trống.
3. **Nếu bạn muốn trade thật:**
   - Chạy mô phỏng ÍT NHẤT 2–4 tuần, ghi lại hiệu suất thực tế.
   - Tự tích hợp API sàn (MetaTrader5, OANDA, Interactive Brokers) vào `execute_live_order()`.
   - **Bắt buộc** thêm bước chờ bạn phê duyệt qua Telegram trước mỗi lệnh thật —
     đừng bao giờ để AI tự mở lệnh tiền thật.
   - Bắt đầu với vốn rất nhỏ (vài chục USD).
4. Chi phí API: mỗi chu kỳ gọi ~5 lần ChatGPT. Với `gpt-4o-mini`, chi phí ~0.01–0.03 USD/ngày;
   với `gpt-4o` ~0.2–0.5 USD/ngày.
5. Vàng giao dịch 24/5 (đóng cửa cuối tuần). Hệ thống tự nghỉ Thứ 7, Chủ Nhật.

---

## 🛠️ Tùy chỉnh

- **Đổi chiến lược:** Sửa `system_prompt` của từng agent trong `agents.py` — ví dụ dạy
  TECH_ANALYST dùng lý thuyết Elliott Wave, hoặc thêm quy tắc chỉ trade theo xu hướng lớn.
- **Thêm tin tức thật:** Đăng ký [NewsAPI](https://newsapi.org) (free tier), thêm hàm lấy
  tin tức vàng/USD/FED trong `tools.py` và nối vào context của SENTIMENT_ANALYST.
- **Đổi khung thời gian:** Sửa `interval="1h"` trong `main.py` thành `"15m"` / `"4h"` / `"1d"`.
- **Thêm chỉ báo:** Bổ sung trong `get_gold_data()` ở `tools.py` (thư viện `ta` có sẵn hơn 100 chỉ báo).

---

## 📁 Cấu trúc file
```
gold-trading-agents/
├── requirements.txt    # Danh sách thư viện
├── .env.example        # Mẫu cấu hình → sao chép thành .env
├── config.py           # Đọc cấu hình
├── tools.py            # Lấy dữ liệu, chỉ báo, paper trading, Telegram
├── agents.py           # Định nghĩa 5 AI + prompt riêng
├── main.py             # Lõi điều phối + vòng lặp 24/5
└── README.md           # File này
```

Chúc bạn vận hành an toàn và hiệu quả! 📈
