"""
main.py - Lõi điều phối: chạy 5 AI theo chu trình, trade mô phỏng, báo cáo Telegram.
Chạy: python main.py
"""
import sys
import time
from datetime import datetime, timezone

import config
import tools
from agents import tech_analyst, sentiment_analyst, risk_manager, execution_trader, reporter


def is_market_open():
    """
    Kiểm tra thị trường vàng có đang mở cửa không (ước lượng đơn giản theo UTC).
    Vàng giao dịch ~24/5: từ 22:00 UTC Chủ Nhật đến 21:00 UTC Thứ 6.
    Ở đây ta cho phép chạy Thứ 2 (0) đến hết Thứ 6 (4), bỏ qua cuối tuần cho an toàn.
    """
    now = datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Thứ2 ... 4=Thứ6, 5=Thứ7, 6=ChủNhật
    if weekday >= 5:
        return False
    return True


def build_context(summary, state, closed_this_round):
    """Dựng context (chuỗi text) gửi cho các AI agent."""
    open_pos_str = "KHÔNG CÓ"
    if state["open_positions"]:
        open_pos_str = "\n".join([
            f"- {p['id']} | {p['side']} | entry={p['entry']} | SL={p['stop_loss']} | TP={p['take_profit']} | size={p['size']} oz"
            for p in state["open_positions"]
        ])
    closed_str = "KHÔNG CÓ"
    if closed_this_round:
        closed_str = "\n".join([
            f"- {c['id']} | {c['side']} | PnL={c['pnl']} USD | đóng tại {c['exit_price']}"
            for c in closed_this_round
        ])

    ctx = f"""===== DỮ LIỆU THỊ TRƯỜNG VÀNG (lúc {summary['time_utc']}) =====
Symbol: {summary['symbol']}
Giá hiện tại: {summary['current_price']} USD
Thay đổi nến gần nhất: {summary['change_1bar_pct']}%
Đỉnh 24h: {summary['high_24h']} | Đáy 24h: {summary['low_24h']}

--- Chỉ báo kỹ thuật ---
RSI(14): {summary['RSI_14']} ({summary['RSI_status']})
EMA9={summary['EMA9']} | EMA21={summary['EMA21']} | EMA50={summary['EMA50']} → Xu hướng EMA: {summary['EMA_trend']}
MACD={summary['MACD']} | Signal={summary['MACD_signal_line']} | Histogram={summary['MACD_histogram']} → {summary['MACD_signal']}
Bollinger: Trên={summary['BB_upper']} | Giữa={summary['BB_middle']} | Dưới={summary['BB_lower']} → Giá {summary['price_vs_BB']}
Stochastic K={summary['Stoch_K']} | D={summary['Stoch_D']}
ADX(14)={summary['ADX_14']} → Độ mạnh xu hướng: {summary['ADX_trend_strength']}
ATR(14)={summary['ATR_14']} (độ biến động trung bình mỗi nến)
Hỗ trợ then chốt: gần nhất {summary['BB_lower']} và đáy 24h {summary['low_24h']}
Kháng cự then chốt: gần nhất {summary['BB_upper']} và đỉnh 24h {summary['high_24h']}

===== TRẠNG THÁI TÀI KHOẢN (MÔ PHỎNG) =====
Số dư: {state['balance']:.2f} USD (vốn gốc {config.INITIAL_BALANCE} USD)
Đỉnh vốn: {state['equity_peak']:.2f} USD
P&L hôm nay: {state['daily_pnl']:.2f} USD | Số lệnh hôm nay: {state['daily_trade_count']}
Rủi ro mỗi lệnh: {config.RISK_PER_TRADE_PERCENT}% vốn | Tổn thất tối đa/ngày: {config.MAX_DAILY_LOSS_PERCENT}%
Vị thế đang mở:
{open_pos_str}
Lệnh vừa đóng chu kỳ này:
{closed_str}
"""
    return ctx


