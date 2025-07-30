

from typing import Dict
from venv import logger

def get_pending_orders(api, token: str) -> list:
    """
    Get pending orders for a specific side (0 = BUY, 1 = SELL)
    """
    response = api.get_pending_orders(
        page=1,
        size=10,
        tokenId=token,
    )

    response = response["result"]["items"]

    return response

def get_SELL_balance(api, token: str) -> float:
    try:
        response = api.get_current_balance(accountType="FUND")
        balances = response.get("result", {}).get("balance", [])
        for item in balances:
            if item.get("coin") == token:
                raw = float(item.get("transferBalance", 0))
                print(f"(SELL {token} balance) = {raw}")
                return int(raw)
        logger.warning(f"Token {token} not found in balances")
        return 0.0
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")
        return 0.0

def get_BUY_balance(api, token: str, total: float) -> float:
    try:
        transfer_balance = get_SELL_balance(api, token)
        orders = get_pending_orders(api, token)
        active_volume = sum(
            float(o.get("notifyTokenQuantity", 0)) for o in orders
        )

        available_balance = max(total - transfer_balance - active_volume, 0)
        print(f"(total) {total} {token}- (transfer balance) {transfer_balance} - (active volume ){active_volume} = (available balance){available_balance}")
        return int(available_balance) 
        
    except Exception as e:
        logger.error(f"Failed to calculate buy balance: {e}")
        return 0.0