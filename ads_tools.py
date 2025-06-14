import json
import os


def fetch_filtered_competitor_ads(api, payment_map: dict, pages: int = 5) -> list:
    payment_type_to_name = {
        val["paymentType"]: val["paymentName"]
        for val in payment_map.values()
        if "paymentType" in val and "paymentName" in val
    }

    all_items = []
    for page in range(1, pages + 1):
        data = api.get_online_ads(tokenId="USDT", currencyId="PLN", side='1', page=str(page))
        items = data.get("result", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)

    filtered = []
    for ad in all_items:
        payment_types = ad.get("payments", [])
        matching = [pt for pt in payment_types if pt in payment_type_to_name]
        if not matching:
            continue

        filtered.append({
            "id": ad.get("id"),
            "nickName": ad.get("nickName"),
            "price": ad.get("price"),
            "quantity": ad.get("quantity"),
            "minAmount": ad.get("minAmount"),
            "maxAmount": ad.get("maxAmount"),
            "paymentTypes": matching,
            "registerTimeThreshold": ad.get("tradingPreferenceSet", {}).get("registerTimeThreshold"),
            "orderFinishNumberDay30": ad.get("tradingPreferenceSet", {}).get("orderFinishNumberDay30"),
            "completeRateDay30": ad.get("tradingPreferenceSet", {}).get("completeRateDay30"),
            "remark": ad.get("remark", "").strip()
        })

    os.makedirs("./data", exist_ok=True)
    with open("./data/filtered_sell_adds.json", "w", encoding="utf-8") as f:
      json.dump(filtered, f, indent=2, ensure_ascii=False)

    return filtered
