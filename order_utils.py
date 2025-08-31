
import json
import logging
import os
import re
from typing import Optional
import uuid
from translitua import translit
import yaml

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

def extract_payment_info(order: dict, direction: str, token_name: str = "USDT") -> list:
    """
    Витягує всі унікальні способи оплати з ордеру.
    Повертає список унікальних payment info об'єктів.
    """
    # ВСІ можливі поля для пошуку
    all_fields = [
        "bankName", "branchName", "accountNo", "payMessage", 
        "mobile", "concept", "clabe", "firstName", "lastName",
        "paymentExt1", "paymentExt2", "paymentExt3", 
        "paymentExt4", "paymentExt5", "paymentExt6"
    ]
    
    terms = order.get("paymentTermList", [])
    logging.info(f"[PAYMENT_INFO] Order {order.get('id')}: found {len(terms)} payment terms")
    
    if not terms:
        logging.warning(f"[PAYMENT_INFO] No payment terms for order {order.get('id')}")
        return []
    
    unique_payments = []
    seen_combinations = set()  # Для перевірки унікальності
    
    # ВИПРАВЛЕННЯ: Обробляємо ВСІ терміни без фільтрації по назві банку
    for i, term in enumerate(terms):
        payment_name = term.get("paymentConfigVo", {}).get("paymentName", "Unknown")
        logging.info(f"[PAYMENT_INFO] Processing term {i}: {payment_name} (type: {term.get('paymentType')})")
        
        def find_iban_in_term():
            for f in all_fields:  # ✅ Шукаємо в УСІХ полях
                v = term.get(f, "")
                result = extract_iban(v)
                if result:
                    logging.info(f"[PAYMENT_INFO] Found IBAN in field '{f}': {result}")
                    return result
            logging.warning(f"[PAYMENT_INFO] No IBAN found in term {i}")
            return "Not Found"

        def find_phone_in_term():
            for f in all_fields:  # ✅ Шукаємо в УСІХ полях
                v = term.get(f, "")
                result = extract_polish_phone(v)
                if result:
                    logging.info(f"[PAYMENT_INFO] Found phone in field '{f}': {result}")
                    return result
            logging.warning(f"[PAYMENT_INFO] No phone found in term {i}")
            return "Not Found"
        
        # Витягуємо дані
        iban = find_iban_in_term()
        phone = find_phone_in_term()
        real_name = translit(term.get("realName", "").strip()) or "Not Found"
        
        # ВИПРАВЛЕННЯ: Різні правила для назви банку
        if direction == "SELL":
            bank_name = "PKO Bank"  # ✅ Хардкод для SELL
        else:  # BUY
            bank_name = term.get("paymentConfigVo", {}).get("paymentName", "Not Found")  # ✅ Реальна назва для BUY
        
        # Створюємо комбінацію для перевірки унікальності (ПІСЛЯ нормалізації)
        combination_key = (iban, phone, real_name)  # Без bank_name, бо для SELL воно завжди PKO
        
        # Перевіряємо унікальність
        if combination_key in seen_combinations:
            logging.info(f"[PAYMENT_INFO] Term {i} is duplicate, skipping")
            continue
        
        # Пропускаємо якщо немає корисних даних
        if iban == "Not Found" and phone == "Not Found":
            logging.info(f"[PAYMENT_INFO] Term {i} has no useful data (no IBAN, no phone), skipping")
            continue
            
        seen_combinations.add(combination_key)
        
        # Додаємо унікальний спосіб оплати
        payment_info = {
            "bank": bank_name,
            "phone": phone,
            "full_name": real_name,
            "iban": iban,
            "order_id": f"zakup {token_name.lower()} na bybit #{order['id']}" if "id" in order else "Not Found",
        }
        
        unique_payments.append(payment_info)
        logging.info(f"[PAYMENT_INFO] Added unique payment method {len(unique_payments)}: {payment_info}")
    
    logging.info(f"[PAYMENT_INFO] Final result: {len(unique_payments)} unique payment methods for order {order.get('id')}")
    return unique_payments

def send_payment_info_to_chat(api, order_id, info: dict):
    if not order_id:
        logging.warning("[CHAT] No order_id in info")
        return

    # Відправляємо прості поля як раніше
    simple_fields = ["bank", "full_name", "order_id"]
    for key in simple_fields:
        value = info.get(key, "Not Found")
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

    # ОКРЕМО обробляємо телефони - кожен окремим повідомленням
    phones = info.get("phone", "Not Found")
    if phones != "Not Found":
        phone_list = [p.strip() for p in phones.split(",")]
        for i, phone in enumerate(phone_list):
            try:
                api.send_chat_message(
                    message=phone,
                    contentType="str",
                    orderId=order_id,
                    msgUuid=uuid.uuid4().hex
                )
                logging.info(f"[CHAT] Sent phone {i+1} → {phone}")
            except Exception as e:
                logging.exception(f"[CHAT] Failed to send phone {phone}: {e}")

    # ОКРЕМО обробляємо IBAN - кожен окремим повідомленням
    ibans = info.get("iban", "Not Found") 
    if ibans != "Not Found":
        iban_list = [iban.strip() for iban in ibans.split(",")]
        for i, iban in enumerate(iban_list):
            try:
                api.send_chat_message(
                    message=iban,
                    contentType="str",
                    orderId=order_id,
                    msgUuid=uuid.uuid4().hex
                )
                logging.info(f"[CHAT] Sent IBAN {i+1} → {iban}")
            except Exception as e:
                logging.exception(f"[CHAT] Failed to send IBAN {iban}: {e}")

def send_payment_block_to_chat(api, order_id: str, info: dict, country_code: str = "EN", token_name: str = "USDT"):
    """Send the full payment info as a single block message based on country_code."""
    with open("config/payment_labels.yaml", encoding="utf-8") as f:
      FIELD_LABELS = yaml.safe_load(f)

    if not order_id:
        logging.warning("[CHAT] No order_id in info")
        return

    labels = FIELD_LABELS.get(country_code.upper(), FIELD_LABELS["EN"])

    lines = [
        f"{labels['recipient']}:\n{info.get('full_name', 'Not Found')}",
        f"{labels['account']}:\n{info.get('iban', 'Not Found')}",
        f"{labels['or']}",
        f"{labels['phone']}:\n{info.get('phone', 'Not Found')}",
        f"{labels['title']}:\n zakup {token_name.lower()} na Bybit {info.get('order_id', 'Not Found')}"
    ]
    message = "\n\n".join(lines)


    try:
        api.send_chat_message(
            message=message,
            contentType="str",
            orderId=order_id,
            msgUuid=uuid.uuid4().hex
        )
        logging.info(f"[CHAT] Sent payment block for {country_code} to order {order_id}")
    except Exception as e:
        logging.exception(f"[CHAT] Failed to send payment block: {e}")

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
