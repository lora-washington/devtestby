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
        
    if time.time() - entry_time > max_hold_sec:
    if closes and volumes and len(closes) >= 10 and len(volumes) >= 10:
        recent_return = (closes[-1] - closes[-10]) / closes[-10] * 100
        avg_volume = sum(volumes[-10:]) / 10
        vol_now = volumes[-1]

        if abs(recent_return) < 0.3 and vol_now < avg_volume * 0.6:
            reasons.append("Умный Timeout: рынок стоит и вялый ⌛")
    else:
        reasons.append("Timeout ⏳")

    if current_price <= entry_price * (1 - sl_pct / 100):
        reasons.append("Stop Loss 💀")

    if time.time() - entry_time > max_hold_sec:
        reasons.append("Timeout ⏳")

    if reasons:
        return True, reasons[0]
    return False, ""
