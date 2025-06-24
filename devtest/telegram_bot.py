import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from utils.pnl_logger import read_latest_pnl
from utils.pnl_logger import analyze_trades

# === Telegram API Token ===
import json
with open("config.json") as f:
    config = json.load(f)
API_TOKEN = config.get("TELEGRAM_TOKEN", "your_token_here")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# === Глобальные переменные ===
bots = []
running_bots = []
client = None

# === Функции для установки внешних значений ===
def set_bots(bot_list):
    global bots
    bots = bot_list

def register_running_bot(task, bot_instance):
    running_bots.append((task, bot_instance))

def set_client(external_client):
    global client
    client = external_client

# === Команды Telegram ===

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    await message.answer("✅ Бот запущен. Управление: /pause, /resume, /status, /stop.")

@dp.message_handler(commands=["pause"])
async def pause_bot(message: types.Message):
    for bot in bots:
        bot.active = False
    await message.reply("⏸️ Все боты на паузе.")

@dp.message_handler(commands=["resume"])
async def resume_bot(message: types.Message):
    for bot in bots:
        bot.active = True
    await message.reply("▶️ Боты активированы.")

@dp.message_handler(commands=["stop"])
async def stop_handler(message: types.Message):
    for task, bot_instance in running_bots:
        task.cancel()
    running_bots.clear()
    await message.answer("🛑 Все боты остановлены.")

@dp.message_handler(commands=["help"])
async def help_handler(message: types.Message):
    await message.answer(
        "📖 Команды:\n"
        "/start — запуск\n"
        "/pause — пауза\n"
        "/resume — продолжить\n"
        "/stop — остановить\n"
        "/status — статус и баланс\n"
        "/help — помощь"
    )


@dp.message_handler(commands=["status"])
async def status_handler(message: types.Message):
    pnl = read_latest_pnl()
    await message.answer(f"📊 Последние сделки:\n<pre>{pnl}</pre>", parse_mode=ParseMode.HTML)
    
    analysis = analyze_trades()
    await message.answer(f"📋 Статистика за 24ч:\n<pre>{analysis}</pre>", parse_mode=ParseMode.HTML)
    
    if client is None:
        await message.answer("⚠️ Клиент не инициализирован. Баланс недоступен.")
        return

    try:
        balance = await client.get_balance()
        usdt_balance = balance.get("USDT", 0.0)
        await message.answer(f"💰 Баланс USDT: {usdt_balance:.2f} USDT")

    except Exception as e:
        await message.answer(f"⚠️ Ошибка получения баланса: {e}")