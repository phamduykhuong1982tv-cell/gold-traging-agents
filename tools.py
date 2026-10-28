"""
tools.py - Các công cụ hỗ trợ: lấy dữ liệu thị trường, chỉ báo kỹ thuật,
           paper trading, gửi Telegram, lưu trạng thái.
"""
import json
import os
from datetime import datetime, timezone
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

import config


# ============================================================
# 1. LẤY DỮ LIỆU THỊ TRƯỜNG VÀNG
# ============================================================
def get_gold_data(period="60d", interval="1h"):
    """
    Lấy dữ liệu lịch sử vàng từ yfinance (miễn phí).
    Trả về DataFrame với các cột: Open, High, Low, Close, Volume
    + các chỉ báo kỹ thuật đã tính sẵn.
    """
    ticker = yf.Ticker(config.GOLD_SYMBOL)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"Không lấy được dữ liệu cho {config.GOLD_SYMBOL}")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()

    # ----- Các chỉ báo kỹ thuật -----
    # EMA ngắn & dài
    df["EMA9"] = EMAIndicator(close=df["Close"], window=9).ema_indicator()
    df["EMA21"] = EMAIndicator(close=df["Close"], window=21).ema_indicator()
    df["EMA50"] = EMAIndicator(close=df["Close"], window=50).ema_indicator()

    # RSI (14)
    df["RSI"] = RSIIndicator(close=df["Close"], window=14).rsi()

    # MACD
    macd = MACD(close=df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_signal"] = macd.macd_signal()
    df["MACD_hist"] = macd.macd_diff()

    # Bollinger Bands (20, 2 std)
    bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
    df["BB_upper"] = bb.bollinger_hband()
    df["BB_middle"] = bb.bollinger_mavg()
    df["BB_lower"] = bb.bollinger_lband()

    # Stochastic
    stoch = StochasticOscillator(high=df["High"], low=df["Low"], close=df["Close"])
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()

    # ADX (độ mạnh xu hướng)
    adx = ADXIndicator(high=df["High"], low=df["Low"], close=df["Close"], window=14)
    df["ADX"] = adx.adx()

    # ATR (độ biến động - dùng để đặt stop loss)
    atr = AverageTrueRange(high=df["High"], low=df["Low"], close=df["Close"], window=14)
    df["ATR"] = atr.average_true_range()

    df = df.dropna()
    return df


def market_summary(df):
    """Trích xuất các con số quan trọng nhất từ dữ liệu gần nhất để gửi cho AI."""
    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = float(last["Close"])
    change_pct = float((last["Close"] - prev["Close"]) / prev["Close"] * 100)

    # Xu hướng EMA
    ema_trend = "TĂNG (uptrend)" if last["EMA9"] > last["EMA21"] > last["EMA50"] else \
                "GIẢM (downtrend)" if last["EMA9"] < last["EMA21"] < last["EMA50"] else \
                "ĐI NGANG (sideways/không rõ xu hướng)"

    # Tín hiệu MACD
    macd_signal = "BULLISH (cắt lên)" if last["MACD_hist"] > 0 and prev["MACD_hist"] <= 0 else \
                  "BEARISH (cắt xuống)" if last["MACD_hist"] < 0 and prev["MACD_hist"] >= 0 else \
                  ("Đang dương" if last["MACD_hist"] > 0 else "Đang âm")

    summary = {
        "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "symbol": config.GOLD_SYMBOL,
        "current_price": round(price, 2),
        "change_1bar_pct": round(change_pct, 2),
        "high_24h": round(float(df["High"].tail(24).max()), 2),
        "low_24h": round(float(df["Low"].tail(24).min()), 2),
        "RSI_14": round(float(last["RSI"]), 1),
        "RSI_status": "QUÁ MUA (>70)" if last["RSI"] > 70 else "QUÁ BÁN (<30)" if last["RSI"] < 30 else "TRUNG LẬP",
        "EMA9": round(float(last["EMA9"]), 2),
        "EMA21": round(float(last["EMA21"]), 2),
        "EMA50": round(float(last["EMA50"]), 2),
        "EMA_trend": ema_trend,
        "MACD": round(float(last["MACD"]), 2),
        "MACD_signal_line": round(float(last["MACD_signal"]), 2),
        "MACD_histogram": round(float(last["MACD_hist"]), 2),
        "MACD_signal": macd_signal,
        "BB_upper": round(float(last["BB_upper"]), 2),
        "BB_middle": round(float(last["BB_middle"]), 2),
        "BB_lower": round(float(last["BB_lower"]), 2),
        "Stoch_K": round(float(last["Stoch_K"]), 1),
        "Stoch_D": round(float(last["Stoch_D"]), 1),
        "ADX_14": round(float(last["ADX"]), 1),
        "ADX_trend_strength": "MẠNH (>25)" if last["ADX"] > 25 else "YẾU (<25, thị trường đi ngang)",
        "ATR_14": round(float(last["ATR"]), 2),
        "price_vs_BB": "Chạm BIÊN TRÊN (quá mua)" if price >= last["BB_upper"] else
                       "Chạm BIÊN DƯỚI (quá bán)" if price <= last["BB_lower"] else "Nằm trong dải Bollinger",
    }
    return summary


# ============================================================
# 2. PAPER TRADING ENGINE (MÔ PHỎNG GIAO DỊCH)
# ============================================================
def load_state():
    """Đọc trạng thái hiện tại (số dư, vị thế mở, lịch sử lệnh) từ file JSON."""
    if os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Trạng thái mặc định
    return {
        "balance": config.INITIAL_BALANCE,
        "equity_peak": config.INITIAL_BALANCE,
        "open_positions": [],   # [{id, side, entry, sl, tp, size, open_time}]
        "closed_trades": [],    # [{id, side, entry, exit, pnl, ...}]
        "daily_pnl": 0.0,
        "daily_trade_count": 0,
        "last_trade_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "trading_halted": False,
    }


def save_state(state):
    with open(config.STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def reset_daily_if_new_day(state):
    """Reset thống kê ngày nếu sang ngày mới."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("last_trade_date") != today:
        state["daily_pnl"] = 0.0
        state["daily_trade_count"] = 0
        state["last_trade_date"] = today
        state["trading_halted"] = False
    return state


def can_open_new_position(state):
    """Kiểm tra guardrails trước khi mở lệnh mới. Trả về (bool, lý_do)."""
    if state.get("trading_halted"):
        return False, "Đã dừng trade hôm nay do vượt ngưỡng tổn thất tối đa."
    if len(state["open_positions"]) >= config.MAX_OPEN_POSITIONS:
        return False, f"Đã đạt giới hạn {config.MAX_OPEN_POSITIONS} vị thế mở cùng lúc."
    daily_loss_limit = config.INITIAL_BALANCE * config.MAX_DAILY_LOSS_PERCENT / 100
    if state["daily_pnl"] <= -daily_loss_limit:
        state["trading_halted"] = True
        save_state(state)
        return False, f"Đã lỗ {abs(state['daily_pnl']):.2f} USD hôm nay, vượt ngưỡng {config.MAX_DAILY_LOSS_PERCENT}% -> TỰ ĐỘNG DỪNG."
    return True, "OK"


def calculate_position_size(entry, stop_loss, balance):
    """Tính kích thước vị thế dựa trên % rủi ro mỗi lệnh (position sizing chuẩn)."""
    risk_amount = balance * config.RISK_PER_TRADE_PERCENT / 100
    stop_distance = abs(entry - stop_loss)
    if stop_distance <= 0:
        return 0.0
    # size tính bằng oz vàng (1 lot chuẩn = 100 oz, ở đây tính oz thôi)
    size = risk_amount / stop_distance
    return round(size, 2)


def open_paper_position(state, side, entry, stop_loss, take_profit, reason=""):
    """Mở vị thế mô phỏng. side = 'BUY' hoặc 'SELL'."""
    allowed, reason_deny = can_open_new_position(state)
    if not allowed:
        return None, reason_deny

    size = calculate_position_size(entry, stop_loss, state["balance"])
    if size <= 0:
        return None, "Kích thước vị thế = 0 (khoảng cách stop loss không hợp lệ)."

    pos_id = f"P{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    position = {
        "id": pos_id,
        "side": side,
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "take_profit": round(take_profit, 2),
        "size": size,
        "open_time": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    }
    state["open_positions"].append(position)
    state["daily_trade_count"] += 1
    save_state(state)
    return position, "Mở lệnh thành công (mô phỏng)."


def close_position_at_price(state, position, exit_price):
    """Đóng vị thế mô phỏng tại giá exit_price, cập nhật P&L."""
    direction = 1 if position["side"] == "BUY" else -1
    pnl = direction * (exit_price - position["entry"]) * position["size"]
    state["balance"] += pnl
    state["daily_pnl"] += pnl
    state["equity_peak"] = max(state["equity_peak"], state["balance"])

    closed = {
        **position,
        "exit_price": round(exit_price, 2),
        "pnl": round(pnl, 2),
        "close_time": datetime.now(timezone.utc).isoformat(),
    }
    state["closed_trades"].append(closed)
    state["open_positions"] = [p for p in state["open_positions"] if p["id"] != position["id"]]
    save_state(state)
    return closed


def check_open_positions(state, current_price):
    """Kiểm tra các vị thế mở có chạm SL/TP không, đóng nếu có. Trả về danh sách lệnh vừa đóng."""
    closed_now = []
    for pos in list(state["open_positions"]):
        hit = None
        if pos["side"] == "BUY":
            if current_price <= pos["stop_loss"]:
                hit = pos["stop_loss"]
            elif current_price >= pos["take_profit"]:
                hit = pos["take_profit"]
        else:  # SELL
            if current_price >= pos["stop_loss"]:
                hit = pos["stop_loss"]
            elif current_price <= pos["take_profit"]:
                hit = pos["take_profit"]
        if hit is not None:
            closed = close_position_at_price(state, pos, hit)
            closed_now.append(closed)
    return closed_now


# ============================================================
# 3. GỬI TELEGRAM
# ============================================================
def send_telegram(message):
    """Gửi tin nhắn Telegram. Trả về True/False."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[Telegram] Chưa cấu hình bot, bỏ qua gửi tin.")
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Lỗi gửi: {e}")
        return False


# ============================================================
# 4. GHI LOG
# ============================================================
def log(msg):
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}"
    print(line)
    try:
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ============================================================
# 5. (ĐỂ TRỐNG) THỰC THI LỆNH THẬT - BẠN TỰ TÍCH HỢP SÀN
# ============================================================
def execute_live_order(side, entry, stop_loss, take_profit, size):
    """
    ⚠️ HÀM NÀY ĐỂ TRỐNG CỐ Ý.
    Nếu bạn muốn trade thật, hãy tích hợp API của sàn ở đây (ví dụ MetaTrader5,
    OANDA, Interactive Brokers, Binance Futures). Trả về dict chứa order_id.
    KHÔNG BAO GIỜ để hệ thống tự gọi hàm này mà không có cơ chế phê duyệt của bạn.
    """
    raise NotImplementedError(
        "Chế độ LIVE chưa được tích hợp. Hãy tự kết nối sàn của bạn vào hàm này "
        "và thêm bước chờ phê duyệt qua Telegram trước khi mở lệnh thật."
    )
