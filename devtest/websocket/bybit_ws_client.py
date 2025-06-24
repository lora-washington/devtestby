import asyncio
import websockets
import json
import hmac
import hashlib
import time
import requests
import aiohttp
import math

class BybitWebSocketClient:
    def __init__(self, api_key, api_secret, symbol, is_testnet=False, market_type="spot"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol.upper()
        self.market_type = market_type
        self.is_testnet = is_testnet

        if is_testnet:
            self.base_ws_url = "wss://stream-testnet.bybit.com/v5/public/spot"
            self.base_rest_url = "https://api-testnet.bybit.com"
        else:
            self.base_ws_url = "wss://stream.bybit.com/v5/public/spot"
            self.base_rest_url = "https://api.bybit.com"

    async def get_balance(self):
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"
        param_str = "accountType=UNIFIED"

        sign_payload = f"{timestamp}{self.api_key}{recv_window}{param_str}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        url = f"{self.base_rest_url}/v5/account/wallet-balance?{param_str}"
        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "X-BAPI-SIGN": signature,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                try:
                    result = await response.json()
                except Exception as e:
                    print(f"[ERROR] JSON decode error: {e}")
                    return {"USDT": 0.0}

                print(f"[RAW BALANCE RESPONSE] {result}")

                try:
                    coin_data = result['result']['list'][0]['coin']
                    for item in coin_data:
                        if item.get('coin') == 'USDT':
                            return {"USDT": float(item.get('walletBalance', 0.0))}
                except Exception as e:
                    print(f"[BALANCE PARSE ERROR] {e}")
                    print(f"[RAW BALANCE RESPONSE] {result}")

                print("[ERROR] USDT balance not found.")
                return {"USDT": 0.0}

    async def connect(self, callback):
        self.callback = callback
        while True:
            try:
                print(f"[WS CONNECT] Connecting to {self.base_ws_url}")
                async with websockets.connect(self.base_ws_url) as websocket:
                    await self.subscribe_price_stream(websocket)
                    async for message in websocket:
                        await self.handle_message(json.loads(message))
            except Exception as e:
                print(f"[WS ERROR] {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def subscribe_price_stream(self, ws):
        msg = {
            "op": "subscribe",
            "args": [f"tickers.{self.symbol}"]
        }
        print(f"[WS SUBSCRIBE] {msg}")
        await ws.send(json.dumps(msg))

    async def handle_message(self, msg):
        if "data" not in msg:
            return
        data = msg["data"]
        price = data.get("lastPrice")
        volume = data.get("turnover", data.get("volume24h", 0))

        if price:
            print(f"[PRICE STREAM] {self.symbol} → {price}")
            await self.callback(float(price), float(volume))

    async def place_market_order(self, side, qty):
        url = f"{self.base_rest_url}/v5/order/create"
        timestamp = str(int(time.time() * 1000))
        recv_window = "5000"

        body = {
            "category": "spot",
            "symbol": self.symbol,
            "side": side.upper(),
            "orderType": "Market",
            "qty": str(qty),
            "timeInForce": "IOC"
        }

        payload = json.dumps(body)
        sign_raw = f"{timestamp}{self.api_key}{recv_window}{payload}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_raw.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, data=payload) as response:
                    result = await response.json()
                    if result.get("retCode") != 0:
                        print(f"[ORDER ERROR] Failed to place order: {result.get('retMsg')}")
                    else:
                        print(f"[ORDER SUCCESS] {side} {qty} {self.symbol} → OrderID: {result['result'].get('orderId')}")
                    return result
            except Exception as e:
                print(f"[ORDER ERROR] Exception: {e}")
                return {"retCode": -1, "retMsg": str(e)}

    async def get_qty_info(self):
        url = f"{self.base_rest_url}/v5/market/instruments-info?category=spot"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                for item in data['result']['list']:
                    if item['symbol'] == self.symbol:
                        try:
                            step = float(item.get('lotSizeFilter', {}).get('qtyStep', '1'))
                            min_qty = float(item.get('lotSizeFilter', {}).get('minOrderQty', '1'))
                            return step, min_qty
                        except Exception as e:
                            print(f"[PRECISION ERROR] {e}")
        return 1.0, 1.0  # fallback
