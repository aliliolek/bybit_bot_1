import asyncio
import logging
from pprint import pprint
from ads import fetch_market_ads, get_my_ads, has_flag, update_ad_dynamic
from api_client import get_api
from calc_price import find_price_from_config, to_float
from orders_log import process_active_orders
from telegram_bot import run_bot, running_flags, config_state as config
from calc_balance import get_BUY_balance, get_SELL_balance

# Глобальні константи
api = get_api(config)
TOKEN = config["p2p"]["token"]
TOTAL = float(config["p2p"]["total"])

def process_ads_with_flags(ads, side, market_ads, quantity, side_config, price_offset):
    """Обробляє оголошення з флагами #p та #q"""
    last_price = None
    
    for ad in ads:
        if not has_flag(ad, "#p") and not has_flag(ad, "#q"):
            continue
            
        price = None
        if has_flag(ad, "#p"):
            price = calculate_ad_price(ad, side, market_ads, side_config, price_offset)
            last_price = price
            
        quantity_to_update = quantity if has_flag(ad, "#q") else None
        update_ad_dynamic(api, ad, price=price, quantity=quantity_to_update)
    
    return last_price

def calculate_ad_price(ad, side, market_ads, side_config, price_offset):
    """Розраховує ціну для оголошення"""
    payments = [term["paymentType"] for term in ad.get("paymentTerms", [])]
    pprint(f"[{side}] Payments for ad {ad['id']}: {payments}")

    custom_config = side_config.copy()
    custom_config["allowed_payment_types"] = [str(p) for p in payments]

    price = find_price_from_config(
        ads_list=market_ads,
        side_config=custom_config, 
        side_code=config["p2p"]["side_codes"][side],
        price_gap=to_float(config["pricing"]["price_gap"]),
        fallback_price=custom_config["fallback_price"]
    )
    return round(price + price_offset, 2)

def process_side(side, is_buy=False):
    # Отримуємо дані
    market_ads = fetch_market_ads(api, side, config)
    my_ads = get_my_ads(api, config, side)
    
    # Розраховуємо кількість
    if is_buy:
        quantity = get_BUY_balance(api, TOKEN, TOTAL)
        price_offset = 0.01
    else:
        quantity = get_SELL_balance(api, TOKEN)  
        price_offset = -0.01
    
    # Обробляємо оголошення
    last_price = process_ads_with_flags(
        my_ads, side, market_ads, quantity, config[side], price_offset
    )
    
    # Обробляємо активні ордери
    process_active_orders(api, config, side)
    
    return last_price

async def main_loop():
    """Основний цикл програми"""
    while True:
        if not running_flags["main_loop"]:
            await asyncio.sleep(1)
            continue

        try:
            # BUY операції
            last_buy_price = process_side("BUY", is_buy=True)
            
            # Передаємо BUY-ціну для SELL reference
            config["SELL"]["reference_buy_price"] = last_buy_price or 0
            
            # SELL операції
            process_side("SELL", is_buy=False)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[!] Error in main loop: {e}")

        await asyncio.sleep(30)

async def main():
    """Запуск програми"""
    await asyncio.gather(main_loop(), run_bot())

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    asyncio.run(main())