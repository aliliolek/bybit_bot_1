from typing import List, Dict
from config import config
import logging

logger = logging.getLogger(__name__)

def get_limit_price(ads: List[Dict], side: str) -> float:
    side_config = config[side]
    # logger.info(f"Processing {side.upper()} ads with config: {side_config}")

    if side_config["fixed_price"] is not None:
        # logger.info(f"Using fixed price: {side_config['fixed_price']}")
        return side_config["fixed_price"]

    valid_ads = filter_ads(ads, side_config)
    logger.info(f"Found {len(valid_ads)} ads passing filters")

    if side_config["check_target_nicknames"]:
        target_ad = find_target_ad(valid_ads, side_config["target_nicknames"], side)
        if target_ad:
            # logger.info(f"Found matching target nickname ad: {target_ad['nickName']} at price {target_ad['price']}")
            return float(target_ad["price"])
        else:
            logger.info("No target nickname ads matched all filters")

    if valid_ads:
        # logger.info(f"Using first valid ad: {valid_ads[0]['nickName']} at price {valid_ads[0]['price']}")
        return float(valid_ads[0]["price"])

    logger.warning(f"No valid ads found. Using fallback price: {side_config['fallback_price']}")
    return side_config["fallback_price"]

def filter_ads(ads: List[Dict], cfg: Dict) -> List[Dict]:
    filtered = []
    for ad in ads:
        if ad_passes_filters(ad, cfg):
            filtered.append(ad)
        else:
            logger.debug(f"Ad {ad['nickName']} did not pass filters")
    return filtered

def ad_passes_filters(ad: Dict, cfg: Dict) -> bool:
    if cfg["check_payment_methods"]:
        if not set(ad["payments"]).intersection(cfg["allowed_payment_types"]):
            # logger.debug(f"[FILTER] Payment methods mismatch for {ad['nickName']}")
            return False

    if cfg["check_min_balance"]:
        if float(ad["lastQuantity"]) < cfg["min_amount_threshold"]:
            # logger.debug(f"[FILTER] lastQuantity too low for {ad['nickName']}: {ad['lastQuantity']}")
            return False

    if cfg["check_min_limit"]:
        if float(ad["minAmount"]) > cfg["min_limit_threshold"]:
            # logger.debug(f"[FILTER] minAmount too high for {ad['nickName']}: {ad['minAmount']}")
            return False

    if cfg["check_register_days"]:
        reg_days = ad["tradingPreferenceSet"].get("registerTimeThreshold", 0)
        if reg_days > cfg["min_register_days"]:
            # logger.debug(f"[FILTER] registerTimeThreshold too high for {ad['nickName']}: {reg_days}")
            return False

    if cfg["check_min_orders"]:
        orders_count = ad["tradingPreferenceSet"].get("orderFinishNumberDay30", 0)
        if orders_count > cfg["min_order_count"]:
            # logger.debug(f"[FILTER] orderFinishNumberDay30 too high for {ad['nickName']}: {orders_count}")
            return False

    return True

def find_target_ad(ads: List[Dict], target_nicknames: List[str], side: str) -> Dict:
    target_ads = [ad for ad in ads if ad["nickName"] in target_nicknames]
    if not target_ads:
        return None

    logger.info(f"Found {len(target_ads)} target nickname ads")

    if side.upper() == "SELL":
        return target_ads[0]  # Already sorted lowest price first
    elif side.upper() == "BUY":
        return target_ads[0]  # Already sorted highest price first

    return None
