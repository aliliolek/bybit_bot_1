
import json
import logging
import os
import re
from typing import Optional
import uuid
from translitua import translit

def normalize_numeric_string(text: str) -> str:
    """
    Remove all non-digit characters from start and end (not inside),
    then remove all spaces inside.
    """
    if not text:
        return ""

    # Видаляє нецифрові символи тільки на початку і в кінці
    trimmed = re.sub(r"^[^\d]+|[^\d]+$", "", text)

    # Видаляє пробіли всередині
    no_spaces = trimmed.replace(" ", "")

    return no_spaces

def extract_iban(text: str) -> Optional[str]:
    digits = normalize_numeric_string(text)
    return digits if re.fullmatch(r"\d{26}", digits) else None

def extract_polish_phone(text: str) -> Optional[str]:
    digits = normalize_numeric_string(text)
    if re.fullmatch(r"\d{9}", digits):
        return digits
    if re.fullmatch(r"48\d{9}", digits):
        return digits[2:]
    return None

def extract_payment_info(order: dict, direction: str) -> dict:
    fields = ["bankName", "branchName", "accountNo", "payMessage"]
    terms = order.get("paymentTermList", [])

    term = None

    if direction == "SELL":
        # only PKO Bank / Bank Transfer
        for t in terms:
            name = t.get("paymentConfigVo", {}).get("paymentName", "")
            if name in ["PKO Bank", "Bank Transfer"]:
                term = t
                break
    else:  # BUY
        if terms:
            term = terms[0]

    if not term:
        return {
            "bank": "Not Found",
            "phone": "Not Found",
            "full_name": "Not Found",
            "iban": "Not Found",
            "order_id": f"#{order['id']}" if "id" in order else "Not Found",
        }

    def find_iban():
        for f in fields:
            v = term.get(f, "")
            result = extract_iban(v)
            if result:
                return result
        return "Not Found"

    def find_phone():
        for f in fields:
            v = term.get(f, "")
            result = extract_polish_phone(v)
            if result:
                return result
        return "Not Found"

    return {
        "bank": term.get("paymentConfigVo", {}).get("paymentName", "Not Found"),
        "phone": find_phone(),
        "full_name": translit(term.get("realName", "").strip()) or "Not Found",
        "iban": find_iban(),
        "order_id": f"#{order['id']}" if "id" in order else "Not Found",
    }



def send_payment_info_to_chat(api, order_id, info: dict):
    if not order_id:
        logging.warning("[CHAT] No order_id in info")
        return

    for key, value in info.items():
        message = str(value) if value else f"{key}: Not Found"
        try:
            api.send_chat_message(
                message=message,
                contentType="str",
                orderId=order_id,
                msgUuid=uuid.uuid4().hex
            )
            logging.info(f"[CHAT] Sent {key} → {message}")
        except Exception as e:
            logging.exception(f"[CHAT] Failed to send {key}: {e}")


def append_order_details(order_result: dict, filename: str = "oRDERdetAILS.json"):
    # Якщо файл існує — зчитай поточний вміст
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []

    # Додай новий ордер
    data.append(order_result)

    # Запиши назад
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)