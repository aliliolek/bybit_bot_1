from pprint import pprint
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

ads_cache = {}

def get_pending_orders(api, config: Dict) -> list:
    """
    Get pending orders for a specific side (0 = BUY, 1 = SELL)
    """
    response = api.get_pending_orders(
        page=1,
        size=10,
        tokenId=config["p2p"]["token"],
    )

    response = response["result"]["items"]

    return response

def exclude_own_ads(ads: List[Dict], my_uid: str) -> List[Dict]:
    return [ad for ad in ads if str(ad.get("userId", "")) != str(my_uid)]

def fetch_market_ads(api, side: str, config: Dict, max_pages: int = 5) -> List[Dict]:
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

def get_my_ads(api, config, side: str) -> List[Dict]:
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

def is_auto_ad(ad: Dict, side: str) -> bool:
    tag = "#B" if side.upper() == "BUY" else "#S"
    expected_side = 0 if side.upper() == "BUY" else 1
    return ad.get("side") == expected_side and str(ad.get("remark", "")).startswith(tag)

def should_update_ad(current_ad: Dict, new_price: float, new_quantity: int) -> bool:
    current_price = float(current_ad.get("price", 0))
    current_quantity = float(current_ad.get("quantity", 0))

    return not (
        current_price == new_price and
        current_quantity == new_quantity
    )

def get_SELL_balance(api, token: str) -> float:
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

def get_BUY_balance(api, config: Dict) -> float:
    try:
        total = float(config["p2p"]["total"])
        token = config["p2p"]["token"]
        transfer_balance = get_SELL_balance(api, token)
        orders = get_pending_orders(api, config)
        active_volume = sum(
            float(o.get("notifyTokenQuantity", 0)) for o in orders
        )

        available_balance = max(total - transfer_balance - active_volume, 0)
        print(f"(total) {total} - (transfer balance) {transfer_balance} - (active volume ){active_volume} = (available balance){available_balance}")
        return int(available_balance) 
        
    except Exception as e:
        logger.error(f"Failed to calculate buy balance: {e}")
        return 0.0

def update_auto_ads(
    api,
    config: Dict,
    side: str,  # "BUY" або "SELL"
    new_price: float,
    available_quantity: float
):
    logger.info(f"Starting update process for {side} ads with price {new_price}")

    all_ads = get_my_ads(api, config, side=side)

    if available_quantity <= 0:
        logger.warning(f"No available {side.lower()} balance")
        return

    updated_any = False
    for ad in all_ads:
        if not is_auto_ad(ad, side):
            continue

        ad_id = ad["id"]
        try:
            current_price = float(ad["price"])
            current_quantity = float(ad["quantity"])
            if current_price == new_price and current_quantity == available_quantity:
                logger.info(f"Skipping unchanged {side} ad {ad_id}")
                continue

            logger.info(f"Updating {side} ad {ad_id} with price {new_price} and quantity {available_quantity}")
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
            logger.info(f"{side} ad {ad_id} updated successfully")
            updated_any = True
        except Exception as e:
            logger.error(f"Failed to update {side} ad {ad_id}: {e}")

    if not updated_any:
        logger.info(f"No {side} ads were updated")