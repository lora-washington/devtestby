import time

def should_exit_trade(current_price, entry_price, high_price, entry_time,
                      closes=None, volumes=None,
                      tp_pct=5.0, tsl_pct=0.5, sl_pct=2.0, max_hold_sec=120,
                      trailing_stop=None):
                    
    reasons = []

    if trailing_stop is not None and current_price <= trailing_stop:
        reasons.append(f"Trailing Stop Hit 🔻 ({trailing_stop:.4f})")

    elif high_price and current_price <= high_price * (1 - tsl_pct / 100):
        reasons.append("Trailing Stop 🔻")

    if current_price >= entry_price * (1 + tp_pct / 100):
        reasons.append("Take Profit ✅")

    if current_price <= entry_price * (1 - sl_pct / 100):
        reasons.append("Stop Loss 💀")

    if time.time() - entry_time > max_hold_sec:
        reasons.append("Timeout ⏳")

    if reasons:
        return True, reasons[0]
    return False, ""
