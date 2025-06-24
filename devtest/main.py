import asyncio
import json
import os
import sys
import threading

from bots.momentum_ws_bot import MomentumBot
from telegram_runner import start_telegram
from telegram_bot import set_bots, register_running_bot, set_client  # 🔁 вернули set_client
from websocket.bybit_ws_client import BybitWebSocketClient  # 💡 клиент нужен отдельно
from utils.pnl_logger import test_log
test_log()



sys.path.append(os.path.join(os.path.dirname(__file__), "bots"))
sys.path.append(os.path.join(os.path.dirname(__file__), "utils"))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

async def main():
    print("🚀 Запуск Momentum ботов и Telegram...")

    with open("config.json") as f:
        config = json.load(f)

    api_key = config["API_KEY"]
    api_secret = config["API_SECRET"]
    pairs = config["PAIRS"]

    # ✅ создаём общий клиент (любой символ подойдёт, он просто для Telegram)
    shared_client = BybitWebSocketClient(
        api_key=api_key,
        api_secret=api_secret,
        symbol=pairs[0],  # можно взять первый актив
        is_testnet=config.get("IS_TESTNET", False),
        market_type=config.get("MARKET_TYPE", "spot")
    )
    set_client(shared_client)  # 🧠 установили клиент в telegram_bot

    tasks = []
    all_bots = []

    for symbol in pairs:
        print(f"🔄 Запуск MomentumBot для {symbol}")

        momentum_bot = MomentumBot(
            api_key=api_key,
            api_secret=api_secret,
            symbol=symbol,
            **config["momentum"]
        )

        task_momentum = asyncio.create_task(momentum_bot.start())
        register_running_bot(task_momentum, momentum_bot)

        all_bots.append(momentum_bot)
        tasks.append(task_momentum)

    set_bots(all_bots)

    # 🚀 Старт Telegram в отдельном потоке
    threading.Thread(target=start_telegram, daemon=True).start()

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
    print("✅ Все боты запущены. Ожидание сообщений Telegram...")
