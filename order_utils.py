
import json
import logging
import os
import re
from typing import Optional, Dict
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

def get_my_payment_method_with_hash(api) -> Optional[Dict]:
    """
    Отримує мій спосіб оплати з branchName що починається з '###'
    """
    try:
        response = api.get_user_payment_types()
        my_payment_methods = response.get("result", [])
        
        for method in my_payment_methods:
            branch_name = method.get("branchName", "")
            if branch_name.startswith("###"):
                logging.info(f"[MY_PAYMENT] Found payment method with ###: ID {method.get('id')}")
                return method
                
        logging.warning("[MY_PAYMENT] No payment method found with branchName starting with ###")
        return None
        
    except Exception as e:
        logging.error(f"[MY_PAYMENT] Failed to get user payment types: {e}")
        return None

def extract_payment_info(api, order: dict, direction: str, token_name: str = "USDT", currency: str = "") -> dict:
    """
    Витягує дані про оплату:
    - SELL + PLN: використовує мої власні дані (з branchName що починається з ###)
    - BUY або не PLN: використовує дані з ордера як раніше
    """
    order_id = order.get('id', 'Unknown')
    logging.info(f"[PAYMENT_INFO] Processing {direction} order {order_id}, currency: {currency}")
    
    # Для SELL в PLN використовуємо мої власні дані
    if direction == "SELL" and currency == "PLN":
        logging.info(f"[PAYMENT_INFO] SELL PLN detected, using my payment method")
        my_payment = get_my_payment_method_with_hash(api)
        
        if my_payment:
            # Витягуємо дані з мого способу оплати
            my_iban = extract_iban(my_payment.get("accountNo", ""))
            my_phone = extract_polish_phone(my_payment.get("bankName", ""))
            my_real_name = translit(my_payment.get("realName", "").strip())
            
            payment_info = {
                "bank": "PKO Bank",  # Хардкод для SELL
                "phone": my_phone or "Not Found",
                "full_name": my_real_name or "Not Found",
                "iban": my_iban or "Not Found",
                "order_id": f"zakup {token_name.lower()} na bybit #{order_id}",
            }
            
            logging.info(f"[PAYMENT_INFO] Using my payment data: IBAN={my_iban}, Phone={my_phone}")
            return payment_info
        else:
            logging.error(f"[PAYMENT_INFO] My payment method with ### not found, falling back to defaults")
            return {
                "bank": "PKO Bank",
                "phone": "Not Found",
                "full_name": "Not Found", 
                "iban": "Not Found",
                "order_id": f"zakup {token_name.lower()} na bybit #{order_id}",
            }
    
    # Для BUY або не PLN - використовуємо дані з ордера як раніше
    logging.info(f"[PAYMENT_INFO] Using order payment data for {direction} {currency}")
    
    all_fields = [
        "bankName", "branchName", "accountNo", "payMessage", 
        "mobile", "concept", "clabe", "firstName", "lastName",
        "paymentExt1", "paymentExt2", "paymentExt3", 
        "paymentExt4", "paymentExt5", "paymentExt6"
    ]
    
    terms = order.get("paymentTermList", [])
    logging.info(f"[PAYMENT_INFO] Order {order_id}: found {len(terms)} payment terms")
    
    if not terms:
        logging.warning(f"[PAYMENT_INFO] No payment terms for order {order_id}")
        return {
            "bank": "PKO Bank" if direction == "SELL" else "Not Found",
            "phone": "Not Found",
            "full_name": "Not Found",
            "iban": "Not Found",
            "order_id": f"zakup {token_name.lower()} na bybit #{order_id}",
        }
    
    # Збираємо всі унікальні дані з ордера
    unique_ibans = set()
    unique_phones = set()
    first_real_name = None
    first_bank_name = None
    
    for i, term in enumerate(terms):
        payment_name = term.get("paymentConfigVo", {}).get("paymentName", "Unknown")
        logging.info(f"[PAYMENT_INFO] Processing term {i}: {payment_name}")
        
        # Шукаємо IBAN у всіх полях
        for f in all_fields:
            v = term.get(f, "")
            iban = extract_iban(v)
            if iban:
                unique_ibans.add(iban)
                logging.info(f"[PAYMENT_INFO] Found IBAN in term {i}, field '{f}': {iban}")
        
        # Шукаємо телефон у всіх полях  
        for f in all_fields:
            v = term.get(f, "")
            phone = extract_polish_phone(v)
            if phone:
                unique_phones.add(phone)
                logging.info(f"[PAYMENT_INFO] Found phone in term {i}, field '{f}': {phone}")
        
        # Беремо перше знайдене ім'я
        if not first_real_name:
            real_name = translit(term.get("realName", "").strip())
            if real_name:
                first_real_name = real_name
                logging.info(f"[PAYMENT_INFO] Using real name: {real_name}")
        
        # Беремо назву банку для BUY
        if direction == "BUY" and not first_bank_name:
            bank_name = term.get("paymentConfigVo", {}).get("paymentName", "")
            if bank_name:
                first_bank_name = bank_name
                logging.info(f"[PAYMENT_INFO] Using bank name: {bank_name}")
    
    # Формуємо фінальні дані
    final_iban = ", ".join(sorted(unique_ibans)) if unique_ibans else "Not Found"
    final_phone = ", ".join(sorted(unique_phones)) if unique_phones else "Not Found"
    final_name = first_real_name or "Not Found"
    
    if direction == "SELL":
        final_bank = "PKO Bank"  # Хардкод для SELL
    else:  # BUY  
        final_bank = first_bank_name or "Not Found"  # Реальна назва для BUY
    
    payment_info = {
        "bank": final_bank,
        "phone": final_phone,
        "full_name": final_name,
        "iban": final_iban,
        "order_id": f"zakup {token_name.lower()} na bybit #{order_id}",
    }
    
    logging.info(f"[PAYMENT_INFO] Final aggregated payment info with {len(unique_ibans)} IBANs, {len(unique_phones)} phones")
    
    return payment_info

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
