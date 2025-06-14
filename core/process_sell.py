import math
from utils.api_tools import safe_call


def update_target_sell_ads_to_max_balance(api, config, ad_id_1: str, ad_id_2: str):
    # 1. Get available transfer balance
    balance_data = safe_call(api.get_current_balance, accountType="FUND", coin="USDT")
    usdt_info = next(b for b in balance_data["result"]["balance"] if b["coin"] == "USDT")
    transfer_balance = str(math.trunc((round(float(usdt_info["transferBalance"])) * 100 ) / 100 ))
    print(f"💰 Transfer balance: {transfer_balance}")

    # 2. Get all ads
    ads_data = safe_call(api.get_ads_list, side=1, tokenId="USDT", currency_id="PLN")
    ads = ads_data["result"]["items"]

    # 3. Get both ads by ID
    ad1 = next(ad for ad in ads if ad["id"] == ad_id_1)
    ad2 = next(ad for ad in ads if ad["id"] == ad_id_2)

    # 4. Update ad 1
    safe_call(
        api.update_ad,
        id=ad1["id"],
        priceType=ad1["priceType"],
        premium=ad1["premium"],
        price=str(config["minSellPrice"]),
        minAmount=str(config["minSellLimit"]),
        maxAmount=str(config["maxSellLimit"]),
        remark=ad1["remark"],
        tradingPreferenceSet=ad1["tradingPreferenceSet"],
        paymentIds=[term["id"] for term in ad1.get("paymentTerms", [])],
        actionType="MODIFY" if ad1["status"] == 10 else "ACTIVE",
        quantity=transfer_balance,
        paymentPeriod=ad1["paymentPeriod"]
    )
    print(f"✅ Updated ad {ad1['id']}")

    # 5. Update ad 2
    safe_call(
        api.update_ad,
        id=ad2["id"],
        priceType=ad2["priceType"],
        premium=ad2["premium"],
        price=str(config["minSellPrice"]),
        minAmount=str(config["minSellLimit"]),
        maxAmount=str(config["maxSellLimit"]),
        remark=ad2["remark"],
        tradingPreferenceSet=ad2["tradingPreferenceSet"],
        paymentIds=[term["id"] for term in ad2.get("paymentTerms", [])],
        actionType="MODIFY" if ad2["status"] == 10 else "ACTIVE",
        quantity=transfer_balance,
        paymentPeriod=ad2["paymentPeriod"]
    )
    print(f"✅ Updated ad {ad2['id']}")