# telegram_bot.py
import yaml
import aiofiles
from functools import wraps
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import config  # тільки для Telegram токена
from config import config as initial_config

# === Конфіг (динамічний) ===
config_state = initial_config.copy()

# === Telegram токен ===
TELEGRAM_BOT_TOKEN = config["telegram"]["token"]
AUTHORIZED_CHAT_ID = int(config["telegram"]["chat_id"])

# === Обгортка: тільки для власника ===
def only_owner(func):
    @wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.id != AUTHORIZED_CHAT_ID:
            await message.answer("🚫 Access denied.")
            return
        return await func(message, *args, **kwargs)
    return wrapper

# === Прапорці керування ===
running_flags = {
    "main_loop": False
}

# === Telegram ініціалізація ===
bot = Bot(
    token=TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# === Команди ===

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

@dp.message(Command("upload_config"))
@only_owner
async def prompt_for_config(message: Message):
    await message.answer("📎 Please send the new <code>config.yaml</code> file now.")

@dp.message(lambda m: m.document is not None and m.document.file_name.endswith(".yaml"))
@only_owner
async def handle_uploaded_config(message: Message):
    document = message.document

    try:
        # 1. Завантажити
        file_path = f"./data/{document.file_name}"
        await bot.download(document, destination=file_path)

        # 2. Прочитати вміст YAML
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            raw = await f.read()
            new_config = yaml.safe_load(raw)

        # 3. Мінімальна валідація
        if not any(k in new_config for k in ["BUY", "SELL", "p2p"]):
            await message.answer("❌ Invalid config: no BUY / SELL / p2p section.")
            return

        # 4. Оновити лише ключові секції (решта зберігається)
        safe_keys = ["BUY", "SELL", "p2p", "limits", "filters"]
        for key in safe_keys:
            if key in new_config:
                config_state[key] = new_config[key]

        await message.answer("✅ Config updated in memory (core sections only).")

    except Exception as e:
        await message.answer(f"❌ Failed to load config: <code>{e}</code>")


# === Запуск Telegram-петлі ===
async def run_bot():
    await dp.start_polling(bot)
