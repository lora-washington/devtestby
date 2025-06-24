# exchange_client.py
from utils.exchange import init_exchange
import json

with open("config.json") as f:
    config = json.load(f)

client = init_exchange(
    api_key=config["API_KEY"],
    api_secret=config["API_SECRET"],
    symbol="USDT",  # временный символ
    is_testnet=False,
    market_type="spot"
)