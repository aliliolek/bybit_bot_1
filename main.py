import asyncio
import logging
from pprint import pprint
from ads import fetch_market_ads, get_my_ads, has_flag, update_ad_dynamic
from api_client import get_api
from calc_price import find_price_from_config, to_float
from orders_log import process_active_orders
import asyncio
from telegram_bot import run_bot, running_flags
from telegram_bot import config_state as config
from calc_balance import get_BUY_balance, get_SELL_balance


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
            token = config["p2p"]["token"]
            total = float(config["p2p"]["total"])

            # --- BUY ---
            market_ads_buy = fetch_market_ads(api, "BUY", config)
            my_ads_buy = get_my_ads(api, config, "BUY")
            quantity_buy = get_BUY_balance(api, token, total)

            price = None

            for ad in my_ads_buy:
                if not has_flag(ad, "#p") and not has_flag(ad, "#q"):
                    continue

                if has_flag(ad, "#p"):
                    payments = [term["paymentType"] for term in ad.get("paymentTerms", [])]

                    pprint(f"[BUY] Payments for ad {ad['id']}: {payments}")

                    custom_config = config["BUY"].copy()
                    custom_config["allowed_payment_types"] = [str(p) for p in payments]

                    price = find_price_from_config(
                        ads_list=market_ads_buy,
                        side_config=custom_config,
                        side_code=config["p2p"]["side_codes"]["BUY"],
                        price_gap=to_float(config["pricing"]["price_gap"]),
                        fallback_price=custom_config["fallback_price"]
                    )
                    price = round(price + 0.01, 2)

                qty = quantity_buy if has_flag(ad, "#q") else None
                update_ad_dynamic(api, ad, price=price, quantity=qty)

            process_active_orders(api, config, "BUY")

            # --- SELL ---
            market_ads_sell = fetch_market_ads(api, "SELL", config)
            my_ads_sell = get_my_ads(api, config, "SELL")
            quantity_sell = get_SELL_balance(api, token)

            # Передаємо BUY-ціну для SELL reference
            config["SELL"]["reference_buy_price"] = price if price is not None else 0

            for ad in my_ads_sell:
                if not has_flag(ad, "#p") and not has_flag(ad, "#q"):
                    continue

                price = None
                if has_flag(ad, "#p"):
                    payments = [term["paymentType"] for term in ad.get("paymentTerms", [])]

                    pprint(f"[SELL] Payments for ad {ad['id']}: {payments}")

                    custom_config = config["SELL"].copy()
                    custom_config["allowed_payment_types"] = [str(p) for p in payments]

                    price = find_price_from_config(
                        ads_list=market_ads_sell,
                        side_config=custom_config,
                        side_code=config["p2p"]["side_codes"]["SELL"],
                        price_gap=to_float(config["pricing"]["price_gap"]),
                        fallback_price=custom_config["fallback_price"]
                    )
                    price = round(price - 0.01, 2)

                qty = quantity_sell if has_flag(ad, "#q") else None
                update_ad_dynamic(api, ad, price=price, quantity=qty)

            process_active_orders(api, config, "SELL")

        except Exception as e:
          import traceback
          traceback.print_exc()
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