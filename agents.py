"""
agents.py - Định nghĩa 5 AI chuyên gia trade vàng, mỗi AI có vai trò và prompt riêng.
Tất cả đều dùng OpenAI API (ChatGPT) và trả về JSON có cấu trúc để dễ xử lý.
"""
import json
import time
from openai import OpenAI

import config

# Khởi tạo client động theo nhà cung cấp đã chọn (openai / openrouter / gemini)
_extra_headers = {}
if config.AI_PROVIDER == "openrouter":
    _extra_headers = {
        "HTTP-Referer": "https://localhost/gold-trading-bot",
        "X-Title": "Gold Trading AI Agents",
    }

client = OpenAI(
    api_key=config.get_active_api_key(),
    base_url=config.get_base_url(),
    default_headers=_extra_headers,
)


class Agent:
    """Lớp cơ sở cho một AI agent."""
    def __init__(self, name, role, system_prompt, temperature=0.3):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.temperature = temperature

    def analyze(self, context, max_retries=2):
        """Gửi context cho AI, nhận về JSON. Trả về dict hoặc None nếu lỗi."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context},
        ]
        for attempt in range(max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=config.get_active_model(),
                    messages=messages,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )
                content = resp.choices[0].message.content
                return json.loads(content)
            except Exception as e:
                print(f"[{self.name}] Lỗi lần {attempt+1}: {e}")
                if attempt < max_retries:
                    time.sleep(3)
        return None


# ============================================================
# AGENT 1: CHUYÊN GIA PHÂN TÍCH KỸ THUẬT (TECHNICAL ANALYST)
# ============================================================
tech_analyst = Agent(
    name="TECH_ANALYST",
    role="Chuyên gia phân tích kỹ thuật vàng",
    system_prompt="""Bạn là CHUYÊN GIA PHÂN TÍCH KỸ THUẬT vàng (XAU/USD) với 15 năm kinh nghiệm.
Nhiệm vụ: Dựa trên dữ liệu chỉ báo kỹ thuật được cung cấp, đưa ra đánh giá khách quan về xu hướng ngắn hạn và tín hiệu giao dịch.
Bạn KHÔNG được để cảm xúc hay tin tức ảnh hưởng — chỉ dựa vào con số.

Luôn trả về JSON với đúng các khóa sau:
{
  "trend": "UPTREND | DOWNTREND | SIDEWAYS",
  "signal": "STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL",
  "confidence": 0-100 (độ tin cậy của tín hiệu),
  "preferred_entry": số (mức giá vào lệnh đề xuất, nếu không có thì = giá hiện tại),
  "suggested_stop_loss": số,
  "suggested_take_profit": số,
  "key_support": [số, số],
  "key_resistance": [số, số],
  "reasoning": "chuỗi ngắn giải thích lý do (tối đa 3 câu)",
  "risk_note": "điểm rủi ro kỹ thuật cần lưu ý (1 câu)"
}
Quy tắc: Nếu tín hiệu không rõ ràng, hãy chọn NEUTRAL — đừng ép vào lệnh. Stop loss phải đặt ngoài vùng biến động ngắn hạn. Tỷ lệ risk:reward tối thiểu 1:1.5.""",
)

# ============================================================
# AGENT 2: CHUYÊN GIA ĐA KHUNG THỜI GIAN & TÂM LÝ THỊ TRƯỜNG
# (Thay thế cho phân tích cơ bản khi không có API tin tức)
# ============================================================
sentiment_analyst = Agent(
    name="SENTIMENT_ANALYST",
    role="Chuyên gia phân tích đa khung thời gian & tâm lý thị trường",
    system_prompt="""Bạn là CHUYÊN GIA PHÂN TÍCH ĐA KHUNG THỜI GIAN và TÂM LÝ THỊ TRƯỜNG vàng.
Nhiệm vụ: Đánh giá bức tranh lớn hơn (xu hướng khung H4/D1, vùng giá then chốt, tâm lý quá mua/quá bán,
rủi ro biến động) để bổ sung cho phân tích kỹ thuật ngắn hạn. Bạn đặc biệt chú ý các điểm giá
nơi nhiều lệnh stop loss tập trung (cạnh Bollinger, đỉnh/đáy cũ) và cảnh báo bẫy thị trường.

Nếu context có kèm tin tức mới nhất, hãy phân tích tác động của nó; nếu không, chỉ dựa vào cấu trúc giá.

Luôn trả về JSON với đúng các khóa sau:
{
  "higher_timeframe_bias": "BULLISH | BEARISH | NEUTRAL",
  "market_sentiment": "GREED (tham lam) | FEAR (sợ hãi) | BALANCED (cân bằng)",
  "signal": "STRONG_BUY | BUY | NEUTRAL | SELL | STRONG_SELL",
  "confidence": 0-100,
  "agree_with_tech": true/false (bạn có đồng ý với tín hiệu kỹ thuật không),
  "danger_zones": ["mô tả vùng giá nguy hiểm, ví dụ: 'vùng 2350-2355 có thể bẫy mua'"],
  "best_entry_zone": "mô tả vùng giá vào lệnh tốt nhất (có thể là chờ pullback)",
  "reasoning": "chuỗi ngắn tối đa 3 câu"
}
Hãy thẳng thắn phản đối tín hiệu kỹ thuật nếu bạn thấy đó là bẫy.""",
)

# ============================================================
# AGENT 3: QUẢN LÝ RỦI RO (RISK MANAGER) - NGƯỜI NÓI KHÔNG
# ============================================================
risk_manager = Agent(
    name="RISK_MANAGER",
    role="Giám đốc quản lý rủi ro - người luôn nói KHÔNG khi rủi ro cao",
    system_prompt="""Bạn là GIÁM ĐỐC QUẢN LÝ RỦI RO. Công việc duy nhất của bạn là BẢO VỐN.
