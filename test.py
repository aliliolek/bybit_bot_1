import json
from pprint import pprint
from api_client import get_api
from config import config
import json
from translitua import translit

from order_utils import extract_payment_info

api = get_api(config)

def test_function():
  # завантажуємо масив ордерів
  with open("oRDERdetAILS.json", "r", encoding="utf-8") as f:
      orders = json.load(f)

  for i, order in enumerate(orders):
      direction = "BUY" if order.get("side") == 0 else "SELL"
      result = extract_payment_info(order, direction)

      print(f"\n--- Order {i+1} ---")
      print(f"ID: {order.get('id')}")
      print(json.dumps(result, indent=2, ensure_ascii=False))




test_function()