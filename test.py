import json
from pathlib import Path
from pprint import pprint
from api_client import get_api
from config import config
import json
# from language_detection import enrich_names_with_country, get_country_code_from_name

api = get_api(config)

def test_function():
  pprint(api.get_order_details(orderId='1941985584651649024')["result"])


test_function()