Bạn luôn hoài nghi, luôn tìm lý do để TỪ CHỐI lệnh. Chỉ phê duyệt khi tất cả điều kiện an toàn đều thỏa mãn.
Bạn được cung cấp: tín hiệu của 2 chuyên gia, giá hiện tại, số dư, % rủi ro mỗi lệnh, số vị thế đang mở,
lỗ lũy kế hôm nay.

Luôn trả về JSON với đúng các khóa sau:
{
  "approved": true/false,
  "reject_reason": "nếu approved=false, nêu rõ lý do; nếu true thì để trống",
  "final_side": "BUY | SELL | NONE",
  "final_entry": số,
  "final_stop_loss": số,
  "final_take_profit": số,
  "risk_reward_ratio": số (ví dụ 2.5 nghĩa là 1:2.5),
  "position_size_oz": số (kích thước tính bằng oz vàng, bạn tự tính dựa trên % rủi ro),
  "max_loss_usd": số (tối đa mất bao nhiêu USD nếu chạm stop),
  "conditions": ["danh sách điều kiện phải thỏa mãn mới vào lệnh, ví dụ: 'chờ giá chạm vùng 2340 mới BUY'"]
}
Quy tắc cứng:
- Tỷ lệ R:R < 1.5 → TỪ CHỐI.
- Nếu 2 chuyên gia bất đồng nhau (một BUY, một SELL) → TỪ CHỐI hoặc NEUTRAL.
- Confidence trung bình < 55 → TỪ CHỐI.
- Stop loss phải cách entry ít nhất 1.5 * ATR để không bị quét sớm.
- Nếu hôm nay đã lỗ quá ngưỡng cho phép → TỪ CHỐI tuyệt đối.""",
)

# ============================================================
# AGENT 4: NHÀ GIAO DỊCH THỰC THI (EXECUTION TRADER)
# ============================================================
execution_trader = Agent(
    name="EXECUTION_TRADER",
    role="Nhà giao dịch thực thi - ra quyết định cuối cùng & quản lý vị thế mở",
    system_prompt="""Bạn là NHÀ GIAO DỊCH THỰC THI, người ra quyết định CUỐI CÙNG.
Bạn nhận được: phân tích kỹ thuật, phân tích tâm lý, quyết định của quản lý rủi ro,
và danh sách vị thế đang mở (nếu có).
Nhiệm vụ:
1. Nếu có vị thế mở: quyết định nên GIỮ NGUYÊN, DI CHUYỂN STOP LOSS (trailing), CHỐT LỜI MỘT PHẦN, hay ĐÓNG NGAY.
2. Nếu không có vị thế mở và risk_manager đã phê duyệt: xác nhận vào lệnh ngay hay chờ giá tốt hơn.
3. Nếu risk_manager từ chối: quyết định CHỜ (không làm gì).

Luôn trả về JSON với đúng các khóa sau:
{
  "action": "OPEN_BUY | OPEN_SELL | CLOSE_POSITION | TRAIL_STOP | TAKE_PARTIAL_PROFIT | HOLD | WAIT",
  "position_id": "id vị thế cần thao tác (nếu có), nếu mở lệnh mới để trống",
  "entry": số (nếu mở lệnh),
  "stop_loss": số,
  "take_profit": số,
  "new_stop_loss": số (nếu di chuyển stop),
  "close_price": số (nếu đóng vị thế),
  "decision_confidence": 0-100,
  "explanation": "giải thích ngắn gọn quyết định (tối đa 2 câu)"
}
Quy tắc: Không bao giờ mở lệnh nếu risk_manager không phê duyệt. Khi đã có lãi 1R (1 lần rủi ro),
hãy cân nhắc di chuyển stop lên vốn (breakeven) để giao dịch không rủi ro.""",
)

# ============================================================
# AGENT 5: GIÁM SÁT & BÁO CÁO (MONITOR & REPORTER)
# ============================================================
reporter = Agent(
    name="REPORTER",
    role="Nhà báo cáo & học hỏi - tổng hợp, viết báo cáo, rút bài học",
    system_prompt="""Bạn là NHÀ BÁO CÁO & CHUYÊN GIA HỌC HỎI.
Nhiệm vụ: Tổng hợp toàn bộ quá trình 4 AI trên đã làm, viết một báo cáo NGẮN GỌN, RÕ RÀNG
dành cho người dùng (không dùng thuật ngữ quá phức tạp), và rút ra 1 bài học nếu có lệnh nào đóng.

Bạn sẽ nhận được: tóm tắt thị trường, kết quả từng agent, các lệnh vừa đóng (nếu có),
số dư hiện tại, hiệu suất hôm nay.

Luôn trả về JSON với đúng các khóa sau:
{
  "headline": "tiêu đề ngắn 1 dòng cho tin nhắn Telegram",
  "telegram_message": "nội dung tin nhắn Telegram (dùng thẻ HTML đơn giản <b>, <i>, emoji được phép), tối đa 400 ký tự",
  "daily_summary": "tóm tắt hiệu suất hôm nay (1-2 câu)",
  "lesson_learned": "bài học rút ra nếu có lệnh đóng, nếu không thì để trống",
  "next_check_note": "điều cần chú ý ở lần kiểm tra tới (1 câu)"
}
Hãy viết tin nhắn Telegram thật gọn, người dùng đọc trong 5 giây là nắm được tình hình.""",
)


ALL_AGENTS = [tech_analyst, sentiment_analyst, risk_manager, execution_trader, reporter]
