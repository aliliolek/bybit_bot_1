import json
from typing import Dict

def load_payment_type_to_name(path: str = "./data/payment_map.json") -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        entry["paymentType"]: entry["paymentName"]
        for entry in data.values()
        if entry.get("paymentType") and entry.get("paymentName")
    }