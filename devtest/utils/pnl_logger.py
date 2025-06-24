import os
from datetime import datetime

# Абсолютный путь — всегда попадёт в правильный logs/trades.txt
LOG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs", "trades.txt"))
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

def log_trade(symbol, side, amount, entry_price, exit_price, reason=""):
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        pnl = (exit_price - entry_price) * amount if side == "SELL" else 0

        line = f"{timestamp} | {symbol} | {side} | Qty: {amount} | Entry: {entry_price:.4f} | Exit: {exit_price:.4f} | PnL: {pnl:.4f} | Reason: {reason}\n"

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)

        print(f"[LOGGED ✅] {line.strip()}")  # дебаг в консоль
    except Exception as e:
        print(f"[FATAL LOG ERROR] {e} — {symbol=}, {amount=}, {entry_price=}, {exit_price=}")

def test_log():
    log_trade("TESTCOIN", "SELL", 10, 1.0, 1.5, "🧪 Тестовая запись")


def read_latest_pnl(n=5):
    if not os.path.exists(LOG_PATH):
        return "No trades yet."

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()[-n:]

    formatted = []
    for line in lines:
        try:
            ts, symbol, side, qty, entry, exit_, pnl, reason = line.strip().split(" | ")
            formatted.append(
                f"📈 <b>{symbol}</b> | {ts}\n"
                f"🔄 {side} | {qty} | {entry} → {exit_}\n"
                f"💵 {pnl} | 📌 {reason}\n"
                f"{'-'*30}"
            )
        except Exception:
            formatted.append(line.strip())

    return "\n".join(formatted)
