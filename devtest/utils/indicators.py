import numpy as np

def calculate_ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]:
        ema = price * k + ema * (1 - k)
    return ema

def calculate_rsi(prices, period=14):
    prices = np.array(prices, dtype=np.float64)
    if len(prices) < period:
        return np.zeros_like(prices)

    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed > 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:period] = 100. - 100. / (1. + rs)

    for i in range(period, len(prices)):
        delta = deltas[i - 1]
        upval = max(delta, 0)
        downval = -min(delta, 0)

        up = (up * (period - 1) + upval) / period
        down = (down * (period - 1) + downval) / period
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)

    return rsi

def calculate_obv(prices, volumes):
    obv = [0]
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            obv.append(obv[-1] + volumes[i])
        elif prices[i] < prices[i - 1]:
            obv.append(obv[-1] - volumes[i])
        else:
            obv.append(obv[-1])
    return np.array(obv)

def calculate_volume_ma(volumes, period):
    if len(volumes) < period:
        return np.zeros_like(volumes)
    return np.convolve(volumes, np.ones(period) / period, mode='valid')

def calculate_order_book_pressure(bids, asks):
    bid_volume = sum([bid[1] for bid in bids])
    ask_volume = sum([ask[1] for ask in asks])
    if bid_volume + ask_volume == 0:
        return 0
    return (bid_volume - ask_volume) / (bid_volume + ask_volume)
