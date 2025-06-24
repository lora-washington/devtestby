# === m1/bots/momentum_ws_bot.py ===
import asyncio
from utils.indicators import calculate_rsi, calculate_ema
from websocket.bybit_ws_client import BybitWebSocketClient
from utils.pnl_logger import log_trade
import numpy as np
import sys, os
import time
import datetime
import math
from utils.indicators import calculate_ema_series

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.screener import should_enter_trade
from core.exit_logic import should_exit_trade

class MomentumBot:
    def __init__(self,
                 api_key,
                 api_secret,
                 symbol,
                 capital_per_trade=50.0,
                 rsi_entry_threshold=35,
                 take_profit_pct=2.5,
                 trailing_stop_pct=1.2,
                 cooldown_sec=300,
                 max_drawdown_pct=-5.0,
                 testnet=True,
                 **kwargs):

        self.client = BybitWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            is_testnet=testnet,
            market_type="spot"
        )

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
                print("[PNL ERROR] Невалидный баланс — PnL не рассчитывается.")
                return

            if self.daily_start_balance is None:
                self.daily_start_balance = current_balance["USDT"]
                print(f"[BALANCE INIT] Стартовый баланс: {self.daily_start_balance:.2f} USDT")

            self.daily_pnl = ((current_balance["USDT"] - self.daily_start_balance) / self.daily_start_balance) * 100

            if self.daily_pnl <= self.max_drawdown_pct:
                print(f"[DRAWDOWN] Просадка {self.daily_pnl:.2f}% — бот останавливается.")
                self.active = False
                return

        except Exception as e:
            print(f"[PNL ERROR] Ошибка при расчете PnL: {e}")
            return

        print(f"[MOMENTUM] {self.symbol} → Price: {price:.2f}, Volume: {volume}, In Position: {self.in_position}")
        self.prices.append(price)
        self.volumes.append(volume)

        if len(self.prices) > 100:
            self.prices.pop(0)
            self.volumes.pop(0)

        try:
            if not self.in_position and self.check_entry_signal():
                await self.enter_position(price)
            elif self.in_position:
                await self.manage_position(price)
        except Exception as e:
            print(f"[MOMENTUM ERROR] Ошибка в торговой логике: {e}")

    def check_entry_signal(self):
        if len(self.prices) < 30:
            print(f"[SIGNAL] Недостаточно данных для {self.symbol}: {len(self.prices)} цен")
            return False
    
        now = datetime.datetime.utcnow()
        last_time = self.last_trade_time.get(self.symbol)
        if last_time:
            delta = now - last_time
            if delta.total_seconds() < self.cooldown_minutes * 60:
                print(f"[COOLDOWN] {self.symbol} в кулдауне: {delta.total_seconds():.0f}s")
                return False
    
        closes = self.prices[-30:]
        try:
            rsi_series = calculate_rsi(closes, period=14)
            ema_fast_val = calculate_ema(closes, period=12)
            ema_slow_val = calculate_ema(closes, period=26)
    
            if rsi_series is None or not isinstance(rsi_series, (list, np.ndarray)):
                print(f"[SIGNAL] RSI не рассчитан для {self.symbol}")
                return False
            if ema_fast_val is None or ema_slow_val is None:
                print(f"[SIGNAL] EMA не рассчитан для {self.symbol}")
                return False
    
            rsi_val = rsi_series[-1]
            print(f"[SIGNAL] {self.symbol} → RSI={rsi_val:.2f}, EMA12={ema_fast_val:.4f}, EMA26={ema_slow_val:.4f}")
    
            if rsi_val < self.rsi_entry_threshold and ema_fast_val > ema_slow_val:
                print(f"[SIGNAL ✅] Вход разрешён по {self.symbol}")
                return True
            else:
                print(f"[SIGNAL ❌] Вход НЕ разрешён по {self.symbol}")
                return False
    
        except Exception as e:
            print(f"[ENTRY CHECK ERROR] {e}")
            return False


    async def enter_position(self, price):
        self.entry_price = price
        self.amount = round(self.capital_per_trade / price, self.qty_precision)
        self.high_price = price
        self.high_price_ema = price
        self.trailing_stop = price * (1 - self.trailing_stop_pct / 100)

        print(f"[ENTRY] BUY @ {price} x {self.amount}")
        try:
            response = await self.client.place_market_order("BUY", self.amount)
            print(f"[ORDER RESPONSE] {response}")

            if response and response.get("retCode") == 0:
                self.in_position = True
                self.last_trade_time[self.symbol] = datetime.datetime.utcnow()
                self.entry_time = time.time()
            else:
                print(f"[ENTRY ERROR] Покупка не удалась: {response}")
                self.in_position = False
                self.entry_price = None
                self.amount = None
                return

        except Exception as e:
            print(f"[ORDER ERROR] {e}")
            self.in_position = False
            self.entry_price = None
            self.amount = None
            return

    async def manage_position(self, price):
        if price > self.high_price:
            self.high_price = price

        alpha = 0.2
        self.high_price_ema = alpha * price + (1 - alpha) * self.high_price_ema

        price_gain_pct = ((price - self.entry_price) / self.entry_price) * 100

        if price_gain_pct > 3:
            dynamic_trailing = 0.5
        elif price_gain_pct > 2:
            dynamic_trailing = 0.8
        elif price_gain_pct > 1:
            dynamic_trailing = 1.2
        else:
            dynamic_trailing = self.trailing_stop_pct

        previous_trailing = self.trailing_stop
        # === Адаптивный трейлинг по EMA ===
        ema_series = calculate_ema_series(self.prices[-30:], period=9)  # 9 — как пример
        if len(ema_series) >= 3:
            ema_slope = (ema_series[-1] - ema_series[-3]) / ema_series[-3] * 100
        else:
            ema_slope = 0
        
        # Корректируем trailing от наклона EMA
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
            self.trailing_stop = candidate_stop
            print(f"[TRAILING UPDATE] Новая цена стопа: {self.trailing_stop:.4f} (была: {previous_trailing:.4f})")

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
            print(f"[EXIT] Причина выхода: {reason}")
            await self.exit_position(price, reason)

    async def exit_position(self, price, reason="Manual Exit"):
        print(f"[EXIT] SELL @ {price}")

        if self.amount is None:
            print("[ERROR] self.amount is None, logging failed exit")
            log_trade(
                self.symbol,
                "SELL",
                0,
                self.entry_price if self.entry_price else 0.0,
                price,
                "❌ AMOUNT LOST"
            )
            return

        try:
            adjusted_qty = math.floor(self.amount / self.qty_step) * self.qty_step
            adjusted_qty = round(adjusted_qty, self.qty_precision)

            if adjusted_qty < self.min_qty:
                print(f"[ORDER SKIPPED] Кол-во меньше минимума: {adjusted_qty} < {self.min_qty}")
                log_trade(
                    self.symbol,
                    "SELL",
                    adjusted_qty,
                    self.entry_price,
                    price,
                    "❌ Below min qty"
                )
                return

            response = await self.client.place_market_order("SELL", adjusted_qty)
            print(f"[DEBUG ORDER RESPONSE] {response}")

            success = response and response.get("retCode") == 0
            ret_msg = response.get("retMsg", "API Error") if isinstance(response, dict) else "No Response"

            print(f"[DEBUG LOG INPUT] symbol={self.symbol}, amount={adjusted_qty}, entry_price={self.entry_price}, exit_price={price}")
            log_trade(
                self.symbol,
                "SELL",
                adjusted_qty,
                self.entry_price,
                price,
                reason if success else f"❌ {ret_msg}"
            )

            print(f"[TRADE LOGGED {'✅' if success else '❌'}] {self.symbol} @ {price}")

        except Exception as e:
            print(f"[LOGGING ERROR] {e}")

        self.in_position = False
        self.entry_price = None
        self.amount = None
        self.high_price = None
        self.high_price_ema = None
        self.trailing_stop = None
        self.entry_time = None
