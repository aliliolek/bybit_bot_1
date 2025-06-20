import json
from pprint import pprint
from ads import get_buy_balance
from api_client import get_api
from config import config
import json

api = get_api(config)

def test_function():
  get_buy_balance(api, config)




test_function()