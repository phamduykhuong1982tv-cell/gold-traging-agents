"""
config.py - Đọc cấu hình từ file .env
Hỗ trợ 3 nhà cung cấp API: openai / openrouter / gemini (chỉ cần đổi 1 dòng)
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ===== CHỌN NHÀ CUNG CẤP API =====
# Các giá trị hợp lệ: "openai" | "openrouter" | "gemini"
# - openai:    dùng API OpenAI trực tiếp (cần VPN ở Việt Nam, đã nạp tiền)
# - openrouter: dùng OpenRouter (không cần VPN, hỗ trợ thanh toán quốc tế, gom nhiều model)
# - gemini:    dùng Google Gemini (không cần VPN, CÓ BẢN MIỄN PHÍ, dễ lấy key nhất)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

# ===== API KEYS (điền key tương ứng với provider đã chọn) =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# ===== MODEL THEO TỪNG PROVIDER =====
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3.8-flash-exp:free")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# ===== Telegram =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ===== Trade =====
TRADE_MODE = os.getenv("TRADE_MODE", "PAPER").upper()  # PAPER hoặc LIVE
INITIAL_BALANCE = float(os.getenv("INITIAL_BALANCE", "10000"))
RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", "1.5"))
MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "3"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "1"))
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "30"))
GOLD_SYMBOL = os.getenv("GOLD_SYMBOL", "GC=F")

# ===== File lưu trạng thái =====
STATE_FILE = "trading_state.json"
LOG_FILE = "trading_log.txt"


def get_active_api_key():
    """Trả về API key của provider đang được chọn."""
    if AI_PROVIDER == "openai":
        return OPENAI_API_KEY
    if AI_PROVIDER == "openrouter":
        return OPENROUTER_API_KEY
    if AI_PROVIDER == "gemini":
        return GEMINI_API_KEY
    return ""


def get_active_model():
    """Trả về tên model của provider đang được chọn."""
    if AI_PROVIDER == "openai":
        return OPENAI_MODEL
    if AI_PROVIDER == "openrouter":
        return OPENROUTER_MODEL
    if AI_PROVIDER == "gemini":
        return GEMINI_MODEL
    return OPENAI_MODEL


def get_base_url():
    """Trả về base_url tương thích OpenAI cho từng provider."""
    if AI_PROVIDER == "openrouter":
        return "https://openrouter.ai/api/v1"
    if AI_PROVIDER == "gemini":
        # Google cung cấp endpoint tương thích OpenAI
        return "https://generativelanguage.googleapis.com/v1beta/openai/"
    return None  # OpenAI dùng mặc định


def validate_config():
    """Kiểm tra cấu hình cơ bản, trả về danh sách lỗi (nếu có)"""
    errors = []
    if AI_PROVIDER not in ("openai", "openrouter", "gemini"):
        errors.append("AI_PROVIDER chỉ được là: openai, openrouter, hoặc gemini")

    key = get_active_api_key()
    if not key or key in ("sk-xxx", "your-key-here", ""):
        errors.append(f"Chưa điền API key cho provider '{AI_PROVIDER}' trong file .env")

    if TRADE_MODE not in ("PAPER", "LIVE"):
        errors.append("TRADE_MODE chỉ được là PAPER hoặc LIVE")
    if TRADE_MODE == "LIVE":
        errors.append(
            "CHẾ ĐỘ LIVE CHƯA ĐƯỢC TÍCH HỢP SÀN. Hãy giữ PAPER cho đến khi bạn "
            "tự tích hợp API sàn (MT5/OANDA/IBKR) vào hàm execute_live_order() trong tools.py"
        )
    return errors
