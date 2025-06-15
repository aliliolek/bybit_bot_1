import json
from pprint import pprint
from api_client import get_api
from config import config
import json

api = get_api(config)

def test_function():
  # pprint(api.get_pending_orders(
  #     page=1,
  #     size=10
  # ))

  pprint(api.get_order_details(
      orderId="1933861307560738816"
  ))

test_function()