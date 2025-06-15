import logging
from logging import config
import uuid



def get_order_details(api, order_id: str) -> dict:
    response = api.get_order_details(orderId=order_id)
    return response.get("result", {})

def mark_order_as_paid(api, order_id: str, payment_type: str, payment_id: str):
    api.mark_as_paid(
        orderId=order_id,
        paymentType=str(payment_type),
        paymentId=str(payment_id)
    )

def send_message_to_order(api, order_id: str, message: str):
    api.send_chat_message(
        message=message,
        contentType="str",
        orderId=order_id,
        msgUuid=uuid.uuid4().hex
    )

def release_order(api, order_id: str):
    api.release_assets(orderId=order_id)

def process_all_buy_orders(api):
    buy_orders = get_pending_orders(api, side=0)
    for order in buy_orders:
        try:
            if order.get("status") != 10:
                logging.info(f"Skipping BUY order {order['id']} — already marked as paid or not in expected status")
                continue

            details = get_order_details(api, order["id"])
            term = details.get("paymentTermList", [])[0]

            mark_order_as_paid(api, order["id"], term["paymentType"], term["id"])
            send_message_to_order(api, order["id"], config["messages"]["BUY_order_opened"]["EN"])

        except Exception as e:
            logging.error(f"[!] Failed to process BUY order {order['id']}: {e}")


def process_all_sell_orders(api):
    sell_orders = get_pending_orders(api, side=1)
    for order in sell_orders:
        try:
            order_id = order["id"]
            send_message_to_order(api, order_id, "👋👀")
        except Exception as e:
            print(f"[!] Failed to process SELL order {order['id']}: {e}")

def process_orders_loop(api, config):
    tracker = OrderTracker()

    while True:
        all_orders = api.get_pending_orders(page=1, size=30, tokenId="USDT", side=[0, 1])
        for order in all_orders.get("result", {}).get("items", []):
            order_id = order["id"]
            side = order["side"]
            status = order["status"]

            previous_status = tracker.get(order_id)
            if previous_status == status:
                continue  # вже оброблено

            if side == 0:
                handle_buy_order(api, config, order, tracker)
            elif side == 1:
                handle_sell_order(api, config, order, tracker)

            tracker.set(order_id, status)

        time.sleep(config["p2p"].get("update_interval", 60))
