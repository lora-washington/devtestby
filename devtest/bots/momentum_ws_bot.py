# === momentum_ws_bot.py (доработанный) ===

import asyncio
import datetime
import time
import math
import os, sys
import numpy as np

from utils.indicators import calculate_rsi, calculate_ema, calculate_ema_series
from websocket.bybit_ws_client import BybitWebSocketClient
from utils.pnl_logger import log_trade
from core.screener import should_enter_trade
from core.exit_logic import should_exit_trade

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

class MomentumBot:
    def __init__(self, api_key, api_secret, symbol,
                 capital_per_trade=50.0,
                 rsi_entry_threshold=35,
                 take_profit_pct=2.5,
                 trailing_stop_pct=1.2,
                 cooldown_sec=300,
                 max_drawdown_pct=-5.0,
                 testnet=True,
                 **kwargs):

        self.client = BybitWebSocketClient(api_key, api_secret, symbol, is_testnet=testnet, market_type="spot")
        self.symbol = symbol
        self.capital_per_trade = capital_per_trade
        self.rsi_entry_threshold = rsi_entry_threshold
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.cooldown_minutes = cooldown_sec / 60
        self.max_drawdown_pct = max_drawdown_pct

        self.prices = []
        self.volumes = []
        self.in_position = False
        self.entry_price = None
        self.amount = None
        self.qty_precision = 3
        self.qty_step = 1.0
        self.min_qty = 1.0
        self.high_price = None
        self.high_price_ema = None
        self.trailing_stop = None
        self.entry_time = None

        self.last_trade_time = {}
        self.daily_pnl = 0.0
        self.daily_start_balance = None
        self.active = True

    async def start(self):
        self.qty_step, self.min_qty = await self.client.get_qty_info()
        self.qty_precision = max(0, abs(int(round(-math.log10(self.qty_step)))))
        await self.client.connect(self.on_price_update)

    async def on_price_update(self, price, volume, *_):
        if not self.active:
            return
        try:
            price = float(price)
            volume = float(volume)
        except Exception as e:
            print(f"[PARSE ERROR] Failed to convert price/volume: {e}")
            return

        try:
            current_balance = await self.client.get_balance()
            if current_balance is None or current_balance["USDT"] == 0.0:
                print("[PNL ERROR] Invalid balance")
                return
            if self.daily_start_balance is None:
                self.daily_start_balance = current_balance["USDT"]
            self.daily_pnl = ((current_balance["USDT"] - self.daily_start_balance) / self.daily_start_balance) * 100
            if self.daily_pnl <= self.max_drawdown_pct:
                print(f"[DRAWDOWN] Max drawdown hit: {self.daily_pnl:.2f}% — disabling bot")
                self.active = False
                return
        except Exception as e:
            print(f"[PNL ERROR] {e}")
            return

        self.prices.append(price)
        self.volumes.append(volume)
        if len(self.prices) > 100:
            self.prices.pop(0)
            self.volumes.pop(0)

        print(f"[MOMENTUM] {self.symbol} → Price: {price:.2f}, Volume: {volume}, In Position: {self.in_position}")

        try:
            if not self.in_position and self.check_entry_signal():
                await self.enter_position(price)
            elif self.in_position:
                await self.manage_position(price)
        except Exception as e:
            print(f"[MOMENTUM ERROR] {e}")

    def check_entry_signal(self):
        if len(self.prices) < 30:
            return False
        now = datetime.datetime.utcnow()
        last_time = self.last_trade_time.get(self.symbol)
        if last_time and (now - last_time).total_seconds() < self.cooldown_minutes * 60:
            print(f"[COOLDOWN] {self.symbol} is cooling down")
            return False
        closes = self.prices[-30:]
        rsi_series = calculate_rsi(closes, period=14)
        ema_fast_val = calculate_ema(closes, period=12)
        ema_slow_val = calculate_ema(closes, period=26)
        if rsi_series is None or not isinstance(rsi_series, (list, np.ndarray)):
            return False
        if ema_fast_val is None or ema_slow_val is None:
            return False
        rsi_val = rsi_series[-1]
        print(f"[ENTRY SIGNAL] RSI: {rsi_val:.2f}, EMA Fast: {ema_fast_val:.2f}, EMA Slow: {ema_slow_val:.2f}")
        return rsi_val < self.rsi_entry_threshold and ema_fast_val > ema_slow_val

    async def enter_position(self, price):
        self.amount = round(self.capital_per_trade / price, self.qty_precision)
        if self.amount < self.min_qty:
            print(f"[ENTRY ERROR] Qty {self.amount} < min {self.min_qty}, skipping entry")
            log_trade(self.symbol, "BUY", self.amount, price, price, "❌ Below min qty")
            return

        self.entry_price = price
        self.high_price = price
        self.high_price_ema = price
        self.trailing_stop = price * (1 - self.trailing_stop_pct / 100)

        print(f"[ENTRY] BUY @ {price:.4f} x {self.amount}")
        try:
            response = await self.client.place_market_order("BUY", self.amount)
            print(f"[ORDER RESPONSE] {response}")
            if response and response.get("retCode") == 0:
                self.in_position = True
                self.last_trade_time[self.symbol] = datetime.datetime.utcnow()
                self.entry_time = time.time()
            else:
                reason = response.get("retMsg", "Unknown")
                print(f"[ENTRY ERROR] Order failed: {reason}")
                log_trade(self.symbol, "BUY", self.amount, price, price, f"❌ {reason}")
        except Exception as e:
            print(f"[ORDER EXCEPTION] {e}")
            log_trade(self.symbol, "BUY", self.amount, price, price, f"❌ Exception {e}")

    async def manage_position(self, price):
        if price > self.high_price:
            self.high_price = price

        alpha = 0.2
        self.high_price_ema = alpha * price + (1 - alpha) * self.high_price_ema

        ema_series = calculate_ema_series(self.prices[-30:], period=9)
        ema_slope = 0
        if len(ema_series) >= 3:
            ema_slope = (ema_series[-1] - ema_series[-3]) / ema_series[-3] * 100

        if ema_slope > 0.5:
            dynamic_trailing = 0.5
        elif ema_slope > 0.3:
            dynamic_trailing = 0.8
        elif ema_slope > 0.1:
            dynamic_trailing = 1.2
        else:
            dynamic_trailing = self.trailing_stop_pct

        candidate_stop = self.high_price_ema * (1 - dynamic_trailing / 100)
        if candidate_stop > self.trailing_stop:
            print(f"[TRAILING UPDATE] New trailing stop: {candidate_stop:.4f}")
            self.trailing_stop = candidate_stop

        should_exit, reason = should_exit_trade(
            current_price=price,
            entry_price=self.entry_price,
            high_price=self.high_price,
            entry_time=self.entry_time,
            trailing_stop=self.trailing_stop,
            closes=self.prices,
            volumes=self.volumes
        )

        if should_exit:
            print(f"[EXIT] Reason: {reason}")
            await self.exit_position(price, reason)

    async def exit_position(self, price, reason="Manual Exit"):
        print(f"[EXIT] SELL @ {price:.4f}")
        if self.amount is None:
            log_trade(self.symbol, "SELL", 0, self.entry_price or 0.0, price, "❌ AMOUNT LOST")
            return

        try:
            adjusted_qty = math.floor(self.amount / self.qty_step) * self.qty_step
            adjusted_qty = round(adjusted_qty, self.qty_precision)

            if adjusted_qty < self.min_qty:
                print(f"[ORDER SKIPPED] Qty {adjusted_qty} < min {self.min_qty}")
                log_trade(self.symbol, "SELL", adjusted_qty, self.entry_price, price, "❌ Below min qty")
                return

            response = await self.client.place_market_order("SELL", adjusted_qty)
            success = response and response.get("retCode") == 0
            ret_msg = response.get("retMsg", "API Error") if isinstance(response, dict) else "No Response"

            log_trade(self.symbol, "SELL", adjusted_qty, self.entry_price, price,
                      reason if success else f"❌ {ret_msg}")

        except Exception as e:
            print(f"[LOGGING ERROR] {e}")
        self.in_position = False
        self.entry_price = None
        self.amount = None
        self.high_price = None
        self.high_price_ema = None
        self.trailing_stop = None
        self.entry_time = None
