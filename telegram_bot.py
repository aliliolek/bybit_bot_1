# telegram_bot.py
import asyncio
from functools import wraps
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from config import config 
from aiogram.client.default import DefaultBotProperties

# ==== token ====
TELEGRAM_BOT_TOKEN = config["telegram"]["token"]
AUTHORIZED_CHAT_ID = int(config["telegram"]["chat_id"])

def only_owner(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.id != AUTHORIZED_CHAT_ID:
            await message.answer("🚫 Access denied.")
            return
        return await func(message, *args, **kwargs)
    return wrapper

# ==== СТАН ====
running_flags = {
    "main_loop": False
}

# ==== ІНІЦІАЛІЗАЦІЯ ====
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ==== КОМАНДИ ====
@dp.message(Command("start_bot"))
@only_owner
async def start_bot(message: Message):
    running_flags["main_loop"] = True
    await message.answer("✅ Autoupdate adds & orders - started.")

@dp.message(Command("stop_bot"))
@only_owner
async def stop_bot(message: Message):
    running_flags["main_loop"] = False
    await message.answer("🛑 Autoupdate adds & orders - stopped.")

@dp.message(Command("status"))
@only_owner
async def status(message: Message):
    state = '✅ ON' if running_flags["main_loop"] else '❌ OFF'
    await message.answer(f"BOT: {state}")

# ==== ЗАПУСК ====
async def run_bot():
    await dp.start_polling(bot)
