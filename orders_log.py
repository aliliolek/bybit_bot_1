import logging
import os
from pprint import pprint
from typing import Dict
import uuid
from supabase import create_client
from config import config
from order_utils import append_order_details, extract_payment_info, send_payment_info_to_chat

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

def send_tutorial_photos_for_sell(api, order_id: str):
    photo_dir = "./data/buy_tutorial_photo"
    for i in range(1, 9):
        filename = f"step_{i}.jpg"
        filepath = os.path.join(photo_dir, filename)
        if not os.path.isfile(filepath):
            logging.warning(f"[SELL PHOTOS] File not found: {filepath}")
            continue

        try:
            upload_response = api.upload_chat_file(upload_file=filepath)
            file_url = upload_response["result"]["url"]

            send_response = api.send_chat_message(
                message=file_url,
                contentType="pic",
                orderId=order_id,
                msgUuid=uuid.uuid4().hex,
                fileName=filename
            )
            logging.info(f"[SELL PHOTOS] Sent {filename}, response: {send_response}")
        except Exception as e:
            logging.exception(f"[SELL PHOTOS] Failed to send {filename}: {e}")

def send_multilang_messages(api, order_id: str, message_dict: Dict[str, str]):
    """Send the same message in all provided languages to the order chat."""
    for lang, message in message_dict.items():
        if not message:
            continue
        try:
            resp = api.send_chat_message(
                message=message,
                contentType="str",
                orderId=order_id,
                msgUuid=uuid.uuid4().hex
            )
            logging.info(f"[{lang}] Sent message to order {order_id}, response: {resp}")
        except Exception as e:
            logging.exception(f"[{lang}] Failed to send message to order {order_id}: {e}")

def process_active_orders(api, config, side: str):
    url = config["supabase"]["url"]
    key = config["supabase"]["api_key"]
    supabase = create_client(url, key)

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

            # extracting and sending payment info to BUY order chat
            order_details = api.get_order_details(orderId=order_id)["result"]
            payment_info = extract_payment_info(order_details, side)

            logging.info(f"Handling order {order_id} with status {status}")
            log = get_or_create_order_log(supabase, order)

            logging.info(f"Flags in log for order {order_id}: "
             f"msg_status_10_sent={log.get('msg_status_10_sent')}, "
             f"msg_status_20_sent={log.get('msg_status_20_sent')}, "
             f"marked_paid={log.get('marked_paid')}")

            if status == 10 and not log["msg_status_10_sent"]:
              # send_tutorial_photos_for_sell(api, order_id)
              if not log["marked_paid"]:
                send_payment_info_to_chat(api, order_id, payment_info)

              logging.info(f"Sending status_10 message for order {order_id}")
              messages = config["messages"].get("status_10", {}).get(side, {})

              if messages:
                # send_multilang_messages(api, order_id, messages)
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
                messages = config["messages"].get("status_20", {}).get(side, {})
                if messages:
                    send_multilang_messages(api, order_id, messages)
                    update_order_flag(supabase, order_id, "msg_status_20_sent", True)

        except Exception as e:
            logging.error(f"[!] Failed to process order {order.get('id', '?')}: {e}")