def run_one_cycle():
    """Chạy một chu kỳ phân tích & quyết định đầy đủ."""
    tools.log("=" * 60)
    tools.log("Bắt đầu chu kỳ phân tích mới...")

    # 0. Kiểm tra thị trường mở cửa không
    if not is_market_open():
        tools.log("Thị trường vàng đang đóng cửa (cuối tuần). Nghỉ ngơi.")
        return

    # 1. Lấy dữ liệu & trạng thái
    try:
        df = tools.get_gold_data(period="60d", interval="1h")
    except Exception as e:
        tools.log(f"LỖI lấy dữ liệu: {e}")
        tools.send_telegram(f"⚠️ <b>Hệ thống trade vàng</b>\nKhông lấy được dữ liệu thị trường: {e}")
        return

    summary = tools.market_summary(df)
    current_price = summary["current_price"]

    state = tools.load_state()
    state = tools.reset_daily_if_new_day(state)

    # 2. Kiểm tra vị thế mở có chạm SL/TP không
    closed_this_round = tools.check_open_positions(state, current_price)
    if closed_this_round:
        for c in closed_this_round:
            tools.log(f"Đóng lệnh {c['id']} ({c['side']}) tại {c['exit_price']}, PnL = {c['pnl']:.2f} USD")
        tools.send_telegram(
            f"🔔 <b>Đóng lệnh tự động</b>\n" +
            "\n".join([f"{c['side']} {c['size']} oz → PnL: <b>{c['pnl']:+.2f} USD</b>" for c in closed_this_round]) +
            f"\nSố dư hiện tại: {state['balance']:.2f} USD"
        )

    # 3. Dựng context
    context = build_context(summary, state, closed_this_round)

    # 4. AGENT 1: Phân tích kỹ thuật
    tools.log("[1/5] Chuyên gia phân tích kỹ thuật đang làm việc...")
    tech_result = tech_analyst.analyze(context)
    if not tech_result:
        tools.log("Tech Analyst lỗi, bỏ qua chu kỳ này.")
        return
    tools.log(f"    → Tín hiệu: {tech_result.get('signal')} (độ tin cậy {tech_result.get('confidence')}%)")

    # 5. AGENT 2: Phân tích tâm lý & đa khung thời gian
    tools.log("[2/5] Chuyên gia tâm lý thị trường đang làm việc...")
    sentiment_context = context + f"\n\n===== KẾT QUẢ PHÂN TÍCH KỸ THUẬT =====\n{tech_result}"
    sentiment_result = sentiment_analyst.analyze(sentiment_context)
    if not sentiment_result:
        tools.log("Sentiment Analyst lỗi, bỏ qua chu kỳ này.")
        return
    tools.log(f"    → Tín hiệu: {sentiment_result.get('signal')} | Đồng ý kỹ thuật: {sentiment_result.get('agree_with_tech')}")

    # 6. AGENT 3: Quản lý rủi ro (người nói KHÔNG)
    tools.log("[3/5] Giám đốc rủi ro đang xem xét...")
    risk_context = context + (
        f"\n\n===== KẾT QUẢ PHÂN TÍCH KỸ THUẬT =====\n{tech_result}"
        f"\n\n===== KẾT QUẢ PHÂN TÍCH TÂM LÝ =====\n{sentiment_result}"
        f"\n\nGiá hiện tại: {current_price} | ATR={summary['ATR_14']}"
    )
    risk_result = risk_manager.analyze(risk_context)
    if not risk_result:
        tools.log("Risk Manager lỗi, bỏ qua chu kỳ này.")
        return
    approved = risk_result.get("approved", False)
    tools.log(f"    → Phê duyệt: {approved} | {risk_result.get('reject_reason', '')}")

    # 7. AGENT 4: Nhà giao dịch thực thi (quyết định cuối)
    tools.log("[4/5] Nhà giao dịch thực thi ra quyết định cuối...")
    exec_context = risk_context + f"\n\n===== QUYẾT ĐỊNH QUẢN LÝ RỦI RO =====\n{risk_result}"
    exec_result = execution_trader.analyze(exec_context)
    if not exec_result:
        tools.log("Execution Trader lỗi, bỏ qua chu kỳ này.")
        return
    action = exec_result.get("action", "WAIT")
    tools.log(f"    → Hành động: {action}")

    # 8. Thực thi hành động (chỉ MÔ PHỎNG, không trade thật)
    exec_note = ""
    if action in ("OPEN_BUY", "OPEN_SELL") and approved:
        side = "BUY" if action == "OPEN_BUY" else "SELL"
        entry = exec_result.get("entry") or risk_result.get("final_entry") or current_price
        sl = exec_result.get("stop_loss") or risk_result.get("final_stop_loss")
        tp = exec_result.get("take_profit") or risk_result.get("final_take_profit")
        pos, msg = tools.open_paper_position(
            state, side, entry=entry, stop_loss=sl, take_profit=tp,
            reason=f"Tech:{tech_result.get('signal')} | Sentiment:{sentiment_result.get('signal')}"
        )
        exec_note = f"{'✅' if pos else '❌'} Mở lệnh {side} mô phỏng: {msg}"
        if pos:
            tools.send_telegram(
                f"🟢 <b>LỆNH MỚI (MÔ PHỎNG)</b>\n"
                f"Khớp lệnh: <b>{side}</b> {pos['size']} oz tại {pos['entry']}\n"
                f"Stop Loss: {pos['stop_loss']} | Take Profit: {pos['take_profit']}\n"
                f"Rủi ro tối đa: {risk_result.get('max_loss_usd', '?')} USD\n"
                f"<i>Lý do: {pos['reason']}</i>"
            )
    elif action == "CLOSE_POSITION":
        pid = exec_result.get("position_id")
        close_price = exec_result.get("close_price") or current_price
        target = next((p for p in state["open_positions"] if p["id"] == pid), None)
        if target:
            closed = tools.close_position_at_price(state, target, close_price)
            exec_note = f"✅ Đóng thủ công {pid}, PnL = {closed['pnl']:+.2f} USD"
        else:
            exec_note = f"❌ Không tìm thấy vị thế {pid} để đóng"
    elif action == "TRAIL_STOP":
        pid = exec_result.get("position_id")
        new_sl = exec_result.get("new_stop_loss")
        for p in state["open_positions"]:
            if p["id"] == pid and new_sl:
                p["stop_loss"] = new_sl
                exec_note = f"✅ Di chuyển stop loss {pid} lên {new_sl}"
        tools.save_state(state)
    else:
        exec_note = "⏸️ Không hành động (chờ tín hiệu rõ ràng hơn)."

    tools.log(f"    → {exec_note}")

    # 9. AGENT 5: Báo cáo tổng hợp CUỐI NGÀY (chỉ gửi 1 lần/ngày, lúc ~20:00 giờ VN)
    # Các sự kiện quan trọng (mở/đóng lệnh) đã gửi Telegram riêng ở các bước trên.
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    # 13:00 UTC = 20:00 giờ Việt Nam (giờ vàng đóng cửa phiên châu Âu, thích hợp tổng hợp)
    is_daily_summary_time = now_utc.hour >= 13 and state.get("last_daily_summary_date") != today_str

    if is_daily_summary_time:
        tools.log("[5/5] Tổng hợp báo cáo cuối ngày...")
        report_context = (
            context +
            f"\n\n===== KẾT QUẢ 5 AGENT =====\n"
            f"Tech Analyst: {tech_result}\n"
            f"Sentiment Analyst: {sentiment_result}\n"
            f"Risk Manager: {risk_result}\n"
            f"Execution Trader: {exec_result} | Kết quả thực thi: {exec_note}\n"
            f"Số dư cuối: {state['balance']:.2f} USD"
        )
        report = reporter.analyze(report_context)
        if report:
            tg_msg = report.get("telegram_message", "")
            if tg_msg:
                tools.send_telegram(tg_msg)
            tools.log(f"Báo cáo cuối ngày: {report.get('headline', '')}")
        state["last_daily_summary_date"] = today_str
        tools.save_state(state)
    else:
        tools.log("[5/5] Bỏ qua báo cáo Telegram (chỉ gửi khi có lệnh + tổng hợp cuối ngày lúc 20:00 giờ VN)")

    tools.log(f"Kết thúc chu kỳ. Số dư: {state['balance']:.2f} USD")
    tools.log("=" * 60)


