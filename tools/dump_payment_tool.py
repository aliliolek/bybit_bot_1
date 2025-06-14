import json
from bybit_p2p import P2P
import os

def extract_payment_map(api: P2P):
    response = api.get_user_payment_types()
    raw_methods = response["result"]

    result = {}
    for method in raw_methods:
        unique_id = str(method["id"])  # унікальний ключ
        config = method.get("paymentConfigVo", {})

        result[unique_id] = {
            "paymentType": str(method.get("paymentType", "")),  # 🔙 повертаємо!
            "paymentName": config.get("paymentName", ""),
            "realName": method.get("realName", ""),
            "accountNo": method.get("accountNo", ""),
            "bankName": method.get("bankName", ""),
            "branchName": method.get("branchName", ""),
            "payMessage": method.get("payMessage", ""),
            "id": unique_id,
            "visible": method.get("visible", 0),
            "verified": method.get("realNameVerified", False)
        }

    
    os.makedirs("./data", exist_ok=True)
    with open("./data/payment_map.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(result)} payment methods to ./data/payment_map.json")
