
import logging
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

def extract_payment_info(api, order_id: str) -> dict:
    try:
        response = api.get_order_details(orderId=order_id)
        result = response.get("result", {})
    except Exception as e:
        logging.exception(f"[EXTRACT] Failed to get order details for {order_id}: {e}")
        return {}

    # Перевірка типу ордера (має бути BUY)
    if result.get("side") != 0:
        logging.info(f"[EXTRACT] Order {order_id} is not a BUY order, skipping")
        return {}

    term = result.get("confirmedPayTerm", {})
    if not term or not any(term.values()):
        term_list = result.get("paymentTermList", [])
        if term_list and isinstance(term_list[0], dict):
            term = term_list[0]
    payment_name = term.get("paymentConfigVo", {}).get("paymentName", None)

    # Список полів, які потрібно перевірити
    fields_to_check = [
        "accountNo", "bankName", "branchName", "businessName", "clabe",
        "concept", "debitCardNumber", "firstName", "lastName", "mobile", "payMessage"
    ]

    # Витяг текстів усіх полів
    raw_fields = [term.get(field, "") for field in fields_to_check]

    # Пошук номеру рахунку (iban)
    iban = None
    for field in raw_fields:
        iban = extract_iban(field)
        if iban:
            break

    # Пошук номеру телефону
    phone = None
    for field in raw_fields:
        phone = extract_polish_phone(field)
        if phone:
            break

    # Повне ім’я латинкою
    raw_name = term.get("realName", "")
    full_name = translit(raw_name)

    return {
        "bank": payment_name,
        "phone": phone,
        "full_name": full_name,
        "iban": iban,
        "order_id": order_id
    }

def send_payment_info_to_chat_buy(api, info: dict):
    order_id = info.get("order_id")
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