def main():
    # Kiểm tra cấu hình
    errors = config.validate_config()
    if errors:
        print("❌ CẤU HÌNH CHƯA HỢP LỆ:")
        for e in errors:
            print(f"  - {e}")
        print("\nHãy sao chép .env.example thành .env và điền đầy đủ thông tin.")
        sys.exit(1)

    print("=" * 60)
    print("  HỆ THỐNG 5 AI TRADE VÀNG - ĐÃ KHỞI ĐỘNG")
    print(f"  Nhà cung cấp AI: {config.AI_PROVIDER} | Model: {config.get_active_model()}")
    print(f"  Chế độ: {config.TRADE_MODE}")
    print(f"  Kiểm tra thị trường mỗi {config.CHECK_INTERVAL_MINUTES} phút")
    print(f"  Telegram: {'Đã bật' if config.TELEGRAM_BOT_TOKEN else 'CHƯA bật (khuyến nghị cấu hình)'}")
    print("=" * 60)

    tools.send_telegram(
        "🤖 <b>Hệ thống 5 AI trade vàng đã khởi động</b>\n"
        f"Nhà cung cấp: {config.AI_PROVIDER} ({config.get_active_model()})\n"
        f"Chế độ: {config.TRADE_MODE} | Vốn mô phỏng: {config.INITIAL_BALANCE} USD\n"
        f"Kiểm tra mỗi {config.CHECK_INTERVAL_MINUTES} phút. Báo cáo sẽ gửi tự động."
    )

    # Vòng lặp chính: chạy mãi mãi, nghỉ giữa các chu kỳ
    while True:
        try:
            run_one_cycle()
        except Exception as e:
            tools.log(f"LỖI NGOẠI LỆ trong chu kỳ: {e}")
            tools.send_telegram(f"⚠️ Hệ thống gặp lỗi: {e}\nSẽ thử lại sau {config.CHECK_INTERVAL_MINUTES} phút.")
        tools.log(f"Nghỉ {config.CHECK_INTERVAL_MINUTES} phút đến chu kỳ tiếp theo...")
        time.sleep(config.CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
