import asyncio
import json
import logging
from pprint import pprint
import time
import uuid
from ads import exclude_own_ads, fetch_market_ads, get_available_balance, get_buy_balance, update_buy_ads, update_sell_ads
from api_client import get_api
from config import config
from find_twice import find_price_from_config
from orders import get_pending_orders, process_all_buy_orders, process_all_sell_orders
from orders_log import process_active_orders
from pricing import get_limit_price
from test import test_function
from utils import load_payment_type_to_name
import asyncio
from telegram_bot import run_bot, running_flags

api = get_api()

async def main_loop(api):
    while True:
        if not running_flags["main_loop"]:
            await asyncio.sleep(1)
            continue

        try:
            for side in ["BUY", "SELL"]:
                ads = fetch_market_ads(api, side)
                price = find_price_from_config(ads, config, side)

                if side == "SELL":
                    update_sell_ads(api, new_price=round(price - 0.01, 2))
                elif side == "BUY":
                    update_buy_ads(api, new_price=round(price + 0.01, 2))

                process_active_orders(api, side)

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