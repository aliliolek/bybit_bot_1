import json
from pprint import pprint
from api_client import get_api
from config import config
import json
from translitua import translit

api = get_api(config)

def test_function():
        # response = api.get_pending_orders(
        #     page=1,
        #     size=10,
        #     tokenId=config["p2p"]["token"],
        #     side=config["p2p"]["side_codes"]["BUY"]
        # )
        # orders = response.get("result", {}).get("items", [])
        # pprint(orders)
        pprint(api.get_order_details(orderId="1935333440879173632"))




test_function()