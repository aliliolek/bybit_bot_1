import json
from pathlib import Path
from pprint import pprint
from api_client import get_api
from config import config
import json
# from language_detection import enrich_names_with_country, get_country_code_from_name

api = get_api(config)

def test_function():
  sell_ads = api.get_online_ads(
      tokenId="USDT",
      currencyId="PLN",
      side="1",
      page="1",
      size="100",
  )
    
  ads_list = sell_ads.get("result", {}).get("items", [])

  for ad in ads_list:
      if float(ad.get("quantity", 0)) > 500:
        if float(ad.get("minAmount", 0)) < 300:
          pprint(f"{ad['nickName']} - {ad['price']} {ad['payments']}")


test_function()