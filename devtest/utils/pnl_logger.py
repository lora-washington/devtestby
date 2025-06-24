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
    
def analyze_trades(hours=24):
    if not os.path.exists(LOG_PATH):
        return "Нет данных о сделках."

    now = datetime.utcnow()
    cutoff = now.timestamp() - hours * 3600
    total = wins = losses = 0
    total_pnl = 0.0

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            try:
                parts = line.strip().split(" | ")
                if len(parts) < 8:
                    continue

                ts_str = parts[0]
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
                if ts < cutoff:
                    continue

                side = parts[2]
                pnl_str = parts[6].replace("PnL: ", "")
                pnl = float(pnl_str)

                if side != "SELL":
                    continue  # считаем только завершённые сделки

                total += 1
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1

            except Exception:
                continue

        if total == 0:
            return "Нет сделок за последние 24 часа."

        winrate = wins / total * 100

        return (
            f"📊 Статистика за 24ч:\n"
            f"🧾 Сделок: {total}\n"
            f"✅ Профитных: {wins}\n"
            f"❌ Убыточных: {losses}\n"
            f"📈 WinRate: {winrate:.1f}%\n"
            f"💰 Общий PnL: {total_pnl:.2f} USDT"
        )

    except Exception as e:
        return f"❌ Ошибка анализа: {e}"
