from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

def has_flag(ad: Dict, flag: str) -> bool:
    """
    Checks if the given flag (e.g. "#p", "#q") exists in the ad's remark.
    Case-insensitive, whitespace-separated.
    """
    return flag.lower() in str(ad.get("remark", "")).lower().split()

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
        return [ad for ad in all_ads if str(ad.get("userId", "")) != my_uid]

    except Exception as e:
        logger.error(f"Failed to fetch {side} ads: {e}")
        return []

def update_ad_dynamic(api, ad: Dict, price: float | None = None, quantity: float | None = None):
    ad_id = ad["id"]
    try:
        logger.info(f"✏️ Updating ad {ad_id} with price={price} quantity={quantity}")
        api.update_ad(
            id=ad_id,
            priceType=0,
            premium="0",
            price=price if price is not None else float(ad.get("price", 0)),
            quantity=quantity if quantity is not None else float(ad.get("quantity", 0)),
            minAmount=ad["minAmount"],
            maxAmount=ad["maxAmount"],
            remark=ad["remark"],
            tradingPreferenceSet=ad["tradingPreferenceSet"],
            paymentIds=[term["id"] for term in ad.get("paymentTerms", [])],
            actionType="MODIFY" if ad["status"] == 10 else "ACTIVE",
            paymentPeriod=ad["paymentPeriod"]
        )
    except Exception as e:
        logger.error(f"❌ Failed to update ad {ad_id}: {e}")