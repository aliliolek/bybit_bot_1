import asyncio
import logging
from pprint import pprint
from ads import fetch_market_ads, update_buy_ads, update_sell_ads
from api_client import get_api
from find_twice import find_price_from_config
from orders_log import process_active_orders
import asyncio
from telegram_bot import run_bot, running_flags
from telegram_bot import config_state as config

# 🔐 Перевірка, що ключі є
try:
    print("[CONFIG] Bybit config loaded:")
except KeyError:
    print("[FATAL] Missing 'bybit' config. Please upload config.yaml via Telegram.")
    exit(1)

api = get_api(config)

async def main_loop(api):
    while True:
        if not running_flags["main_loop"]:
            await asyncio.sleep(1)
            continue

        try:
            # --- BUY ---
            buy_ads = fetch_market_ads(api, "BUY", config)
            buy_price = find_price_from_config(buy_ads, config, "BUY")
            update_buy_ads(api, config, new_price=round(buy_price + 0.01, 2))
            process_active_orders(api, config, "BUY")

            # Передаємо BUY-ціну в SELL-конфіг
            config["SELL"]["reference_buy_price"] = buy_price

            # --- SELL ---
            sell_ads = fetch_market_ads(api, "SELL", config)
            sell_price = find_price_from_config(sell_ads, config, "SELL")
            update_sell_ads(api, config, new_price=round(sell_price - 0.01, 2))
            process_active_orders(api, config, "SELL")

        except Exception as e:
            print(f"[!] Error in loop: {e}")

        await asyncio.sleep(30)

async def main():
    await asyncio.gather(
        main_loop(api),
        run_bot()
    )

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())