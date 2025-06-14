from pprint import pprint
from config import config
import logging
from typing import List, Dict
from orders import get_pending_orders

logger = logging.getLogger(__name__)

ads_cache = {}

def exclude_own_ads(ads: List[Dict], my_uid: str) -> List[Dict]:
    return [ad for ad in ads if str(ad.get("userId", "")) != str(my_uid)]

def fetch_market_ads(api, side: str, max_pages: int = 5) -> List[Dict]:
    try:
        side_code = config["p2p"]["side_codes"][side.upper()]
        token = config["p2p"]["token"]
        currency = config["p2p"]["currency"]
        size = config["p2p"]["page_size"]

        all_ads = []
        for page in range(1, max_pages + 1):
            resp = api.get_online_ads(
                tokenId=str(token),
                currencyId=str(currency),
                side=str(side_code),
                page=str(page),
                size=str(size)
            )
            items = resp.get("result", {}).get("items", [])
            all_ads.extend(items)

            if len(items) < int(size):
                break

        my_uid = str(config["p2p"]["my_uid"])
        all_ads = exclude_own_ads(all_ads, my_uid)
        
        return all_ads
    except Exception as e:
        logger.error(f"Failed to fetch {side} ads: {e}")
        return []

def get_my_ads(api, side: str) -> List[Dict]:
    try:
        response = api.get_ads_list(
            tokenId=config["p2p"]["token"],
            currency_id=config["p2p"]["currency"],
            side=config["p2p"]["side_codes"][side.upper()]
        )
        return response.get("result", {}).get("items", [])
    except Exception as e:
        logger.error(f"Failed to fetch my {side} ads: {e}")
        return []

def get_available_balance(api, token: str) -> float:
    try:
        response = api.get_current_balance(accountType="FUND")
        balances = response.get("result", {}).get("balance", [])
        for item in balances:
            if item.get("coin") == token:
                raw = float(item.get("transferBalance", 0))
                return int(raw)
        logger.warning(f"Token {token} not found in balances")
        return 0.0
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        return 0.0

def is_auto_sell_ad(ad: Dict) -> bool:
    return ad.get("side") == 1 and str(ad.get("remark", "")).startswith("#S")

def is_auto_buy_ad(ad: Dict) -> bool:
    return ad.get("side") == 0 and str(ad.get("remark", "")).startswith("#B")

def should_update_ad(ad_id: str, new_price: float, new_quantity: int) -> bool:
    cached = ads_cache.get(ad_id)
    if cached:
        if cached["price"] == new_price and cached["quantity"] == new_quantity:
            return False
    ads_cache[ad_id] = {
        "price": new_price,
        "quantity": new_quantity,
    }
    return True

def update_sell_ads(api, new_price: float):
    logger.info(f"Starting update process for SELL ads with price {new_price}")

    all_ads = get_my_ads(api, side="SELL")
    auto_sell_ads = [ad for ad in all_ads if is_auto_sell_ad(ad)]

    if not auto_sell_ads:
        logger.info("No auto-managed SELL ads found with tag #S")
        return

    available_balance = get_available_balance(api, config["p2p"]["token"])

    if available_balance == 0:
        logger.warning("No available balance to update SELL ads")
        return

    for ad in auto_sell_ads:
        ad_id = ad["id"]
        try:
            if not should_update_ad(ad_id, new_price, available_balance):
                logger.info(f"Skipping unchanged SELL ad {ad_id}")
                continue

            logger.info(f"Updating SELL ad {ad_id} with price {new_price} and quantity {available_balance}")
            api.update_ad(
                id=ad_id,
                priceType=0,
                premium="0",
                price=new_price,
                minAmount=ad["minAmount"],
                maxAmount=ad["maxAmount"],
                remark=ad["remark"],
                tradingPreferenceSet=ad["tradingPreferenceSet"],
                paymentIds=[term["id"] for term in ad.get("paymentTerms", [])],
                actionType="MODIFY" if ad["status"] == 10 else "ACTIVE",
                quantity=available_balance,
                paymentPeriod=ad["paymentPeriod"]
            )
            logger.info(f"SELL ad {ad_id} updated successfully")
        except Exception as e:
            logger.error(f"Failed to update SELL ad {ad_id}: {e}")

def get_buy_balance(api) -> float:
    try:
        total = float(config["p2p"]["total"])
        token = config["p2p"]["token"]
        transfer_balance = get_available_balance(api, token)

        orders = get_pending_orders(api, 0)

        active_volume = sum(
            float(o.get("quantity", 0)) for o in orders
            if o.get("status") not in [3, 5]
        )

        available_balance = max(total - transfer_balance - active_volume, 0)
        print(f"AVAILABLE BUY balance:{available_balance}")
        return int(available_balance) 
        
    except Exception as e:
        logger.error(f"Failed to calculate buy balance: {e}")
        return 0.0

def update_buy_ads(api, new_price: float):
    logger.info(f"Starting update process for BUY ads with price {new_price}")

    all_ads = get_my_ads(api, side="BUY")
    auto_buy_ads = [ad for ad in all_ads if is_auto_buy_ad(ad)]

    if not auto_buy_ads:
        logger.info("No auto-managed BUY ads found with tag #B")
        return

    available_quantity = get_buy_balance(api)
    if available_quantity <= 0:
        logger.warning("No available buy balance")
        return

    for ad in auto_buy_ads:
        ad_id = ad["id"]
        try:
          current_price = float(ad["price"])
          current_quantity = float(ad["quantity"])
          if current_price == new_price and current_quantity == available_quantity:
              logger.info(f"Skipping unchanged BUY ad {ad_id} (price and quantity already match)")
              continue

          logger.info(f"Updating BUY ad {ad_id} with price {new_price} and quantity {available_quantity}")
          api.update_ad(
              id=ad_id,
              priceType=0,
              premium="0",
              price=new_price,
              minAmount=ad["minAmount"],
              maxAmount=ad["maxAmount"],
              remark=ad["remark"],
              tradingPreferenceSet=ad["tradingPreferenceSet"],
              paymentIds=[term["id"] for term in ad.get("paymentTerms", [])],
              actionType="MODIFY" if ad["status"] == 10 else "ACTIVE",
              quantity=available_quantity,
              paymentPeriod=ad["paymentPeriod"]
          )
          logger.info(f"BUY ad {ad_id} updated successfully")
        except Exception as e:
            logger.error(f"Failed to update BUY ad {ad_id}: {e}")
