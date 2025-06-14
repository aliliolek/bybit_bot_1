import logging
from pprint import pprint
from typing import Dict
import uuid
from supabase import create_client
from config import config

url = config["supabase"]["url"]
key = config["supabase"]["api_key"]
supabase = create_client(url, key)

logging.basicConfig(level=logging.INFO)

def get_or_create_order_log(supabase, order):
    order_id = order["id"]
    logging.info(f"Checking log existence for order {order_id}")
    existing = supabase.table("orders_log").select("*").eq("order_id", order_id).execute()
    if existing.data and isinstance(existing.data[0], dict):
        logging.info(f"Found existing log for order {order_id}")
        return existing.data[0]

    side = "BUY" if order["side"] == 0 else "SELL"

    payload = {
        "order_id": order_id,
        "side": side,
        "status": order["status"],
        "price": float(order["price"]),
        "amount": float(order["amount"]),
        "quantity": float(order["notifyTokenQuantity"]),
        "real_name": order.get("buyerRealName") if side == "BUY" else order.get("sellerRealName", ""),
        "nickname": order.get("targetNickName") if side == "BUY" else order.get("nickName", ""),
        "payment_data": order.get("confirmedPayTerm") or {},
        "msg_status_10_sent": False,
        "msg_status_20_sent": False,
        "marked_paid": False,
    }

    logging.info(f"Inserting new log for order {order_id}")
    inserted = supabase.table("orders_log").insert(payload).execute()
    return inserted.data[0]

def update_order_flag(supabase, order_id: str, field: str, value: bool):
    logging.info(f"Updating order {order_id}: setting {field} = {value}")
    supabase.table("orders_log").update({field: value}).eq("order_id", order_id).execute()

def process_active_orders(api, side: str):
    logging.info(f"Processing active orders for side: {side}")
    try:
        response = api.get_pending_orders(
            page=1,
            size=10,
            tokenId=config["p2p"]["token"],
            side=config["p2p"]["side_codes"][side]
        )
        orders = response.get("result", {}).get("items", [])
        logging.info(f"Fetched {len(orders)} pending orders for side {side}")
    except Exception as e:
        logging.error(f"Failed to fetch orders: {e}")
        return

    for order in orders:
        if not isinstance(order, dict):
            logging.error(f"Invalid order format: {order}")
            continue

        try:
            order_id = order["id"]
            status = order["status"]
            logging.info(f"Handling order {order_id} with status {status}")
            log = get_or_create_order_log(supabase, order)

            logging.info(f"Flags in log for order {order_id}: "
             f"msg_status_10_sent={log.get('msg_status_10_sent')}, "
             f"msg_status_20_sent={log.get('msg_status_20_sent')}, "
             f"marked_paid={log.get('marked_paid')}")

            if status == 10 and not log["msg_status_10_sent"]:
                logging.info(f"Sending status_10 message for order {order_id}")
                message = config["messages"].get("status_10", {}).get(side, {}).get("EN", "")
                if message:
                    resp = api.send_chat_message(
                        message=message,
                        contentType="str",
                        orderId=order_id,
                        msgUuid=uuid.uuid4().hex
                    )
                    logging.info(f"Chat message sent, response: {resp}")
                    update_order_flag(supabase, order_id, "msg_status_10_sent", True)

            if side == "BUY" and status == 10 and not log["marked_paid"]:
              logging.info(f"Marking order {order_id} as paid")
              try:
                  raw_response = api.get_order_details(orderId=order_id)
                  details = raw_response.get("result", {})
            
                  payment_terms = details.get("paymentTermList", [])
                  logging.info(f"Payment terms for order {order_id}: {payment_terms}")

                  if not payment_terms:
                      logging.error(f"[!] No payment terms found for order {order_id}, skipping mark_as_paid")
                      return

                  term = payment_terms[0]

                  response = api.mark_as_paid(
                      orderId=str(order_id),
                      paymentType=str(term["paymentType"]),
                      paymentId=str(term["id"])
                  )
                  logging.info(f"mark_as_paid response: {response}")

                  update_order_flag(supabase, order_id, "marked_paid", True)
                  logging.info(f"Updated 'marked_paid' flag for order {order_id} to True")

              except Exception as e:
                  logging.exception(f"[!] Failed to mark order {order_id} as paid: {e}")

            if status == 20 and not log["msg_status_20_sent"]:
                logging.info(f"Sending status_20 message for order {order_id}")
                message = config["messages"].get("status_20", {}).get(side, {}).get("EN", "")
                if message:
                    resp = api.send_chat_message(
                        message=message,
                        contentType="str",
                        orderId=order_id,
                        msgUuid=uuid.uuid4().hex
                    )
                    logging.info(f"Chat message sent, response: {resp}")
                    update_order_flag(supabase, order_id, "msg_status_20_sent", True)

        except Exception as e:
            logging.error(f"[!] Failed to process order {order.get('id', '?')}: {e}")
