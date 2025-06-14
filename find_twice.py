from pprint import pprint
import yaml

# =======================================================================
# 1. ДОПОМІЖНІ ФУНКЦІЇ ТА РУШІЙ ПРАВИЛ
# =======================================================================

def _is_ad_acceptable(ad: dict, side_config: dict) -> bool:
    """
    Перевіряє, чи є оголошення прийнятним, використовуючи повністю data-driven
    підхід з розділенням логіки активації та валідації.
    """
    def to_float(value):
        """Безпечно конвертує значення у float."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # --- ЄДИНИЙ ЦЕНТР УСІХ ПРАВИЛ ВАЛІДАЦІЇ ---
    ALL_RULES = [
        {
            'name': 'Payment Methods',
            'is_active': lambda ad, cfg: cfg.get('check_payment_methods', False),
            'is_valid': lambda ad, cfg: (
                len(
                    set(cfg.get('allowed_payment_types', [])).intersection(set(ad.get('payments', [])))
                ) >= min(
                    cfg.get('min_payment_matches', 1),
                    len(cfg.get('allowed_payment_types', []))
                )
            ),
        },
        {
            'name': 'Minimum Balance',
            'is_active': lambda ad, cfg: cfg.get('check_min_balance', False),
            'is_valid': lambda ad, cfg: to_float(ad.get('lastQuantity')) >= cfg.get('min_amount_threshold', 0),
        },
        {
            'name': 'Minimum Limit',
            'is_active': lambda ad, cfg: cfg.get('check_min_limit', False),
            'is_valid': lambda ad, cfg: to_float(ad.get('minAmount')) <= cfg.get('min_limit_threshold', float('inf')),
        },
        {
            'name': 'Limit Range',
            'is_active': lambda ad, cfg: cfg.get('check_limit_range', False),
            'is_valid': lambda ad, cfg: (to_float(ad.get('maxAmount')) - to_float(ad.get('minAmount'))) >= cfg.get('min_limit_range', 0),
        },
        {
            'name': 'Advertiser Register Time',
            'is_active': lambda ad, cfg: cfg.get('check_register_days', False) and ad.get('tradingPreferenceSet', {}).get('hasRegisterTime') == 1,
            'is_valid': lambda ad, cfg: to_float(ad.get('tradingPreferenceSet', {}).get('registerTimeThreshold')) <= cfg.get('min_register_days', float('inf')),
        },
        {
            'name': 'Advertiser Order Count',
            'is_active': lambda ad, cfg: cfg.get('check_min_orders', False) and ad.get('tradingPreferenceSet', {}).get('hasOrderFinishNumberDay30') == 1,
            'is_valid': lambda ad, cfg: to_float(ad.get('tradingPreferenceSet', {}).get('orderFinishNumberDay30')) <= cfg.get('min_order_count', float('inf')),
        },
        # --- НОВЕ ПРАВИЛО ДЛЯ ПЕРЕВІРКИ КРАЇНИ ---
        {
            'name': 'Country Whitelist',
            # Правило активне, якщо воно ввімкнене в конфігурації
            'is_active': lambda ad, cfg: cfg.get('check_country_whitelist', False),
            # Логіка валідації:
            # Оголошення проходить, якщо:
            # 1. В нього вимкнений ліміт по країнах (hasNationalLimit != 1)
            # АБО
            # 2. Перетин нашого білого списку країн та списку країн з оголошення не є порожнім.
            'is_valid': lambda ad, cfg: (
                ad.get('tradingPreferenceSet', {}).get('hasNationalLimit') != 1 or
                not set(cfg.get('country_whitelist', [])).isdisjoint(set(ad.get('tradingPreferenceSet', {}).get('nationalLimit', [])))
            ),
        },
                {
            'name': 'Remark Blacklist (BUY only)',
            # Правило активне, якщо воно ввімкнене в конфігурації
            'is_active': lambda ad, cfg: cfg.get('check_remark_blacklist', False),
            # Логіка валідації:
            # Оголошення вважається невалідним (повертаємо False),
            # якщо хоча б одне слово з 'remark_blacklist' знайдено в полі 'remark'
            # `any(...)` поверне True, якщо знайдено хоча б один збіг.
            # `not any(...)` інвертує результат: True -> False (невалідне), False -> True (валідне).
            'is_valid': lambda ad, cfg: not any(
                word in ad.get('remark', '').lower()
                for word in cfg.get('remark_blacklist', [])
            ),
        },
    ]

    # --- УНІВЕРСАЛЬНИЙ РУШІЙ ВАЛІДАЦІЇ ---
    for rule in ALL_RULES:
        if rule['is_active'](ad, side_config):
            if not rule['is_valid'](ad, side_config):
                # print(f"Ad {ad.get('id')} failed rule: {rule['name']}") # Для дебагінгу
                return False

    return True

def _find_neighbor_price(ad_to_check: dict, all_ads: list, gap: float, side_code: int) -> bool:
    """Перевіряє, чи має дане оголошення відповідного сусіда у списку."""
    ad_price = float(ad_to_check['price'])
    ad_owner = ad_to_check['nickName']

    for neighbor_ad in all_ads:
        if neighbor_ad['nickName'] == ad_owner:
            continue
        neighbor_price = float(neighbor_ad['price'])
        if side_code == 1 and neighbor_price > ad_price and (neighbor_price - ad_price) <= gap:
            return True
        elif side_code == 0 and neighbor_price < ad_price and (ad_price - neighbor_price) <= gap:
            return True
    return False

def _find_price_in_list(list_to_search: list, all_ads: list, gap: float, side_code: int) -> float | None:
    """
    Ітерує по списку оголошень і повертає ціну першого,
    що має відповідного сусіда.
    """
    for ad in list_to_search:
        if _find_neighbor_price(ad, all_ads, gap, side_code):
            print(f"Знайдено оголошення з сусідом: {ad['nickName']} за ціною {ad['price']}.")
            return float(ad['price'])
    return None

def find_price_from_config(ads_list: list, config: dict, side: str) -> float:
    side = side.upper()
    side_config = config[side]
    side_code = config['p2p']['side_codes'][side]
    price_gap = config['pricing']['price_gap']
    fallback_price = side_config['fallback_price']

    filtered_ads = [ad for ad in ads_list if _is_ad_acceptable(ad, side_config)]
    print("Пройшло фільтрацію:")
    for ad in filtered_ads:
        print(f"{ad['nickName']} за {ad['price']}")

    if not filtered_ads:
        print("Фільтр не пройдено. Повертаємо fallback.")
        return fallback_price

    use_target = side_config.get("check_target_nicknames", False)
    use_neighbors = side_config.get("check_price_neighbors", True)

    if use_target:
        target_nicknames = side_config.get("target_nicknames", [])
        target_ads = [ad for ad in filtered_ads if ad['nickName'] in target_nicknames]
        other_ads = [ad for ad in filtered_ads if ad['nickName'] not in target_nicknames]

        if use_neighbors:
            price = _find_price_in_list(target_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
            price = _find_price_in_list(other_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
        else:
            if target_ads:
                return float(target_ads[0]['price'])
            if other_ads:
                return float(other_ads[0]['price'])
    else:
        if use_neighbors:
            price = _find_price_in_list(filtered_ads, filtered_ads, price_gap, side_code)
            if price is not None:
                return price
        else:
            return float(filtered_ads[0]['price'])

    print("Не знайдено ціни. Повертаємо fallback.")
    return fallback_price
