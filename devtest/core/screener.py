import numpy as np
from utils.indicators import calculate_rsi, calculate_ema

def should_enter_trade(closes, volumes, period_rsi=14, ema_fast_period=12, ema_slow_period=26):
    if len(closes) < 30:
        return False, "Недостаточно данных"

    try:
        # Импульс по цене
        recent_change = (closes[-1] - closes[-5]) / closes[-5] * 100
        if recent_change < 1.5:
            return False, f"Импульс слабый: {recent_change:.2f}%"

        # Объём выше среднего
        recent_vol = volumes[-1]
        avg_vol = np.mean(volumes[-6:-1])
        if recent_vol < avg_vol * 2:
            return False, f"Объём слабый: {recent_vol:.2f} < {avg_vol * 2:.2f}"
                    # === Доп. проверка: был ли объёмный импульс
            vol_spikes = [volumes[-i] > volumes[-i-1] for i in range(1, 4)]
            if sum(vol_spikes) < 2:
                return False, "Нет уверенного роста объёма (менее 2 всплесков подряд)"
                
        # RSI
        rsi_series = calculate_rsi(closes, period_rsi)
        if rsi_series[-1] < 60:
            return False, f"RSI не пробил 60: {rsi_series[-1]:.2f}"

        from utils.indicators import calculate_ema_series  # добавь вверху

        ema_series = calculate_ema_series(closes, ema_fast_period)
        if len(ema_series) < 3:
            return False, "Недостаточно EMA-данных"

        ema_slope = (ema_series[-1] - ema_series[-3]) / ema_series[-3] * 100
        if ema_slope < 0.1:
            return False, f"EMA наклон низкий: {ema_slope:.3f}%"
        # EMA пересечение
        ema_fast = calculate_ema(closes, ema_fast_period)
        ema_slow = calculate_ema(closes, ema_slow_period)
        if ema_fast <= ema_slow:
            return False, f"EMA12 {ema_fast:.2f} ≤ EMA26 {ema_slow:.2f}"

        # Свеча (форма)
        body = abs(closes[-1] - closes[-2])
        wick = abs(closes[-2] - closes[-3])
        if body < wick:
            return False, "Свеча с тенями, не импульс"

        return True, "Сигнал валиден ✅"

    except Exception as e:
        return False, f"Ошибка фильтра: {e}"
