from websocket.bybit_ws_client import BybitWebSocketClient  # правильно импортируем

def init_exchange(api_key, api_secret, symbol="USDT", is_testnet=False, market_type="spot"):
    return BybitWebSocketClient(
        api_key=api_key,
        api_secret=api_secret,
        symbol=symbol,
        is_testnet=is_testnet,
        market_type=market_type
    )