import json
from bybit_p2p import P2P

def check_sell_adds(api: P2P, payment_map: dict, pages: int = 5, output_path: str = "./data/filtered_competitor_ads.json"):
    # Створюємо зворотну мапу: paymentType → paymentName
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

        payment_names = [payment_type_to_name[pt] for pt in matching]
        pref = ad.get("tradingPreferenceSet", {})

        filtered.append({
            "id": ad.get("id"),
            "nickName": ad.get("nickName"),
            "price": ad.get("price"),
            "quantity": ad.get("quantity"),
            "minAmount": ad.get("minAmount"),
            "maxAmount": ad.get("maxAmount"),
            "paymentTypes": matching,
            "banks": payment_names,
            "registerTimeThreshold": pref.get("registerTimeThreshold"),
            "orderFinishNumberDay30": pref.get("orderFinishNumberDay30"),
            "completeRateDay30": pref.get("completeRateDay30"),
            "remark": ad.get("remark", "").strip()
        })

    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(filtered, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(filtered)} filtered competitor ads to {output_path}")
