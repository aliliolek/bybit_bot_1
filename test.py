import json
from pprint import pprint
from api_client import get_api
from config import config
import json

api = get_api()

def test_function():
  with open("data/payment_map.json", "r", encoding="utf-8") as f:
    my_payment_methods = json.load(f)

  my_payment_types = set(
    entry["paymentType"] for entry in my_payment_methods.values()
  )
    # #do nothing
  # my_sell_adds = api.get_ads_list(
  #   status="2",
  #   side=config["side"]["SELL"],
  #   page="1",
  #   size="2",
  #   tokenId=config["token"],
  #   currency_id=config["currency"]
  # )

  # with open("TEMP_FILE.json", "w", encoding="utf-8") as f:
  #   json.dump(my_sell_adds, f, ensure_ascii=False, indent=2)

  # side_code_to_label = {v: k for k, v in config["side"].items()}
  
  other_sell_adds = api.get_online_ads(
    tokenId=config["p2p"]["token"],
    currencyId=config["p2p"]["currency"],
    side=config["p2p"]["side_codes"]["SELL"],
    page="1",
    size="2"
  )

  pprint(other_sell_adds)

  # filtered_ads = [
  #   ad for ad in other_sell_adds["result"]["items"]
  #   if my_payment_types & set(ad.get("payments", []))
  # ]

  # formatted_to_show_adds = [{
  #     "side": side_code_to_label.get(str(ad.get("side")), "UNKNOWN"),
  #     "price": ad.get("price"),
  #     "quantity": ad.get("quantity"),
  #     "minAmount": ad.get("minAmount"),
  #     "maxAmount": ad.get("maxAmount"),
  #     # "remark": ad.get("remark"),
  #     "payments": ad.get("payments")
  #   }
  #   for ad in filtered_ads
  # ]

  # pprint(formatted_to_show_adds)

  # #ми зараз займаємося лише обробкою процесу  SELL оголошень
  # # 1.збираємо SELL adds конкурентів:
  # other_sell_adds = api.get_online_ads(
  #   tokenId=config["token"],
  #   currencyId=config["currency"],
  #   side=config["side"]["SELL"],
  #   page="1",
  #   size="50"
  # )
